import httpx
import logging
from config import config

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


async def send_telegram(message: str, chat_id: str = None) -> bool:
    token = config.TELEGRAM_BOT_TOKEN
    target = chat_id or config.TELEGRAM_CHAT_ID

    if not token or not target:
        logger.warning("Telegram not configured, skipping notification")
        return False

    url = TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": target,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Telegram message sent")
                return True
            else:
                logger.error(f"Telegram error: {resp.status_code} {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


def format_trade_alert(side: str, symbol: str, entry_price: float, stop_loss: float, take_profit: float) -> str:
    emoji = "🟢" if side == "LONG" else "🔴"
    return (
        f"{emoji} <b>{side} {symbol}</b>\n"
        f"Entrada: ${entry_price:,.2f}\n"
        f"Stop Loss: ${stop_loss:,.2f}\n"
        f"Take Profit: ${take_profit:,.2f}"
    )


def format_trade_closed(side: str, symbol: str, exit_price: float, pnl: float, reason: str) -> str:
    emoji = "✅" if pnl >= 0 else "❌"
    return (
        f"{emoji} <b>{side} {symbol} CERRADA</b>\n"
        f"Salida: ${exit_price:,.2f}\n"
        f"PnL: ${pnl:+,.2f}\n"
        f"Razón: {reason}"
    )


def format_daily_summary(total_pnl: float, trades_today: int, win_rate: float) -> str:
    emoji = "📈" if total_pnl >= 0 else "📉"
    return (
        f"{emoji} <b>Resumen Diario</b>\n"
        f"PnL Hoy: ${total_pnl:+,.2f}\n"
        f"Operaciones: {trades_today}\n"
        f"Win Rate: {win_rate:.1f}%"
    )


def format_system_alert(message: str) -> str:
    return f"⚠️ <b>Sistema</b>\n{message}"


def format_risk_alert(nivel: str, accion: str, razon: str, precio: float = None) -> str:
    emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(nivel, "🟢")
    precio_txt = f"\nPrecio: ${precio:,.2f}" if precio else ""
    return (
        f"{emoji} <b>Alerta de Riesgo</b>\n"
        f"Nivel: {nivel.upper()}\n"
        f"Acción: {accion}{precio_txt}\n"
        f"🤖 {razon}"
    )
