import pandas as pd
import numpy as np
import random
from dataclasses import dataclass
from typing import List, Dict
import sys
sys.stdout.reconfigure(encoding='utf-8')

from config import CONFIG
from data_collector import DataCollector
from indicators import Indicators
from strategy import Strategy
from backtester import Backtester
from metrics import Metrics


@dataclass
class MonteCarloResult:
    # Drawdown distribution
    avg_drawdown: float
    worst_drawdown: float
    drawdown_percentile_5: float
    drawdown_percentile_95: float
    # Probability of ruin
    prob_ruin_10pct: float
    prob_ruin_20pct: float
    prob_ruin_30pct: float
    # Max consecutive losses
    avg_max_consecutive: float
    worst_max_consecutive: float
    # Capital at risk
    capital_at_risk_5pct: float
    capital_at_risk_95pct: float
    # Path metrics
    avg_trades_to_recovery: float
    worst_trades_to_recovery: float
    total_return: float


class MonteCarlo:
    def __init__(self, iterations: int = 10000):
        self.iterations = iterations

    def run(self, trades_df: pd.DataFrame, initial_capital: float = 100.0) -> MonteCarloResult:
        if trades_df.empty:
            raise ValueError("No hay trades para simular")

        pnls = trades_df["pnl"].tolist()
        drawdowns = []
        consecutive_losses_list = []
        ruin_10 = 0
        ruin_20 = 0
        ruin_30 = 0
        recovery_list = []

        print(f"Ejecutando {self.iterations} simulaciones Monte Carlo...")

        for i in range(self.iterations):
            if (i + 1) % 2000 == 0:
                print(f"  {i+1}/{self.iterations}...")

            shuffled = random.sample(pnls, len(pnls))
            equity = [initial_capital]
            peak = initial_capital
            max_dd = 0
            max_consecutive = 0
            current_consecutive = 0
            ruined_10 = False
            ruined_20 = False
            ruined_30 = False
            ruin_threshold_10 = initial_capital * 0.9
            ruin_threshold_20 = initial_capital * 0.8
            ruin_threshold_30 = initial_capital * 0.7
            recovery_trades = 0
            recovered = False

            for pnl in shuffled:
                new_eq = equity[-1] + pnl
                equity.append(new_eq)
                peak = max(peak, new_eq)
                dd = (new_eq - peak) / peak if peak > 0 else 0
                max_dd = min(max_dd, dd)

                if pnl <= 0:
                    current_consecutive += 1
                    max_consecutive = max(max_consecutive, current_consecutive)
                else:
                    current_consecutive = 0

                # Check ruin (once per simulation)
                if new_eq <= ruin_threshold_10 and not ruined_10:
                    ruin_10 += 1
                    ruined_10 = True
                if new_eq <= ruin_threshold_20 and not ruined_20:
                    ruin_20 += 1
                    ruined_20 = True
                if new_eq <= ruin_threshold_30 and not ruined_30:
                    ruin_30 += 1
                    ruined_30 = True

                # Track recovery
                if not recovered and new_eq >= initial_capital:
                    recovery_trades += len(equity) - 1
                    recovered = True

            drawdowns.append(max_dd * 100)
            consecutive_losses_list.append(max_consecutive)
            if not recovered:
                recovery_list.append(len(shuffled))

        total_return = (equity[-1] - initial_capital) / initial_capital * 100

        return MonteCarloResult(
            avg_drawdown=np.mean(drawdowns),
            worst_drawdown=min(drawdowns),
            drawdown_percentile_5=np.percentile(drawdowns, 5),
            drawdown_percentile_95=np.percentile(drawdowns, 95),
            prob_ruin_10pct=ruin_10 / self.iterations * 100,
            prob_ruin_20pct=ruin_20 / self.iterations * 100,
            prob_ruin_30pct=ruin_30 / self.iterations * 100,
            avg_max_consecutive=np.mean(consecutive_losses_list),
            worst_max_consecutive=max(consecutive_losses_list),
            capital_at_risk_5pct=initial_capital * (1 + np.percentile(drawdowns, 5) / 100),
            capital_at_risk_95pct=initial_capital * (1 + np.percentile(drawdowns, 95) / 100),
            avg_trades_to_recovery=np.mean(recovery_list) if recovery_list else 0,
            worst_trades_to_recovery=max(recovery_list) if recovery_list else 0,
            total_return=total_return,
        )

    def print_report(self, result: MonteCarloResult, initial_capital: float = 100.0):
        print("\n" + "=" * 60)
        print("  MONTE CARLO SIMULATION - REPORTE")
        print("=" * 60)

        print(f"\n  Capital inicial: ${initial_capital:,.2f}")
        print(f"  Retorno total (orden original): {result.total_return:+.2f}%")

        print(f"\n  --- DISTRIBUCION DE DRAWDOWN ---")
        print(f"  Drawdown promedio:        {result.avg_drawdown:.1f}%")
        print(f"  Peor drawdown:            {result.worst_drawdown:.1f}%")
        print(f"  Drawdown Percentil 5:     {result.drawdown_percentile_5:.1f}%")
        print(f"  Drawdown Percentil 95:    {result.drawdown_percentile_95:.1f}%")

        print(f"\n  --- PROBABILIDAD DE RUINA ---")
        print(f"  Perder 10% del capital:   {result.prob_ruin_10pct:.1f}%")
        print(f"  Perder 20% del capital:   {result.prob_ruin_20pct:.1f}%")
        print(f"  Perder 30% del capital:   {result.prob_ruin_30pct:.1f}%")

        print(f"\n  --- PERDIDAS CONSECUTIVAS ---")
        print(f"  Promedio max consecutivas: {result.avg_max_consecutive:.0f}")
        print(f"  Peor racha:               {result.worst_max_consecutive}")

        print(f"\n  --- CAPITAL EN RIESGO ---")
        print(f"  Capital minimo (95% CI):   ${result.capital_at_risk_95pct:,.2f}")
        print(f"  Capital minimo (5% CI):    ${result.capital_at_risk_5pct:,.2f}")

        if result.avg_trades_to_recovery > 0:
            print(f"\n  --- RECUPERACION ---")
            print(f"  Trades promedio para recuperar: {result.avg_trades_to_recovery:.0f}")
            print(f"  Trades peor caso:               {result.worst_trades_to_recovery}")

        print("\n" + "=" * 60)


if __name__ == "__main__":
    collector = DataCollector()
    indicators = Indicators()
    strategy = Strategy()
    backtester = Backtester()
    metrics = Metrics()

    data = collector.collect_all()

    for (symbol, tf), df in data.items():
        print(f"\n{'='*60}")
        print(f"  MONTE CARLO: {symbol} {tf}")
        print(f"{'='*60}")

        df_ind = indicators.add_all(df)
        df_sig = strategy.generate_signals(df_ind)
        result = backtester.run(df_sig)

        if result["trades"].empty:
            print("  No hay trades para simular")
            continue

        mc = MonteCarlo(iterations=10000)
        mc_result = mc.run(result["trades"], CONFIG.initial_capital)
        mc.print_report(mc_result, CONFIG.initial_capital)
