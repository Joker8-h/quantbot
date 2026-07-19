import pandas as pd
import numpy as np
from itertools import product
from dataclasses import dataclass
from typing import List, Dict, Tuple
import sys
sys.stdout.reconfigure(encoding='utf-8')

from config import TradingConfig
from indicators import Indicators
from strategy import Strategy
from backtester import Backtester
from metrics import Metrics


@dataclass
class WindowResult:
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    best_params: Dict
    train_return: float
    test_return: float
    train_pf: float
    test_pf: float
    train_trades: int
    test_trades: int


class WalkForward:
    def __init__(self):
        self.param_grid = {
            "atr_sl_multiplier": [2.0, 2.5, 3.0],
            "rr_ratio": [2.0, 2.5, 3.0],
            "min_bars_between_trades": [72, 120, 168],
        }
        self.train_years = 2
        self.test_years = 1

    def run(self, df: pd.DataFrame) -> List[WindowResult]:
        windows = self._create_windows(df)
        results = []

        for i, (train_data, test_data) in enumerate(windows):
            print(f"\n--- Ventana {i+1}/{len(windows)} ---")
            print(f"  Train: {train_data['datetime'].iloc[0].date()} a {train_data['datetime'].iloc[-1].date()}")
            print(f"  Test:  {test_data['datetime'].iloc[0].date()} a {test_data['datetime'].iloc[-1].date()}")

            best_params, train_return, train_pf, train_trades = self._optimize(train_data)
            test_return, test_pf, test_trades = self._test(test_data, best_params)

            result = WindowResult(
                window_id=i + 1,
                train_start=str(train_data["datetime"].iloc[0].date()),
                train_end=str(train_data["datetime"].iloc[-1].date()),
                test_start=str(test_data["datetime"].iloc[0].date()),
                test_end=str(test_data["datetime"].iloc[-1].date()),
                best_params=best_params,
                train_return=train_return,
                test_return=test_return,
                train_pf=train_pf,
                test_pf=test_pf,
                train_trades=train_trades,
                test_trades=test_trades,
            )
            results.append(result)

            print(f"  Params: ATR SL {best_params['atr_sl_multiplier']}, R:R {best_params['rr_ratio']}, "
                  f"Cooldown {best_params['min_bars_between_trades']}")
            print(f"  Train: {train_return:+.2f}% (PF {train_pf:.2f}, {train_trades} trades)")
            print(f"  Test:  {test_return:+.2f}% (PF {test_pf:.2f}, {test_trades} trades)")

        return results

    def _create_windows(self, df: pd.DataFrame) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        windows = []
        start_year = df["datetime"].iloc[0].year
        end_year = df["datetime"].iloc[-1].year

        for train_end in range(start_year + self.train_years - 1, end_year - self.test_years + 1):
            test_start = train_end + 1
            test_end = test_start + self.test_years - 1

            train_mask = (df["datetime"].dt.year >= train_end - self.train_years + 1) & \
                         (df["datetime"].dt.year <= train_end)
            test_mask = (df["datetime"].dt.year >= test_start) & \
                        (df["datetime"].dt.year <= test_end)

            train_data = df[train_mask].copy().reset_index(drop=True)
            test_data = df[test_mask].copy().reset_index(drop=True)

            if len(train_data) > 100 and len(test_data) > 100:
                windows.append((train_data, test_data))

        return windows

    def _optimize(self, train_data: pd.DataFrame) -> Tuple[Dict, float, float, int]:
        keys = list(self.param_grid.keys())
        values = list(self.param_grid.values())
        best_pf = 0
        best_params = {}
        best_return = 0
        best_trades = 0

        for combo in product(*values):
            params = dict(zip(keys, combo))
            return_pct, pf, trades = self._run_backtest(train_data, params)

            if pf > best_pf and trades >= 10:
                best_pf = pf
                best_params = params
                best_return = return_pct
                best_trades = trades

        return best_params, best_return, best_pf, best_trades

    def _test(self, test_data: pd.DataFrame, params: Dict) -> Tuple[float, float, int]:
        return_pct, pf, trades = self._run_backtest(test_data, params)
        return return_pct, pf, trades

    def _run_backtest(self, df: pd.DataFrame, params: Dict) -> Tuple[float, float, int]:
        config = TradingConfig(
            atr_sl_multiplier=params["atr_sl_multiplier"],
            rr_ratio=params["rr_ratio"],
            min_bars_between_trades=params["min_bars_between_trades"],
        )

        indicators = Indicators(config)
        strategy = Strategy(config)
        backtester = Backtester(config)
        metrics = Metrics()

        df_ind = indicators.add_all(df)
        df_sig = strategy.generate_signals(df_ind)
        result = backtester.run(df_sig)

        if result["trades"].empty:
            return 0, 0, 0

        m = metrics.calculate(result["trades"], result["equity_curve"])
        return_pct = m["rentabilidad"]
        pf = m["profit_factor"]
        trades = m["total_trades"]

        return return_pct, pf, trades

    def print_report(self, results: List[WindowResult]):
        print("\n" + "=" * 70)
        print("  WALK-FORWARD ANALYSIS - REPORTE FINAL")
        print("=" * 70)

        for r in results:
            status = "+" if r.test_return > 0 else "-"
            print(f"\nVentana {r.window_id}: {r.train_start} -> {r.test_end}")
            print(f"  Params: ATR SL {r.best_params['atr_sl_multiplier']}, R:R {r.best_params['rr_ratio']}, "
                  f"Cooldown {r.best_params['min_bars_between_trades']}")
            print(f"  Train: {r.train_return:+.2f}% (PF {r.train_pf:.2f}, {r.train_trades} trades)")
            print(f"  Test:  {r.test_return:+.2f}% (PF {r.test_pf:.2f}, {r.test_trades} trades) [{status}]")

        test_returns = [r.test_return for r in results]
        test_pfs = [r.test_pf for r in results]
        profitable_windows = sum(1 for r in test_returns if r > 0)

        print(f"\n{'='*70}")
        print(f"  RESUMEN")
        print(f"{'='*70}")
        print(f"  Ventanas totales:        {len(results)}")
        print(f"  Ventanas rentables:      {profitable_windows}/{len(results)} ({profitable_windows/len(results)*100:.0f}%)")
        print(f"  Retorno promedio test:   {np.mean(test_returns):+.2f}%")
        print(f"  PF promedio test:        {np.mean(test_pfs):.2f}")
        print(f"  Mejor test:              {max(test_returns):+.2f}%")
        print(f"  Peor test:               {min(test_returns):+.2f}%")


if __name__ == "__main__":
    df = pd.read_csv("data/raw/BTC_USDT_1h.csv")
    df["datetime"] = pd.to_datetime(df["datetime"])
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)

    wf = WalkForward()

    print(f"\n{'='*70}")
    print(f"  WALK-FORWARD: BTC/USDT 1h")
    print(f"{'='*70}")

    results = wf.run(df)
    wf.print_report(results)
