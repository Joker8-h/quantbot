"""Notificador de riesgo: evalua el mercado y envia alerta por Telegram/WhatsApp
cuando el nivel de riesgo cambia (ej. de bajo a alto). Se ejecuta en un cron
(en Railway como scheduled job o en el backend periodicamente).

NO vende ni opera. Solo avisa al usuario para que tome decisiones disciplinadas.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import asyncio
import sys
import importlib.util

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Registrar backend/config como modulo 'config' para que los servicios del
# backend (telegram, etc.) lo resuelvan. Los modulos raiz (indicators,
# data_collector) resuelven su propio CONFIG por ruta de archivo.
_spec = importlib.util.spec_from_file_location(
    "config", os.path.join(ROOT, "backend", "config.py"))
_bcfg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bcfg)
sys.modules["config"] = _bcfg
backend_config = _bcfg.config

from backend.services.investment import estado_completo
from backend.services.telegram import format_risk_alert, send_telegram
from risk_filter import EMOJI

STATE_FILE = os.path.join(ROOT, "ultimo_riesgo.json")


def _leer_ultimo() -> str:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""


def _guardar(nivel: str):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(nivel)


async def notificar(symbol: str = "BTC/USDT"):
    r = estado_completo(symbol=symbol, api_key=backend_config.OPENAI_API_KEY)
    if r.get("error"):
        print("sin datos:", r["error"])
        return
    nivel = r["riesgo"]
    ultimo = _leer_ultimo()
    if nivel != ultimo:
        msg = format_risk_alert(nivel, r["accion"], r["razon"], r["precio"])
        await send_telegram(msg)
        _guardar(nivel)
        print(f"Alerta enviada: {EMOJI.get(nivel)} {nivel} -> {r['accion']}")
    else:
        print(f"Sin cambio de riesgo ({nivel}). Sin alerta.")


if __name__ == "__main__":
    asyncio.run(notificar())
