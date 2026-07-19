"""Exp A: filtro de regimen ADX + breakout en 1h/4h/1d.
Solo operar LONG cuando ADX>umbral (tendencia) y SHORT cuando tendencia bajista fuerte.
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
for tf in ['1h', '4h', '1D']:
    d2 = load(tf)
    for adx_min in [20, 25, 30]:
        sig = pd.Series(0, index=d2.index)
        trend_up = d2['adx'] > adx_min
        trend_dn = d2['adx'] > adx_min
        sig[(d2['ema_fast'] > d2['ema_slow']) & (d2['rsi'] > 50) &
            (d2['close'] > d2['high'].shift(1)) & (d2['volume'] > d2['vol_avg']) & trend_up] = 1
        sig[(d2['ema_fast'] < d2['ema_slow']) & (d2['rsi'] < 30) &
            (d2['close'] < d2['low'].shift(1)) & (d2['volume'] > d2['vol_avg'] * 2) & trend_dn] = -1
        for atr_sl in [3.0, 4.0]:
            for rr in [2.0, 2.5]:
                m = run(d2, sig, atr_sl, rr, 24)
                if m['total_trades'] >= 30:
                    results.append((m['profit_factor'], tf, adx_min, atr_sl, rr,
                                    m['win_rate'], m['rentabilidad'], m['max_drawdown'], m['total_trades']))

results.sort(reverse=True)
print('TOP 15 (ADX filter):')
for r in results[:15]:
    print(f"PF {r[0]:.2f} {r[1]} adx>{r[2]} sl{r[3]} rr{r[4]} WR {r[5]:.0f} Ret {r[6]:+.1f}% DD {r[7]:.1f}% N {r[8]}")
print(f"\nTotal configs viables: {len(results)}")
