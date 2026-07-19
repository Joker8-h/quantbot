import pandas as pd
import numpy as np

from config import CONFIG


class Strategy:
    def __init__(self, config=CONFIG):
        self.rsi_threshold = config.rsi_threshold

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Condiciones comunes
        cond_volume = df["volume"] > df["vol_avg"]

        # LONG: EMA fast > slow + RSI > 50 + rompe máximo + volumen
        cond_ema_bull = df["ema_fast"] > df["ema_slow"]
        cond_rsi_bull = df["rsi"] > self.rsi_threshold
        cond_breakout_bull = df["close"] > df["high"].shift(1)
        cond_bull = cond_ema_bull & cond_rsi_bull & cond_breakout_bull & cond_volume

        # SHORT: muy estricto - solo tendencias bajistas fuertes
        cond_ema_bear = df["ema_fast"] < df["ema_slow"]
        cond_rsi_bear = df["rsi"] < 35
        cond_breakout_bear = df["close"] < df["low"].shift(1)
        cond_volume_high = df["volume"] > (df["vol_avg"] * 2.0)
        cond_bear = cond_ema_bear & cond_rsi_bear & cond_breakout_bear & cond_volume_high

        # Señales: 1 = LONG, -1 = SHORT, 0 = sin señal
        df["signal"] = 0
        df.loc[cond_bull, "signal"] = 1
        df.loc[cond_bear, "signal"] = -1

        # Evitar señales consecutivas del mismo tipo
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


if __name__ == "__main__":
    from data_collector import DataCollector
    from indicators import Indicators

    collector = DataCollector()
    indicators = Indicators()
    strategy = Strategy()

    data = collector.collect_all()

    for (symbol, tf), df in data.items():
        df_ind = indicators.add_all(df)
        df_sig = strategy.generate_signals(df_ind)
        summary = strategy.get_signal_summary(df_sig)

        print(f"\n{symbol} {tf}")
        print(f"  Señales totales: {summary['total_signals']}")
        print(f"  LONG: {summary['long_signals']} | SHORT: {summary['short_signals']}")
        print(f"  % de velas con señal: {summary['signal_pct']}%")

        longs = df_sig[df_sig["signal"] == 1]
        shorts = df_sig[df_sig["signal"] == -1]
        if not longs.empty:
            print(f"\n  Primeras 3 señales LONG:")
            print(longs[["datetime", "close", "ema_fast", "ema_slow", "rsi"]].head(3))
        if not shorts.empty:
            print(f"\n  Primeras 3 señales SHORT:")
            print(shorts[["datetime", "close", "ema_fast", "ema_slow", "rsi"]].head(3))
