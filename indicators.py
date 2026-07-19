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
        self.adx_period = config.adx_period
        self.bb_period = config.bb_period
        self.bb_std = config.bb_std

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

    def calculate_adx(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        high = df["high"]
        low = df["low"]
        close = df["close"]

        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.ewm(span=period, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)

        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1))
        adx = dx.ewm(span=period, adjust=False).mean()

        return pd.DataFrame({
            "adx": adx,
            "plus_di": plus_di,
            "minus_di": minus_di,
        }, index=df.index)

    def calculate_bollinger(self, df: pd.DataFrame, period: int, std_dev: float) -> pd.DataFrame:
        sma = df["close"].rolling(window=period).mean()
        std = df["close"].rolling(window=period).std()

        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        width = (upper - lower) / sma  # Ancho relativo (normalizado)

        return pd.DataFrame({
            "bb_upper": upper,
            "bb_middle": sma,
            "bb_lower": lower,
            "bb_width": width,
        }, index=df.index)

    def add_all(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ema_fast"] = self.calculate_ema(df, self.ema_fast)
        df["ema_slow"] = self.calculate_ema(df, self.ema_slow)
        df["rsi"] = self.calculate_rsi(df, self.rsi_period)
        df["atr"] = self.calculate_atr(df, self.atr_period)
        df["vol_avg"] = self.calculate_volume_avg(df, self.volume_avg_period)

        adx_df = self.calculate_adx(df, self.adx_period)
        df["adx"] = adx_df["adx"]
        df["plus_di"] = adx_df["plus_di"]
        df["minus_di"] = adx_df["minus_di"]

        bb_df = self.calculate_bollinger(df, self.bb_period, self.bb_std)
        df["bb_upper"] = bb_df["bb_upper"]
        df["bb_middle"] = bb_df["bb_middle"]
        df["bb_lower"] = bb_df["bb_lower"]
        df["bb_width"] = bb_df["bb_width"]

        return df


if __name__ == "__main__":
    from data_collector import DataCollector

    collector = DataCollector()
    data = collector.collect_all()

    indicators = Indicators()

    for (symbol, tf), df in data.items():
        df_ind = indicators.add_all(df)
        print(f"\n{symbol} {tf} - Ultimas 5 filas con indicadores:")
        cols = ["datetime", "close", "ema_fast", "ema_slow", "rsi", "atr",
                "adx", "bb_width", "vol_avg"]
        print(df_ind[cols].tail())
