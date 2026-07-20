import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from database import Base


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user")  # admin, user
    currency_preference = Column(String(3), default="USD")  # USD, COP
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String(255), nullable=False)
    invited_by = Column(String, ForeignKey("users.id"))
    token = Column(String(100), unique=True, nullable=False)
    used = Column(Boolean, default=False)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ExchangeConnection(Base):
    __tablename__ = "exchange_connections"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    exchange = Column(String(50), nullable=False)
    api_key_encrypted = Column(Text, nullable=False)
    api_secret_encrypted = Column(Text, nullable=False)
    testnet = Column(Boolean, default=True)  # True = Spot Testnet (dinero ficticio)
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Trade(Base):
    __tablename__ = "trades"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # LONG, SHORT
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    quantity = Column(Float, nullable=False)
    pnl = Column(Float)
    pnl_usd = Column(Float)
    pnl_cop = Column(Float)
    fee = Column(Float)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime)
    exit_reason = Column(String(50))
    status = Column(String(20), default="open")  # open, closed


class BalanceSnapshot(Base):
    __tablename__ = "balance_snapshots"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    total_balance_usd = Column(Float)
    total_balance_cop = Column(Float)
    available_usd = Column(Float)
    unrealized_pnl_usd = Column(Float)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    alert_type = Column(String(50), nullable=False)
    channel = Column(String(20), nullable=False)  # whatsapp, telegram, email
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class UserContact(Base):
    __tablename__ = "user_contacts"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    phone = Column(String(20))
    telegram_chat_id = Column(String(50))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SystemStatus(Base):
    __tablename__ = "system_status"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    is_running = Column(Boolean, default=False)
    last_trade_time = Column(DateTime)
    last_signal = Column(String(20))
    total_pnl_usd = Column(Float, default=0.0)
    today_pnl_usd = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

