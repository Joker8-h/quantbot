import pandas as pd
import numpy as np

from config import CONFIG


class Strategy:
    def __init__(self, config=CONFIG):
        self.rsi_threshold = config.rsi_threshold

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Volume filter
        cond_volume = df["volume"] > df["vol_avg"]

        # === LONG: identico al original ===
        cond_long = (
            (df["ema_fast"] > df["ema_slow"]) &
            (df["rsi"] > self.rsi_threshold) &
            (df["close"] > df["high"].shift(1)) &
            cond_volume
        )

        # === SHORT: estricto (original) ===
        cond_short = (
            (df["ema_fast"] < df["ema_slow"]) &
            (df["rsi"] < 30) &
            (df["close"] < df["low"].shift(1)) &
            (df["volume"] > df["vol_avg"] * 2.0)
        )

        df["signal"] = 0
        df.loc[cond_long, "signal"] = 1
        df.loc[cond_short, "signal"] = -1

        signal_changed = df["signal"] != df["signal"].shift(1)
        df["signal"] = df["signal"].where(signal_changed, 0)

        return df

    def get_signal_summary(self, df: pd.DataFrame) -> dict:
        total_long = (df["signal"] == 1).sum()
        total_short = (df["signal"] == -1).sum()
        total = total_long + total_short
        return {
            "total_signals": int(total),
            "long_signals": int(total_long),
            "short_signals": int(total_short),
            "signal_pct": round(total / len(df) * 100, 2),
        }
