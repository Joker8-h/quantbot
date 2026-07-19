import os
import time
import importlib.util
from datetime import datetime, timezone

import ccxt
import pandas as pd

# Resolver config RAIZ por ruta de archivo (evita colision con backend/config.py)
_root_cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
_spec = importlib.util.spec_from_file_location("root_config_module", _root_cfg_path)
_root_cfg_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_root_cfg_mod)
CONFIG = _root_cfg_mod.CONFIG


class DataCollector:
    def __init__(self):
        self.exchange = ccxt.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        self.data_dir = CONFIG.data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        ).timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        ).timestamp() * 1000)

        all_candles = []
        current_ts = start_ts

        print(f"Descargando {symbol} {timeframe} desde {start_date} hasta {end_date}...")

        while current_ts < end_ts:
            try:
                candles = self.exchange.fetch_ohlcv(
                    symbol, timeframe, since=current_ts, limit=1000
                )
                if not candles:
                    break

                all_candles.extend(candles)
                current_ts = candles[-1][0] + 1

                print(f"  Descargadas {len(all_candles)} velas...")

                time.sleep(self.exchange.rateLimit / 1000)

            except ccxt.NetworkError as e:
                print(f"  Error de red: {e}. Reintentando en 5s...")
                time.sleep(5)
            except ccxt.ExchangeError as e:
                print(f"  Error del exchange: {e}")
                break

        if not all_candles:
            print(f"  No se obtuvieron datos para {symbol} {timeframe}")
            return pd.DataFrame()

        df = pd.DataFrame(
            all_candles,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

        # Filtrar por fecha final
        df = df[df["timestamp"] <= end_ts].reset_index(drop=True)

        return df

    def save_csv(self, df: pd.DataFrame, symbol: str, timeframe: str):
        filename = f"{symbol.replace('/', '_')}_{timeframe}.csv"
        filepath = os.path.join(self.data_dir, filename)
        df.to_csv(filepath, index=False)
        print(f"  Guardado: {filepath} ({len(df)} velas)")
        return filepath

    def load_csv(self, symbol: str, timeframe: str) -> pd.DataFrame:
        filename = f"{symbol.replace('/', '_')}_{timeframe}.csv"
        filepath = os.path.join(self.data_dir, filename)
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            df["datetime"] = pd.to_datetime(df["datetime"])
            print(f"  Cargado: {filepath} ({len(df)} velas)")
            return df
        return pd.DataFrame()

    def collect_all(self):
        results = {}
        for symbol in CONFIG.symbols:
            for timeframe in CONFIG.timeframes:
                print(f"\n{'='*50}")
                print(f"Procesando: {symbol} | {timeframe}")
                print(f"{'='*50}")

                # Intentar cargar CSV existente
                df = self.load_csv(symbol, timeframe)
                if not df.empty:
                    results[(symbol, timeframe)] = df
                    continue

                # Descargar datos
                df = self.fetch_ohlcv(
                    symbol, timeframe, CONFIG.start_date, CONFIG.end_date
                )
                if not df.empty:
                    self.save_csv(df, symbol, timeframe)
                    results[(symbol, timeframe)] = df

        return results


if __name__ == "__main__":
    collector = DataCollector()
    data = collector.collect_all()

    for (symbol, tf), df in data.items():
        print(f"\n{symbol} {tf}: {len(df)} velas")
        print(f"  Desde: {df['datetime'].iloc[0]}")
        print(f"  Hasta: {df['datetime'].iloc[-1]}")
        print(f"  Precio inicial: ${df['close'].iloc[0]:,.2f}")
        print(f"  Precio final: ${df['close'].iloc[-1]:,.2f}")
