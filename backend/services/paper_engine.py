"""Motor automatico de PAPER TRADING sobre el Spot Testnet de Binance.

🔴 Solo dinero FICTICIO (testnet.binance.vision). Nunca dinero real.

Flujo por cada tick (lo dispara el scheduler cada N minutos):
  1. Buscar usuarios con conexion TESTNET activa y sistema encendido.
  2. Traer precio del testnet + datos 1d para la senal.
  3. Senal simple SMA20/SMA50 (cruce). Solo COMPRA si el filtro de
     riesgo IA no marca riesgo alto.
  4. Ejecuta la orden en el testnet (flujo real de codigo, dinero ficticio).
  5. Registra la operacion en la tabla Trade (Postgres) con comision 0.1%.

Seguridad y robustez (honestidad radical de Vill):
  - Una sola posicion abierta por usuario/simbolo (no duplica ordenes).
  - Circuit breaker: si la perdida del dia supera el limite o se hacen
    demasiadas operaciones, el motor se detiene ese dia.
  - Se recupera solo tras un reinicio leyendo la posicion abierta de la DB.
  - Cada paso va en try/except: un fallo de un usuario no tumba el ciclo.

Nota honesta: las pruebas historicas NO hallaron ventaja en estrategias
activas (PF 0.12-0.67). Este motor es educativo: deja ver el flujo real
de trading sin arriesgar dinero.
"""
import os
import sys
import logging
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logger = logging.getLogger(__name__)

# Parametros del motor (testnet, dinero ficticio)
SYMBOL = os.getenv("PAPER_SYMBOL", "BTC/USDT")
MONTO_USD = float(os.getenv("PAPER_MONTO_USD", "100"))   # tamano de cada compra
FEE_PCT = 0.001                                          # comision spot 0.1%
CAPITAL_BASE = float(os.getenv("PAPER_CAPITAL_BASE", "1000"))  # base del breaker
MAX_TRADES_DIA = int(os.getenv("PAPER_MAX_TRADES_DIA", "10"))
MAX_PERDIDA_PCT_DIA = float(os.getenv("PAPER_MAX_PERDIDA_PCT_DIA", "5"))
SMA_CORTA = 20
SMA_LARGA = 50


def _sma_signal(symbol: str):
    """Devuelve ('buy'|'sell'|'hold', precio, razon) segun cruce SMA en 1d."""
    from services.investment import _cargar_1d, _precio_vivo
    df = _cargar_1d(symbol)
    if df.empty or len(df) < SMA_LARGA + 2:
        return "hold", None, "sin datos suficientes"

    close = df["close"]
    sma_c = close.rolling(SMA_CORTA).mean()
    sma_l = close.rolling(SMA_LARGA).mean()
    c_now, l_now = sma_c.iloc[-1], sma_l.iloc[-1]
    if c_now != c_now or l_now != l_now:  # NaN
        return "hold", None, "medias no disponibles"

    precio = _precio_vivo(symbol) or float(close.iloc[-1])
    if c_now > l_now:
        return "buy", float(precio), "Tendencia alcista (SMA20 > SMA50)"
    return "sell", float(precio), "Tendencia bajista (SMA20 < SMA50)"


def _breaker_activo(db, user_id: str) -> tuple:
    """Circuit breaker: (detenido: bool, razon: str)."""
    from models import Trade
    inicio_dia = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cerradas_hoy = (
        db.query(Trade)
        .filter(Trade.user_id == user_id, Trade.status == "closed",
                Trade.exit_time >= inicio_dia)
        .all()
    )
    if len(cerradas_hoy) >= MAX_TRADES_DIA:
        return True, f"Limite de {MAX_TRADES_DIA} operaciones/dia alcanzado"
    pnl_hoy = sum((t.pnl_usd or 0.0) for t in cerradas_hoy)
    limite = -(CAPITAL_BASE * MAX_PERDIDA_PCT_DIA / 100.0)
    if pnl_hoy <= limite:
        return True, f"Perdida diaria {pnl_hoy:.2f} <= limite {limite:.2f}"
    return False, ""


def _posicion_abierta(db, user_id: str, symbol: str):
    from models import Trade
    return (
        db.query(Trade)
        .filter(Trade.user_id == user_id, Trade.symbol == symbol,
                Trade.status == "open")
        .first()
    )


def _svc_para(conn):
    """Crea un BinanceService testnet con las claves descifradas del usuario."""
    from services.crypto import descifrar
    from services.binance import BinanceService
    return BinanceService(
        api_key=descifrar(conn.api_key_encrypted),
        api_secret=descifrar(conn.api_secret_encrypted),
        testnet=bool(getattr(conn, "testnet", True)),
    )


def _abrir_posicion(db, user, conn, symbol, precio, razon):
    from models import Trade, SystemStatus
    svc = _svc_para(conn)
    res = svc.ejecutar_compra(symbol, MONTO_USD, paper=True)
    if not res.get("ok"):
        logger.warning(f"[paper_engine] compra fallo user={user.id}: {res.get('error')}")
        return None
    precio_real = float(res.get("precio") or precio)
    cantidad = float(res.get("cantidad") or (MONTO_USD / precio_real))
    fee = MONTO_USD * FEE_PCT
    trade = Trade(
        user_id=user.id,
        symbol=symbol,
        side="LONG",
        entry_price=precio_real,
        quantity=cantidad,
        fee=fee,
        entry_time=datetime.now(timezone.utc),
        status="open",
    )
    db.add(trade)
    _tocar_estado(db, user.id, señal="BUY")
    db.commit()
    logger.info(f"[paper_engine] COMPRA user={user.id} {symbol} @ {precio_real} cant={cantidad}")
    return trade


def _cerrar_posicion(db, user, conn, trade, precio, razon="Cruce bajista"):
    from datetime import datetime, timezone
    svc = _svc_para(conn)
    res = svc.ejecutar_venta(trade.symbol, trade.quantity, paper=True)
    if not res.get("ok"):
        logger.warning(f"[paper_engine] venta fallo user={user.id}: {res.get('error')}")
        return None
    precio_salida = float(res.get("precio") or precio)
    bruto = (precio_salida - trade.entry_price) * trade.quantity
    fee_salida = precio_salida * trade.quantity * FEE_PCT
    pnl = bruto - (trade.fee or 0.0) - fee_salida
    trade.exit_price = precio_salida
    trade.exit_time = datetime.now(timezone.utc)
    trade.exit_reason = razon
    trade.fee = (trade.fee or 0.0) + fee_salida
    trade.pnl = round(bruto, 2)
    trade.pnl_usd = round(pnl, 2)
    trade.status = "closed"
    _tocar_estado(db, user.id, señal="SELL", pnl=pnl)
    db.commit()
    logger.info(f"[paper_engine] VENTA user={user.id} {trade.symbol} @ {precio_salida} pnl={pnl:.2f}")
    return trade


def _tocar_estado(db, user_id, señal=None, pnl=None):
    from models import SystemStatus
    st = db.query(SystemStatus).filter(SystemStatus.user_id == user_id).first()
    if not st:
        st = SystemStatus(user_id=user_id, is_running=True)
        db.add(st)
    st.last_trade_time = datetime.now(timezone.utc)
    if señal:
        st.last_signal = señal
    if pnl is not None:
        st.total_pnl_usd = (st.total_pnl_usd or 0.0) + pnl
    st.updated_at = datetime.now(timezone.utc)


def procesar_usuario(db, user, conn, symbol=SYMBOL):
    """Ejecuta un ciclo para un usuario. Devuelve dict con lo ocurrido."""
    detenido, razon_cb = _breaker_activo(db, user.id)
    abierta = _posicion_abierta(db, user.id, symbol)

    accion, precio, razon = _sma_signal(symbol)
    if precio is None:
        return {"user_id": user.id, "accion": "hold", "razon": razon}

    # Vender siempre que haya senal bajista y posicion abierta (protege capital).
    if accion == "sell" and abierta:
        _cerrar_posicion(db, user, conn, abierta, precio, razon)
        return {"user_id": user.id, "accion": "sell", "precio": precio, "razon": razon}

    # Comprar solo si no hay posicion, breaker apagado y riesgo no alto.
    if accion == "buy" and not abierta:
        if detenido:
            return {"user_id": user.id, "accion": "hold", "razon": f"breaker: {razon_cb}"}
        try:
            from services.investment import _cargar_1d, evaluar_riesgo
            import importlib
            api_key = importlib.import_module("backend.config").config.OPENAI_API_KEY
            nivel, r_riesgo, _ = evaluar_riesgo(_cargar_1d(symbol), api_key)
        except Exception as e:
            nivel, r_riesgo = "low", f"riesgo no evaluado: {e}"
        if nivel == "high":
            return {"user_id": user.id, "accion": "hold", "razon": f"riesgo alto: {r_riesgo}"}
        _abrir_posicion(db, user, conn, symbol, precio, razon)
        return {"user_id": user.id, "accion": "buy", "precio": precio, "razon": razon}

    return {"user_id": user.id, "accion": "hold", "razon": razon}


def ejecutar_tick(symbol=SYMBOL) -> dict:
    """Un ciclo completo: procesa todos los usuarios elegibles."""
    from database import SessionLocal
    from models import User, ExchangeConnection, SystemStatus
    db = SessionLocal()
    resultados = []
    try:
        conexiones = (
            db.query(ExchangeConnection)
            .filter(ExchangeConnection.is_active == True,
                    ExchangeConnection.testnet == True)
            .all()
        )
        for conn in conexiones:
            try:
                st = db.query(SystemStatus).filter(SystemStatus.user_id == conn.user_id).first()
                if not st or not st.is_running:
                    continue
                user = db.query(User).filter(User.id == conn.user_id).first()
                if not user or not user.is_active:
                    continue
                resultados.append(procesar_usuario(db, user, conn, symbol))
            except Exception as e:
                db.rollback()
                logger.error(f"[paper_engine] error usuario {conn.user_id}: {e}")
        return {"ok": True, "procesados": len(resultados), "resultados": resultados}
    except Exception as e:
        logger.error(f"[paper_engine] tick fallo: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(ejecutar_tick())
