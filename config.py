import os
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List


@dataclass
class TradingConfig:
    # Capital
    initial_capital: float = 100.0

    # Simbolos y temporalidades
    symbols: List[str] = field(default_factory=lambda: ["BTC/USDT"])
    timeframes: List[str] = field(default_factory=lambda: ["1h"])

    # Periodo de datos historicos
    start_date: str = "2019-01-01"
    end_date: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Indicadores base
    ema_fast: int = 20
    ema_slow: int = 50
    rsi_period: int = 14
    rsi_threshold: int = 50
    atr_period: int = 14
    volume_avg_period: int = 20

    # Pullback strategy
    pullback_window: int = 3  # Lookback para detectar pullback
    bounce_threshold: float = 0.002  # 0.2% bounce minimum

    # Indicadores nuevos
    adx_period: int = 14
    adx_threshold: int = 25
    bb_period: int = 20
    bb_std: float = 2.0

    # Sistema de puntuacion (confluencia)
    min_score: int = 4

    # Market Regime
    lateral_adx_threshold: int = 20
    volatile_atr_multiplier: float = 2.0

    # Riesgo
    risk_per_trade: float = 0.005  # 0.5% del capital
    rr_ratio: float = 2.0  # Risk/Reward 1:2
    atr_sl_multiplier: float = 3.0  # Stop Loss = 3.0 * ATR
    max_open_positions: int = 2

    # Trailing Stop - ACTIVADO para proteger ganancias
    trail_atr_multiplier: float = 1.0  # Trailing stop a 1.0 * ATR

    # Comisiones y slippage
    fee: float = 0.001  # 0.1% por operacion
    slippage: float = 0.0005  # 0.05%

    # Circuit breakers
    daily_loss_limit: float = 0.02  # 2% perdida diaria
    weekly_loss_limit: float = 0.05  # 5% perdida semanal
    max_consecutive_losses: int = 3
    cooldown_hours: int = 24  # Pausa 24h despues de 3 losses consecutivas

    # Minimo espacio entre trades
    min_bars_between_trades: int = 168  # 7 dias en 1h (optimizado)

    # Backtesting
    max_open_positions: int = 2

    # Escenarios de costos (para testing)
    scenario_optimistic_fee: float = 0.00075
    scenario_optimistic_slippage: float = 0.0003
    scenario_pessimistic_fee: float = 0.0015
    scenario_pessimistic_slippage: float = 0.001

    # Rutas
    data_dir: str = os.path.join(os.path.dirname(__file__), "data", "raw")


@dataclass
class BacktestScenarios:
    """Diferentes escenarios de comisiones para probar robustez."""
    conservative: float = 0.001  # 0.1%
    intermediate: float = 0.00075  # 0.075%
    optimistic: float = 0.0005  # 0.05%


# Configuracion por defecto
CONFIG = TradingConfig()
SCENARIOS = BacktestScenarios()
