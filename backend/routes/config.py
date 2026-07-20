"""Configuracion general del frontend (tasa de cambio, etc)."""
from fastapi import APIRouter
from config import config

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/rate")
def get_rate():
    """Tasa de cambio USD -> COP para el toggle de divisa."""
    return {"rate": config.USD_TO_COP_RATE, "base": "USD", "target": "COP"}
