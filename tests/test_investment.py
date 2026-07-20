"""Tests del servicio de inversion (Modo Conservador/Moderado)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
sys.path.insert(0, ROOT)

from services.investment import calcular_features_riesgo, _cargar_1d
import pandas as pd


def test_cargar_1d_devuelve_dataframe():
    df = _cargar_1d("BTC/USDT")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    for col in ["open", "high", "low", "close", "rsi", "adx", "atr"]:
        assert col in df.columns


def test_features_riesgo_tienen_claves():
    df = _cargar_1d("BTC/USDT")
    f = calcular_features_riesgo(df)
    for k in ["return_7d", "return_30d", "adx", "rsi", "drawdown_pct"]:
        assert k in f
        assert isinstance(f[k], (int, float))


def test_estado_multi_no_falla():
    from services.investment import _estado_multi
    r = _estado_multi(["BTC/USDT", "ETH/USDT", "SOL/USDT"], None, None)
    assert r["multi"] is True
    assert "activos" in r
    assert len(r["activos"]) >= 1
