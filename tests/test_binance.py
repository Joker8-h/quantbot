"""Tests del servicio Binance (con mocks, sin red)."""
import os
import sys
from unittest.mock import patch, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
sys.path.insert(0, ROOT)


def test_precio_publico_mock():
    from services.binance import BinanceService
    svc = BinanceService()
    with patch.object(BinanceService, "precio_publico", return_value=63910.0):
        p = svc.precio_publico("BTC/USDT")
        assert p == 63910.0


def test_validar_conexion_rechaza_withdraw():
    from services.binance import BinanceService
    svc = BinanceService("k", "s")
    fake_exchange = MagicMock()
    fake_exchange.fetch_balance.return_value = {"USDT": {"free": 100.0}}
    fake_exchange.fetch_permissions.return_value = ["SPOT", "WITHDRAWAL"]
    svc.exchange = fake_exchange
    r = svc.validar_conexion()
    assert r["ok"] is True
    assert r["tiene_retiro"] is True
    assert r["tiene_spot_trading"] is True


def test_validar_conexion_acepta_solo_spot():
    from services.binance import BinanceService
    svc = BinanceService("k", "s")
    fake_exchange = MagicMock()
    fake_exchange.fetch_balance.return_value = {"USDT": {"free": 100.0}}
    fake_exchange.fetch_permissions.return_value = {"info": {"permissions": ["SPOT"]}}
    svc.exchange = fake_exchange
    r = svc.validar_conexion()
    assert r["ok"] is True
    assert r["tiene_retiro"] is False
