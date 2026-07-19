"""Exp G: ride-the-trend custom backtest (long solo, cierra en cruce opuesto).
Valida si seguir la tendencia captura el +1583% de BTC."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd

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
d = pd.DataFrame({'open':o,'high':h,'low':l,'close':c,'volume':v}).dropna().reset_index()
d['ema_fast'] = d['close'].ewm(span=20).mean()
d['ema_slow'] = d['close'].ewm(span=50).mean()
d['sma200'] = d['close'].rolling(200).mean()

FEE = 0.001; SLIP = 0.0005

def ride_long(use_sma_filter):
    cap = 100.0
    pos = 0.0; entry = 0.0
    trades = []
    for i in range(1, len(d)):
        price = d['close'].iloc[i]
        uptrend = d['ema_fast'].iloc[i] > d['ema_slow'].iloc[i]
        if use_sma_filter:
            uptrend = uptrend and (d['close'].iloc[i] > d['sma200'].iloc[i])
        # entrar
        if pos == 0 and uptrend and i > 200:
            entry = price * (1 + SLIP)
            pos = (cap * 0.95) / entry
            cap -= pos * entry * FEE
        # salir
        elif pos > 0 and not uptrend:
            exit_p = price * (1 - SLIP)
            cap += pos * exit_p
            cap -= pos * (entry + exit_p) * FEE
            trades.append((exit_p - entry) / entry)
            pos = 0.0
    # cerrar al final
    if pos > 0:
        exit_p = d['close'].iloc[-1] * (1 - SLIP)
        cap += pos * exit_p
        trades.append((exit_p - entry) / entry)
    ret = (cap / 100 - 1) * 100
    wr = sum(1 for t in trades if t > 0) / len(trades) * 100 if trades else 0
    return ret, wr, len(trades), cap

for flt in [False, True]:
    ret, wr, n, cap = ride_long(flt)
    print(f"Ride-trend SMAfilter={flt}: Ret {ret:+.1f}% WR {wr:.0f}% N {n} cap ${cap:.1f}")
