from config import CONFIG


class RiskManager:
    def __init__(self, config=CONFIG):
        self.risk_per_trade = config.risk_per_trade
        self.rr_ratio = config.rr_ratio
        self.atr_sl_multiplier = config.atr_sl_multiplier
        self.trail_atr_multiplier = config.trail_atr_multiplier
        self.daily_loss_limit = config.daily_loss_limit
        self.weekly_loss_limit = config.weekly_loss_limit
        self.max_consecutive_losses = config.max_consecutive_losses

    def calculate_stop_loss(self, entry_price: float, atr_value: float, side: str = "LONG") -> float:
        if side == "LONG":
            return entry_price - (self.atr_sl_multiplier * atr_value)
        else:  # SHORT
            return entry_price + (self.atr_sl_multiplier * atr_value)

    def calculate_take_profit(self, entry_price: float, stop_distance: float, side: str = "LONG") -> float:
        if side == "LONG":
            return entry_price + (stop_distance * self.rr_ratio)
        else:  # SHORT
            return entry_price - (stop_distance * self.rr_ratio)

    def update_trailing_stop(
        self,
        current_price: float,
        stop_price: float,
        atr_value: float,
        side: str = "LONG",
    ) -> float:
        if side == "LONG":
            # LONG: stop sube cuando precio sube
            new_stop = current_price - (self.trail_atr_multiplier * atr_value)
            return max(new_stop, stop_price)  # Solo subir
        else:  # SHORT
            # SHORT: stop baja cuando precio baja
            new_stop = current_price + (self.trail_atr_multiplier * atr_value)
            return min(new_stop, stop_price)  # Solo bajar

    def calculate_position_size(
        self,
        capital: float,
        entry_price: float,
        stop_price: float,
        fee: float,
        slippage: float,
    ) -> float:
        risk_amount = capital * self.risk_per_trade
        stop_distance = abs(entry_price - stop_price)

        if stop_distance == 0:
            return 0.0

        # Ajustar por costos
        cost_factor = 1 + fee + slippage
        effective_distance = stop_distance * cost_factor

        position_size = risk_amount / effective_distance
        return position_size

    def check_circuit_breaker(
        self,
        daily_pnl_pct: float,
        weekly_pnl_pct: float,
        consecutive_losses: int,
    ) -> dict:
        stop_daily = daily_pnl_pct <= -self.daily_loss_limit
        stop_weekly = weekly_pnl_pct <= -self.weekly_loss_limit
        stop_consecutive = consecutive_losses >= self.max_consecutive_losses

        return {
            "should_stop": stop_daily or stop_weekly or stop_consecutive,
            "daily_stop": stop_daily,
            "weekly_stop": stop_weekly,
            "consecutive_stop": stop_consecutive,
            "reason": (
                "Daily loss limit" if stop_daily
                else "Weekly loss limit" if stop_weekly
                else "Consecutive losses" if stop_consecutive
                else None
            ),
        }


if __name__ == "__main__":
    rm = RiskManager()

    capital = 10.0
    entry = 50000.0
    atr = 500.0

    # Test LONG
    sl_long = rm.calculate_stop_loss(entry, atr, "LONG")
    tp_long = rm.calculate_take_profit(entry, entry - sl_long, "LONG")
    size_long = rm.calculate_position_size(capital, entry, sl_long, 0.001, 0.0005)

    print("=== LONG ===")
    print(f"Entry:  ${entry:,.2f}")
    print(f"SL:     ${sl_long:,.2f} ({abs(entry-sl_long)/entry*100:.2f}%)")
    print(f"TP:     ${tp_long:,.2f} ({abs(tp_long-entry)/entry*100:.2f}%)")
    print(f"Size:   {size_long:.6f} BTC")

    # Test SHORT
    sl_short = rm.calculate_stop_loss(entry, atr, "SHORT")
    tp_short = rm.calculate_take_profit(entry, sl_short - entry, "SHORT")
    size_short = rm.calculate_position_size(capital, entry, sl_short, 0.001, 0.0005)

    print("\n=== SHORT ===")
    print(f"Entry:  ${entry:,.2f}")
    print(f"SL:     ${sl_short:,.2f} ({abs(sl_short-entry)/entry*100:.2f}%)")
    print(f"TP:     ${tp_short:,.2f} ({abs(entry-tp_short)/entry*100:.2f}%)")
    print(f"Size:   {size_short:.6f} BTC")

    # Test trailing stop
    print("\n=== TRAILING STOP ===")
    price = 51000.0
    new_sl = rm.update_trailing_stop(price, sl_long, atr, "LONG")
    print(f"Price: ${price:,.2f} | Old SL: ${sl_long:,.2f} | New SL: ${new_sl:,.2f}")
