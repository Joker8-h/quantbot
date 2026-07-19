"""Exp R: IA como filtro de operaciones sobre 1D breakout BTC.
Valida fuera de muestra (2024-2026). La IA solo recibe features (NO retorno futuro).
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd

from indicators import Indicators
from backtester import Backtester
from metrics import Metrics
from config import TradingConfig
from ai_regime import AIRegimeClassifier

API=os.environ.get("OPENAI_API_KEY")
clf = AIRegimeClassifier(api_key=API)

# Cargar BTC 1h -> 1D
df = pd.read_csv('data/raw/BTC_USDT_1h.csv')
df['datetime'] = pd.to_datetime(df['datetime'])
for c in ['open','high','low','close','volume']: df[c]=df[c].astype(float)
o=df.set_index('datetime')['open'].resample('1D').first()
h=df.set_index('datetime')['high'].resample('1D').max()
l=df.set_index('datetime')['low'].resample('1D').min()
c=df.set_index('datetime')['close'].resample('1D').last()
v=df.set_index('datetime')['volume'].resample('1D').sum()
d2=Indicators().add_all(pd.DataFrame({'open':o,'high':h,'low':l,'close':c,'volume':v}).dropna().reset_index())

# Senal base breakout
base = pd.Series(0, index=d2.index)
base[(d2['ema_fast']>d2['ema_slow'])&(d2['rsi']>50)&(d2['close']>d2['high'].shift(1))&(d2['volume']>d2['vol_avg'])] = 1

# Solo validar fuera de muestra: desde 2024
mask = d2['datetime'] >= '2024-01-01'
idx = d2.index[mask]
print(f"Ventanas OOS: {len(idx)}")

# Senal filtrada por IA
ai_sig = pd.Series(0, index=d2.index)
for i in idx:
    if base.loc[i] != 1:
        continue
    feat = {
        'return_pct': (d2['close'].iloc[i] / d2['close'].iloc[i-1] - 1) * 100,
        'adx': float(d2['adx'].iloc[i]),
        'rsi': float(d2['rsi'].iloc[i]),
        'atr_pct': float(d2['atr'].iloc[i] / d2['close'].iloc[i] * 100),
        'vol_ratio': float(d2['volume'].iloc[i] / d2['vol_avg'].iloc[i]),
        'ema_slope': float(d2['ema_fast'].iloc[i] - d2['ema_slow'].iloc[i]) / d2['close'].iloc[i],
        'bb_width_pct': float(d2['bb_width'].iloc[i] / d2['close'].iloc[i] * 100),
    }
    _, conf, operar = clf.classify(feat)
    if operar:
        ai_sig.loc[i] = 1

def run(sig):
    d2s=d2.copy(); d2s['signal']=sig.values
    cfg=TradingConfig(atr_sl_multiplier=4.0, rr_ratio=2.5, min_bars_between_trades=1)
    res=Backtester(cfg).run(d2s); return Metrics().calculate(res['trades'],res['equity_curve'])

m_base = run(base)
m_ai = run(ai_sig)
print(f"\nBASE (todas las senales) OOS 2024+: PF {m_base['profit_factor']:.2f} WR {m_base['win_rate']:.0f}% Ret {m_base['rentabilidad']:+.1f}% N {m_base['total_trades']}")
print(f"FILTRADO IA OOS 2024+:       PF {m_ai['profit_factor']:.2f} WR {m_ai['win_rate']:.0f}% Ret {m_ai['rentabilidad']:+.1f}% N {m_ai['total_trades']}")
