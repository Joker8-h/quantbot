"""Servicio de inversion: une precio en vivo, filtro de riesgo IA y DCA.

Flujo (arquitectura final de Vill):
  Datos de Binance -> Indicadores -> RiskFilter IA -> nivel de riesgo
  -> DCAEngine ajusta monto -> estado de inversion -> alertas.

El servicio es el cerebro del Modo Conservador.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import pandas as pd

# Permitir importar modulos del proyecto raiz
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import importlib
import importlib.util
backend_config = importlib.import_module("backend.config").config

# Indicadores/data_collector resuelven su propio CONFIG raiz por ruta.
# Cargar CONFIG raiz explicitamente para pasarlo a Indicators.
_spec = importlib.util.spec_from_file_location("root_config_module", os.path.join(ROOT, "config.py"))
_root_config_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_root_config_mod)
ROOT_CONFIG = _root_config_mod.CONFIG

from risk_filter import RiskFilter, ACCIONES, EMOJI
from dca_engine import DCAEngine
from indicators import Indicators
from data_collector import DataCollector


def _cargar_1d(symbol: str = "BTC/USDT"):
    """Carga datos 1D desde CSV local o los descarga."""
    path = os.path.join(ROOT, "data", "raw", f"{symbol.replace('/', '_')}_1h.csv")
    if not os.path.exists(path):
        c = DataCollector()
        df = c.fetch_ohlcv(symbol, "1h", "2019-01-01", "2026-07-18")
        if df.empty:
            return pd.DataFrame()
        c.save_csv(df, symbol, "1h")
    else:
        df = pd.read_csv(path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    o = df.set_index('datetime')['open'].resample('1D').first()
    h = df.set_index('datetime')['high'].resample('1D').max()
    l = df.set_index('datetime')['low'].resample('1D').min()
    c = df.set_index('datetime')['close'].resample('1D').last()
    v = df.set_index('datetime')['volume'].resample('1D').sum()
    out = pd.DataFrame({'open': o, 'high': h, 'low': l, 'close': c, 'volume': v}).dropna().reset_index()
    return Indicators(config=ROOT_CONFIG).add_all(out)


def calcular_features_riesgo(d2: pd.DataFrame) -> dict:
    # Usar la ultima vela COMPLETA (la ultima fila suele ser el dia en curso, parcial)
    ult = d2.iloc[-2] if len(d2) > 2 else d2.iloc[-1]
    close = d2['close']
    ret7 = (close.iloc[-1] / close.iloc[-8] - 1) * 100 if len(close) > 8 else 0.0
    ret30 = (close.iloc[-1] / close.iloc[-31] - 1) * 100 if len(close) > 31 else 0.0
    roll_max = close.rolling(90).max()
    dd = (close.iloc[-1] / roll_max.iloc[-1] - 1) * 100 if roll_max.iloc[-1] > 0 else 0.0
    return {
        "return_7d": round(float(ret7), 2),
        "return_30d": round(float(ret30), 2),
        "adx": round(float(ult['adx']), 1),
        "rsi": round(float(ult['rsi']), 1),
        "atr_pct": round(float(ult['atr'] / ult['close'] * 100), 2),
        "vol_ratio": round(float(ult['volume'] / ult['vol_avg']), 2),
        "bb_width_pct": round(float(ult['bb_width'] / ult['close'] * 100), 2),
        "drawdown_pct": round(float(dd), 2),
    }


def evaluar_riesgo(d2: pd.DataFrame, api_key: str = None) -> tuple:
    features = calcular_features_riesgo(d2)
    rf = RiskFilter(api_key=api_key or backend_config.OPENAI_API_KEY)
    nivel, razon = rf.evaluate(features)
    return nivel, razon, features


def estado_completo(symbol: str = "BTC/USDT", api_key: str = None,
                    db_path: str = None) -> dict:
    """Devuelve el estado completo del Modo Conservador para el dashboard."""
    d2 = _cargar_1d(symbol)
    if d2.empty:
        return {"error": "sin datos"}
    precio = float(d2['close'].iloc[-1])
    nivel, razon, features = evaluar_riesgo(d2, api_key)

    from datetime import datetime, timedelta
    proxima = (datetime.now() + timedelta(days=30)).strftime("%d de %B")

    engine = DCAEngine(db_path=db_path or os.path.join(ROOT, "dca_state.json"))
    est = engine.estado(
        precio_actual=precio,
        riesgo=nivel,
        razon=razon,
        accion=ACCIONES.get(nivel, "Continuar DCA normal"),
        proxima_compra=proxima,
    )
    return {
        "symbol": symbol,
        "precio": round(precio, 2),
        "riesgo": nivel,
        "riesgo_emoji": EMOJI.get(nivel, "🟢"),
        "accion": ACCIONES.get(nivel, "Continuar DCA normal"),
        "razon": razon,
        "features": features,
        "capital_invertido": est.capital_invertido,
        "valor_actual": est.valor_actual,
        "ganancia": est.ganancia,
        "ganancia_pct": est.ganancia_pct,
        "pausado": est.pausado,
        "proxima_compra": est.proxima_compra,
        "total_compras": len(est.compras),
    }


if __name__ == "__main__":
    r = estado_completo(api_key=os.environ.get("OPENAI_API_KEY"))
    print(r)
