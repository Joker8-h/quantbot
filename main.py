from data_collector import DataCollector
from indicators import Indicators
from strategy import Strategy
from backtester import Backtester
from metrics import Metrics
import sys
sys.stdout.reconfigure(encoding='utf-8')


def run_backtest():
    print("=" * 60)
    print("  QUANTBOT v2 - BACKTEST COMPLETO")
    print("=" * 60)

    print("\n[1/4] Cargando datos...")
    collector = DataCollector()
    data = collector.collect_all()

    if not data:
        print("  No hay datos disponibles.")
        return

    indicators = Indicators()
    strategy = Strategy()
    backtester = Backtester()
    metrics = Metrics()

    for (symbol, tf), df in data.items():
        print(f"\n{'='*60}")
        print(f"  {symbol} | {tf}")
        print(f"{'='*60}")

        print("\n[2/4] Calculando indicadores...")
        df_ind = indicators.add_all(df)
        print(f"  OK: {len(df_ind)} velas")

        print("\n[3/4] Generando senales (LONG + SHORT)...")
        df_sig = strategy.generate_signals(df_ind)
        s = strategy.get_signal_summary(df_sig)
        print(f"  LONG: {s['long_signals']} | SHORT: {s['short_signals']} | Total: {s['total_signals']}")

        print("\n[4/4] Ejecutando backtest...")
        result = backtester.run(df_sig)

        m = metrics.calculate(result["trades"], result["equity_curve"])
        metrics.print_report(m)

        if not result["trades"].empty:
            result["trades"].to_csv("trades_v2.csv", index=False)
            result["equity_curve"].to_csv("equity_curve_v2.csv", index=False)
            print("\n  Archivos guardados: trades_v2.csv, equity_curve_v2.csv")


if __name__ == "__main__":
    run_backtest()
