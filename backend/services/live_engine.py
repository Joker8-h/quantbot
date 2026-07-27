"""Motor de trading 100% real: confluencia tecnica + filtro Groq + gestion de riesgo.

No existe modo paper. No hay `random`. Toda operacion es una orden de
mercado real contra Binance Spot, y el PnL se calcula sobre el fill que
Binance devuelve, nunca sobre una estimacion.

Cada tick (lo dispara el scheduler cada N minutos):
  1. Descarga velas OHLCV REALES de mainnet.
  2. Si hay una posicion abierta -> la gestiona (stop loss, take profit,
     trailing stop, time stop). Si nada se disparo, no hace nada.
  3. Si no hay posicion -> evalua confluencia de 6 indicadores en cada
     simbolo. Si algun simbolo alcanza el score minimo:
       a. Verifica MIN_NOTIONAL contra el USDT libre real.
       b. Pide segunda opinion a Groq (si esta configurado).
       c. Si todo aprueba, ejecuta la compra real.
  4. Si nada aprueba, el motor se queda quieto. Quedarse quieto es la
     posicion por defecto, no una falla.

Circuit breakers (se evaluan ANTES de cada entrada):
  - Una sola posicion abierta a la vez.
  - Limite de perdida diaria (corta el motor ese dia).
  - Maximo de operaciones por dia.
  - Cooldown tras N perdidas consecutivas.

Interruptor: LIVE_TRADING_ENABLED=true habilita el motor. En false, el tick
corre igual (para ver senales en el log) pero nunca envia ordenes.
"""
import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logger = logging.getLogger(__name__)


def _f(nombre, defecto):
    try:
        return float(os.getenv(nombre, str(defecto)))
    except (TypeError, ValueError):
        return defecto


def _i(nombre, defecto):
    try:
        return int(os.getenv(nombre, str(defecto)))
    except (TypeError, ValueError):
        return defecto


def _bool(nombre, defecto=False):
    return os.getenv(nombre, str(defecto)).strip().lower() in ("1", "true", "yes", "si", "on")


SYMBOLS = [s.strip() for s in os.getenv(
    "TRADE_SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT"
).split(",") if s.strip()]

TIMEFRAME = os.getenv("TRADE_TIMEFRAME", "15m")
VELAS = _i("TRADE_VELAS", 300)

RIESGO_POR_TRADE = _f("TRADE_RIESGO_PCT", 0.01)
ATR_SL_MULT = _f("TRADE_ATR_SL_MULT", 2.5)
RR_RATIO = _f("TRADE_RR_RATIO", 2.0)
TRAIL_ATR_MULT = _f("TRADE_TRAIL_ATR_MULT", 1.5)
TRAIL_ACTIVAR_ATR = _f("TRADE_TRAIL_ACTIVAR_ATR", 1.0)

MAX_POSICIONES = _i("TRADE_MAX_POSICIONES", 1)
MAX_TRADES_DIA = _i("TRADE_MAX_TRADES_DIA", 4)
PERDIDA_DIA_PCT = _f("TRADE_PERDIDA_DIA_PCT", 0.05)
MAX_PERDIDAS_SEGUIDAS = _i("TRADE_MAX_PERDIDAS_SEGUIDAS", 3)
COOLDOWN_HORAS = _f("TRADE_COOLDOWN_HORAS", 6)
MAX_HORAS_POSICION = _f("TRADE_MAX_HORAS_POSICION", 48)

MIN_NOTIONAL = _f("TRADE_MIN_NOTIONAL", 10.0)   # minimo real de Binance Spot
MAX_NOTIONAL_PCT = _f("TRADE_MAX_NOTIONAL_PCT", 0.9)  # capital chico: casi todo cabe en 1 trade
RESERVA_USDT = _f("TRADE_RESERVA_USDT", 0.0)

MIN_SCORE = _i("TRADE_MIN_SCORE", 5)
ATR_PCT_MIN = _f("TRADE_ATR_PCT_MIN", 0.0015)
ATR_PCT_MAX = _f("TRADE_ATR_PCT_MAX", 0.05)

COSTO_ROUND_TRIP = _f("TRADE_COSTO_ROUND_TRIP", 0.002)
USAR_GROQ = _bool("TRADE_USAR_GROQ", True)

ESTRATEGIA = "confluencia_v1"


def _live() -> bool:
    return _bool("LIVE_TRADING_ENABLED", False)


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------- #
# Senal: confluencia de indicadores sobre velas reales de mainnet
# --------------------------------------------------------------------- #
def _cargar_velas(symbol: str) -> pd.DataFrame:
    from services.binance import BinanceService

    raw = BinanceService.velas_publicas(symbol, TIMEFRAME, VELAS)
    if not raw or len(raw) < 210:
        return pd.DataFrame()

    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.iloc[:-1].reset_index(drop=True)  # descarta la vela en formacion


def _evaluar_senal(symbol: str) -> dict:
    df = _cargar_velas(symbol)
    if df.empty:
        return {"entrar": False, "razon": "sin datos de mercado suficientes", "score": 0}

    from indicators import Indicators

    df = Indicators().add_all(df)
    u = df.iloc[-1]
    prev = df.iloc[-2]

    precio = float(u["close"])
    atr = float(u["atr"]) if pd.notna(u["atr"]) else 0.0
    if atr <= 0 or precio <= 0:
        return {"entrar": False, "razon": "ATR invalido", "score": 0}

    atr_pct = atr / precio
    razones = []
    score = 0

    if u["ema_fast"] > u["ema_slow"]:
        score += 1
        razones.append("EMA20>EMA50")
    if u["supertrend_dir"] == 1:
        score += 1
        razones.append("SuperTrend alcista")
    if pd.notna(u["adx"]) and u["adx"] > 20 and u["plus_di"] > u["minus_di"]:
        score += 1
        razones.append(f"ADX {u['adx']:.0f} con +DI dominante")
    if pd.notna(u["rsi"]) and 35 <= u["rsi"] <= 60 and u["rsi"] > prev["rsi"]:
        score += 1
        razones.append(f"RSI {u['rsi']:.0f} recuperando")
    if pd.notna(u["vol_avg"]) and u["vol_avg"] > 0 and u["volume"] > u["vol_avg"]:
        score += 1
        razones.append("volumen sobre la media")
    if pd.notna(u["vwap"]) and precio > u["vwap"]:
        score += 1
        razones.append("precio sobre VWAP")

    if atr_pct < ATR_PCT_MIN:
        return {"entrar": False, "razon": f"mercado sin movimiento (ATR {atr_pct:.3%})",
                "score": score, "precio": precio, "atr": atr, "atr_pct": atr_pct}
    if atr_pct > ATR_PCT_MAX:
        return {"entrar": False, "razon": f"volatilidad extrema (ATR {atr_pct:.3%})",
                "score": score, "precio": precio, "atr": atr, "atr_pct": atr_pct}

    objetivo_pct = (ATR_SL_MULT * atr * RR_RATIO) / precio
    if objetivo_pct < COSTO_ROUND_TRIP * 3:
        return {"entrar": False, "razon": f"objetivo {objetivo_pct:.2%} no cubre comisiones",
                "score": score, "precio": precio, "atr": atr, "atr_pct": atr_pct}

    return {
        "entrar": score >= MIN_SCORE,
        "score": score,
        "precio": precio,
        "atr": atr,
        "atr_pct": atr_pct,
        "razones": razones,
        "razon": " + ".join(razones) if razones else "sin confluencia",
    }


# --------------------------------------------------------------------- #
# Riesgo: estado leido siempre de operaciones REALES en la base de datos
# --------------------------------------------------------------------- #
def _estado_riesgo(db, user_id, capital):
    from models import Trade

    ahora = datetime.now(timezone.utc)
    inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)

    cerrados = (
        db.query(Trade)
        .filter(Trade.user_id == user_id, Trade.status == "closed", Trade.strategy == ESTRATEGIA)
        .all()
    )
    hoy = [t for t in cerrados if _aware(t.exit_time) and _aware(t.exit_time) >= inicio_dia]
    pnl_hoy = sum(t.pnl_usd or 0.0 for t in hoy)

    recientes = sorted(
        [t for t in cerrados if _aware(t.exit_time)],
        key=lambda t: _aware(t.exit_time), reverse=True,
    )
    seguidas = 0
    ultima_perdida = None
    for t in recientes:
        if (t.pnl_usd or 0.0) < 0:
            seguidas += 1
            ultima_perdida = ultima_perdida or _aware(t.exit_time)
        else:
            break

    if len(hoy) >= MAX_TRADES_DIA:
        return False, f"limite de {MAX_TRADES_DIA} operaciones diarias alcanzado", pnl_hoy
    if capital > 0 and pnl_hoy <= -(PERDIDA_DIA_PCT * capital):
        return False, f"limite de perdida diaria alcanzado (${pnl_hoy:.2f})", pnl_hoy
    if seguidas >= MAX_PERDIDAS_SEGUIDAS and ultima_perdida:
        falta = (ultima_perdida + timedelta(hours=COOLDOWN_HORAS)) - ahora
        if falta.total_seconds() > 0:
            return False, f"{seguidas} perdidas seguidas, en pausa {falta.total_seconds()/3600:.1f}h", pnl_hoy

    return True, "ok", pnl_hoy


def _registrar_senal(db, user_id, symbol, senal, ejecutado, motivo_no):
    from models import SignalLog

    try:
        db.add(SignalLog(
            user_id=user_id,
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            action="buy" if senal.get("entrar") else "hold",
            precio=senal.get("precio"),
            confianza=round(senal.get("score", 0) / 6.0, 3),
            atr=senal.get("atr"),
            votos_buy=senal.get("score", 0),
            votos_sell=0,
            estrategia_buy=json.dumps(senal.get("razones", []), ensure_ascii=False),
            razon_final=senal.get("razon", "")[:500],
            ejecutado=ejecutado,
            razon_no_ejecutado=(motivo_no or "")[:500],
        ))
    except Exception as e:
        logger.warning(f"[signal_log] no se pudo registrar: {e}")


# --------------------------------------------------------------------- #
# Gestion de una posicion abierta
# --------------------------------------------------------------------- #
def _gestionar_abierta(db, svc, trade) -> dict:
    from services.binance import BinanceService

    precio = BinanceService.precio_publico(trade.symbol)
    if not precio:
        return {"symbol": trade.symbol, "accion": "sin precio"}

    atr = 0.0
    try:
        df = _cargar_velas(trade.symbol)
        if not df.empty:
            from indicators import Indicators
            atr_serie = Indicators().calculate_atr(df, 14)
            if pd.notna(atr_serie.iloc[-1]):
                atr = float(atr_serie.iloc[-1])
    except Exception as e:
        logger.warning(f"[trailing] ATR no disponible para {trade.symbol}: {e}")

    maximo = max(trade.max_price or trade.entry_price, precio)
    trade.max_price = maximo

    if atr > 0 and TRAIL_ATR_MULT > 0 and maximo >= trade.entry_price + (TRAIL_ACTIVAR_ATR * atr):
        nuevo_stop = maximo - (TRAIL_ATR_MULT * atr)
        if nuevo_stop > (trade.stop_loss or 0):
            trade.stop_loss = nuevo_stop
            logger.info(f"[TRAILING] {trade.symbol} stop subido a {nuevo_stop:.6f}")

    motivo = None
    if trade.stop_loss and precio <= trade.stop_loss:
        motivo = "stop_loss"
    elif trade.take_profit and precio >= trade.take_profit:
        motivo = "take_profit"
    else:
        abierta_desde = _aware(trade.entry_time)
        if abierta_desde and (datetime.now(timezone.utc) - abierta_desde).total_seconds() / 3600 >= MAX_HORAS_POSICION:
            motivo = "time_stop"

    if not motivo:
        db.commit()
        return {
            "symbol": trade.symbol, "accion": "mantener", "precio": precio,
            "stop_loss": trade.stop_loss, "take_profit": trade.take_profit,
            "pnl_no_realizado": round((precio - trade.entry_price) * trade.quantity, 4),
        }

    venta = svc.vender_verificado(trade.symbol, trade.quantity)
    if not venta.get("ok"):
        logger.error(f"[CIERRE_FALLIDO] {trade.symbol} ({motivo}): {venta.get('error')}")
        db.commit()
        return {"symbol": trade.symbol, "accion": "cierre_fallido", "motivo": motivo, "error": venta.get("error")}

    precio_salida = venta["precio_fill"]
    cantidad = venta["cantidad"] or trade.quantity
    comision_total = (trade.fee or 0.0) + venta["comision_usd"]
    pnl = (precio_salida - trade.entry_price) * cantidad - comision_total

    trade.exit_price = precio_salida
    trade.exit_time = datetime.now(timezone.utc)
    trade.exit_reason = motivo
    trade.status = "closed"
    trade.fee = round(comision_total, 6)
    trade.pnl = round(pnl, 6)
    trade.pnl_usd = round(pnl, 6)
    trade.exit_order_id = str(venta.get("orden_id") or "")
    db.commit()

    logger.info(f"[CIERRE] {trade.symbol} {motivo} @ {precio_salida} | PnL real ${pnl:.4f}")
    return {"symbol": trade.symbol, "accion": "cerrada", "motivo": motivo,
            "precio_salida": precio_salida, "pnl_usd": round(pnl, 4)}


# --------------------------------------------------------------------- #
# Apertura: MIN_NOTIONAL + filtro Groq + orden real
# --------------------------------------------------------------------- #
def _abrir(db, svc, user_id, symbol, senal, capital, usdt_libre) -> dict:
    from models import Trade

    precio = senal["precio"]
    atr = senal["atr"]

    stop = precio - (ATR_SL_MULT * atr)
    if stop <= 0 or stop >= precio:
        return {"symbol": symbol, "accion": "descartada", "motivo": "stop invalido"}

    distancia = precio - stop
    riesgo_usd = capital * RIESGO_POR_TRADE
    notional = riesgo_usd / (distancia / precio)

    tope_capital = capital * MAX_NOTIONAL_PCT
    disponible = max(0.0, usdt_libre - RESERVA_USDT)
    notional = min(notional, tope_capital, disponible * 0.98)

    # --- Verificacion MIN_NOTIONAL (limite real de Binance Spot) ---
    if notional < MIN_NOTIONAL:
        if disponible * 0.98 < MIN_NOTIONAL:
            return {"symbol": symbol, "accion": "descartada",
                    "motivo": f"USDT disponible ${disponible:.2f} < minimo Binance ${MIN_NOTIONAL}"}
        riesgo_al_minimo = MIN_NOTIONAL * (distancia / precio)
        if riesgo_al_minimo > riesgo_usd * 4:
            return {"symbol": symbol, "accion": "descartada",
                    "motivo": (f"el minimo de ${MIN_NOTIONAL} arriesgaria ${riesgo_al_minimo:.2f}, "
                               f"muy por encima del objetivo ${riesgo_usd:.2f}")}
        notional = MIN_NOTIONAL

    if notional < MIN_NOTIONAL:
        return {"symbol": symbol, "accion": "descartada",
                "motivo": f"notional final ${notional:.2f} bajo el minimo de Binance"}

    # --- Segunda opinion de Groq (si esta configurado) ---
    if USAR_GROQ:
        from services.groq_filter import confirmar_entrada
        veredicto = confirmar_entrada(symbol, precio, senal["score"], senal.get("razones", []),
                                       senal.get("atr_pct", 0.0))
        if not veredicto.get("aprobado", True):
            return {"symbol": symbol, "accion": "descartada",
                    "motivo": f"Groq veto: {veredicto.get('razon')}"}

    compra = svc.comprar_verificado(symbol, round(notional, 2))
    if not compra.get("ok"):
        return {"symbol": symbol, "accion": "fallida", "error": compra.get("error")}

    precio_entrada = compra["precio_fill"]
    cantidad = compra["cantidad"]
    if cantidad <= 0:
        return {"symbol": symbol, "accion": "fallida", "error": "Binance no reporto cantidad llenada"}

    stop_real = precio_entrada - (ATR_SL_MULT * atr)
    objetivo_real = precio_entrada + ((precio_entrada - stop_real) * RR_RATIO)

    trade = Trade(
        user_id=user_id, symbol=symbol, side="LONG",
        entry_price=precio_entrada, quantity=cantidad,
        fee=compra["comision_usd"], entry_time=datetime.now(timezone.utc),
        status="open", strategy=ESTRATEGIA,
        stop_loss=stop_real, take_profit=objetivo_real, max_price=precio_entrada,
        entry_order_id=str(compra.get("orden_id") or ""),
    )
    db.add(trade)
    db.commit()

    logger.info(f"[APERTURA_REAL] {symbol} @ {precio_entrada} | ${compra['notional_usd']:.2f} | "
                f"SL {stop_real:.6f} TP {objetivo_real:.6f} | score {senal['score']}/6")
    return {"symbol": symbol, "accion": "abierta", "precio": precio_entrada,
            "notional": compra["notional_usd"], "stop_loss": stop_real,
            "take_profit": objetivo_real, "score": senal["score"], "razon": senal["razon"]}


# --------------------------------------------------------------------- #
# Credenciales: SOLO la cuenta real del usuario, nunca la de otro
# --------------------------------------------------------------------- #
def _servicio_de(db, user):
    from models import ExchangeConnection
    from services.binance import BinanceService

    conn = (
        db.query(ExchangeConnection)
        .filter(ExchangeConnection.user_id == user.id, ExchangeConnection.is_active == True,
                ExchangeConnection.testnet == False)
        .first()
    )
    if conn and conn.api_key_encrypted and conn.api_secret_encrypted:
        from services.crypto import descifrar
        key = descifrar(conn.api_key_encrypted)
        sec = descifrar(conn.api_secret_encrypted)
        if key and sec:
            return BinanceService(api_key=key, api_secret=sec, testnet=False), "db"

    key = os.getenv("BINANCE_API_KEY", "").strip()
    sec = os.getenv("BINANCE_API_SECRET", "").strip()
    dueno = os.getenv("BINANCE_OWNER_EMAIL", "").strip().lower()
    if key and sec and (not dueno or (user.email or "").lower() == dueno):
        return BinanceService(api_key=key, api_secret=sec, testnet=False), "env"

    return None, "sin credenciales reales"


# --------------------------------------------------------------------- #
# Tick principal
# --------------------------------------------------------------------- #
def ejecutar_tick():
    from database import SessionLocal
    from models import User, Trade

    db = SessionLocal()
    salida = {"live": _live(), "usuarios": []}

    try:
        usuarios = db.query(User).filter(User.is_active == True).all()
        if not usuarios:
            return {"ok": True, "razon": "sin usuarios activos"}

        for user in usuarios:
            detalle = {"user_id": user.id, "acciones": []}
            try:
                st_user = _get_status(db, user.id)
                if not st_user.is_running:
                    detalle["estado"] = "motor apagado por el usuario"
                    salida["usuarios"].append(detalle)
                    continue

                svc, origen = _servicio_de(db, user)
                if svc is None:
                    detalle["estado"] = "sin credenciales reales"
                    salida["usuarios"].append(detalle)
                    continue
                detalle["credenciales"] = origen

                try:
                    bal = svc.balance_total_usdt()
                    capital = float(bal.get("total_usdt") or 0.0)
                    usdt_libre = float(bal.get("disponible_usdt") or 0.0)
                except Exception as e:
                    detalle["estado"] = f"no se pudo leer el saldo real: {e}"
                    salida["usuarios"].append(detalle)
                    continue

                detalle["capital_usdt"] = round(capital, 2)
                detalle["usdt_libre"] = round(usdt_libre, 2)

                abiertas = (
                    db.query(Trade)
                    .filter(Trade.user_id == user.id, Trade.status == "open", Trade.strategy == ESTRATEGIA)
                    .all()
                )
                for t in abiertas:
                    try:
                        detalle["acciones"].append(_gestionar_abierta(db, svc, t))
                    except Exception as e:
                        db.rollback()
                        logger.error(f"[gestion] {t.symbol}: {e}")

                abiertas_ahora = (
                    db.query(Trade)
                    .filter(Trade.user_id == user.id, Trade.status == "open", Trade.strategy == ESTRATEGIA)
                    .count()
                )
                if abiertas_ahora >= MAX_POSICIONES:
                    detalle["estado"] = f"{abiertas_ahora} posicion(es) abierta(s)"
                    _actualizar_status(db, user.id)
                    salida["usuarios"].append(detalle)
                    continue

                puede, motivo, pnl_hoy = _estado_riesgo(db, user.id, capital)
                detalle["pnl_hoy"] = round(pnl_hoy, 4)
                if not puede:
                    detalle["estado"] = f"detenido: {motivo}"
                    _actualizar_status(db, user.id)
                    salida["usuarios"].append(detalle)
                    continue

                if usdt_libre - RESERVA_USDT < MIN_NOTIONAL:
                    detalle["estado"] = f"USDT libre ${usdt_libre:.2f} bajo el minimo de ${MIN_NOTIONAL}"
                    _actualizar_status(db, user.id)
                    salida["usuarios"].append(detalle)
                    continue

                if not _live():
                    detalle["estado"] = "LIVE_TRADING_ENABLED=false: solo observando senales"

                candidatas = []
                for symbol in SYMBOLS:
                    try:
                        senal = _evaluar_senal(symbol)
                    except Exception as e:
                        logger.warning(f"[senal] {symbol}: {e}")
                        continue
                    if senal.get("entrar"):
                        candidatas.append((senal["score"], symbol, senal))
                    else:
                        _registrar_senal(db, user.id, symbol, senal, False, senal.get("razon", ""))

                if not candidatas:
                    db.commit()
                    detalle.setdefault("estado", "sin senal de entrada (sin operar)")
                    _actualizar_status(db, user.id)
                    salida["usuarios"].append(detalle)
                    continue

                candidatas.sort(key=lambda c: c[0], reverse=True)
                _, symbol, senal = candidatas[0]

                if _live():
                    res = _abrir(db, svc, user.id, symbol, senal, capital, usdt_libre)
                else:
                    res = {"symbol": symbol, "accion": "simulacion_bloqueada",
                           "motivo": "LIVE_TRADING_ENABLED=false"}

                detalle["acciones"].append(res)
                _registrar_senal(db, user.id, symbol, senal, res.get("accion") == "abierta",
                                 res.get("motivo") or res.get("error") or "")
                db.commit()

                detalle.setdefault("estado", "ok")
                _actualizar_status(db, user.id)
                salida["usuarios"].append(detalle)

            except Exception as e:
                db.rollback()
                logger.error(f"[live_engine] usuario {user.id}: {e}")
                detalle["estado"] = f"error: {e}"
                salida["usuarios"].append(detalle)

        salida["ok"] = True
        return salida

    except Exception as e:
        logger.error(f"[live_engine] tick fallo: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def _get_status(db, user_id):
    from models import SystemStatus
    st = db.query(SystemStatus).filter(SystemStatus.user_id == user_id).first()
    if not st:
        st = SystemStatus(user_id=user_id, is_running=False)
        db.add(st)
        db.commit()
    return st


def _actualizar_status(db, user_id):
    from models import Trade, SystemStatus

    try:
        cerrados = (
            db.query(Trade)
            .filter(Trade.user_id == user_id, Trade.status == "closed", Trade.strategy == ESTRATEGIA)
            .all()
        )
        total = sum(t.pnl_usd or 0.0 for t in cerrados)
        inicio_dia = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        hoy = sum(t.pnl_usd or 0.0 for t in cerrados
                  if _aware(t.exit_time) and _aware(t.exit_time) >= inicio_dia)
        ultima = max((_aware(t.exit_time) for t in cerrados if _aware(t.exit_time)), default=None)

        st = db.query(SystemStatus).filter(SystemStatus.user_id == user_id).first()
        if not st:
            st = SystemStatus(user_id=user_id)
            db.add(st)
        st.total_pnl_usd = round(total, 6)
        st.today_pnl_usd = round(hoy, 6)
        if ultima:
            st.last_trade_time = ultima
        st.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"[status] no se pudo actualizar: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import pprint
    pprint.pprint(ejecutar_tick())
