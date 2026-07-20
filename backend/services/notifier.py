"""Notificador de riesgo: dispara alertas a Telegram y WhatsApp.

Cuando el nivel de riesgo del mercado sube (medium/alto), QuantBot avisa
al usuario por los canales que tenga configurados. Esto es parte del
filtro de riesgo IA del Modo Conservador: la IA no predice precio, solo
avisa cuando el riesgo esta alto para pausar/comprar menos.

No envia spam: solo notifica cuando el nivel CAMBIA respecto al anterior
 guardado en estado_riesgo.json.
"""
import os
import json
import asyncio
import logging

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ESTADO_PATH = os.path.join(ROOT, "estado_riesgo.json")

logger = logging.getLogger(__name__)


def _leer_nivel_previo() -> str:
    if not os.path.exists(ESTADO_PATH):
        return ""
    try:
        with open(ESTADO_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("nivel", "")
    except Exception:
        return ""


def _guardar_nivel(nivel: str):
    try:
        with open(ESTADO_PATH, "w", encoding="utf-8") as f:
            json.dump({"nivel": nivel}, f)
    except Exception:
        pass


async def notificar_cambio_riesgo(nivel: str, accion: str, razon: str,
                                   precio: float = None, phone: str = None):
    """Notifica solo si el nivel de riesgo cambio.

    Devuelve True si se envio alguna notificacion.
    """
    previo = _leer_nivel_previo()
    if previo == nivel:
        return False

    _guardar_nivel(nivel)

    # Solo alertar cuando sube el riesgo (medium/alto)
    if nivel not in ("medium", "high"):
        return False

    from services.telegram import send_telegram, format_risk_alert
    from services.whatsapp import send_whatsapp

    msg = format_risk_alert(nivel, accion, razon, precio)
    wa_msg = f"*Alerta de Riesgo*\nNivel: {nivel.upper()}\nAccion: {accion}" + \
             (f"\nPrecio: ${precio:,.2f}" if precio else "") + f"\n{razon}"

    # Enviar en paralelo a ambos canales
    try:
        await asyncio.gather(
            send_telegram(msg),
            send_whatsapp(wa_msg, phone=phone),
        )
        return True
    except Exception as e:
        logger.error(f"Error enviando alertas de riesgo: {e}")
        return False
