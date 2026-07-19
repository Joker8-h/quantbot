import pandas as pd
import numpy as np

from config import CONFIG


class Strategy:
    def __init__(self, config=CONFIG):
        self.rsi_threshold = config.rsi_threshold

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Mean reversion: buy oversold in up-trend, sell overbought in down-trend
        vol_high = df["volume"] > (df["vol_avg"] * 1.5)

        # LONG: uptrend but pulled back to oversold (RSI < 35), bounce
        cond_long = (
            (df["ema_fast"] > df["ema_slow"]) &
            (df["rsi"] < 35) &
            (df["close"] > df["open"]) &  # bullish candle
            (df["low"] <= df["ema_fast"] * 1.01) &  # near EMA support
            vol_high
        )

        # SHORT: downtrend but rallied to overbought (RSI > 65), drop
        cond_short = (
            (df["ema_fast"] < df["ema_slow"]) &
            (df["rsi"] > 65) &
            (df["close"] < df["open"]) &  # bearish candle
            (df["high"] >= df["ema_fast"] * 0.99) &  # near EMA resistance
            vol_high
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
