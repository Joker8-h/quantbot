"""Control del motor de trading REAL (sin modo paper).

El usuario enciende/apaga el motor desde el dashboard. Mientras esta
apagado, el tick del scheduler no ejecuta ninguna orden para ese usuario.
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

router = APIRouter(prefix="/api/live", tags=["live"])


def _conn_real(db, user_id):
    return (
        db.query(ExchangeConnection)
        .filter(ExchangeConnection.user_id == user_id, ExchangeConnection.is_active == True,
                ExchangeConnection.testnet == False)
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
    from services.live_engine import ESTRATEGIA, TIMEFRAME, SYMBOLS, MAX_TRADES_DIA, _live

    conn = _conn_real(db, user.id)
    st = _get_estado(db, user.id)
    abierta = (
        db.query(Trade)
        .filter(Trade.user_id == user.id, Trade.status == "open", Trade.strategy == ESTRATEGIA)
        .order_by(Trade.entry_time.desc())
        .first()
    )
    cerradas = (
        db.query(Trade)
        .filter(Trade.user_id == user.id, Trade.status == "closed", Trade.strategy == ESTRATEGIA)
        .all()
    )
    ganadas = sum(1 for t in cerradas if (t.pnl_usd or 0) > 0)

    return {
        "conectado_real": bool(conn),
        "is_running": bool(st.is_running),
        "live_trading_enabled_env": _live(),
        "estrategia": ESTRATEGIA,
        "timeframe": TIMEFRAME,
        "symbols": SYMBOLS,
        "max_trades_dia": MAX_TRADES_DIA,
        "last_trade_time": st.last_trade_time.isoformat() if st.last_trade_time else None,
        "total_pnl_usd": round(st.total_pnl_usd or 0.0, 4),
        "today_pnl_usd": round(st.today_pnl_usd or 0.0, 4),
        "total_operaciones": len(cerradas),
        "operaciones_ganadas": ganadas,
        "win_rate": round(ganadas / len(cerradas) * 100, 1) if cerradas else None,
        "posicion_abierta": None if not abierta else {
            "symbol": abierta.symbol,
            "entry_price": abierta.entry_price,
            "quantity": abierta.quantity,
            "stop_loss": abierta.stop_loss,
            "take_profit": abierta.take_profit,
            "entry_time": abierta.entry_time.isoformat() if abierta.entry_time else None,
        },
    }


@router.post("/start")
def iniciar(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _conn_real(db, user.id):
        raise HTTPException(
            status_code=400,
            detail="Conecta primero tu cuenta REAL de Binance en la pestana Cuenta.",
        )
    st = _get_estado(db, user.id)
    st.is_running = True
    st.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "is_running": True, "mensaje": "Motor de trading real activado."}


@router.post("/stop")
def detener(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    st = _get_estado(db, user.id)
    st.is_running = False
    st.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "is_running": False, "mensaje": "Motor de trading real pausado."}


@router.post("/tick")
def tick_manual(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fuerza un ciclo del motor ahora mismo (para verificar que todo funciona)."""
    from services.live_engine import ejecutar_tick
    return {"ok": True, "resultado": ejecutar_tick()}


@router.get("/analisis-groq")
def obtener_analisis_groq():
    """Devuelve un analisis en lenguaje natural generado en vivo por Groq AI (Llama 3.3)."""
    from services.groq_filter import analizar_estado_mercado
    return analizar_estado_mercado()
