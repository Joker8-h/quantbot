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

# Precio en vivo publico de Binance (sin credenciales)
try:
    from services.binance import BinanceService
    _TIENE_BINANCE = True
except Exception:
    _TIENE_BINANCE = False


# Mapa simbolo -> id de CoinGecko (funciona desde datacenters US, Binance no)
_COINGECKO_IDS = {
    "BTC/USDT": "bitcoin",
    "ETH/USDT": "ethereum",
    "SOL/USDT": "solana",
    "BTC/USD": "bitcoin",
    "ETH/USD": "ethereum",
    "SOL/USD": "solana",
}


def _precio_coingecko(symbol: str) -> float:
    """Precio en vivo desde CoinGecko (no geo-bloqueado en Railway US)."""
    coin_id = _COINGECKO_IDS.get(symbol)
    if not coin_id:
        return None
    try:
        import urllib.request
        import json as _json
        url = (
            "https://api.coingecko.com/api/v3/simple/price"
            f"?ids={coin_id}&vs_currencies=usd"
        )
        with urllib.request.urlopen(url, timeout=8) as r:
            data = _json.loads(r.read())
        precio = data.get(coin_id, {}).get("usd")
        return float(precio) if precio else None
    except Exception as e:
        print(f"[investment] CoinGecko fallo para {symbol}: {e}")
        return None


def _precio_vivo(symbol: str) -> float:
    """Precio en vivo con fallback: Binance -> CoinGecko -> None.

    En Railway (datacenter US) Binance esta geo-bloqueado, por eso se
    intenta CoinGecko como respaldo antes de rendirse.
    """
    if _TIENE_BINANCE:
        try:
            p = BinanceService.precio_publico(symbol)
            if p:
                return float(p)
        except Exception:
            pass
    return _precio_coingecko(symbol)


def _cargar_1d(symbol: str = "BTC/USDT"):
    """Carga datos 1D para el filtro de riesgo.

    Prioridad:
      1. CSV 1D local cacheado (rapido).
      2. Descarga directa en timeframe 1d desde Binance (pequeno y rapido,
         ~400 velas, con timeout para no colgar el endpoint).
      3. Fallback: recorte del CSV 1h local si existe.
    """
    from datetime import datetime, timedelta

    path_1d = os.path.join(ROOT, "data", "raw", f"{symbol.replace('/', '_')}_1d.csv")
    if os.path.exists(path_1d):
        df = pd.read_csv(path_1d)
        return _normalizar_1d(df)

    # Descarga directa 1d (evita el CSV 1h gigante)
    try:
        import ccxt
        ex = ccxt.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
            "timeout": 15000,
        })
        since = int((datetime.now() - timedelta(days=400)).timestamp() * 1000)
        ohlcv = ex.fetch_ohlcv(symbol, "1d", since=since, limit=420)
        if ohlcv:
            df = pd.DataFrame(ohlcv, columns=["datetime", "open", "high", "low", "close", "volume"])
            df["datetime"] = pd.to_datetime(df["datetime"], unit="ms")
            try:
                df.to_csv(path_1d, index=False)
            except Exception:
                pass
            return _normalizar_1d(df)
    except Exception as e:
        print(f"[investment] descarga 1d fallo para {symbol}: {e}")

    # Fallback: recortar CSV 1h local si esta presente
    path = os.path.join(ROOT, "data", "raw", f"{symbol.replace('/', '_')}_1h.csv")
    if os.path.exists(path):
        df = pd.read_csv(path)
        df['datetime'] = pd.to_datetime(df['datetime'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        out = pd.DataFrame({
            "open": df.set_index('datetime')['open'].resample('1D').first(),
            "high": df.set_index('datetime')['high'].resample('1D').max(),
            "low": df.set_index('datetime')['low'].resample('1D').min(),
            "close": df.set_index('datetime')['close'].resample('1D').last(),
            "volume": df.set_index('datetime')['volume'].resample('1D').sum(),
        }).dropna().reset_index()
        return Indicators(config=ROOT_CONFIG).add_all(out)

    return pd.DataFrame()


def _normalizar_1d(df: pd.DataFrame) -> pd.DataFrame:
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    return Indicators(config=ROOT_CONFIG).add_all(df)


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
                    db_path: str = None, symbols: list = None) -> dict:
    """Devuelve el estado completo del Modo Conservador para el dashboard.

    Si se pasa `symbols` (Modo Moderado), calcula el estado agregado de
    varios activos y la distribucion de exposicion.
    """
    if symbols:
        return _estado_multi(symbols, api_key, db_path)

    d2 = _cargar_1d(symbol)
    if d2.empty:
        return {"error": "sin datos"}
    vivo = _precio_vivo(symbol)
    precio = vivo if vivo else float(d2['close'].iloc[-1])
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


def _estado_multi(symbols: list, api_key: str, db_path: str) -> dict:
    """Modo Moderado: estado agregado de varios activos + distribucion."""
    from datetime import datetime, timedelta
    proxima = (datetime.now() + timedelta(days=30)).strftime("%d de %B")

    activos = []
    capital_total = 0.0
    valor_total = 0.0
    for sym in symbols:
        d2 = _cargar_1d(sym)
        if d2.empty:
            continue
        vivo = _precio_vivo(sym)
        precio = vivo if vivo else float(d2['close'].iloc[-1])
        nivel, razon, _ = evaluar_riesgo(d2, api_key)
        engine = DCAEngine(db_path=db_path or os.path.join(ROOT, f"dca_state_{sym.replace('/', '_')}.json"))
        est = engine.estado(
            precio_actual=precio,
            riesgo=nivel,
            razon=razon,
            proxima_compra=proxima,
        )
        capital_total += est.capital_invertido
        valor_total += est.valor_actual
        activos.append({
            "symbol": sym,
            "precio": round(precio, 2),
            "riesgo": nivel,
            "riesgo_emoji": EMOJI.get(nivel, "🟢"),
            "capital_invertido": est.capital_invertido,
            "valor_actual": est.valor_actual,
            "ganancia_pct": est.ganancia_pct,
        })
    ganancia = valor_total - capital_total
    ganancia_pct = (ganancia / capital_total * 100) if capital_total > 0 else 0.0
    # Distribucion de exposicion (por valor actual)
    for a in activos:
        a["peso_pct"] = round(a["valor_actual"] / valor_total * 100, 1) if valor_total > 0 else 0.0
    return {
        "multi": True,
        "activos": activos,
        "capital_invertido": round(capital_total, 2),
        "valor_actual": round(valor_total, 2),
        "ganancia": round(ganancia, 2),
        "ganancia_pct": round(ganancia_pct, 2),
        "proxima_compra": proxima,
    }


if __name__ == "__main__":
    r = estado_completo(api_key=os.environ.get("OPENAI_API_KEY"))
    print(r)

