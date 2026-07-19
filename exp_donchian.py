"""Exp B: Donchian breakout + long-only + varios lookbacks en 1d/4h/1h.
La hipotesis: BTC tiene drift alcista; breakout de canal largo captura tendencias.
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
for tf in ['1D', '4h', '1h']:
    d2 = load(tf)
    for lb in [10, 20, 40, 60]:
        hh = d2['high'].rolling(lb).max().shift(1)
        ll = d2['low'].rolling(lb).min().shift(1)
        # breakout ambos lados
        sig2 = pd.Series(0, index=d2.index)
        sig2[(d2['close'] > hh)] = 1
        sig2[(d2['close'] < ll)] = -1
        # solo long
        sig1 = pd.Series(0, index=d2.index)
        sig1[(d2['close'] > hh)] = 1
        for label, sig in [('both', sig2), ('long', sig1)]:
            for atr_sl in [3.0, 4.0]:
                for rr in [2.0, 2.5, 3.0]:
                    m = run(d2, sig, atr_sl, rr, int(lb/2)+1 if tf!='1D' else int(lb*0.5))
                    if m['total_trades'] >= 30:
                        results.append((m['profit_factor'], tf, f'lb{lb}', label, atr_sl, rr,
                                        m['win_rate'], m['rentabilidad'], m['max_drawdown'], m['total_trades']))

results.sort(reverse=True)
print('TOP 20 (Donchian):')
for r in results[:20]:
    print(f"PF {r[0]:.2f} {r[1]} {r[2]} {r[3]} sl{r[4]} rr{r[5]} WR {r[6]:.0f} Ret {r[7]:+.1f}% DD {r[8]:.1f}% N {r[9]}")
print(f"\nTotal viables: {len(results)}")
