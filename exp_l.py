"""Exp L: ride-trend LONG-ONLY corregido. Varias EMA en 1D y 4h.
SL real para proteccion, cierra y queda plano en tendencia bajar.
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
    return sig  # 0 = plano

def run(d2, sig, atr_sl, rr, cd, fee=0.001, slip=0.0005):
    d2s = d2.copy(); d2s['signal'] = sig.values
    cfg = TradingConfig(atr_sl_multiplier=atr_sl, rr_ratio=rr, min_bars_between_trades=cd, fee=fee, slippage=slip)
    res = Backtester(cfg).run(d2s)
    return res, Metrics().calculate(res['trades'], res['equity_curve'])

results = []
for tf in ['1D', '4h']:
    d2 = load(tf)
    for fast in [10, 20, 25]:
        for slow in [40, 50, 100]:
            sig = signal(d2, fast, slow)
            for atr_sl in [3.0, 5.0, 8.0]:
                for rr in [2.0, 3.0]:
                    res, m = run(d2, sig, atr_sl, rr, 1)
                    if m['total_trades'] >= 20 and m['profit_factor'] > 1.0:
                        results.append((m['profit_factor'], tf, f'{fast}/{slow}', atr_sl, rr,
                                        m['win_rate'], m['rentabilidad'], m['max_drawdown'], m['total_trades']))
results.sort(reverse=True)
print('TOP 20 (LONG-ONLY ride-trend):')
for r in results[:20]:
    print(f"PF {r[0]:.2f} {r[1]} ema{r[2]} sl{r[3]} rr{r[4]} WR {r[5]:.0f} Ret {r[6]:+.1f}% DD {r[7]:.1f}% N {r[8]}")
print(f"\nConfigs rentables: {len(results)}")
