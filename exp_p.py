"""Exp P: reverion a la media SOLO en regimen lateral (ADX bajo) + breakout SOLO en tendencia.
Combina: lateral->comprar toque banda inferior; tendencia->ride. Filtrado por ADX/vol.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd

from indicators import Indicators
from backtester import Backtester
from metrics import Metrics
from config import TradingConfig

FILES = {'BTC':'data/raw/BTC_USDT_1h.csv','ETH':'data/raw/ETH_USDT_1h.csv','SOL':'data/raw/SOL_USDT_1h.csv'}

def load_raw(path):
    df=pd.read_csv(path); df['datetime']=pd.to_datetime(df['datetime'])
    for c in ['open','high','low','close','volume']: df[c]=df[c].astype(float)
    return df

def to_tf(df,tf):
    o=df.set_index('datetime')['open'].resample(tf).first()
    h=df.set_index('datetime')['high'].resample(tf).max()
    l=df.set_index('datetime')['low'].resample(tf).min()
    c=df.set_index('datetime')['close'].resample(tf).last()
    v=df.set_index('datetime')['volume'].resample(tf).sum()
    return Indicators().add_all(pd.DataFrame({'open':o,'high':h,'low':l,'close':c,'volume':v}).dropna().reset_index())

def run(d2,sig,atr_sl,rr,cd,fee=0.001,slip=0.0005):
    d2s=d2.copy(); d2s['signal']=sig.values
    cfg=TradingConfig(atr_sl_multiplier=atr_sl,rr_ratio=rr,min_bars_between_trades=cd,fee=fee,slippage=slip)
    res=Backtester(cfg).run(d2s); return Metrics().calculate(res['trades'],res['equity_curve'])

for sym,path in FILES.items():
    raw=load_raw(path)
    print(f"\n########## {sym} ##########")
    for tf in ['1D','4h']:
        d2=to_tf(raw,tf)
        adx=d2['adx']; lateral = adx < 20
        # reverion en lateral: tocar banda inferior
        lower = d2['bb_middle'] - 2*d2['bb_width']/2
        upper = d2['bb_middle'] + 2*d2['bb_width']/2
        sig=pd.Series(0,index=d2.index)
        sig[(lateral)&(d2['close']<=lower)&(d2['close']>d2['open'])] = 1
        sig[(~lateral)] = 0  # en tendencia queda plano
        m=run(d2,sig,3.0,2.0,1)
        print(f"  lateral-rev {tf}: PF {m['profit_factor']:.2f} WR {m['win_rate']:.0f}% Ret {m['rentabilidad']:+.1f}% DD {m['max_drawdown']:.1f}% N {m['total_trades']}")
