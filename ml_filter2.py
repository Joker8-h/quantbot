"""Fase 1b: ML con features ENRIQUECIDOS (contexto de la operacion, como pidio Vill).
Incluye: distancia al SL, fuerza del movimiento, distancia a soporte/resistencia.
Compara 3 modelos. Si AUC < 0.55 -> no hay edge detectable -> eliminar IA.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import numpy as np

from indicators import Indicators
from backtester import Backtester
from metrics import Metrics
from config import TradingConfig
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
import xgboost as xgb
import lightgbm as lgb

def load_1d(path):
    df = pd.read_csv(path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    for c in ['open','high','low','close','volume']: df[c]=df[c].astype(float)
    o=df.set_index('datetime')['open'].resample('1D').first()
    h=df.set_index('datetime')['high'].resample('1D').max()
    l=df.set_index('datetime')['low'].resample('1D').min()
    c=df.set_index('datetime')['close'].resample('1D').last()
    v=df.set_index('datetime')['volume'].resample('1D').sum()
    return Indicators().add_all(pd.DataFrame({'open':o,'high':h,'low':l,'close':c,'volume':v}).dropna().reset_index())

def generate_signals(d2):
    sig = pd.Series(0, index=d2.index)
    sig[(d2['ema_fast']>d2['ema_slow'])&(d2['rsi']>50)&(d2['close']>d2['high'].shift(1))&(d2['volume']>d2['vol_avg'])] = 1
    return sig

def label_outcomes(d2, sig, atr_sl=4.0, rr=2.5):
    d2s = d2.copy(); d2s['signal'] = sig.values
    cfg = TradingConfig(atr_sl_multiplier=atr_sl, rr_ratio=rr, min_bars_between_trades=1)
    trades = Backtester(cfg).run(d2s)['trades']
    labels = pd.Series(np.nan, index=d2.index)
    for _, t in trades.iterrows():
        row = d2[d2['datetime']==t['entry_time']]
        if len(row):
            labels.loc[row.index[0]] = 1 if t['pnl'] > 0 else 0
    return labels

def build_features(d2, sig, atr_sl=4.0):
    feats = pd.DataFrame(index=d2.index)
    atr = d2['atr']
    sl_dist = atr_sl * atr
    feats['adx'] = d2['adx']
    feats['rsi'] = d2['rsi']
    feats['atr_pct'] = atr / d2['close'] * 100
    feats['vol_ratio'] = d2['volume'] / d2['vol_avg']
    feats['ema_slope'] = (d2['ema_fast'] - d2['ema_slow']) / d2['close']
    feats['bb_width_pct'] = d2['bb_width'] / d2['close'] * 100
    # Contexto de la operacion (lo que pidio Vill)
    feats['dist_to_support_pct'] = (d2['close'] - d2['low'].rolling(20).min()) / d2['close'] * 100
    feats['dist_to_resist_pct'] = (d2['high'].rolling(20).max() - d2['close']) / d2['close'] * 100
    feats['move_strength'] = (d2['close'] - d2['close'].shift(1)) / atr  # velas de ATR de fuerza
    feats['dist_to_sl_pct'] = sl_dist / d2['close'] * 100  # distancia al stop loss
    feats['return_5'] = d2['close'].pct_change(5) * 100
    feats['return_20'] = d2['close'].pct_change(20) * 100
    feats['signal'] = sig.values
    return feats

def run_filtered(d2, sig, proba, thr):
    ai = pd.Series(0, index=d2.index)
    for i in d2.index:
        if sig.loc[i]==1 and proba.get(i,0) >= thr:
            ai.loc[i]=1
    d2s=d2.copy(); d2s['signal']=ai.values
    cfg=TradingConfig(atr_sl_multiplier=4.0,rr_ratio=2.5,min_bars_between_trades=1)
    res=Backtester(cfg).run(d2s); return Metrics().calculate(res['trades'],res['equity_curve'])

def main():
    d2 = load_1d('data/raw/BTC_USDT_1h.csv')
    sig = generate_signals(d2)
    labels = label_outcomes(d2, sig)
    feats = build_features(d2, sig)
    tr = d2['datetime'] < '2024-01-01'; te = d2['datetime'] >= '2024-01-01'
    idx_tr = d2.index[tr & (sig==1) & labels.notna()]
    idx_te = d2.index[te & (sig==1) & labels.notna()]
    Xtr,ytr = feats.loc[idx_tr].values, labels.loc[idx_tr].values
    Xte,yte = feats.loc[idx_te].values, labels.loc[idx_te].values
    print(f"Train {len(Xtr)} (win {int(ytr.sum())}) | Test {len(Xte)} (win {int(yte.sum())})")

    models = {
        'RandomForest': RandomForestClassifier(n_estimators=300, max_depth=5, random_state=42),
        'XGBoost': xgb.XGBClassifier(n_estimators=300, max_depth=3, random_state=42, verbosity=0),
        'LightGBM': lgb.LGBMClassifier(n_estimators=300, max_depth=3, random_state=42, verbose=-1),
    }
    for name, model in models.items():
        model.fit(Xtr,ytr)
        auc = roc_auc_score(yte, model.predict_proba(Xte)[:,1])
        te_all = d2.index[te & (sig==1)]
        proba_full = pd.Series(0.0, index=d2.index)
        proba_full.loc[te_all] = model.predict_proba(feats.loc[te_all].values)[:,1]
        # baseline A
        base = pd.Series(0, index=d2.index); base[te & (sig==1)] = 1
        d2s=d2.copy(); d2s['signal']=base.values
        cfgA=TradingConfig(atr_sl_multiplier=4.0,rr_ratio=2.5,min_bars_between_trades=1)
        m_base=Metrics().calculate(Backtester(cfgA).run(d2s)['trades'], Backtester(cfgA).run(d2s)['equity_curve'])
        best=(0.5,-1,None)
        for thr in [0.55,0.6,0.65,0.7]:
            m=run_filtered(d2,sig,{i:p for i,p in proba_full.items()},thr)
            if m['total_trades']>=10 and m['profit_factor']>best[1]:
                best=(thr,m['profit_factor'],m)
        print(f"\n=== {name} (AUC {auc:.2f}) ===")
        print(f"  A sin IA : PF {m_base['profit_factor']:.2f} WR {m_base['win_rate']:.0f}% Ret {m_base['rentabilidad']:+.1f}% N {m_base['total_trades']}")
        if best[2]:
            print(f"  B con IA : PF {best[2]['profit_factor']:.2f} WR {best[2]['win_rate']:.0f}% Ret {best[2]['rentabilidad']:+.1f}% N {best[2]['total_trades']} (thr {best[0]})")

if __name__=='__main__':
    main()
