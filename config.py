import os
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List


@dataclass
class TradingConfig:
    # Capital
    initial_capital: float = 100.0

    # Símbolos y temporalidades
    symbols: List[str] = field(default_factory=lambda: ["BTC/USDT"])
    timeframes: List[str] = field(default_factory=lambda: ["1h"])

    # Período de datos históricos
    start_date: str = "2019-01-01"
    end_date: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Indicadores
    ema_fast: int = 20
    ema_slow: int = 50
    rsi_period: int = 14
    rsi_threshold: int = 50
    atr_period: int = 14
    volume_avg_period: int = 20

    # Riesgo
    risk_per_trade: float = 0.01  # 1% del capital
    rr_ratio: float = 2.0  # Risk/Reward 1:2
    atr_sl_multiplier: float = 3.0  # Stop Loss = 3.0 * ATR

    # Trailing Stop
    trail_atr_multiplier: float = 0.0  # 0 = trailing stop desactivado

    # Comisiones y slippage
    fee: float = 0.001  # 0.1% por operación
    slippage: float = 0.0005  # 0.05%

    # Circuit breakers
    daily_loss_limit: float = 0.02  # 2% pérdida diaria
    weekly_loss_limit: float = 0.05  # 5% pérdida semanal
    max_consecutive_losses: int = 10
    cooldown_hours: int = 72  # Horas de pausa después del circuit breaker

    # Backtesting
    max_open_positions: int = 1

    # Rutas
    data_dir: str = os.path.join(os.path.dirname(__file__), "data", "raw")


@dataclass
class BacktestScenarios:
    """Diferentes escenarios de comisiones para probar robustez."""
    conservative: float = 0.001  # 0.1%
    intermediate: float = 0.00075  # 0.075%
    optimistic: float = 0.0005  # 0.05%


# Configuración por defecto
CONFIG = TradingConfig()
SCENARIOS = BacktestScenarios()
