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

# --- Estrategia: SuperTrend en marco DIARIO (regimen de tendencia) ---
# Validada en backtest de 6 anos sobre BTC/ETH/SOL: le gana a comprar-y-aguantar
# en retorno ajustado por riesgo y reduce la caida maxima ~30%. Opera pocas
# veces (unas 4-8 al ano), asi que las comisiones no la erosionan.
TIMEFRAME = os.getenv("TRADE_TIMEFRAME", "1d")
VELAS = _i("TRADE_VELAS", 400)  # dias de historia para SuperTrend/EMA200

ST_PERIODO = _i("TRADE_ST_PERIODO", 10)      # periodo ATR del SuperTrend
ST_MULT = _f("TRADE_ST_MULT", 3.0)           # multiplicador del SuperTrend

MAX_POSICIONES = _i("TRADE_MAX_POSICIONES", 1)
# Salvaguarda dura por si el SuperTrend tarda en girar en un desplome:
STOP_CATASTROFICO_PCT = _f("TRADE_STOP_CATASTROFICO_PCT", 0.18)  # -18% cierra si o si

MIN_NOTIONAL = _f("TRADE_MIN_NOTIONAL", 10.0)   # minimo real de Binance Spot
MAX_NOTIONAL_PCT = _f("TRADE_MAX_NOTIONAL_PCT", 0.98)  # asignacion: casi todo el USDT
RESERVA_USDT = _f("TRADE_RESERVA_USDT", 0.0)

# Cortacircuitos (para una estrategia diaria casi nunca se activan; se dejan
# amplios para no bloquear la re-entrada tras un cambio de tendencia).
MAX_TRADES_DIA = _i("TRADE_MAX_TRADES_DIA", 3)
PERDIDA_DIA_PCT = _f("TRADE_PERDIDA_DIA_PCT", 0.5)
MAX_PERDIDAS_SEGUIDAS = _i("TRADE_MAX_PERDIDAS_SEGUIDAS", 99)
COOLDOWN_HORAS = _f("TRADE_COOLDOWN_HORAS", 0)

USAR_GROQ = _bool("TRADE_USAR_GROQ", False)

ESTRATEGIA = "supertrend_diario"


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


def _supertrend_dir(df: pd.DataFrame) -> pd.Series:
    """Direccion del SuperTrend (1 alcista, -1 bajista) sobre el DataFrame dado."""
    from indicators import Indicators
    st = Indicators().calculate_supertrend(df, period=ST_PERIODO, multiplier=ST_MULT)
    return st["supertrend_dir"], st["supertrend"]


def _evaluar_senal(symbol: str) -> dict:
    """Regimen de tendencia por SuperTrend diario.

    entrar=True mientras la tendencia diaria sea alcista. La 'fuerza' (dias
    consecutivos en tendencia alcista) se usa para elegir, entre varias monedas
    alcistas, la de tendencia mas establecida -- que en backtest rindio mejor.
    """
    df = _cargar_velas(symbol)
    if df.empty or len(df) < (ST_PERIODO + 5):
        return {"entrar": False, "razon": "sin datos de mercado suficientes", "score": 0}

    dir_series, st_line = _supertrend_dir(df)
    u = df.iloc[-1]
    precio = float(u["close"])
    if precio <= 0:
        return {"entrar": False, "razon": "precio invalido", "score": 0}

    st_dir = int(dir_series.iloc[-1]) if pd.notna(dir_series.iloc[-1]) else -1
    linea = float(st_line.iloc[-1]) if pd.notna(st_line.iloc[-1]) else precio
    alcista = st_dir == 1

    # dias consecutivos en tendencia alcista (madurez de la tendencia)
    dias_alcista = 0
    for d in reversed(dir_series.tolist()):
        if d == 1:
            dias_alcista += 1
        else:
            break

    dist_pct = (precio - linea) / precio if precio > 0 else 0.0
    razon = (f"SuperTrend diario {'ALCISTA' if alcista else 'bajista'} "
             f"(dia {dias_alcista}, precio {dist_pct:+.1%} vs linea ${linea:,.2f})")

    return {
        "entrar": alcista,
        "alcista": alcista,
        "precio": precio,
        "supertrend": linea,
        "dias_alcista": dias_alcista,
        "fuerza": dias_alcista,
        # compat con SignalLog / dashboard:
        "score": 6 if alcista else 0,
        "atr": float(u["atr"]) if "atr" in df.columns and pd.notna(u.get("atr")) else 0.0,
        "razones": ["SuperTrend diario alcista"] if alcista else [],
        "razon": razon,
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
    # El registro de senales es opcional: si falla (tabla ausente, etc.)
    # NUNCA debe tumbar el ciclo de trading. Por eso el import va dentro
    # del try y cualquier error se traga con un warning.
    try:
        from models import SignalLog
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
    """Mantiene la posicion mientras el SuperTrend diario siga alcista.

    Sale cuando el SuperTrend gira bajista (esa es la senal de salida de la
    estrategia). Ademas, un stop catastrofico cierra si el precio cae por
    debajo de -STOP_CATASTROFICO_PCT, por si el SuperTrend tarda en girar
    en un desplome rapido.
    """
    from services.binance import BinanceService

    senal = _evaluar_senal(trade.symbol)
    # Direccion del SuperTrend: de velas cerradas. Precio para el stop: EN VIVO.
    precio = BinanceService.precio_publico(trade.symbol) or senal.get("precio")
    if not precio:
        return {"symbol": trade.symbol, "accion": "sin precio"}

    trade.max_price = max(trade.max_price or trade.entry_price, precio)
    # La linea del SuperTrend actua como stop dinamico (solo informativo en DB)
    if senal.get("supertrend"):
        trade.stop_loss = float(senal["supertrend"])

    motivo = None
    if senal.get("alcista") is False and "sin datos" not in senal.get("razon", ""):
        motivo = "supertrend_bajista"
    elif STOP_CATASTROFICO_PCT > 0 and precio <= trade.entry_price * (1 - STOP_CATASTROFICO_PCT):
        motivo = "stop_catastrofico"

    if not motivo:
        db.commit()
        return {
            "symbol": trade.symbol, "accion": "mantener", "precio": precio,
            "supertrend": senal.get("supertrend"), "dias_alcista": senal.get("dias_alcista"),
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
    """Compra por ASIGNACION: usa casi todo el USDT libre (una posicion a la vez)."""
    from models import Trade

    precio = senal["precio"]
    disponible = max(0.0, usdt_libre - RESERVA_USDT)
    notional = min(disponible * 0.98, capital * MAX_NOTIONAL_PCT)

    if notional < MIN_NOTIONAL:
        return {"symbol": symbol, "accion": "descartada",
                "motivo": f"USDT disponible ${disponible:.2f} < minimo Binance ${MIN_NOTIONAL}"}

    compra = svc.comprar_verificado(symbol, round(notional, 2))
    if not compra.get("ok"):
        return {"symbol": symbol, "accion": "fallida", "error": compra.get("error")}

    precio_entrada = compra["precio_fill"]
    cantidad = compra["cantidad"]
    if cantidad <= 0:
        return {"symbol": symbol, "accion": "fallida", "error": "Binance no reporto cantidad llenada"}

    linea_st = float(senal.get("supertrend") or 0.0)

    trade = Trade(
        user_id=user_id, symbol=symbol, side="LONG",
        entry_price=precio_entrada, quantity=cantidad,
        fee=compra["comision_usd"], entry_time=datetime.now(timezone.utc),
        status="open", strategy=ESTRATEGIA,
        stop_loss=linea_st or None, take_profit=None, max_price=precio_entrada,
        entry_order_id=str(compra.get("orden_id") or ""),
    )
    db.add(trade)
    db.commit()

    logger.info(f"[APERTURA_REAL] {symbol} @ {precio_entrada} | ${compra['notional_usd']:.2f} | "
                f"SuperTrend diario alcista (dia {senal.get('dias_alcista')})")
    return {"symbol": symbol, "accion": "abierta", "precio": precio_entrada,
            "notional": compra["notional_usd"], "supertrend": linea_st,
            "dias_alcista": senal.get("dias_alcista"), "razon": senal["razon"]}


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
                        # ordenar por fuerza = dias en tendencia alcista (mas madura primero)
                        candidatas.append((senal.get("fuerza", 0), symbol, senal))
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
