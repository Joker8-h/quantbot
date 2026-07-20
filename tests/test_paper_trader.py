"""Tests del paper trader (Modo Experimental)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
sys.path.insert(0, ROOT)

from services.paper_trader import simular_estrategia


def test_simulacion_devuelve_claves():
    r = simular_estrategia("BTC/USDT")
    assert r["paper"] is True
    for k in ["valor_final", "retorno_pct", "retorno_hold_pct", "drawdown_pct", "trades"]:
        assert k in r


def test_simulacion_es_determinista():
    a = simular_estrategia("BTC/USDT", capital_inicial=1000.0)
    b = simular_estrategia("BTC/USDT", capital_inicial=1000.0)
    assert a["valor_final"] == b["valor_final"]
    assert a["trades"] == b["trades"]


def test_simulacion_no_usa_dinero_real():
    r = simular_estrategia("ETH/USDT")
    assert "no usa dinero real" in r["advertencia"].lower()
