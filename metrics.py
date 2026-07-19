import pandas as pd
import numpy as np
from typing import Dict


class Metrics:
    def calculate(self, trades_df: pd.DataFrame, equity_df: pd.DataFrame) -> Dict:
        if trades_df.empty:
            return self._empty_metrics()

        # Métricas básicas
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df["pnl"] > 0])
        losing_trades = len(trades_df[trades_df["pnl"] <= 0])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0

        # PnL
        total_pnl = trades_df["pnl"].sum()
        avg_win = trades_df[trades_df["pnl"] > 0]["pnl"].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df["pnl"] <= 0]["pnl"].mean() if losing_trades > 0 else 0

        # Profit Factor
        gross_profit = trades_df[trades_df["pnl"] > 0]["pnl"].sum()
        gross_loss = abs(trades_df[trades_df["pnl"] <= 0]["pnl"].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Drawdown
        equity = equity_df["equity"]
        peak = equity.cummax()
        drawdown = (equity - peak) / peak
        max_drawdown = drawdown.min() * 100

        # Sharpe Ratio (anualizado, asumiendo datos por hora)
        equity_returns = equity.pct_change().dropna()
        if len(equity_returns) > 1 and equity_returns.std() > 0:
            sharpe = (equity_returns.mean() / equity_returns.std()) * np.sqrt(8760)
        else:
            sharpe = 0

        # Fees totales
        total_fees = trades_df["fee"].sum()

        # Capital
        initial_capital = equity_df["equity"].iloc[0]
        final_capital = equity_df["equity"].iloc[-1]
        rentabilidad = (final_capital - initial_capital) / initial_capital * 100

        # Ratios de salida
        exit_reasons = trades_df["exit_reason"].value_counts().to_dict()

        # Racha máxima de pérdidas
        max_consecutive_losses = 0
        current_streak = 0
        for _, trade in trades_df.iterrows():
            if trade["pnl"] <= 0:
                current_streak += 1
                max_consecutive_losses = max(max_consecutive_losses, current_streak)
            else:
                current_streak = 0

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 4),
            "avg_win": round(avg_win, 4),
            "avg_loss": round(avg_loss, 4),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe, 2),
            "total_fees": round(total_fees, 4),
            "initial_capital": round(initial_capital, 2),
            "final_capital": round(final_capital, 2),
            "rentabilidad": round(rentabilidad, 2),
            "exit_reasons": exit_reasons,
            "max_consecutive_losses": max_consecutive_losses,
        }

    def _empty_metrics(self) -> Dict:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "total_fees": 0,
            "initial_capital": 0,
            "final_capital": 0,
            "rentabilidad": 0,
            "exit_reasons": {},
            "max_consecutive_losses": 0,
        }

    def print_report(self, metrics: Dict):
        print("\n" + "=" * 50)
        print("         REPORTE DE BACKTESTING")
        print("=" * 50)

        print(f"\n{'Capital inicial:':<25} ${metrics['initial_capital']:>10.2f}")
        print(f"{'Capital final:':<25} ${metrics['final_capital']:>10.2f}")
        print(f"{'Rentabilidad:':<25} {metrics['rentabilidad']:>9.2f}%")
        print(f"{'PnL total:':<25} ${metrics['total_pnl']:>10.4f}")

        print(f"\n{'-'*50}")
        print(f"{'Operaciones totales:':<25} {metrics['total_trades']:>10}")
        print(f"{'Operaciones ganadoras:':<25} {metrics['winning_trades']:>10}")
        print(f"{'Operaciones perdedoras:':<25} {metrics['losing_trades']:>10}")
        print(f"{'Win Rate:':<25} {metrics['win_rate']:>9.2f}%")

        print(f"\n{'-'*50}")
        print(f"{'Ganancia promedio:':<25} ${metrics['avg_win']:>10.4f}")
        print(f"{'Perdida promedio:':<25} ${metrics['avg_loss']:>10.4f}")
        print(f"{'Profit Factor:':<25} {metrics['profit_factor']:>10.2f}")
        print(f"{'Sharpe Ratio:':<25} {metrics['sharpe_ratio']:>10.2f}")
        print(f"{'Max Drawdown:':<25} {metrics['max_drawdown']:>9.2f}%")

        print(f"\n{'-'*50}")
        print(f"{'Fees totales pagados:':<25} ${metrics['total_fees']:>10.4f}")
        print(f"{'Racha max. perdidas:':<25} {metrics['max_consecutive_losses']:>10}")

        if metrics["exit_reasons"]:
            print(f"\n{'-'*50}")
            print("Razones de salida:")
            for reason, count in metrics["exit_reasons"].items():
                print(f"  {reason:<20} {count}")

        print("\n" + "=" * 50)


if __name__ == "__main__":
    from data_collector import DataCollector
    from indicators import Indicators
    from strategy import Strategy
    from backtester import Backtester

    collector = DataCollector()
    indicators = Indicators()
    strategy = Strategy()
    backtester = Backtester()
    metrics = Metrics()

    data = collector.collect_all()

    for (symbol, tf), df in data.items():
        df_ind = indicators.add_all(df)
        df_sig = strategy.generate_signals(df_ind)
        result = backtester.run(df_sig)

        m = metrics.calculate(result["trades"], result["equity_curve"])
        metrics.print_report(m)
