"""Definicion de los modos de QuantBot (arquitectura final de Vill).

🟢 CONSERVADOR : DCA + Buy & Hold + filtro de riesgo IA. No vende.
🟡 MODERADO    : DCA + rebalanceo periodico + gestion de exposicion.
🔴 EXPERIMENTAL: estrategias activas, SOLO paper trading (sin dinero real).

El sistema puede reportar honestamente:
  Modo activo:     No ha demostrado ventaja (paper trading solo)
  Modo conservador: Activo
  Modo experimental: Solo simulacion
"""
from enum import Enum


class Modo(str, Enum):
    CONSERVADOR = "conservador"
    MODERADO = "moderado"
    EXPERIMENTAL = "experimental"


MODOS = {
    Modo.CONSERVADOR: {
        "nombre": "Conservador",
        "emoji": "🟢",
        "descripcion": "DCA automatico + Buy & Hold + filtro de riesgo por IA. No vende automaticamente.",
        "usa_ia_riesgo": True,
        "puede_operar_real": True,
        "estrategia_activa": False,
    },
    Modo.MODERADO: {
        "nombre": "Moderado",
        "emoji": "🟡",
        "descripcion": "DCA + rebalanceo periodico + gestion de exposicion entre activos.",
        "usa_ia_riesgo": True,
        "puede_operar_real": True,
        "estrategia_activa": False,
    },
    Modo.EXPERIMENTAL: {
        "nombre": "Experimental",
        "emoji": "🔴",
        "descripcion": "Estrategias activas. SOLO simulacion (paper trading). No usa dinero real.",
        "usa_ia_riesgo": False,
        "puede_operar_real": False,
        "estrategia_activa": True,
    },
}

MODO_DEFECTO = Modo.CONSERVADOR
