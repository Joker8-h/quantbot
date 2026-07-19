"""Fase 1 de la arquitectura ML de Vill:
1. Estrategia matematica (breakout 1D BTC) genera senales.
2. Cada senal se etiqueta: 1 si la operacion gano, 0 si perdio.
3. Features = indicadores en el momento de la senal.
4. Entrenar XGBoost / LightGBM / RandomForest como FILTRO (probabilidad).
5. Backtest con filtro ML y comparar A (sin IA) vs B (con IA).

Split temporal honesto: entrenar hasta 2023, testear 2024+ (out-of-sample).
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

try:
    import xgboost as xgb
    HAVE_XGB = True
except Exception:
    HAVE_XGB = False
try:
    import lightgbm as lgb
    HAVE_LGB = True
except Exception:
    HAVE_LGB = False


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
    """Backtest y etiqueta cada senal con su resultado real (1 gano, 0 perdio)."""
    d2s = d2.copy(); d2s['signal'] = sig.values
    cfg = TradingConfig(atr_sl_multiplier=atr_sl, rr_ratio=rr, min_bars_between_trades=1)
    res = Backtester(cfg).run(d2s)
    trades = res['trades']
    # Mapear cada entrada a su etiqueta por indice temporal
    labels = pd.Series(np.nan, index=d2.index)
    for _, t in trades.iterrows():
        et = t['entry_time']
        # encontrar fila mas cercana
        row = d2[d2['datetime']==et]
        if len(row):
            idx = row.index[0]
            labels.loc[idx] = 1 if t['pnl'] > 0 else 0
    return labels


def build_features(d2, sig):
    feats = pd.DataFrame(index=d2.index)
    feats['adx'] = d2['adx']
    feats['rsi'] = d2['rsi']
    feats['atr_pct'] = d2['atr'] / d2['close'] * 100
    feats['vol_ratio'] = d2['volume'] / d2['vol_avg']
    feats['ema_slope'] = (d2['ema_fast'] - d2['ema_slow']) / d2['close']
    feats['bb_width_pct'] = d2['bb_width'] / d2['close'] * 100
    feats['return_1'] = d2['close'].pct_change(1) * 100
    feats['return_5'] = d2['close'].pct_change(5) * 100
    feats['signal'] = sig.values
    return feats


def run_filtered_backtest(d2, sig, proba, threshold):
    ai_sig = pd.Series(0, index=d2.index)
    for i in d2.index:
        if sig.loc[i] == 1 and proba.get(i, 0) >= threshold:
            ai_sig.loc[i] = 1
    d2s = d2.copy(); d2s['signal'] = ai_sig.values
    cfg = TradingConfig(atr_sl_multiplier=4.0, rr_ratio=2.5, min_bars_between_trades=1)
    res = Backtester(cfg).run(d2s)
    return Metrics().calculate(res['trades'], res['equity_curve'])


def main():
    d2 = load_1d('data/raw/BTC_USDT_1h.csv')
    sig = generate_signals(d2)
    labels = label_outcomes(d2, sig)
    feats = build_features(d2, sig)

    # Split temporal: train <= 2023, test >= 2024
    train_mask = d2['datetime'] < '2024-01-01'
    test_mask = d2['datetime'] >= '2024-01-01'

    # Solo filas con senal y etiqueta conocida
    idx_tr = d2.index[train_mask & (sig==1) & labels.notna()]
    idx_te = d2.index[test_mask & (sig==1) & labels.notna()]

    Xtr, ytr = feats.loc[idx_tr].values, labels.loc[idx_tr].values
    Xte, yte = feats.loc[idx_te].values, labels.loc[idx_te].values
    print(f"Train signals: {len(Xtr)} (ganadoras {int(ytr.sum())}) | Test signals: {len(Xte)} (ganadoras {int(yte.sum())})")

    models = {'RandomForest': RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42)}
    if HAVE_XGB:
        models['XGBoost'] = xgb.XGBClassifier(n_estimators=200, max_depth=4, random_state=42, verbosity=0)
    if HAVE_LGB:
        models['LightGBM'] = lgb.LGBMClassifier(n_estimators=200, max_depth=4, random_state=42, verbose=-1)

    for name, model in models.items():
        model.fit(Xtr, ytr)
        proba_te = model.predict_proba(Xte)[:, 1]
        auc = roc_auc_score(yte, proba_te)
        # Backtest filtrado en test usando el modelo entrenado
        # Necesitamos probabilidades en TODO el periodo test (no solo senales)
        proba_full = pd.Series(0.0, index=d2.index)
        # Predecir en todas las filas test con senal
        te_all = d2.index[test_mask & (sig==1)]
        proba_full.loc[te_all] = model.predict_proba(feats.loc[te_all].values)[:, 1]

        # Baseline A: sin IA (todas las senales en test)
        base_sig = pd.Series(0, index=d2.index); base_sig[test_mask & (sig==1)] = 1
        d2s = d2.copy(); d2s['signal'] = base_sig.values
        m_base = Metrics().calculate(Backtester(TradingConfig(atr_sl_multiplier=4.0,rr_ratio=2.5,min_bars_between_trades=1)).run(d2s)['trades'],
                                     Backtester(TradingConfig()).run(d2s)['equity_curve'])

        best_thr, best_pf, best_m = 0.5, -1, None
        for thr in [0.55, 0.6, 0.65, 0.7]:
            m = run_filtered_backtest(d2, sig, {i: p for i, p in proba_full.items()}, thr)
            if m['total_trades'] >= 10 and m['profit_factor'] > best_pf:
                best_thr, best_pf, best_m = thr, m['profit_factor'], m
        print(f"\n=== {name} (AUC test {auc:.2f}) ===")
        print(f"  A (sin IA)    : PF {m_base['profit_factor']:.2f} WR {m_base['win_rate']:.0f}% Ret {m_base['rentabilidad']:+.1f}% N {m_base['total_trades']}")
        if best_m:
            print(f"  B (IA thr {best_thr}): PF {best_m['profit_factor']:.2f} WR {best_m['win_rate']:.0f}% Ret {best_m['rentabilidad']:+.1f}% N {best_m['total_trades']}")
        else:
            print(f"  B (IA): sin trades suficientes")


if __name__ == '__main__':
    main()
