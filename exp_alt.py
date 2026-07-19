"""Experimento final: senales alternativas con trade-count suficiente (4h)."""
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

o = df.set_index('datetime')['open'].resample('4h').first()
h = df.set_index('datetime')['high'].resample('4h').max()
l = df.set_index('datetime')['low'].resample('4h').min()
c = df.set_index('datetime')['close'].resample('4h').last()
v = df.set_index('datetime')['volume'].resample('4h').sum()
d = pd.DataFrame({'open': o, 'high': h, 'low': l, 'close': c, 'volume': v}).dropna().reset_index()

ind = Indicators()
d2 = ind.add_all(d)

def backtest(sig):
    d2s = d2.copy()
    d2s['signal'] = sig.values
    cfg = TradingConfig(atr_sl_multiplier=4.0, rr_ratio=1.5, min_bars_between_trades=72)
    bt = Backtester(cfg)
    m = Metrics().calculate(bt.run(d2s)['trades'], bt.run(d2s)['equity_curve'])
    return m

# S1: RSI mean-reversion extrema
s1 = pd.Series(0, index=d2.index)
c1 = (d2['rsi'] < 30) & (d2['close'] > d2['open']) & (d2['volume'] > d2['vol_avg'] * 1.5)
s1[c1] = 1
c1b = (d2['rsi'] > 70) & (d2['close'] < d2['open']) & (d2['volume'] > d2['vol_avg'] * 1.5)
s1[c1b] = -1

# S2: EMA pullback (precio toca EMA en tendencia)
s2 = pd.Series(0, index=d2.index)
up = d2['ema_fast'] > d2['ema_slow']
dn = d2['ema_fast'] < d2['ema_slow']
pb_up = d2['low'] <= d2['ema_fast'] * 1.01
pb_dn = d2['high'] >= d2['ema_fast'] * 0.99
s2[up & pb_up & (d2['close'] > d2['ema_fast']) & (d2['rsi'] > 40)] = 1
s2[dn & pb_dn & (d2['close'] < d2['ema_fast']) & (d2['rsi'] < 60)] = -1

# S3: breakout original
s3 = pd.Series(0, index=d2.index)
s3[(d2['ema_fast'] > d2['ema_slow']) & (d2['rsi'] > 50) & (d2['close'] > d2['high'].shift(1)) & (d2['volume'] > d2['vol_avg'])] = 1
s3[(d2['ema_fast'] < d2['ema_slow']) & (d2['rsi'] < 30) & (d2['close'] < d2['low'].shift(1)) & (d2['volume'] > d2['vol_avg'] * 2)] = -1

for name, sig in [('S1 RSI-rev', s1), ('S2 EMA-pullback', s2), ('S3 breakout', s3)]:
    m = backtest(sig)
    print(f"{name}: PF {m['profit_factor']:.2f} WR {m['win_rate']:.0f} Ret {m['rentabilidad']:+.1f}% DD {m['max_drawdown']:.1f}% N {m['total_trades']}")
