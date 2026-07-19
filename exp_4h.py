"""Experimento: buscar la mejor config en 4h con grid enfocado."""
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

# Agregar a 4h
o = df.set_index('datetime')['open'].resample('4h').first()
h = df.set_index('datetime')['high'].resample('4h').max()
l = df.set_index('datetime')['low'].resample('4h').min()
c = df.set_index('datetime')['close'].resample('4h').last()
v = df.set_index('datetime')['volume'].resample('4h').sum()
d = pd.DataFrame({'open': o, 'high': h, 'low': l, 'close': c, 'volume': v}).dropna().reset_index()

ind = Indicators()
d2 = ind.add_all(d)

best = []
for vol_mult in [1.5, 2.0]:
    for atr_sl in [3.0, 4.0, 5.0]:
        for rr in [2.0, 2.5, 3.0]:
            for cd in [48, 96]:
                sig = pd.Series(0, index=d2.index)
                cond = (d2['ema_fast'] > d2['ema_slow']) & \
                       (d2['rsi'] > 50) & \
                       (d2['close'] > d2['high'].shift(1)) & \
                       (d2['volume'] > d2['vol_avg'] * vol_mult)
                sig[cond] = 1
                cond2 = (d2['ema_fast'] < d2['ema_slow']) & \
                        (d2['rsi'] < 30) & \
                        (d2['close'] < d2['low'].shift(1)) & \
                        (d2['volume'] > d2['vol_avg'] * 2.0)
                sig[cond2] = -1
                d2s = d2.copy()
                d2s['signal'] = sig.values

                cfg = TradingConfig(atr_sl_multiplier=atr_sl, rr_ratio=rr, min_bars_between_trades=cd)
                bt = Backtester(cfg)
                m = Metrics().calculate(bt.run(d2s)['trades'], bt.run(d2s)['equity_curve'])
                if m['total_trades'] >= 30:
                    best.append((m['profit_factor'], vol_mult, atr_sl, rr, cd,
                                 m['win_rate'], m['rentabilidad'], m['max_drawdown'], m['total_trades']))

best.sort(reverse=True)
print('TOP 10 (4h):')
for b in best[:10]:
    print('PF', round(b[0], 2), 'vol', b[1], 'sl', b[2], 'rr', b[3], 'cd', b[4],
          'WR', round(b[5], 0), 'Ret', round(b[6], 1), 'DD', round(b[7], 1), 'N', b[8])
