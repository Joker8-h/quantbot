"""
daily_update.py - Script para ejecutar diariamente
Descarga datos frescos y ejecuta el backtest
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

from datetime import datetime, timezone
from data_collector import DataCollector
from indicators import Indicators
from strategy import Strategy
from backtester import Backtester
from metrics import Metrics


def daily_update():
    print(f"\n{'='*60}")
    print(f"  QUANTBOT - ACTUALIZACION DIARIA")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")

    # 1. Descargar datos frescos
    print("\n[1/3] Descargando datos frescos...")
    collector = DataCollector()
    data = collector.collect_all()

    if not data:
        print("  Error: No se pudieron descargar datos")
        return

    # 2. Ejecutar backtest
    print("\n[2/3] Ejecutando backtest...")
    indicators = Indicators()
    strategy = Strategy()
    backtester = Backtester()
    metrics = Metrics()

    for (symbol, tf), df in data.items():
        print(f"\n  {symbol} | {tf}")
        df_ind = indicators.add_all(df)
        df_sig = strategy.generate_signals(df_ind)
        result = backtester.run(df_sig)

        m = metrics.calculate(result["trades"], result["equity_curve"])

        # 3. Resumen
        print(f"\n[3/3] Resumen del dia:")
        print(f"  Velas totales: {len(df)}")
        print(f"  Desde: {df['datetime'].iloc[0]}")
        print(f"  Hasta: {df['datetime'].iloc[-1]}")
        print(f"  Precio actual: ${df['close'].iloc[-1]:,.2f}")
        print(f"\n  Capital inicial: ${m['initial_capital']:.2f}")
        print(f"  Capital final:   ${m['final_capital']:.2f}")
        print(f"  Rentabilidad:    {m['rentabilidad']:+.2f}%")
        print(f"  Total trades:    {m['total_trades']}")
        print(f"  Win Rate:        {m['win_rate']:.1f}%")
        print(f"  Profit Factor:   {m['profit_factor']:.2f}")

        # Guardar logs
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f"backtest_{today}.txt")

        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"Fecha: {today}\n")
            f.write(f"Symbol: {symbol} | Timeframe: {tf}\n")
            f.write(f"Velas: {len(df)}\n")
            f.write(f"Precio: ${df['close'].iloc[-1]:,.2f}\n")
            f.write(f"Capital: ${m['initial_capital']:.2f} -> ${m['final_capital']:.2f}\n")
            f.write(f"Rentabilidad: {m['rentabilidad']:+.2f}%\n")
            f.write(f"Trades: {m['total_trades']}\n")
            f.write(f"Win Rate: {m['win_rate']:.1f}%\n")
            f.write(f"Profit Factor: {m['profit_factor']:.2f}\n")

        print(f"\n  Log guardado: {log_file}")

    print(f"\n{'='*60}")
    print(f"  ACTUALIZACION COMPLETADA")
    print(f"{'='*60}")


if __name__ == "__main__":
    daily_update()
