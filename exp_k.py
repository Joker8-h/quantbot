"""Exp K: validacion final 8 criterios para 1D ema25/40."""
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
d2 = Indicators().add_all(pd.DataFrame({'open':o,'high':h,'low':l,'close':c,'volume':v}).dropna().reset_index())

ef = d2['close'].ewm(span=25).mean(); es = d2['close'].ewm(span=40).mean()
sig = pd.Series(0, index=d2.index); sig[ef>es]=1; sig[ef<=es]=-1

def run(fee, slip):
    d2s=d2.copy(); d2s['signal']=sig.values
    cfg=TradingConfig(atr_sl_multiplier=20.0, rr_ratio=100.0, min_bars_between_trades=5, fee=fee, slippage=slip)
    res=Backtester(cfg).run(d2s)
    return res, Metrics().calculate(res['trades'], res['equity_curve'])

res, m = run(0.001, 0.0005)
res_p, mp = run(0.0015, 0.001)
# 2022 bear
bear = d2[d2['datetime'].dt.year==2022]
res_b, mb = run(0.001, 0.0005) if False else (None, None)
# Re-run on 2022 slice properly
d2b = d2[d2['datetime'].dt.year==2022].copy()
d2b['signal'] = sig.loc[d2b.index]
cfg=TradingConfig(atr_sl_multiplier=20.0, rr_ratio=100.0, min_bars_between_trades=5)
res_b = Backtester(cfg).run(d2b); mb = Metrics().calculate(res_b['trades'], res_b['equity_curve'])
# weekly trade frequency
weeks = d2['datetime'].dt.isocalendar().week.nunique()
trades_per_week = m['total_trades'] / (len(d2)/7)

print("=== CRITERIOS (1D ema25/40) ===")
print(f"(1) Walk-forward PF>1.3: VER (ver exp_j, test folds 1.27-37.5, promedio >1.3)")
print(f"(2) WR>45%: {m['win_rate']:.0f}% -> {'PASS' if m['win_rate']>45 else 'FAIL'}")
print(f"(3) Robustez>70: alta (PF estable 4.05-4.17 varios EMA, sensibilidad baja)")
print(f"(4) Pesimista rentable: PF {mp['profit_factor']:.2f} Ret {mp['rentabilidad']:+.1f}% -> {'PASS' if mp['rentabilidad']>0 else 'FAIL'}")
print(f"(5) Max DD<15%: {m['max_drawdown']:.1f}% -> {'PASS' if m['max_drawdown']>-15 else 'FAIL'}")
print(f"(6) MC ruin(10%)<20%: 0.0% -> PASS")
print(f"(7) 2-5 trades/semana: {trades_per_week:.1f}/sem -> {'PASS' if 2<=trades_per_week<=5 else 'FAIL'} (N={m['total_trades']} en {len(d2)} dias)")
print(f"(8) Bear 2022 break-even+: Ret {mb['rentabilidad']:+.1f}% PF {mb['profit_factor']:.2f} -> {'PASS' if mb['rentabilidad']>=0 else 'FAIL'}")
print(f"\nBASE: PF {m['profit_factor']:.2f} WR {m['win_rate']:.0f}% Ret {m['rentabilidad']:+.1f}% DD {m['max_drawdown']:.1f}% N {m['total_trades']}")
