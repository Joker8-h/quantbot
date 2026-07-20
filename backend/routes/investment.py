"""Rutas del Modo Conservador: portafolio, DCA, riesgo, modo.

Todas devuelven datos simples para el dashboard. Los tecnicismos
(RSI, EMA, AUC, ATR) NO se exponen al usuario final; quedan en el
panel tecnico/admin.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import APIRouter, Query
from typing import Optional
import logging

logger = logging.getLogger(__name__)

import importlib
backend_config = importlib.import_module("backend.config").config
from services.investment import estado_completo, evaluar_riesgo, _cargar_1d, calcular_features_riesgo
from services.paper_trader import simular_estrategia
from services.notifier import notificar_cambio_riesgo
from dca_engine import DCAEngine
from modos import Modo, MODOS, MODO_DEFECTO
from risk_filter import ACCIONES, EMOJI

router = APIRouter(prefix="/api", tags=["inversion"])

# Directorio persistente para estado (volumen en Railway); ROOT en local.
STATE = backend_config.STATE_DIR or ROOT
os.makedirs(STATE, exist_ok=True)

DB_PATH = os.path.join(STATE, "dca_state.json")


@router.get("/portfolio")
def portfolio(symbol: str = Query("BTC/USDT"), modo: str = Query("conservador"),
              symbols: str = Query(None), user_id: str = Query(None)):
    """Estado simple de la inversion para el dashboard del usuario.

    modo=moderado acepta symbols=BTC/USDT,ETH/USDT,SOL/USDT para mostrar
    el portafolio multi-activo y la distribucion de exposicion.
    user_id aislada el estado DCA por usuario (multi-usuario).
    """
    db_path = os.path.join(STATE, f"dca_state_{user_id}.json") if user_id else DB_PATH
    simbolos = None
    if modo == "experimental":
        # Modo Experimental: SOLO simulacion paper, sin dinero real
        sym = symbol or "BTC/USDT"
        r = simular_estrategia(sym)
        r["modo"] = modo
        r["modo_info"] = MODOS.get(Modo(modo), MODOS[MODO_DEFECTO])
        return r
    if modo == "moderado" and symbols:
        simbolos = [s.strip() for s in symbols.split(",") if s.strip()]
    r = estado_completo(
        symbol=symbol,
        api_key=backend_config.OPENAI_API_KEY,
        db_path=db_path,
        symbols=simbolos,
    )
    r["modo"] = modo
    r["modo_info"] = MODOS.get(Modo(modo), MODOS[MODO_DEFECTO])
    return r


@router.get("/risk")
def risk(symbol: str = Query("BTC/USDT")):
    """Nivel de riesgo actual del mercado (filtro IA)."""
    d2 = _cargar_1d(symbol)
    if d2.empty:
        return {"error": "sin datos"}
    nivel, razon, features = evaluar_riesgo(d2, backend_config.OPENAI_API_KEY)
    vivo = None
    try:
        from services.binance import BinanceService
        vivo = BinanceService.precio_publico(symbol)
    except Exception:
        pass
    # Disparar alertas si el riesgo subio (medium/alto)
    try:
        import asyncio
        from services.notifier import notificar_cambio_riesgo
        asyncio.run(notificar_cambio_riesgo(
            nivel, ACCIONES.get(nivel, "Continuar DCA normal"), razon,
            precio=float(vivo) if vivo else None,
        ))
    except Exception as e:
        logger.warning(f"No se pudo notificar riesgo: {e}")
    return {
        "symbol": symbol,
        "riesgo": nivel,
        "riesgo_emoji": EMOJI.get(nivel, "🟢"),
        "accion": ACCIONES.get(nivel, "Continuar DCA normal"),
        "razon": razon,
        "features": features,
    }


@router.post("/dca/execute")
def dca_execute(symbol: str = Query("BTC/USDT"), forzar: bool = Query(False),
                user_id: str = Query(None)):
    """Ejecuta la compra DCA programada con el monto ajustado por riesgo.
    Solo se usa en modo conservador/moderado. NUNCA vende.
    """
    db_path = os.path.join(STATE, f"dca_state_{user_id}.json") if user_id else DB_PATH
    r = estado_completo(symbol=symbol, api_key=backend_config.OPENAI_API_KEY, db_path=db_path)
    if r.get("error"):
        return r
    d2 = _cargar_1d(symbol)
    nivel, razon, _ = evaluar_riesgo(d2, backend_config.OPENAI_API_KEY)
    engine = DCAEngine(db_path=db_path)
    compra = engine.ejecutar_compra(precio=r["precio"], riesgo=nivel if not forzar else "low", razon=razon)
    if compra is None:
        return {"ok": False, "mensaje": "Compra pausada por riesgo alto o pausa manual", "riesgo": nivel}
    return {"ok": True, "compra": compra, "riesgo": nivel, "accion": ACCIONES.get(nivel)}


@router.post("/dca/pause")
def dca_pause(pausado: bool = Query(True), user_id: str = Query(None)):
    """Pausa o reanuda manualmente las compras (el usuario decide)."""
    db_path = os.path.join(STATE, f"dca_state_{user_id}.json") if user_id else DB_PATH
    engine = DCAEngine(db_path=db_path)
    engine.configurar(pausado_manual=pausado)
    return {"ok": True, "pausado_manual": pausado}


@router.get("/modo")
def modo_actual():
    """Info de los 3 modos (Conservador / Moderado / Experimental)."""
    return {
        "modo_defecto": MODO_DEFECTO.value,
        "modos": MODOS,
        "mensaje": "No intentamos adivinar el mercado. Invertimos con disciplina y reducimos el riesgo de malas decisiones emocionales.",
    }


@router.post("/risk/notify")
async def notificar_riesgo(symbol: str = Query("BTC/USDT"), phone: str = Query(None)):
    """Fuerza la evaluacion de riesgo y el envio de alertas si subio."""
    d2 = _cargar_1d(symbol)
    if d2.empty:
        return {"error": "sin datos"}
    nivel, razon, _ = evaluar_riesgo(d2, backend_config.OPENAI_API_KEY)
    vivo = None
    try:
        from services.binance import BinanceService
        vivo = BinanceService.precio_publico(symbol)
    except Exception:
        pass
    enviado = await notificar_cambio_riesgo(
        nivel, ACCIONES.get(nivel, "Continuar DCA normal"), razon,
        precio=float(vivo) if vivo else None, phone=phone,
    )
    return {
        "riesgo": nivel,
        "notificado": enviado,
        "mensaje": "Alerta enviada" if enviado else "Sin cambio de nivel o riesgo bajo",
    }


