import os
from datetime import datetime, timezone


def _normalizar_db_url(url: str) -> str:
    """Railway entrega postgres://; SQLAlchemy 2.0 exige postgresql://."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "quantbot-secret-key-change-in-production")
    DATABASE_URL = _normalizar_db_url(os.getenv("DATABASE_URL", "sqlite:///./quantbot.db"))
    # Directorio persistente para estado (DCA, riesgo). En Railway se monta
    # un volumen y se apunta STATE_DIR ahi para no perder datos en cada deploy.
    STATE_DIR = os.getenv("STATE_DIR", "")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7870141447:AAHgAR2gC2GhuqdjEwT-2emn679jKKabMYc")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7880666154")

    # WhatsApp
    WHATSAPP_SERVICE_URL = os.getenv("WHATSAPP_SERVICE_URL", "http://localhost:3001")
    WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE", "+573166575904")
    WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY", "")

    # OpenAI (filtro de RIESGO, no predictor de precio)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Exchange
    DEFAULT_EXCHANGE = "binance"

    # Currency
    USD_TO_COP_RATE = 4200  # Default, will be updated via API


config = Config()

