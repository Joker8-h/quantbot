"""Tasa de cambio USD -> COP en vivo, con cache y fallback.

Usa APIs publicas gratuitas (sin API key). Si todas fallan, cae al
valor de config (4200) para que el dashboard nunca se rompa.
"""
import time
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_FALLBACK = 4200.0
_CACHE_TTL = 3600  # 1 hora
_cache = {"rate": None, "ts": 0.0}

# Fuentes gratuitas sin API key (se intentan en orden).
_FUENTES = [
    ("https://open.er-api.com/v6/latest/USD", lambda d: d["rates"]["COP"]),
    ("https://api.exchangerate.host/latest?base=USD&symbols=COP", lambda d: d["rates"]["COP"]),
    ("https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
     lambda d: d["usd"]["cop"]),
]


def _descargar() -> Optional[float]:
    for url, extractor in _FUENTES:
        try:
            r = httpx.get(url, timeout=6.0)
            r.raise_for_status()
            valor = float(extractor(r.json()))
            if valor > 0:
                return valor
        except Exception as e:
            logger.warning("FX fuente fallo %s: %s", url, e)
    return None


def usd_to_cop() -> float:
    """Devuelve la tasa USD->COP (cacheada 1h). Fallback a 4200."""
    ahora = time.time()
    if _cache["rate"] and (ahora - _cache["ts"]) < _CACHE_TTL:
        return _cache["rate"]

    valor = _descargar()
    if valor:
        _cache["rate"] = valor
        _cache["ts"] = ahora
        return valor

    # Si ya habia un valor viejo en cache, es preferible al fallback fijo.
    if _cache["rate"]:
        return _cache["rate"]
    return _FALLBACK
