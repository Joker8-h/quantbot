"""Servicio de paper trading para el Modo Experimental (arquitectura final de Vill).

🔴 EXPERIMENTAL: SOLO simulacion. Nunca usa dinero real.

Importante (honestidad radical):
  Las pruebas historicas 2019-2026 en BTC/ETH/SOL spot NO encontraron
  ventaja alguna en estrategias activas (PF 0.12-0.67, AUC ~0.5).
  Este modulo SIMULA operaciones activas sobre datos reales para que el
  usuario vea, sin riesgo, como se comportaria una estrategia. No promete
  ganancias. Es educativo y de diagnostico.
"""
import os
import sys
import random
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd

import importlib.util
_spec = importlib.util.spec_from_file_location("root_config_module", os.path.join(ROOT, "config.py"))
_root_config_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_root_config_mod)
ROOT_CONFIG = _root_config_mod.CONFIG

from indicators import Indicators
from data_collector import DataCollector


def _cargar_1d(symbol: str = "BTC/USDT") -> pd.DataFrame:
    """Carga datos 1D reutilizando la logica de investment.

    Usa el CSV diario cacheado (incluido en la imagen) con fallback a
    descarga directa 1d. Evita cargar el CSV 1h gigante que no se sube a
    Railway (Binance esta geo-bloqueado en el datacenter US).
    """
    from services.investment import _cargar_1d as _cargar_1d_inv
    return _cargar_1d_inv(symbol)


def simular_estrategia(symbol: str = "BTC/USDT", capital_inicial: float = 1000.0,
                       ventana: int = 90) -> dict:
    """Simula una estrategia activa de seguimiento de tendencia (paper only).

    Usa los ultimos `ventana` dias de datos reales. Compra cuando el precio
    cruza por encima de la media movil de 20 dias y vende cuando cruza por
    debajo. Es una estrategia de ejemplo, NO una recomendacion.

    Devuelve metricas honestas: capital final, retorno, y comparacion contra
    simple hold (comprar y mantener).
    """
    d2 = _cargar_1d(symbol)
    if d2.empty or len(d2) < ventana + 30:
        return {"error": "sin datos suficientes"}

    df = d2.tail(ventana + 30).reset_index(drop=True)
    precio_actual = float(df['close'].iloc[-1])

    # Medias moviles de ejemplo
    sma20 = df['close'].rolling(20).mean()
    sma50 = df['close'].rolling(50).mean()

    capital = capital_inicial
    unidades = 0.0
    en_mercado = False
    trades = 0
    historia = []

    for i in range(50, len(df)):
        precio = float(df['close'].iloc[i])
        s20 = sma20.iloc[i]
        s50 = sma50.iloc[i]
        if pd.isna(s20) or pd.isna(s50):
            continue
        # Senal simple: cruce alcista
        if not en_mercado and s20 > s50:
            unidades = capital / precio
            capital = 0.0
            en_mercado = True
            trades += 1
        elif en_mercado and s20 < s50:
            capital = unidades * precio
            unidades = 0.0
            en_mercado = False
            trades += 1
        valor = capital + unidades * precio
        historia.append(valor)

    # Liquidar al final si queda en mercado
    valor_final = capital + unidades * precio_actual
    retorno_pct = (valor_final / capital_inicial - 1) * 100

    # Benchmark: buy & hold desde el inicio de la ventana
    precio_inicio = float(df['close'].iloc[50])
    retorno_hold_pct = (precio_actual / precio_inicio - 1) * 100
    valor_hold = capital_inicial * (precio_actual / precio_inicio)

    # Drawdown de la simulacion
    if historia:
        picos = pd.Series(historia).cummax()
        dd = ((pd.Series(historia) - picos) / picos).min() * 100
    else:
        dd = 0.0

    return {
        "modo": "experimental",
        "paper": True,
        "symbol": symbol,
        "capital_inicial": round(capital_inicial, 2),
        "valor_final": round(valor_final, 2),
        "retorno_pct": round(retorno_pct, 2),
        "retorno_hold_pct": round(retorno_hold_pct, 2),
        "valor_hold": round(valor_hold, 2),
        "supero_hold": bool(valor_final > valor_hold),
        "drawdown_pct": round(float(dd), 2),
        "trades": trades,
        "precio_actual": round(precio_actual, 2),
        "ventana_dias": ventana,
        "advertencia": "Simulacion PAPER. No usa dinero real. Las estrategias activas no han demostrado ventaja en pruebas historicas (PF 0.12-0.67).",
    }


if __name__ == "__main__":
    random.seed(42)
    print(simular_estrategia("BTC/USDT"))
    print(simular_estrategia("ETH/USDT"))
    print(simular_estrategia("SOL/USDT"))
