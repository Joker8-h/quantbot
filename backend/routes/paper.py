"""Rutas del MODO PAPER TRADING (motor automatico en testnet).

El usuario enciende/apaga el motor, ve su estado, posicion abierta y el
resumen del dia. Todo es dinero FICTICIO (Spot Testnet de Binance).
"""
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import User, ExchangeConnection, SystemStatus, Trade

router = APIRouter(prefix="/api/paper", tags=["paper"])


def _conn_testnet(db, user_id):
    return (
        db.query(ExchangeConnection)
        .filter(ExchangeConnection.user_id == user_id,
                ExchangeConnection.is_active == True,
                ExchangeConnection.testnet == True)
        .first()
    )


def _get_estado(db, user_id):
    st = db.query(SystemStatus).filter(SystemStatus.user_id == user_id).first()
    if not st:
        st = SystemStatus(user_id=user_id, is_running=False)
        db.add(st)
        db.commit()
    return st


@router.get("/status")
def estado(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from services.paper_engine import SYMBOL, MONTO_USD, MAX_TRADES_DIA, MAX_PERDIDA_PCT_DIA
    from services.daily_report import _resumen_usuario

    conn = _conn_testnet(db, user.id)
    st = _get_estado(db, user.id)
    abierta = (
        db.query(Trade)
        .filter(Trade.user_id == user.id, Trade.status == "open")
        .order_by(Trade.entry_time.desc())
        .first()
    )
    resumen = _resumen_usuario(db, user.id)

    total_cerradas = (
        db.query(Trade)
        .filter(Trade.user_id == user.id, Trade.status == "closed")
        .count()
    )
    total_pnl = st.total_pnl_usd or 0.0

    return {
        "conectado_testnet": bool(conn),
        "is_running": bool(st.is_running),
        "symbol": SYMBOL,
        "monto_usd": MONTO_USD,
        "max_trades_dia": MAX_TRADES_DIA,
        "max_perdida_pct_dia": MAX_PERDIDA_PCT_DIA,
        "last_trade_time": st.last_trade_time.isoformat() if st.last_trade_time else None,
        "last_signal": st.last_signal,
        "total_pnl_usd": round(total_pnl, 2),
        "total_operaciones": total_cerradas,
        "hoy": resumen,
        "posicion_abierta": None if not abierta else {
            "symbol": abierta.symbol,
            "entry_price": abierta.entry_price,
            "quantity": abierta.quantity,
            "entry_time": abierta.entry_time.isoformat() if abierta.entry_time else None,
        },
    }


@router.post("/start")
def iniciar(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _conn_testnet(db, user.id):
        raise HTTPException(
            status_code=400,
            detail="Conecta primero una cuenta TESTNET de Binance en la pestana Cuenta.",
        )
    st = _get_estado(db, user.id)
    st.is_running = True
    st.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "is_running": True, "mensaje": "Motor de paper trading activado."}


@router.post("/stop")
def detener(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    st = _get_estado(db, user.id)
    st.is_running = False
    st.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "is_running": False, "mensaje": "Motor de paper trading pausado."}


@router.post("/tick")
def tick_manual(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ejecuta un ciclo del motor AHORA solo para este usuario (para pruebas)."""
    from services.paper_engine import procesar_usuario, SYMBOL
    conn = _conn_testnet(db, user.id)
    if not conn:
        raise HTTPException(status_code=400, detail="Conecta una cuenta TESTNET primero.")
    st = _get_estado(db, user.id)
    if not st.is_running:
        raise HTTPException(status_code=400, detail="El motor esta pausado. Activalo primero.")
    resultado = procesar_usuario(db, user, conn, SYMBOL)
    return {"ok": True, "resultado": resultado}


@router.post("/report")
async def reporte_ahora(user: User = Depends(get_current_user)):
    """Fuerza el envio del resumen diario a Telegram (para pruebas)."""
    from services.daily_report import enviar_reporte_diario
    return await enviar_reporte_diario()
