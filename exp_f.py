"""Exp F: trend-filter 200-SMA long-only en 1d, sin TP (ride), trailing sale.
Deberia capturar tendencia alcista de BTC sin los small losses constantes.
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
o = df.set_index('datetime')['open'].resample('1D').first()
h = df.set_index('datetime')['high'].resample('1D').max()
l = df.set_index('datetime')['low'].resample('1D').min()
c = df.set_index('datetime')['close'].resample('1D').last()
v = df.set_index('datetime')['volume'].resample('1D').sum()
d1 = pd.DataFrame({'open':o,'high':h,'low':l,'close':c,'volume':v}).dropna().reset_index()
d2 = Indicators().add_all(d1)
d2['sma200'] = d2['close'].rolling(200).mean()

# Senal: 1 cuando close > sma200, 0 cuando cruza abajo (solo long)
sig = pd.Series(0, index=d2.index)
in_market = d2['close'] > d2['sma200']
sig[in_market] = 1
# Para que el backtester SALGA, necesitamos senal -1 o 0; usamos -1 para short-close pero mejor:
# El backtester no cierra en 0 automaticamente. Usamos -1 para forzar cierre (short dummy).
# Mejor: serial de 1 mientras en tendencia, y cuando sale ponemos -1 (no operamos short).
sig = sig.where(in_market, -1)

for trail in [0.0, 2.0, 4.0]:
    d2s = d2.copy(); d2s['signal'] = sig.values
    cfg = TradingConfig(atr_sl_multiplier=20.0, rr_ratio=100.0, min_bars_between_trades=5,
                        trail_atr_multiplier=trail)
    res = Backtester(cfg).run(d2s)
    m = Metrics().calculate(res['trades'], res['equity_curve'])
    print(f"Trail {trail}: PF {m['profit_factor']:.2f} WR {m['win_rate']:.0f} Ret {m['rentabilidad']:+.1f}% DD {m['max_drawdown']:.1f}% N {m['total_trades']}")
