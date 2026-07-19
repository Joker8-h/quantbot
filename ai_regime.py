"""Modulo de clasificacion de regimen de mercado usando OpenAI como FILTRO.

IMPORTANTE: La IA NO predice precios. Solo clasifica el tipo de mercado
(tendencia_alcista / tendencia_bajista / lateral / volatil) a partir de
features numericas, y recomienda si operar o no. La decision final y el
riesgo los maneja la logica matematica (RiskManager), no la IA.

Uso:
    from ai_regime import AIRegimeClassifier
    clf = AIRegimeClassifier()
    label, confianza, operar = clf.classify(features_dict)
"""
import os
import json
from typing import Dict, Tuple

from openai import OpenAI


class AIRegimeClassifier:
    """Clasifica el regimen de mercado usando un LLM como filtro de contexto."""

    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self._cache: Dict[str, Tuple[str, float, bool]] = {}

    def _build_prompt(self, f: Dict) -> str:
        return (
            "Eres un filtro de riesgo para un bot de trading de cripto spot. "
            "Tu unica tarea es clasificar el regimen de mercado y decidir si "
            "TIENE SENTIDO operar siguiendo una estrategia de seguimiento de "
            "tendencia long-only con stop loss y take profit 1:2.\n\n"
            "NO predigas el precio. Solo clasifica y recomienda.\n\n"
            "Features del mercado (ventana reciente):\n"
            f"- Cambio % reciente del precio: {f.get('return_pct'):.2f}\n"
            f"- ADX (fuerza de tendencia, 0-100): {f.get('adx'):.1f}\n"
            f"- RSI (14): {f.get('rsi'):.1f}\n"
            f"- ATR % (volatilidad relativa): {f.get('atr_pct'):.2f}\n"
            f"- Ratio volumen actual / media: {f.get('vol_ratio'):.2f}\n"
            f"- Pendiente EMA(20) vs EMA(50) (alcista si >0): {f.get('ema_slope'):.4f}\n"
            f"- Anchura Bollinger %: {f.get('bb_width_pct'):.2f}\n\n"
            "Responde SOLO con JSON: "
            "{\"regimen\": \"tendencia_alcista|tendencia_bajista|lateral|volatil\", "
            "\"confianza\": 0.0-1.0, \"operar\": true|false, "
            "\"razon\": \"breve explicacion\"}"
        )

    def classify(self, features: Dict) -> Tuple[str, float, bool]:
        """Devuelve (regimen, confianza, operar)."""
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
                max_tokens=150,
            )
            text = resp.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            out = (
                data.get("regimen", "lateral"),
                float(data.get("confianza", 0.5)),
                bool(data.get("operar", False)),
            )
            self._cache[key] = out
            return out
        except Exception as e:
            print(f"[AIRegime] error: {e} -> fallback")
            return self._fallback(features)

    def _fallback(self, f: Dict) -> Tuple[str, float, bool]:
        """Clasificador deterministico de respaldo (no requiere API)."""
        adx = f.get("adx", 0)
        ema_slope = f.get("ema_slope", 0)
        atr_pct = f.get("atr_pct", 0)
        if atr_pct > 5.0:
            return ("volatil", 0.6, False)
        if adx > 25 and ema_slope > 0:
            return ("tendencia_alcista", 0.7, True)
        if adx > 25 and ema_slope < 0:
            return ("tendencia_bajista", 0.7, False)
        return ("lateral", 0.6, False)


if __name__ == "__main__":
    clf = AIRegimeClassifier(api_key=os.environ.get("OPENAI_API_KEY"))
    feat = {"return_pct": 2.1, "adx": 32.0, "rsi": 58.0, "atr_pct": 1.5,
            "vol_ratio": 1.3, "ema_slope": 0.0021, "bb_width_pct": 3.2}
    print(clf.classify(feat))
