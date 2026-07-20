"""Rutas para conectar la cuenta de Binance del usuario.

El usuario pega su API key/secret (permiso SOLO spot trade + lectura, SIN
retiro por seguridad). Se cifran antes de guardarse. Nunca se devuelve el
secret en las respuestas.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import User, ExchangeConnection
from services.crypto import cifrar, descifrar
from services.binance import BinanceService

router = APIRouter(prefix="/api", tags=["exchange"])


class ConexionInput(BaseModel):
    api_key: str
    api_secret: str
    exchange: str = "binance"
    paper: bool = True  # Por defecto, solo pruebas simuladas


@router.post("/exchange/connect")
def conectar_exchange(
    data: ConexionInput,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Valida y guarda (cifrado) la conexion de Binance del usuario."""
    if not data.api_key or not data.api_secret:
        raise HTTPException(status_code=400, detail="API key y secret son requeridos")

    svc = BinanceService(api_key=data.api_key, api_secret=data.api_secret)
    validacion = svc.validar_conexion()
    if not validacion.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=f"Credenciales invalidas o sin acceso: {validacion.get('error')}",
        )
    if validacion.get("tiene_retiro"):
        raise HTTPException(
            status_code=400,
            detail="La API tiene permiso de RETIRO. Por seguridad, genera una API solo lectura + spot trade sin retiro.",
        )

    # Guardar cifrado (reemplaza si ya existe)
    existente = (
        db.query(ExchangeConnection)
        .filter(ExchangeConnection.user_id == user.id, ExchangeConnection.exchange == data.exchange)
        .first()
    )
    if existente:
        existente.api_key_encrypted = cifrar(data.api_key)
        existente.api_secret_encrypted = cifrar(data.api_secret)
        existente.is_active = True
    else:
        existente = ExchangeConnection(
            user_id=user.id,
            exchange=data.exchange,
            api_key_encrypted=cifrar(data.api_key),
            api_secret_encrypted=cifrar(data.api_secret),
        )
        db.add(existente)
    db.commit()

    return {
        "ok": True,
        "exchange": data.exchange,
        "tiene_spot_trading": validacion.get("tiene_spot_trading"),
        "tiene_retiro": validacion.get("tiene_retiro"),
        "saldo_usdt": validacion.get("saldo_usdt", 0.0),
        "paper": data.paper,
        "mensaje": "Cuenta conectada (cifrada). Operando en modo PAPER por defecto.",
    }


@router.get("/exchange/status")
def estado_exchange(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conn = (
        db.query(ExchangeConnection)
        .filter(ExchangeConnection.user_id == user.id, ExchangeConnection.is_active == True)
        .first()
    )
    if not conn:
        return {"conectado": False}
    # No devolvemos el secret; solo confirmamos que existe la key.
    return {
        "conectado": True,
        "exchange": conn.exchange,
        "tiene_api_key": bool(conn.api_key_encrypted),
        "ultima_sync": conn.last_sync.isoformat() if conn.last_sync else None,
    }


@router.delete("/exchange/disconnect")
def desconectar_exchange(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conn = (
        db.query(ExchangeConnection)
        .filter(ExchangeConnection.user_id == user.id, ExchangeConnection.is_active == True)
        .first()
    )
    if conn:
        db.delete(conn)
        db.commit()
    return {"ok": True, "mensaje": "Conexion eliminada"}


@router.get("/exchange/balance")
def balance_exchange(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Balance real de la cuenta conectada, valorado en USDT."""
    conn = (
        db.query(ExchangeConnection)
        .filter(ExchangeConnection.user_id == user.id, ExchangeConnection.is_active == True)
        .first()
    )
    if not conn:
        return {"conectado": False, "total_usdt": 0.0, "disponible_usdt": 0.0, "detalle": []}

    svc = BinanceService(
        api_key=descifrar(conn.api_key_encrypted),
        api_secret=descifrar(conn.api_secret_encrypted),
    )
    try:
        real = svc.balance_total_usdt()
        return {"conectado": True, **real}
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo leer el balance de Binance (posible geo-bloqueo): {e}",
        )


@router.post("/exchange/test-buy")
def prueba_compra(
    symbol: str = "BTC/USDT",
    monto_usd: float = 10.0,
    paper: bool = True,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ejecuta una compra de prueba. Por defecto PAPER (simulado).

    Para pruebas reales usa monto_usd pequeño (ej. $10) y paper=false solo
    si entiendes el riesgo. El sistema NUNCA retira fondos.
    """
    conn = (
        db.query(ExchangeConnection)
        .filter(ExchangeConnection.user_id == user.id, ExchangeConnection.is_active == True)
        .first()
    )
    if not conn:
        raise HTTPException(status_code=400, detail="Conecta tu cuenta de Binance primero")

    svc = BinanceService(
        api_key=descifrar(conn.api_key_encrypted),
        api_secret=descifrar(conn.api_secret_encrypted),
    )
    resultado = svc.ejecutar_compra(symbol, monto_usd, paper=paper)
    return resultado
