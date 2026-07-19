"""Exp C: Bollinger reversion + RR alto en 4h/1h/1d.
Hipotesis: BTC revierte a la media; comprar cuando precio toca banda inferior en tendencia alcista.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd

from indicators import Indicators
from backtester import Backtester
from metrics import Metrics
from config import TradingConfig

RAW = 'data/raw/BTC_USDT_1h.csv'

def load(tf):
    df = pd.read_csv(RAW)
    df['datetime'] = pd.to_datetime(df['datetime'])
    for c in ['open', 'high', 'low', 'close', 'volume']:
        df[c] = df[c].astype(float)
    o = df.set_index('datetime')['open'].resample(tf).first()
    h = df.set_index('datetime')['high'].resample(tf).max()
    l = df.set_index('datetime')['low'].resample(tf).min()
    c = df.set_index('datetime')['close'].resample(tf).last()
    v = df.set_index('datetime')['volume'].resample(tf).sum()
    d = pd.DataFrame({'open': o, 'high': h, 'low': l, 'close': c, 'volume': v}).dropna().reset_index()
    return Indicators().add_all(d)

def run(d2, sig, atr_sl, rr, cd):
    d2s = d2.copy()
    d2s['signal'] = sig.values
    cfg = TradingConfig(atr_sl_multiplier=atr_sl, rr_ratio=rr, min_bars_between_trades=cd)
    bt = Backtester(cfg)
    res = bt.run(d2s)
    return Metrics().calculate(res['trades'], res['equity_curve'])

results = []
for tf in ['4h', '1h', '1D']:
    d2 = load(tf)
    for bb in [1.5, 2.0, 2.5]:
        lower = d2['bb_middle'] - bb * d2['bb_width'] / 2
        upper = d2['bb_middle'] + bb * d2['bb_width'] / 2
        sig = pd.Series(0, index=d2.index)
        # reversion: tocar banda inferior -> long; tocar superior -> short
        sig[(d2['close'] <= lower) & (d2['close'] > d2['open'])] = 1
        sig[(d2['close'] >= upper) & (d2['close'] < d2['open'])] = -1
        for atr_sl in [2.0, 3.0]:
            for rr in [2.0, 3.0, 4.0]:
                m = run(d2, sig, atr_sl, rr, 24)
                if m['total_trades'] >= 30:
                    results.append((m['profit_factor'], tf, f'bb{bb}', atr_sl, rr,
                                    m['win_rate'], m['rentabilidad'], m['max_drawdown'], m['total_trades']))

results.sort(reverse=True)
print('TOP 15 (Bollinger reversion):')
for r in results[:15]:
    print(f"PF {r[0]:.2f} {r[1]} {r[2]} sl{r[3]} rr{r[4]} WR {r[5]:.0f} Ret {r[6]:+.1f}% DD {r[7]:.1f}% N {r[8]}")
print(f"\nTotal viables: {len(results)}")
