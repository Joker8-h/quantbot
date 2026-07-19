"""Exp H: ride-the-trend via backtester real (cierra en senal opuesta).
Mide PF, WR, DD en 1d y 4h con varios EMA y filtro SMA200.
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

def run(d2, sig, atr_sl, rr, cd, trail):
    d2s = d2.copy(); d2s['signal'] = sig.values
    cfg = TradingConfig(atr_sl_multiplier=atr_sl, rr_ratio=rr, min_bars_between_trades=cd, trail_atr_multiplier=trail)
    res = Backtester(cfg).run(d2s)
    return Metrics().calculate(res['trades'], res['equity_curve'])

results = []
for tf in ['1D', '4h']:
    d2 = load(tf)
    d2['sma200'] = d2['close'].rolling(200).mean()
    for fast in [10, 20]:
        for slow in [50, 100]:
            ema_f = d2['close'].ewm(span=fast).mean()
            ema_s = d2['close'].ewm(span=slow).mean()
            for usef in [False, True]:
                sig = pd.Series(0, index=d2.index)
                up = ema_f > ema_s
                if usef:
                    up = up & (d2['close'] > d2['sma200'])
                sig[up] = 1
                sig[~up] = -1
                for trail in [0.0, 3.0]:
                    m = run(d2, sig, 20.0, 100.0, 5, trail)
                    if m['total_trades'] >= 20:
                        results.append((m['profit_factor'], tf, f'{fast}/{slow}', f'sma{usef}', f'tr{trail}',
                                        m['win_rate'], m['rentabilidad'], m['max_drawdown'], m['total_trades']))
results.sort(reverse=True)
print('TOP 15 (ride-trend):')
for r in results[:15]:
    print(f"PF {r[0]:.2f} {r[1]} ema{r[2]} {r[3]} {r[4]} WR {r[5]:.0f} Ret {r[6]:+.1f}% DD {r[7]:.1f}% N {r[8]}")
