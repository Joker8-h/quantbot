import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import sys
sys.stdout.reconfigure(encoding='utf-8')

from config import TradingConfig
from indicators import Indicators
from strategy import Strategy
from backtester import Backtester
from metrics import Metrics


class Optimizer:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def test_robustness(self, base_params: Dict, variation_pct: float = 0.20) -> Dict:
        base_config = TradingConfig(**base_params)
        base_result = self._run_backtest(base_config)

        variations = []
        param_keys = list(base_params.keys())

        for key in param_keys:
            base_val = base_params[key]
            if not isinstance(base_val, (int, float)):
                continue

            for factor in [1 - variation_pct, 1 + variation_pct]:
                test_params = base_params.copy()
                test_params[key] = base_val * factor
                if isinstance(base_val, int):
                    test_params[key] = max(1, int(test_params[key]))

                config = TradingConfig(**test_params)
                result = self._run_backtest(config)

                variations.append({
                    "param": key,
                    "base_value": base_val,
                    "test_value": test_params[key],
                    "pf": result["profit_factor"],
                    "return": result["rentabilidad"],
                    "trades": result["total_trades"],
                })

        pf_values = [v["pf"] for v in variations]
        return_values = [v["return"] for v in variations]

        avg_pf = np.mean(pf_values) if pf_values else 0
        min_pf = min(pf_values) if pf_values else 0
        avg_return = np.mean(return_values) if return_values else 0
        min_return = min(return_values) if return_values else 0

        sensitivity_score = 0
        if base_result["profit_factor"] > 0:
            pf_degradation = (base_result["profit_factor"] - avg_pf) / base_result["profit_factor"]
            sensitivity_score = max(0, 100 - pf_degradation * 200)
            if min_pf < 1.0:
                sensitivity_score *= 0.5

        return {
            "base_pf": base_result["profit_factor"],
            "base_return": base_result["rentabilidad"],
            "base_trades": base_result["total_trades"],
            "avg_pf_variations": round(avg_pf, 2),
            "min_pf_variations": round(min_pf, 2),
            "avg_return_variations": round(avg_return, 2),
            "min_return_variations": round(min_return, 2),
            "sensitivity_score": round(sensitivity_score, 1),
            "variations": variations,
        }

    def test_scenarios(self, base_params: Dict) -> Dict:
        scenarios = {
            "optimista": {
                "fee": 0.00075,
                "slippage": 0.0003,
            },
            "normal": {
                "fee": 0.001,
                "slippage": 0.0005,
            },
            "pesimista": {
                "fee": 0.0015,
                "slippage": 0.001,
            },
        }

        results = {}
        for name, costs in scenarios.items():
            params = base_params.copy()
            params["fee"] = costs["fee"]
            params["slippage"] = costs["slippage"]
            config = TradingConfig(**params)
            result = self._run_backtest(config)
            results[name] = {
                "pf": result["profit_factor"],
                "return": result["rentabilidad"],
                "trades": result["total_trades"],
                "win_rate": result["win_rate"],
            }

        profitable_count = sum(1 for r in results.values() if r["pf"] > 1.0)
        return {
            "scenarios": results,
            "profitable_in": profitable_count,
            "total_scenarios": len(scenarios),
            "passes": profitable_count >= 2,
        }

    def _run_backtest(self, config: TradingConfig) -> Dict:
        indicators = Indicators(config)
        strategy = Strategy(config)
        backtester = Backtester(config)
        metrics = Metrics()

        df_ind = indicators.add_all(self.df)
        df_sig = strategy.generate_signals(df_ind)
        result = backtester.run(df_sig)

        if result["trades"].empty:
            return {"profit_factor": 0, "rentabilidad": 0, "total_trades": 0, "win_rate": 0}

        m = metrics.calculate(result["trades"], result["equity_curve"])
        return {
            "profit_factor": m["profit_factor"],
            "rentabilidad": m["rentabilidad"],
            "total_trades": m["total_trades"],
            "win_rate": m["win_rate"],
        }


if __name__ == "__main__":
    df = pd.read_csv("data/raw/BTC_USDT_1h.csv")
    df["datetime"] = pd.to_datetime(df["datetime"])
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)

    base_params = {
        "atr_sl_multiplier": 2.5,
        "rr_ratio": 2.5,
        "min_bars_between_trades": 168,
    }

    opt = Optimizer(df)

    print("=" * 60)
    print("  PARAMETER ROBUSTNESS TEST (±20%)")
    print("=" * 60)
    robustness = opt.test_robustness(base_params)
    print(f"  Base PF: {robustness['base_pf']:.2f}")
    print(f"  Base Return: {robustness['base_return']:+.2f}%")
    print(f"  Avg PF variations: {robustness['avg_pf_variations']:.2f}")
    print(f"  Min PF variations: {robustness['min_pf_variations']:.2f}")
    print(f"  Sensitivity Score: {robustness['sensitivity_score']}/100")

    print(f"\n{'='*60}")
    print("  SCENARIO TESTING (fees)")
    print("=" * 60)
    scenarios = opt.test_scenarios(base_params)
    for name, data in scenarios["scenarios"].items():
        print(f"  {name}: PF {data['pf']:.2f} | Return {data['return']:+.2f}% | WR {data['win_rate']:.1f}%")
    print(f"  Profitable in: {scenarios['profitable_in']}/{scenarios['total_scenarios']}")
    print(f"  Passes: {scenarios['passes']}")
