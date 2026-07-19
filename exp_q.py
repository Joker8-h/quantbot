"""Exp Q: seguimiento de tendencia FILTRADO (tu formula): ADX alto + volumen + RR1:2.
Solo operar en tendencia confirmada. Long-only. 3 pares, 1D y 4h.
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
        ef=d2['close'].ewm(span=20).mean(); es=d2['close'].ewm(span=50).mean()
        trend_up = ef > es
        adx_ok = d2['adx'] > 25
        vol_ok = d2['volume'] > d2['vol_avg']
        sig=pd.Series(0,index=d2.index)
        # entrar long solo si tendencia + ADX + volumen; salir si no
        sig[trend_up & adx_ok & vol_ok] = 1
        for atr_sl in [3.0,4.0,5.0]:
            for rr in [2.0,2.5,3.0]:
                m=run(d2,sig,atr_sl,rr,1)
                if m['total_trades']>=20:
                    mark='OK' if m['profit_factor']>1.3 else '  '
                    print(f"  [{mark}] {tf} sl{atr_sl} rr{rr}: PF {m['profit_factor']:.2f} WR {m['win_rate']:.0f}% Ret {m['rentabilidad']:+.1f}% DD {m['max_drawdown']:.1f}% N {m['total_trades']}")
