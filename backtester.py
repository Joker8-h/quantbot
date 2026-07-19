import pandas as pd
import numpy as np
from typing import List, Dict, Optional

from config import CONFIG
from risk_manager import RiskManager


class Backtester:
    def __init__(self, config=CONFIG):
        self.initial_capital = config.initial_capital
        self.fee = config.fee
        self.slippage = config.slippage
        self.cooldown_hours = config.cooldown_hours
        self.min_bars_between = config.min_bars_between_trades
        self.max_positions = config.max_open_positions
        self.risk_manager = RiskManager(config)

    def run(self, df: pd.DataFrame) -> Dict:
        capital = self.initial_capital
        trades: List[Dict] = []
        open_positions: List[Dict] = []
        equity_curve = [{"datetime": df["datetime"].iloc[0], "equity": capital}]

        daily_pnl = 0.0
        weekly_pnl = 0.0
        consecutive_losses = 0
        current_day = None
        current_week = None
        last_trade_time = None

        cooldown_until = None

        for i, row in df.iterrows():
            if i < 2:
                continue

            dt = row["datetime"]

            # Cooldown check
            if cooldown_until and dt < cooldown_until:
                unrealized = sum(
                    self._calc_unrealized(row["close"], p["side"], p["entry_price"], p["size"])
                    for p in open_positions
                )
                equity_curve.append({"datetime": dt, "equity": capital + unrealized})
                continue

            # Reset diario/semanal
            if current_day != dt.date():
                daily_pnl = 0.0
                current_day = dt.date()
            if current_week != dt.isocalendar()[1]:
                weekly_pnl = 0.0
                current_week = dt.isocalendar()[1]

            # Circuit breaker
            cb = self.risk_manager.check_circuit_breaker(
                daily_pnl / max(capital, 0.01),
                weekly_pnl / max(capital, 0.01),
                consecutive_losses,
            )
            if cb["should_stop"]:
                # Cerrar todas las posiciones abiertas
                for pos in open_positions[:]:
                    net_pnl = self._close_position(row, pos["entry_price"], pos["side"],
                                                    pos["size"], "circuit_breaker")
                    capital += net_pnl
                    trades.append(self._make_trade(
                        pos["entry_time"], dt, pos["entry_price"], None, pos["side"],
                        pos["size"], net_pnl, "circuit_breaker"
                    ))
                    daily_pnl += net_pnl
                    weekly_pnl += net_pnl
                    consecutive_losses = consecutive_losses + 1 if net_pnl < 0 else 0
                open_positions.clear()

                cooldown_until = dt + pd.Timedelta(hours=self.cooldown_hours)
                consecutive_losses = 0
                daily_pnl = 0.0
                weekly_pnl = 0.0
                equity_curve.append({"datetime": dt, "equity": capital})
                continue

            # Verificar SL/TP para posiciones abiertas
            for pos in open_positions[:]:
                # Trailing stop
                if self.risk_manager.trail_atr_multiplier > 0:
                    atr_val = row["atr"] if "atr" in row.index else 0
                    pos["stop_price"] = self.risk_manager.update_trailing_stop(
                        row["close"], pos["stop_price"], atr_val, pos["side"]
                    )

                # Stop Loss
                hit_sl = False
                if pos["side"] == "LONG" and row["low"] <= pos["stop_price"]:
                    hit_sl = True
                elif pos["side"] == "SHORT" and row["high"] >= pos["stop_price"]:
                    hit_sl = True

                if hit_sl:
                    net_pnl = self._close_position(row, pos["entry_price"], pos["side"],
                                                    pos["size"], "stop_loss", pos["stop_price"])
                    capital += net_pnl
                    trades.append(self._make_trade(
                        pos["entry_time"], dt, pos["entry_price"], None, pos["side"],
                        pos["size"], net_pnl, "stop_loss"
                    ))
                    daily_pnl += net_pnl
                    weekly_pnl += net_pnl
                    consecutive_losses += 1
                    open_positions.remove(pos)
                    continue

                # Take Profit
                hit_tp = False
                if pos["side"] == "LONG" and row["high"] >= pos["take_price"]:
                    hit_tp = True
                elif pos["side"] == "SHORT" and row["low"] <= pos["take_price"]:
                    hit_tp = True

                if hit_tp:
                    net_pnl = self._close_position(row, pos["entry_price"], pos["side"],
                                                    pos["size"], "take_profit", pos["take_price"])
                    capital += net_pnl
                    trades.append(self._make_trade(
                        pos["entry_time"], dt, pos["entry_price"], None, pos["side"],
                        pos["size"], net_pnl, "take_profit"
                    ))
                    daily_pnl += net_pnl
                    weekly_pnl += net_pnl
                    consecutive_losses = 0
                    open_positions.remove(pos)

            # Nueva entrada / cierre por senal
            can_trade = last_trade_time is None or \
                (dt - last_trade_time).total_seconds() / 3600 >= self.min_bars_between

            vol_scale = row.get("vol_scale", 1.0)

            signal = row["signal"]
            # Solo long: senal 1 = entrar long, senal -1 o 0 = salir de long y quedarse plano
            desired_long = (signal == 1)

            if not desired_long:
                for pos in open_positions[:]:
                    if pos["side"] == "LONG":
                        net_pnl = self._close_position(row, pos["entry_price"], pos["side"],
                                                        pos["size"], "signal_exit")
                        capital += net_pnl
                        trades.append(self._make_trade(
                            pos["entry_time"], dt, pos["entry_price"], None, pos["side"],
                            pos["size"], net_pnl, "signal_exit"
                        ))
                        daily_pnl += net_pnl
                        weekly_pnl += net_pnl
                        consecutive_losses = consecutive_losses + 1 if net_pnl < 0 else 0
                        open_positions.remove(pos)
                        last_trade_time = dt
            else:
                if (can_trade
                    and len(open_positions) < self.max_positions
                    and capital > 0):

                    atr_value = row["atr"]

                    entry_price = row["close"] * (1 + self.slippage)
                    stop_price = self.risk_manager.calculate_stop_loss(entry_price, atr_value, "LONG")
                    stop_distance = entry_price - stop_price
                    take_price = self.risk_manager.calculate_take_profit(entry_price, stop_distance, "LONG")

                    position_size = self.risk_manager.calculate_position_size(
                        capital, entry_price, stop_price, self.fee, self.slippage, vol_scale
                    )

                    if position_size > 0 and entry_price * position_size <= capital * 0.95:
                        fee_cost = entry_price * position_size * self.fee
                        capital -= fee_cost
                        open_positions.append({
                        "entry_time": dt,
                        "entry_price": entry_price,
                        "side": "LONG",
                        "size": position_size,
                        "stop_price": stop_price,
                        "take_price": take_price,
                    })
                    last_trade_time = dt

            # Equity
            unrealized = sum(
                self._calc_unrealized(row["close"], p["side"], p["entry_price"], p["size"])
                for p in open_positions
            )
            equity_curve.append({"datetime": dt, "equity": capital + unrealized})

        # Cerrar posiciones abiertas al final
        for pos in open_positions:
            last_row = df.iloc[-1]
            net_pnl = self._close_position(last_row, pos["entry_price"], pos["side"],
                                            pos["size"], "end_of_data")
            capital += net_pnl
            trades.append(self._make_trade(
                pos["entry_time"], last_row["datetime"], pos["entry_price"], None, pos["side"],
                pos["size"], net_pnl, "end_of_data"
            ))

        equity_df = pd.DataFrame(equity_curve)
        trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()

        return {
            "trades": trades_df,
            "equity_curve": equity_df,
            "final_capital": capital,
            "initial_capital": self.initial_capital,
        }

    def _calc_unrealized(self, current_price: float, side: str,
                          entry_price: float, size: float) -> float:
        if side == "LONG":
            return (current_price - entry_price) * size
        else:
            return (entry_price - current_price) * size

    def _close_position(self, row, entry_price: float, side: str,
                         size: float, reason: str,
                         limit_price: float = None) -> float:
        if side == "LONG":
            if limit_price:
                exit_price = limit_price * (1 - self.slippage)
            else:
                exit_price = row["close"] * (1 - self.slippage)
            pnl = (exit_price - entry_price) * size
        else:
            if limit_price:
                exit_price = limit_price * (1 + self.slippage)
            else:
                exit_price = row["close"] * (1 + self.slippage)
            pnl = (entry_price - exit_price) * size

        fee_cost = (entry_price + exit_price) * size * self.fee
        return pnl - fee_cost

    def _make_trade(self, entry_time, exit_time, entry_price, exit_price,
                     side, size, pnl, reason) -> Dict:
        if exit_price is None:
            exit_price = entry_price
        fee_cost = (entry_price + exit_price) * size * self.fee
        return {
            "entry_time": entry_time,
            "exit_time": exit_time,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "side": side,
            "position_size": size,
            "pnl": pnl,
            "fee": fee_cost,
            "exit_reason": reason,
        }


if __name__ == "__main__":
    from data_collector import DataCollector
    from indicators import Indicators
    from strategy import Strategy
    from market_regime import MarketRegime
    from metrics import Metrics

    collector = DataCollector()
    indicators = Indicators()
    strategy = Strategy()
    regime = MarketRegime()
    backtester = Backtester()
    metrics = Metrics()

    data = collector.collect_all()

    for (symbol, tf), df in data.items():
        print(f"\n{'='*50}")
        print(f"Backtest: {symbol} {tf}")
        print(f"{'='*50}")

        df_ind = indicators.add_all(df)
        df_regime = regime.detect(df_ind)
        df_sig = strategy.generate_signals(df_regime)
        result = backtester.run(df_sig)

        m = metrics.calculate(result["trades"], result["equity_curve"])

        print(f"Capital inicial: ${m['initial_capital']:.2f}")
        print(f"Capital final:   ${m['final_capital']:.2f}")
        print(f"Rentabilidad:    {m['rentabilidad']:+.2f}%")
        print(f"Total trades:    {m['total_trades']}")
        print(f"Win Rate:        {m['win_rate']:.1f}%")
        print(f"Profit Factor:   {m['profit_factor']:.2f}")
        print(f"Max Drawdown:    {m['max_drawdown']:.2f}%")
