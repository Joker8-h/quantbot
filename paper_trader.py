import json
import time
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional
import websocket
import threading
import pandas as pd
from config import CONFIG
from indicators import Indicators
from strategy import Strategy
from risk_manager import RiskManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class PaperTrader:
    def __init__(self):
        self.capital = CONFIG.initial_capital
        self.balance = CONFIG.initial_capital
        self.position = None
        self.risk_manager = RiskManager(CONFIG)
        self.indicators = Indicators(CONFIG)
        self.strategy = Strategy(CONFIG)
        self.ws = None
        self.current_price = 0
        self.klines = []
        self.running = False
        self.last_signal_time = None
        self.cooldown_until = None
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect("quantbot.db")
        conn.execute("""CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            symbol TEXT,
            side TEXT,
            entry_price REAL,
            exit_price REAL,
            quantity REAL,
            pnl REAL,
            pnl_usd REAL,
            fee REAL,
            entry_time TEXT,
            exit_time TEXT,
            exit_reason TEXT,
            status TEXT DEFAULT 'open',
            strategy TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS balance_snapshots (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            total_balance_usd REAL,
            available_usd REAL,
            unrealized_pnl_usd REAL,
            timestamp TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS system_status (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT 'system',
            is_running INTEGER DEFAULT 0,
            last_trade_time TEXT,
            last_signal TEXT,
            total_pnl_usd REAL DEFAULT 0,
            today_pnl_usd REAL DEFAULT 0
        )""")
        conn.commit()
        conn.close()

    def _db(self):
        return sqlite3.connect("quantbot.db")

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get('e') == 'kline':
                kline = data['k']
                self.current_price = float(kline['c'])
                self.update_kline(kline)
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def update_kline(self, kline):
        candle = {
            'datetime': datetime.fromtimestamp(kline['t'] / 1000, tz=timezone.utc),
            'open': float(kline['o']),
            'high': float(kline['h']),
            'low': float(kline['l']),
            'close': float(kline['c']),
            'volume': float(kline['v']),
        }

        if len(self.klines) == 0 or candle['datetime'] > self.klines[-1]['datetime']:
            self.klines.append(candle)
            if len(self.klines) > 200:
                self.klines = self.klines[-200:]
            self.process_candle()

    def process_candle(self):
        if len(self.klines) < 50:
            return

        df = pd.DataFrame(self.klines)
        df = self.indicators.add_all(df)
        df = self.strategy.generate_signals(df)

        if self.position:
            self.check_exit(df)
        else:
            self.check_entry(df)

        self.update_system_status()

    def check_entry(self, df):
        if self.cooldown_until and datetime.now(timezone.utc) < self.cooldown_until:
            return

        last_row = df.iloc[-1]
        signal = last_row.get('signal', 0)

        if signal == 1:
            self.enter_position('LONG', df)
        elif signal == -1:
            self.enter_position('SHORT', df)

    def enter_position(self, side, df):
        entry_price = self.current_price
        atr_value = df.iloc[-1].get('atr', 0)
        stop_loss = self.risk_manager.calculate_stop_loss(entry_price, atr_value, side)
        take_profit = self.risk_manager.calculate_take_profit(entry_price, abs(entry_price - stop_loss), side)
        quantity = self.risk_manager.calculate_position_size(
            self.balance, entry_price, stop_loss, CONFIG.fee, CONFIG.slippage
        )

        self.position = {
            'side': side,
            'entry_price': entry_price,
            'quantity': quantity,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_time': datetime.now(timezone.utc),
        }

        self.save_trade(side, entry_price, quantity)
        logger.info(f"{side} entry at ${entry_price:.2f}, SL: ${stop_loss:.2f}, TP: ${take_profit:.2f}")

    def check_exit(self, df):
        if not self.position:
            return

        price = self.current_price
        side = self.position['side']
        stop_loss = self.position['stop_loss']
        take_profit = self.position['take_profit']

        exit_reason = None

        if side == 'LONG':
            if price <= stop_loss:
                exit_reason = 'stop_loss'
            elif price >= take_profit:
                exit_reason = 'take_profit'
        elif side == 'SHORT':
            if price >= stop_loss:
                exit_reason = 'stop_loss'
            elif price <= take_profit:
                exit_reason = 'take_profit'

        if exit_reason:
            self.close_position(price, exit_reason)

    def close_position(self, exit_price, exit_reason):
        if not self.position:
            return

        entry_price = self.position['entry_price']
        quantity = self.position['quantity']
        side = self.position['side']

        if side == 'LONG':
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity

        fee = exit_price * quantity * CONFIG.fee
        net_pnl = pnl - fee
        self.balance += net_pnl

        logger.info(f"Closed {side} at ${exit_price:.2f}, PnL: ${net_pnl:.2f} ({exit_reason})")

        self.update_trade(side, entry_price, exit_price, pnl, fee, exit_reason)

        if net_pnl < 0 and abs(net_pnl) / self.capital > 0.05:
            self.cooldown_until = datetime.now(timezone.utc) + timedelta(hours=CONFIG.cooldown_hours)
            logger.warning("Circuit breaker activated")

        self.position = None
        self.last_signal_time = datetime.now(timezone.utc)

    def save_trade(self, side, entry_price, quantity):
        import uuid
        conn = self._db()
        conn.execute(
            "INSERT INTO trades (id, symbol, side, entry_price, quantity, entry_time, status, strategy) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), CONFIG.symbols[0], side, entry_price, quantity,
             datetime.now(timezone.utc).isoformat(), 'open', 'v3')
        )
        conn.commit()
        conn.close()

    def update_trade(self, side, entry_price, exit_price, pnl, fee, exit_reason):
        conn = self._db()
        conn.execute(
            "UPDATE trades SET exit_price=?, pnl=?, fee=?, exit_reason=?, exit_time=?, status='closed' WHERE side=? AND status='open'",
            (exit_price, pnl, fee, exit_reason, datetime.now(timezone.utc).isoformat(), side)
        )
        conn.commit()
        conn.close()

    def update_system_status(self):
        conn = self._db()
        now = datetime.now(timezone.utc).isoformat()
        pnl = self.balance - self.capital
        conn.execute(
            "INSERT OR REPLACE INTO system_status (id, user_id, is_running, last_trade_time, total_pnl_usd, updated_at) VALUES ('system', 'system', ?, ?, ?, ?)",
            (1 if self.running else 0, now if self.position else None, pnl, now)
        )
        conn.commit()
        conn.close()

    def save_balance_snapshot(self):
        import uuid
        unrealized_pnl = 0
        if self.position:
            if self.position['side'] == 'LONG':
                unrealized_pnl = (self.current_price - self.position['entry_price']) * self.position['quantity']
            else:
                unrealized_pnl = (self.position['entry_price'] - self.current_price) * self.position['quantity']

        conn = self._db()
        conn.execute(
            "INSERT INTO balance_snapshots (id, user_id, total_balance_usd, available_usd, unrealized_pnl_usd, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), 'system', self.balance, self.balance - unrealized_pnl, unrealized_pnl,
             datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()

    def on_open(self, ws):
        logger.info("WebSocket connected")
        self.running = True

    def on_close(self, ws, close_status_code, close_msg):
        logger.info("WebSocket disconnected")
        self.running = False
        time.sleep(5)
        self.connect()

    def on_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")

    def connect(self):
        symbol = CONFIG.symbols[0].lower().replace('/', '')
        ws_url = f"wss://stream.binance.com:9443/ws/{symbol}@kline_1h"
        logger.info(f"Connecting to {ws_url}")

        self.ws = websocket.WebSocketApp(
            ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()

    def start(self):
        logger.info("Starting Paper Trader...")
        self.connect()

        while True:
            time.sleep(60)
            if self.running:
                self.save_balance_snapshot()


if __name__ == '__main__':
    trader = PaperTrader()
    trader.start()
