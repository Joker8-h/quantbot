import pandas as pd
import numpy as np
from typing import List, Dict

from config import CONFIG
from risk_manager import RiskManager


class Backtester:
    def __init__(self, config=CONFIG):
        self.initial_capital = config.initial_capital
        self.fee = config.fee
        self.slippage = config.slippage
        self.cooldown_hours = config.cooldown_hours
        self.risk_manager = RiskManager(config)

    def run(self, df: pd.DataFrame) -> Dict:
        capital = self.initial_capital
        trades: List[Dict] = []
        equity_curve = [{"datetime": df["datetime"].iloc[0], "equity": capital}]

        daily_pnl = 0.0
        weekly_pnl = 0.0
        consecutive_losses = 0
        current_day = None
        current_week = None

        in_position = False
        position_type = None  # "LONG" o "SHORT"
        entry_price = 0.0
        entry_time = None
        position_size = 0.0
        stop_price = 0.0
        take_price = 0.0

        cooldown_until = None
        last_trade_time = None
        min_bars_between_trades = 48  # Minimo 48 velas (2 dias en 1h) entre trades

        for i, row in df.iterrows():
            if i < 2:
                continue

            dt = row["datetime"]

            # Cooldown: saltar velas si estamos en pausa
            if cooldown_until and dt < cooldown_until:
                unrealized = self._calc_unrealized(row["close"], position_type,
                                                    entry_price, position_size) if in_position else 0
                equity_curve.append({"datetime": dt, "equity": capital + unrealized})
                continue

            # Reset diario/semanal
            if current_day != dt.date():
                daily_pnl = 0.0
                current_day = dt.date()
            if current_week != dt.isocalendar()[1]:
                weekly_pnl = 0.0
                current_week = dt.isocalendar()[1]

            # Circuit breaker check
            cb = self.risk_manager.check_circuit_breaker(
                daily_pnl / max(capital, 0.01),
                weekly_pnl / max(capital, 0.01),
                consecutive_losses,
            )
            if cb["should_stop"]:
                if in_position:
                    net_pnl = self._close_position(row, entry_price, position_type,
                                                    position_size, "circuit_breaker")
                    capital += net_pnl
                    trades.append(self._make_trade(
                        entry_time, dt, entry_price, None, position_type,
                        position_size, net_pnl, "circuit_breaker"
                    ))
                    daily_pnl += net_pnl
                    weekly_pnl += net_pnl
                    consecutive_losses = consecutive_losses + 1 if net_pnl < 0 else 0
                    in_position = False
                    position_type = None

                # Activar cooldown en vez de parar para siempre
                cooldown_until = dt + pd.Timedelta(hours=self.cooldown_hours)
                consecutive_losses = 0
                daily_pnl = 0.0
                weekly_pnl = 0.0
                equity_curve.append({"datetime": dt, "equity": capital})
                continue

            # Si estamos en posición, verificar SL/TP y trailing stop
            if in_position:
                # Actualizar trailing stop solo si está activado
                if self.risk_manager.trail_atr_multiplier > 0:
                    if position_type == "LONG":
                        stop_price = self.risk_manager.update_trailing_stop(
                            row["close"], stop_price, row["atr"], "LONG"
                        )
                    elif position_type == "SHORT":
                        stop_price = self.risk_manager.update_trailing_stop(
                            row["close"], stop_price, row["atr"], "SHORT"
                        )

                # Check Stop Loss
                hit_sl = False
                if position_type == "LONG" and row["low"] <= stop_price:
                    hit_sl = True
                elif position_type == "SHORT" and row["high"] >= stop_price:
                    hit_sl = True

                if hit_sl:
                    net_pnl = self._close_position(row, entry_price, position_type,
                                                    position_size, "stop_loss", stop_price)
                    capital += net_pnl
                    trades.append(self._make_trade(
                        entry_time, dt, entry_price, None, position_type,
                        position_size, net_pnl, "stop_loss"
                    ))
                    daily_pnl += net_pnl
                    weekly_pnl += net_pnl
                    consecutive_losses += 1
                    in_position = False
                    position_type = None

                # Check Take Profit
                elif not hit_sl:
                    hit_tp = False
                    if position_type == "LONG" and row["high"] >= take_price:
                        hit_tp = True
                    elif position_type == "SHORT" and row["low"] <= take_price:
                        hit_tp = True

                    if hit_tp:
                        net_pnl = self._close_position(row, entry_price, position_type,
                                                        position_size, "take_profit", take_price)
                        capital += net_pnl
                        trades.append(self._make_trade(
                            entry_time, dt, entry_price, None, position_type,
                            position_size, net_pnl, "take_profit"
                        ))
                        daily_pnl += net_pnl
                        weekly_pnl += net_pnl
                        consecutive_losses = 0
                        in_position = False
                        position_type = None

            # Nueva entrada si no hay posición y hay señal
            can_trade = last_trade_time is None or (dt - last_trade_time).total_seconds() / 3600 >= min_bars_between_trades
            if not in_position and row["signal"] != 0 and capital > 0 and can_trade:
                signal = row["signal"]
                side = "LONG" if signal == 1 else "SHORT"
                atr_value = row["atr"]

                if side == "LONG":
                    entry_price = row["close"] * (1 + self.slippage)
                    stop_price = self.risk_manager.calculate_stop_loss(entry_price, atr_value, "LONG")
                    stop_distance = entry_price - stop_price
                    take_price = self.risk_manager.calculate_take_profit(entry_price, stop_distance, "LONG")
                else:
                    entry_price = row["close"] * (1 - self.slippage)
                    stop_price = self.risk_manager.calculate_stop_loss(entry_price, atr_value, "SHORT")
                    stop_distance = stop_price - entry_price
                    take_price = self.risk_manager.calculate_take_profit(entry_price, stop_distance, "SHORT")

                position_size = self.risk_manager.calculate_position_size(
                    capital, entry_price, stop_price, self.fee, self.slippage
                )

                if position_size > 0 and entry_price * position_size <= capital:
                    fee_cost = entry_price * position_size * self.fee
                    capital -= fee_cost
                    in_position = True
                    position_type = side
                    entry_time = dt
                    last_trade_time = dt

            unrealized = self._calc_unrealized(row["close"], position_type,
                                                entry_price, position_size) if in_position else 0
            equity_curve.append({"datetime": dt, "equity": capital + unrealized})

        # Cerrar posición abierta al final
        if in_position:
            last_row = df.iloc[-1]
            net_pnl = self._close_position(last_row, entry_price, position_type,
                                            position_size, "end_of_data")
            capital += net_pnl
            trades.append(self._make_trade(
                entry_time, last_row["datetime"], entry_price, None, position_type,
                position_size, net_pnl, "end_of_data"
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
        else:  # SHORT
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
        else:  # SHORT
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
            exit_price = entry_price  # Placeholder
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

    collector = DataCollector()
    indicators = Indicators()
    strategy = Strategy()
    backtester = Backtester()

    data = collector.collect_all()

    for (symbol, tf), df in data.items():
        print(f"\n{'='*50}")
        print(f"Backtest: {symbol} {tf}")
        print(f"{'='*50}")

        df_ind = indicators.add_all(df)
        df_sig = strategy.generate_signals(df_ind)
        result = backtester.run(df_sig)

        print(f"Capital inicial: ${result['initial_capital']:.2f}")
        print(f"Capital final:   ${result['final_capital']:.2f}")
        print(f"Operaciones:     {len(result['trades'])}")

        if not result["trades"].empty:
            total_pnl = result["trades"]["pnl"].sum()
            print(f"PnL total:       ${total_pnl:.2f}")
            print(f"Rentabilidad:    {total_pnl/result['initial_capital']*100:.2f}%")
            print(f"\nPor tipo:")
            print(result["trades"]["side"].value_counts().to_string())
