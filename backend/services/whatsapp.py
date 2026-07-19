import httpx
import logging
from config import config

logger = logging.getLogger(__name__)

WHATSAPP_API = None  # Will be set from config


async def send_whatsapp(message: str, phone: str = None) -> bool:
    service_url = config.WHATSAPP_SERVICE_URL

    if not service_url:
        logger.warning("WhatsApp service not configured")
        return False

    target_phone = phone or config.WHATSAPP_PHONE
    payload = {"message": message, "phone": target_phone}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{service_url}/send", json=payload, timeout=15)
            if resp.status_code == 200:
                logger.info("WhatsApp message sent")
                return True
            else:
                logger.error(f"WhatsApp error: {resp.status_code} {resp.text}")
                return False
    except Exception as e:
        logger.error(f"WhatsApp send failed: {e}")
        return False


async def get_whatsapp_status() -> dict:
    service_url = config.WHATSAPP_SERVICE_URL

    if not service_url:
        return {"status": "not_configured", "ready": False}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{service_url}/health", timeout=5)
            if resp.status_code == 200:
                return resp.json()
            return {"status": "error", "ready": False}
    except Exception:
        return {"status": "offline", "ready": False}

