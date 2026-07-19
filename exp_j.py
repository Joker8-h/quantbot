"""Exp J: ajuste WR>45% en 1D + walk-forward + Monte Carlo real."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import numpy as np

from indicators import Indicators
from backtester import Backtester
from metrics import Metrics
from config import TradingConfig
from monte_carlo import MonteCarlo

RAW = 'data/raw/BTC_USDT_1h.csv'
df = pd.read_csv(RAW)
df['datetime'] = pd.to_datetime(df['datetime'])
for c in ['open','high','low','close','volume']:
    df[c] = df[c].astype(float)

def load(tf):
    o = df.set_index('datetime')['open'].resample(tf).first()
    h = df.set_index('datetime')['high'].resample(tf).max()
    l = df.set_index('datetime')['low'].resample(tf).min()
    c = df.set_index('datetime')['close'].resample(tf).last()
    v = df.set_index('datetime')['volume'].resample(tf).sum()
    d = pd.DataFrame({'open':o,'high':h,'low':l,'close':c,'volume':v}).dropna().reset_index()
    return Indicators().add_all(d)

def signal(d2, fast, slow):
    ef = d2['close'].ewm(span=fast).mean()
    es = d2['close'].ewm(span=slow).mean()
    sig = pd.Series(0, index=d2.index)
    sig[ef > es] = 1
    sig[ef <= es] = -1
    return sig

def run(d2, sig, fee=0.001, slip=0.0005, atr_sl=20.0, rr=100.0, cd=5, trail=0.0):
    d2s = d2.copy(); d2s['signal'] = sig.values
    cfg = TradingConfig(atr_sl_multiplier=atr_sl, rr_ratio=rr, min_bars_between_trades=cd,
                        trail_atr_multiplier=trail, fee=fee, slippage=slip)
    res = Backtester(cfg).run(d2s)
    return res, Metrics().calculate(res['trades'], res['equity_curve'])

d2 = load('1D')
print("=== Ajuste WR (1D) ===")
for fast in [15, 20, 25]:
    for slow in [40, 50, 60]:
        sig = signal(d2, fast, slow)
        res, m = run(d2, sig)
        if m['profit_factor'] >= 1.3 and m['win_rate'] >= 45 and m['max_drawdown'] > -15:
            print(f"WIN ema{fast}/{slow}: PF {m['profit_factor']:.2f} WR {m['win_rate']:.0f}% DD {m['max_drawdown']:.1f}% N {m['total_trades']}")
print("=== Walk-forward 1D ema20/50 ===")
sig = signal(d2, 20, 50)
n = len(d2)
fold = n // 6
for k in range(6):
    s, e = k*fold, (k+1)*fold if k < 5 else n
    # train = prev, test = this fold (purged simple)
    if k == 0:
        continue
    tr_s, tr_e = 0, s
    res_t, m_t = run(d2.iloc[tr_s:tr_e], signal(d2.iloc[tr_s:tr_e],20,50))
    res_v, m_v = run(d2.iloc[s:e], sig.iloc[s:e])
    print(f"Fold {k+1}: train PF {m_t['profit_factor']:.2f} | test PF {m_v['profit_factor']:.2f} WR {m_v['win_rate']:.0f}% N {m_v['total_trades']}")

print("=== Monte Carlo 1D ema20/50 ===")
res, m = run(d2, sig)
mc = MonteCarlo(iterations=5000)
mcr = mc.run(res['trades'], initial_capital=100.0)
print(f"ruin(10%): {mcr.ruin_probability if hasattr(mcr,'ruin_probability') else 'n/a'}")
print(f"final median: {mcr.median_final if hasattr(mcr,'median_final') else 'n/a'}")
try:
    mc.print_report(mcr, 100.0)
except Exception as e:
    print('report err', e)
