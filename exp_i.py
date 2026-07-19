"""Exp I: validacion de la mejor config ride-trend (walk-forward + escenarios + MC)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import numpy as np

from indicators import Indicators
from backtester import Backtester
from metrics import Metrics
from config import TradingConfig
from monte_carlo import MonteCarlo

RAW = 'data/raw/BTC_USDT_1h.csv'
df = pd.read_csv(RAW)
df['datetime'] = pd.to_datetime(df['datetime'])
for c in ['open','high','low','close','volume']:
    df[c] = df[c].astype(float)

def load(tf):
    o = df.set_index('datetime')['open'].resample(tf).first()
    h = df.set_index('datetime')['high'].resample(tf).max()
    l = df.set_index('datetime')['low'].resample(tf).min()
    c = df.set_index('datetime')['close'].resample(tf).last()
    v = df.set_index('datetime')['volume'].resample(tf).sum()
    d = pd.DataFrame({'open':o,'high':h,'low':l,'close':c,'volume':v}).dropna().reset_index()
    return Indicators().add_all(d)

def signal(d2, fast, slow):
    ef = d2['close'].ewm(span=fast).mean()
    es = d2['close'].ewm(span=slow).mean()
    sig = pd.Series(0, index=d2.index)
    sig[ef > es] = 1
    sig[ef <= es] = -1
    return sig

def run(d2, sig, fee, slip, atr_sl=20.0, rr=100.0, cd=5, trail=0.0):
    d2s = d2.copy(); d2s['signal'] = sig.values
    cfg = TradingConfig(atr_sl_multiplier=atr_sl, rr_ratio=rr, min_bars_between_trades=cd,
                        trail_atr_multiplier=trail, fee=fee, slippage=slip)
    res = Backtester(cfg).run(d2s)
    return res, Metrics().calculate(res['trades'], res['equity_curve'])

# Configs candidatas
cands = [
    ('1D ema20/50', '1D', 20, 50, 0.0),
    ('4h ema10/100', '4h', 10, 100, 0.0),
    ('4h ema20/100', '4h', 20, 100, 0.0),
]

for name, tf, fast, slow, trail in cands:
    d2 = load(tf)
    sig = signal(d2, fast, slow)
    res, m = run(d2, sig, 0.001, 0.0005)
    # Escenarios
    _, mo = run(d2, sig, 0.00075, 0.0003)
    _, mp = run(d2, sig, 0.0015, 0.001)
    # Monte Carlo
    mc = MonteCarlo()
    # Extraer PnL por trade
    if len(res['trades']) > 0:
        pnls = res['trades']['pnl'].tolist()
        try:
            mc_res = mc.simulate(pnls, initial_capital=100.0, iterations=5000)
            ruin = mc_res.get('ruin_prob', 'n/a')
        except Exception as e:
            ruin = f'err {e}'
    else:
        ruin = 'no trades'
    print(f"\n=== {name} ===")
    print(f"BASE: PF {m['profit_factor']:.2f} WR {m['win_rate']:.0f}% Ret {m['rentabilidad']:+.1f}% DD {m['max_drawdown']:.1f}% N {m['total_trades']}")
    print(f"OPT:  PF {mo['profit_factor']:.2f} Ret {mo['rentabilidad']:+.1f}%  PESS: PF {mp['profit_factor']:.2f} Ret {mp['rentabilidad']:+.1f}%")
    print(f"MC ruin(10%): {ruin}")
