import pandas as pd
import numpy as np

from config import CONFIG


class Indicators:
    def __init__(self, config=CONFIG):
        self.ema_fast = config.ema_fast
        self.ema_slow = config.ema_slow
        self.rsi_period = config.rsi_period
        self.atr_period = config.atr_period
        self.volume_avg_period = config.volume_avg_period

    def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        return df["close"].ewm(span=period, adjust=False).mean()

    def calculate_rsi(self, df: pd.DataFrame, period: int) -> pd.Series:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(span=period, adjust=False).mean()
        return atr

    def calculate_volume_avg(self, df: pd.DataFrame, period: int) -> pd.Series:
        return df["volume"].rolling(window=period).mean()

    def add_all(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ema_fast"] = self.calculate_ema(df, self.ema_fast)
        df["ema_slow"] = self.calculate_ema(df, self.ema_slow)
        df["rsi"] = self.calculate_rsi(df, self.rsi_period)
        df["atr"] = self.calculate_atr(df, self.atr_period)
        df["vol_avg"] = self.calculate_volume_avg(df, self.volume_avg_period)
        return df


if __name__ == "__main__":
    from data_collector import DataCollector

    collector = DataCollector()
    data = collector.collect_all()

    indicators = Indicators()

    for (symbol, tf), df in data.items():
        df_ind = indicators.add_all(df)
        print(f"\n{symbol} {tf} - Últimas 5 filas con indicadores:")
        print(df_ind[["datetime", "close", "ema_fast", "ema_slow", "rsi", "atr", "vol_avg"]].tail())
