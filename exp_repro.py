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
o=df.set_index('datetime')['open'].resample('1D').first()
h=df.set_index('datetime')['high'].resample('1D').max()
l=df.set_index('datetime')['low'].resample('1D').min()
c=df.set_index('datetime')['close'].resample('1D').last()
v=df.set_index('datetime')['volume'].resample('1D').sum()
d2=Indicators().add_all(pd.DataFrame({'open':o,'high':h,'low':l,'close':c,'volume':v}).dropna().reset_index())
print('filas d2:', len(d2), 'index type:', type(d2.index))
ef=d2['close'].ewm(span=20).mean(); es=d2['close'].ewm(span=50).mean()
sig=pd.Series(0,index=d2.index); sig[ef>es]=1; sig[ef<=es]=-1
print('senal cambios (flips):', (sig.diff()!=0).sum())
d2s=d2.copy(); d2s['signal']=sig.values
cfg=TradingConfig(atr_sl_multiplier=20.0,rr_ratio=100.0,min_bars_between_trades=5)
res=Backtester(cfg).run(d2s); m=Metrics().calculate(res['trades'],res['equity_curve'])
print('ema20/50:', 'PF',round(m['profit_factor'],2),'WR',round(m['win_rate'],0),'N',m['total_trades'],'Ret',round(m['rentabilidad'],1))
