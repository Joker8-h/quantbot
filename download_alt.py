"""Descargar ETH/USDT y SOL/USDT 1h 2019-2026."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from data_collector import DataCollector

c = DataCollector()
for sym in ['ETH/USDT', 'SOL/USDT']:
    df = c.fetch_ohlcv(sym, '1h', '2019-01-01', '2026-07-18')
    if not df.empty:
        c.save_csv(df, sym, '1h')
