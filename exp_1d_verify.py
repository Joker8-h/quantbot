"""Verificacion 1d: mejor config + robustness +/-20% + escenarios."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd

from indicators import Indicators
from backtester import Backtester
from metrics import Metrics
from config import TradingConfig

df = pd.read_csv('data/raw/BTC_USDT_1h.csv')
df['datetime'] = pd.to_datetime(df['datetime'])
for c in ['open', 'high', 'low', 'close', 'volume']:
    df[c] = df[c].astype(float)

o = df.set_index('datetime')['open'].resample('1D').first()
h = df.set_index('datetime')['high'].resample('1D').max()
l = df.set_index('datetime')['low'].resample('1D').min()
c = df.set_index('datetime')['close'].resample('1D').last()
v = df.set_index('datetime')['volume'].resample('1D').sum()
d = pd.DataFrame({'open': o, 'high': h, 'low': l, 'close': c, 'volume': v}).dropna().reset_index()

ind = Indicators()
d2 = ind.add_all(d)

sig = pd.Series(0, index=d2.index)
sig[(d2['ema_fast'] > d2['ema_slow']) & (d2['rsi'] > 50) & (d2['close'] > d2['high'].shift(1)) & (d2['volume'] > d2['vol_avg'] * 2.0)] = 1
sig[(d2['ema_fast'] < d2['ema_slow']) & (d2['rsi'] < 30) & (d2['close'] < d2['low'].shift(1)) & (d2['volume'] > d2['vol_avg'] * 2.0)] = -1

def run(slip, fee):
    d2s = d2.copy()
    d2s['signal'] = sig.values
    cfg = TradingConfig(atr_sl_multiplier=2.0, rr_ratio=1.5, min_bars_between_trades=120,
                        slippage=slip, fee=fee)
    bt = Backtester(cfg)
    res = bt.run(d2s)
    return Metrics().calculate(res['trades'], res['equity_curve'])

print('BASE (fee 0.1% slip 0.05%):', run(0.0005, 0.001))
print('OPTIMISTA (fee 0 slip 0):', run(0.0, 0.0))
print('PESSIMISTA (fee 0.2% slip 0.1%):', run(0.001, 0.002))
