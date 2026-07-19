"""Exp E: test del backtester con 1 sola posicion long sostenida (debe ~seguir buy&hold)."""
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
o = df.set_index('datetime')['open'].resample('1D').first()
h = df.set_index('datetime')['high'].resample('1D').max()
l = df.set_index('datetime')['low'].resample('1D').min()
c = df.set_index('datetime')['close'].resample('1D').last()
v = df.set_index('datetime')['volume'].resample('1D').sum()
d1 = pd.DataFrame({'open':o,'high':h,'low':l,'close':c,'volume':v}).dropna().reset_index()
d2 = Indicators().add_all(d1)

# Senal: long en dia 1, mantener
sig = pd.Series(0, index=d2.index)
sig.iloc[0] = 1   # entra dia 1
d2s = d2.copy(); d2s['signal'] = sig.values
cfg = TradingConfig(atr_sl_multiplier=50.0, rr_ratio=100.0, min_bars_between_trades=1, cooldown_hours=999999)
res = Backtester(cfg).run(d2s)
m = Metrics().calculate(res['trades'], res['equity_curve'])
print('1 sola posicion long (SL 50ATR):')
print(m)
