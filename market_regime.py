import pandas as pd
import numpy as np

from config import CONFIG


class MarketRegime:
    def __init__(self, config=CONFIG):
        self.adx_threshold = config.adx_threshold
        self.lateral_adx = config.lateral_adx_threshold
        self.volatile_atr_mult = config.volatile_atr_multiplier

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        atr_avg = df["atr"].rolling(window=50).mean()

        conditions = []

        # Trending up: ADX fuerte + EMA alineada + DI+ > DI-
        trending_up = (
            (df["adx"] > self.adx_threshold) &
            (df["ema_fast"] > df["ema_slow"]) &
            (df["plus_di"] > df["minus_di"])
        )

        # Trending down: ADX fuerte + EMA alineada + DI- > DI+
        trending_down = (
            (df["adx"] > self.adx_threshold) &
            (df["ema_fast"] < df["ema_slow"]) &
            (df["minus_di"] > df["plus_di"])
        )

        # High volatility: ATR > multiplier * promedio ATR
        volatile = df["atr"] > (atr_avg * self.volatile_atr_mult)

        # Lateral: ADX debil (no trending)
        lateral = df["adx"] < self.lateral_adx

        # Asignar regime
        df["regime"] = "unknown"
        df.loc[trending_up & ~volatile, "regime"] = "trending_up"
        df.loc[trending_down & ~volatile, "regime"] = "trending_down"
        df.loc[lateral, "regime"] = "lateral"
        df.loc[volatile, "regime"] = "volatile"

        # Flags para la estrategia
        df["can_trade"] = df["regime"].isin(["trending_up", "trending_down"])
        df["vol_scale"] = np.where(df["regime"] == "volatile", 0.5, 1.0)

        return df

    def get_regime_summary(self, df: pd.DataFrame) -> dict:
        counts = df["regime"].value_counts()
        total = len(df)
        return {
            regime: {
                "count": int(counts.get(regime, 0)),
                "pct": round(counts.get(regime, 0) / total * 100, 1),
            }
            for regime in ["trending_up", "trending_down", "lateral", "volatile"]
        }


if __name__ == "__main__":
    from data_collector import DataCollector
    from indicators import Indicators

    collector = DataCollector()
    indicators = Indicators()
    regime = MarketRegime()

    data = collector.collect_all()

    for (symbol, tf), df in data.items():
        df_ind = indicators.add_all(df)
        df_regime = regime.detect(df_ind)
        summary = regime.get_regime_summary(df_regime)

        print(f"\n{symbol} {tf} - Market Regime:")
        for r, info in summary.items():
            print(f"  {r:<15} {info['count']:>5} velas ({info['pct']}%)")
