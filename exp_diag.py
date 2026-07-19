"""Exp D: baseline buy&hold + stop muy amplio (long-only) para diagnosticar.
Si buy&hold es positivo pero estrategias pierden -> el problema es la senal/SL.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd

from indicators import Indicators
from backtester import Backtester
from metrics import Metrics
from config import TradingConfig

RAW = 'data/raw/BTC_USDT_1h.csv'
df = pd.read_csv(RAW)
df['datetime'] = pd.to_datetime(df['datetime'])
for c in ['open', 'high', 'low', 'close', 'volume']:
    df[c] = df[c].astype(float)

# Baseline buy&hold en 1d
o = df.set_index('datetime')['open'].resample('1D').first()
c = df.set_index('datetime')['close'].resample('1D').last()
d1 = pd.DataFrame({'open': o, 'close': c}).dropna().reset_index()
ret_bh = (d1['close'].iloc[-1] / d1['close'].iloc[0] - 1) * 100
print(f'BUY&HOLD 1d: Ret {ret_bh:+.1f}%  ({len(d1)} dias, {d1["datetime"].iloc[0].date()} -> {d1["datetime"].iloc[-1].date()})')

# Long-only con SL/TP ratios extremos (stop ancho)
o = df.set_index('datetime')['open'].resample('1D').first()
h = df.set_index('datetime')['high'].resample('1D').max()
l = df.set_index('datetime')['low'].resample('1D').min()
c = df.set_index('datetime')['close'].resample('1D').last()
v = df.set_index('datetime')['volume'].resample('1D').sum()
d1 = pd.DataFrame({'open': o, 'high': h, 'low': l, 'close': c, 'volume': v}).dropna().reset_index()
d2 = Indicators().add_all(d1)
results = []
for atr_sl in [5.0, 8.0, 12.0]:
    for rr in [3.0, 5.0]:
        sig = pd.Series(0, index=d2.index)
        # entrada simple: cruce EMA alcista
        sig[(d2['ema_fast'] > d2['ema_slow']) & (d2['close'] > d2['close'].shift(1))] = 1
        d2s = d2.copy(); d2s['signal'] = sig.values
        cfg = TradingConfig(atr_sl_multiplier=atr_sl, rr_ratio=rr, min_bars_between_trades=10)
        res = Backtester(cfg).run(d2s)
        m = Metrics().calculate(res['trades'], res['equity_curve'])
        if m['total_trades'] >= 20:
            results.append((m['profit_factor'], atr_sl, rr, m['win_rate'], m['rentabilidad'], m['max_drawdown'], m['total_trades']))
results.sort(reverse=True)
print('\nLong-only SL ancho:')
for r in results[:10]:
    print(f"PF {r[0]:.2f} sl{r[1]} rr{r[2]} WR {r[3]:.0f} Ret {r[4]:+.1f}% DD {r[5]:.1f}% N {r[6]}")
