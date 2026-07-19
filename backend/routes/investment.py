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

import importlib
backend_config = importlib.import_module("backend.config").config
from services.investment import estado_completo, evaluar_riesgo, _cargar_1d, calcular_features_riesgo
from dca_engine import DCAEngine
from modos import Modo, MODOS, MODO_DEFECTO
from risk_filter import ACCIONES, EMOJI

router = APIRouter(prefix="/api", tags=["inversion"])

DB_PATH = os.path.join(ROOT, "dca_state.json")


@router.get("/portfolio")
def portfolio(symbol: str = Query("BTC/USDT"), modo: str = Query("conservador"),
              symbols: str = Query(None)):
    """Estado simple de la inversion para el dashboard del usuario.

    modo=moderado acepta symbols=BTC/USDT,ETH/USDT,SOL/USDT para mostrar
    el portafolio multi-activo y la distribucion de exposicion.
    """
    simbolos = None
    if modo == "moderado" and symbols:
        simbolos = [s.strip() for s in symbols.split(",") if s.strip()]
    r = estado_completo(
        symbol=symbol,
        api_key=backend_config.OPENAI_API_KEY,
        db_path=DB_PATH,
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
    return {
        "symbol": symbol,
        "riesgo": nivel,
        "riesgo_emoji": EMOJI.get(nivel, "🟢"),
        "accion": ACCIONES.get(nivel, "Continuar DCA normal"),
        "razon": razon,
        "features": features,
    }


@router.post("/dca/execute")
def dca_execute(symbol: str = Query("BTC/USDT"), forzar: bool = Query(False)):
    """Ejecuta la compra DCA programada con el monto ajustado por riesgo.
    Solo se usa en modo conservador/moderado. NUNCA vende.
    """
    r = estado_completo(symbol=symbol, api_key=backend_config.OPENAI_API_KEY, db_path=DB_PATH)
    if r.get("error"):
        return r
    d2 = _cargar_1d(symbol)
    nivel, razon, _ = evaluar_riesgo(d2, backend_config.OPENAI_API_KEY)
    engine = DCAEngine(db_path=DB_PATH)
    compra = engine.ejecutar_compra(precio=r["precio"], riesgo=nivel if not forzar else "low", razon=razon)
    if compra is None:
        return {"ok": False, "mensaje": "Compra pausada por riesgo alto o pausa manual", "riesgo": nivel}
    return {"ok": True, "compra": compra, "riesgo": nivel, "accion": ACCIONES.get(nivel)}


@router.post("/dca/pause")
def dca_pause(pausado: bool = Query(True)):
    """Pausa o reanuda manualmente las compras (el usuario decide)."""
    engine = DCAEngine(db_path=DB_PATH)
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

