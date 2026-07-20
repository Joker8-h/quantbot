"""Filtro de RIESGO por IA (NO predictor de precio).

El unico trabajo de este modulo es evaluar el nivel de riesgo del mercado
para decidir la disciplina de DCA:

  🟢 RIESGO BAJO   -> continuar DCA normal
  🟡 RIESGO MEDIO  -> reducir la compra periodica
  🔴 RIESGO ALTO   -> pausar nuevas compras

NO dice "compra porque va a subir". Solo senala situaciones de riesgo
elevado para no tomar malas decisiones emocionales.

NO vende automaticamente: la decision de pausar compras es distinta de
liquidar la posicion (evita sobreoptimizacion y panic-selling).
"""
import os
import json
from typing import Dict, Tuple

from openai import OpenAI

# Niveles de riesgo
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"

ACCIONES = {
    RISK_LOW: "Continuar DCA normal",
    RISK_MEDIUM: "Reducir la compra periodica",
    RISK_HIGH: "Pausar nuevas compras",
}

EMOJI = {RISK_LOW: "🟢", RISK_MEDIUM: "🟡", RISK_HIGH: "🔴"}


class RiskFilter:
    """Clasifica el riesgo del mercado usando OpenAI como filtro de contexto."""

    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key, timeout=10, max_retries=1) if self.api_key else None
        self._cache: Dict[str, Tuple[str, str]] = {}

    def _build_prompt(self, f: Dict) -> str:
        return (
            "Eres el filtro de RIESGO de un sistema de inversion automatica "
            "(DCA + buy&hold) en cripto. Tu unica funcion es evaluar si el "
            "mercado esta en una situacion de RIESGO ELEVADO para PAUSAR las "
            "nuevas compras. NO predicts precios ni digas si subira o bajara.\n\n"
            "Features actuales del mercado:\n"
            f"- Cambio % precio 7 dias: {f.get('return_7d'):.2f}\n"
            f"- Cambio % precio 30 dias: {f.get('return_30d'):.2f}\n"
            f"- ADX (0-100): {f.get('adx'):.1f}\n"
            f"- RSI (14): {f.get('rsi'):.1f}\n"
            f"- ATR % (volatilidad relativa): {f.get('atr_pct'):.2f}\n"
            f"- Ratio volumen actual/media: {f.get('vol_ratio'):.2f}\n"
            f"- Anchura Bollinger %: {f.get('bb_width_pct'):.2f}\n"
            f"- Drawdown actual desde maximo: {f.get('drawdown_pct'):.2f}\n\n"
            "Criterios:\n"
            "- Riesgo ALTO: volatilidad extrema (ATR% > 6 o BB% > 12), "
            "caida fuerte reciente, o euforia (+50% en 30d tras RSI > 75).\n"
            "- Riesgo MEDIO: volatilidad alta o tendencia debil/inestable.\n"
            "- Riesgo BAJO: mercado estable y sin extremos.\n\n"
            "Responde SOLO con JSON: "
            "{\"riesgo\": \"low|medium|high\", "
            "\"razon\": \"breve explicacion en espanol\"}"
        )

    def evaluate(self, features: Dict) -> Tuple[str, str]:
        """Devuelve (nivel_riesgo, razon)."""
        key = json.dumps(features, sort_keys=True, default=str)
        if key in self._cache:
            return self._cache[key]

        if not self.client:
            return self._fallback(features)

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": self._build_prompt(features)}],
                temperature=0.0,
                max_tokens=160,
            )
            text = resp.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            nivel = data.get("riesgo", "low")
            if nivel not in (RISK_LOW, RISK_MEDIUM, RISK_HIGH):
                nivel = RISK_LOW
            out = (nivel, data.get("razon", ""))
            self._cache[key] = out
            return out
        except Exception as e:
            print(f"[RiskFilter] error: {e} -> fallback")
            return self._fallback(features)

    def _fallback(self, f: Dict) -> Tuple[str, str]:
        """Clasificador deterministico de respaldo (no requiere API)."""
        atr_pct = f.get("atr_pct", 0)
        bb = f.get("bb_width_pct", 0)
        ret30 = f.get("return_30d", 0)
        rsi = f.get("rsi", 50)
        if atr_pct > 6 or bb > 12 or (ret30 > 50 and rsi > 75):
            return (RISK_HIGH, "Volatilidad extrema o euforia reciente")
        if atr_pct > 3.5 or bb > 8:
            return (RISK_MEDIUM, "Volatilidad alta, reducir compras")
        return (RISK_LOW, "Mercado estable")


if __name__ == "__main__":
    rf = RiskFilter(api_key=os.environ.get("OPENAI_API_KEY"))
    feat = {"return_7d": -8.0, "return_30d": -20.0, "adx": 18.0, "rsi": 38.0,
            "atr_pct": 4.5, "vol_ratio": 1.4, "bb_width_pct": 9.0, "drawdown_pct": -22.0}
    nivel, razon = rf.evaluate(feat)
    print(EMOJI[nivel], nivel, "-", razon)
