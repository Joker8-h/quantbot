"""Exp N: buy-the-dip (precio < SMA lenta -> long, > SMA -> plano) en 1D/4h/1h."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd

from indicators import Indicators
from backtester import Backtester
from metrics import Metrics
from config import TradingConfig

RAW='data/raw/BTC_USDT_1h.csv'
df=pd.read_csv(RAW); df['datetime']=pd.to_datetime(df['datetime'])
for c in ['open','high','low','close','volume']: df[c]=df[c].astype(float)

def load(tf):
    o=df.set_index('datetime')['open'].resample(tf).first()
    h=df.set_index('datetime')['high'].resample(tf).max()
    l=df.set_index('datetime')['low'].resample(tf).min()
    c=df.set_index('datetime')['close'].resample(tf).last()
    v=df.set_index('datetime')['volume'].resample(tf).sum()
    d=pd.DataFrame({'open':o,'high':h,'low':l,'close':c,'volume':v}).dropna().reset_index()
    return Indicators().add_all(d)

def run(d2, sig, atr_sl, rr, cd):
    d2s=d2.copy(); d2s['signal']=sig.values
    cfg=TradingConfig(atr_sl_multiplier=atr_sl, rr_ratio=rr, min_bars_between_trades=cd)
    res=Backtester(cfg).run(d2s); return Metrics().calculate(res['trades'],res['equity_curve'])

for tf in ['1D','4h','1h']:
    d2=load(tf)
    for p in [20,50,100]:
        sma=d2['close'].rolling(p).mean()
        sig=pd.Series(0,index=d2.index)
        sig[d2['close'] < sma] = 1  # comprar la caida
        sig[d2['close'] > sma * 1.02] = 0  # vender cuando recupera 2%
        for atr_sl in [3.0,5.0]:
            for rr in [2.0,3.0]:
                m=run(d2,sig,atr_sl,rr,1)
                if m['total_trades']>=20:
                    print(f"{tf} SMA{p}: PF {m['profit_factor']:.2f} WR {m['win_rate']:.0f}% Ret {m['rentabilidad']:+.1f}% DD {m['max_drawdown']:.1f}% N {m['total_trades']}")
