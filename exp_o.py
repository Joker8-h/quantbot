"""Exp O: mismo set de estrategias en ETH y SOL. Baseline buy&hold + ride-trend + breakout."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd

from indicators import Indicators
from backtester import Backtester
from metrics import Metrics
from config import TradingConfig

FILES = {'BTC':'data/raw/BTC_USDT_1h.csv','ETH':'data/raw/ETH_USDT_1h.csv','SOL':'data/raw/SOL_USDT_1h.csv'}

def load_raw(path):
    df = pd.read_csv(path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    for c in ['open','high','low','close','volume']:
        df[c] = df[c].astype(float)
    return df

def to_tf(df, tf):
    o=df.set_index('datetime')['open'].resample(tf).first()
    h=df.set_index('datetime')['high'].resample(tf).max()
    l=df.set_index('datetime')['low'].resample(tf).min()
    c=df.set_index('datetime')['close'].resample(tf).last()
    v=df.set_index('datetime')['volume'].resample(tf).sum()
    d=pd.DataFrame({'open':o,'high':h,'low':l,'close':c,'volume':v}).dropna().reset_index()
    return Indicators().add_all(d)

def run(d2, sig, atr_sl=4.0, rr=2.5, cd=1, fee=0.001, slip=0.0005):
    d2s=d2.copy(); d2s['signal']=sig.values
    cfg=TradingConfig(atr_sl_multiplier=atr_sl, rr_ratio=rr, min_bars_between_trades=cd, fee=fee, slippage=slip)
    res=Backtester(cfg).run(d2s); return Metrics().calculate(res['trades'],res['equity_curve'])

for sym, path in FILES.items():
    raw = load_raw(path)
    # buy&hold 1d
    d1 = to_tf(raw,'1D')
    bh = (d1['close'].iloc[-1]/d1['close'].iloc[0]-1)*100
    print(f"\n########## {sym}  (buy&hold 1d: {bh:+.0f}%) ##########")
    for tf in ['1D','4h','1h']:
        d2 = to_tf(raw, tf)
        # breakout
        s1=pd.Series(0,index=d2.index)
        s1[(d2['ema_fast']>d2['ema_slow'])&(d2['rsi']>50)&(d2['close']>d2['high'].shift(1))&(d2['volume']>d2['vol_avg'])]=1
        # ride-trend long-only
        ef=d2['close'].ewm(span=20).mean(); es=d2['close'].ewm(span=50).mean()
        s2=pd.Series(0,index=d2.index); s2[ef>es]=1
        # buy-the-dip
        sma=d2['close'].rolling(50).mean()
        s3=pd.Series(0,index=d2.index); s3[d2['close']<sma]=1
        for nm,sig in [('breakout',s1),('ride',s2),('dip',s3)]:
            m=run(d2,sig)
            if m['total_trades']>=20:
                mark = 'OK' if m['profit_factor']>1.3 else '  '
                print(f"  [{mark}] {tf:3} {nm:8} PF {m['profit_factor']:.2f} WR {m['win_rate']:.0f}% Ret {m['rentabilidad']:+.1f}% DD {m['max_drawdown']:.1f}% N {m['total_trades']}")
