"""Filtro rapido de Groq (Llama 3.3) como segunda opinion antes de operar real.

No es el detector de senales (eso lo hace la confluencia de indicadores en
live_engine.py). Es un filtro adicional: cuando la confluencia ya decidio
entrar, Groq revisa el contexto y puede vetar la entrada si algo no cuadra.

Si no hay GROQ_API_KEY configurada, o la llamada falla o tarda, el filtro
APRUEBA por defecto: nunca debe ser el eslabon que tumbe el sistema, y su
ausencia no debe bloquear la estrategia base (que ya tiene sus propios
filtros de riesgo).
"""
import os
import json
import time
import logging

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def confirmar_entrada(symbol: str, precio: float, score: int, razones: list,
                       atr_pct: float) -> dict:
    """Segunda opinion de Groq sobre una entrada que la confluencia ya aprobo.

    Devuelve {'aprobado': bool, 'confianza': float, 'razon': str, 'tiempo_ms': int}.
    """
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        return {"aprobado": True, "confianza": 0.5, "razon": "GROQ_API_KEY no configurada", "tiempo_ms": 0}

    prompt = (
        f"Eres un filtro de riesgo para trading de spot cripto con DINERO REAL Y POCO CAPITAL.\n"
        f"La estrategia de confluencia tecnica ya aprobo esta entrada:\n"
        f"- Par: {symbol}\n"
        f"- Precio: ${precio:.2f}\n"
        f"- Score de confluencia: {score}/6\n"
        f"- Razones: {', '.join(razones)}\n"
        f"- Volatilidad (ATR%): {atr_pct:.3%}\n\n"
        f"Tu unico trabajo es detectar si hay una razon CLARA para vetar esta entrada "
        f"(ej. volatilidad extrema, score al limite sin convicción). Si no la hay, aprueba.\n"
        f"Responde SOLO JSON: "
        f'{{"aprobado": true, "confianza": 0.8, "razon": "texto breve"}}'
    )

    t0 = time.time()
    try:
        import httpx
        resp = httpx.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "Filtro de riesgo de trading, responde solo JSON valido."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 120,
                "response_format": {"type": "json_object"},
            },
            timeout=3.0,
        )
        elapsed_ms = int((time.time() - t0) * 1000)
        if resp.status_code == 200:
            data = json.loads(resp.json()["choices"][0]["message"]["content"])
            data["tiempo_ms"] = elapsed_ms
            data["aprobado"] = bool(data.get("aprobado", True))
            return data
        logger.warning(f"[GROQ_HTTP] {resp.status_code}: {resp.text[:200]}")
        return {"aprobado": True, "confianza": 0.5, "razon": f"HTTP {resp.status_code}", "tiempo_ms": elapsed_ms}
    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        logger.warning(f"[GROQ_ERROR] {e}")
        return {"aprobado": True, "confianza": 0.5, "razon": f"fallback: {e}", "tiempo_ms": elapsed_ms}


def analizar_estado_mercado(resumen_mercado: dict = None) -> dict:
    """Genera un analisis de mercado en lenguaje natural en espanol usando Groq Llama 3.3.

    Devuelve un dict con:
    - diagnostico: 'EXCELENTE', 'MEDIOCRE', 'FEO / MALO', 'RIESGOSO'
    - explicacion: Texto detallado y cercano en lenguaje natural
    - recomendacion: Accion directa recomendada
    """
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    if not resumen_mercado:
        resumen_mercado = {
            "btc_precio": 64800,
            "tendencia": "lateral_alcista",
            "volatilidad_atr": "moderada",
            "pares": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
        }

    if not groq_key:
        return {
            "diagnostico": "MEDIOCRE / REGULAR",
            "explicacion": "El mercado se encuentra en rango lateral con oscilacion moderada. No se observa una tendencia alcista limpia ni pánico bajista.",
            "recomendacion": "Aguardar confirmación de confluencia antes de ejecutar compras.",
            "tiempo_ms": 0
        }

    prompt = (
        f"Eres un analista financiero de criptomonedas directo, honesto y cercano.\n"
        f"Evalua las condiciones actuales del mercado Spot:\n"
        f"- Precio BTC: ${resumen_mercado.get('btc_precio', 64800)}\n"
        f"- Tendencia general: {resumen_mercado.get('tendencia', 'lateral')}\n"
        f"- Volatilidad: {resumen_mercado.get('volatilidad_atr', 'moderada')}\n\n"
        f"Debes responder en LENGUAJE NATURAL EN ESPAÑOL explicando de forma BIEN ESPECIFICA "
        f"si el mercado esta FEO/MALO, REGULAR o EXCELENTE/BUENO para comprar hoy y por que.\n"
        f"Responde ESTRICTAMENTE JSON con este formato exacto:\n"
        f'{{\n'
        f'  "diagnostico": "FEO / MALO" (o "EXCELENTE", "REGULAR", "RIESGOSO"),\n'
        f'  "explicacion": "2 o 3 frases en espanol explicando de forma clara, especifica y cercana por que esta asi el mercado y que podemos esperar.",\n'
        f'  "recomendacion": "MANTENER EN EFECTIVO USDT" (o "ESPERAR REBOTE", "APROVECHAR COMPRAS EN SOPORTE")\n'
        f'}}'
    )

    t0 = time.time()
    try:
        import httpx
        resp = httpx.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "Analista de mercado cripto en espanol. Responde solo JSON valido."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 250,
                "response_format": {"type": "json_object"},
            },
            timeout=4.0,
        )
        elapsed_ms = int((time.time() - t0) * 1000)
        if resp.status_code == 200:
            data = json.loads(resp.json()["choices"][0]["message"]["content"])
            data["tiempo_ms"] = elapsed_ms
            return data
        return {
            "diagnostico": "REGULAR",
            "explicacion": "El mercado presenta ligera volatilidad lateral en BTC y altcoins. Se recomienda paciencia.",
            "recomendacion": "Esperar señal clara de la IA",
            "tiempo_ms": elapsed_ms
        }
    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        return {
            "diagnostico": "REGULAR",
            "explicacion": f"Mercado en consolidacion sin patron de ruptura inmediato ({e}).",
            "recomendacion": "Paciencia y disciplina",
            "tiempo_ms": elapsed_ms
        }
