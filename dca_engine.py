"""Motor de DCA (Dollar Cost Averaging) + Buy & Hold de largo plazo.

Responsabilidades:
- Calcular las compras programadas periodicas (ej. mensual).
- Registrar el estado de la inversion (capital invertido, valor actual, ganancia).
- Aplicar la disciplina de riesgo del RiskFilter:
    bajo   -> comprar monto normal
    medio  -> comprar monto reducido (mitad)
    alto   -> pausar nueva compra (NO vender)
- NUNCA vende automaticamente. El DCA acumula y mantiene.

El motor es determinista y no requiere IA para funcionar; la IA solo
aporta el nivel de riesgo usado para ajustar el monto.
"""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict


@dataclass
class Compra:
    fecha: str
    monto_usd: float
    precio: float
    cantidad: float
    riesgo: str


@dataclass
class EstadoInversion:
    capital_invertido: float = 0.0
    valor_actual: float = 0.0
    ganancia: float = 0.0
    ganancia_pct: float = 0.0
    riesgo: str = "low"
    accion: str = "Continuar DCA normal"
    razon: str = ""
    proxima_compra: str = ""
    pausado: bool = False
    compras: List[Dict] = field(default_factory=list)


class DCAEngine:
    def __init__(self, db_path: str = "dca_state.json"):
        self.db_path = db_path
        self.state = self._cargar()

    def _cargar(self) -> dict:
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "monto_base_usd": 50.0,
            "compras": [],
            "pausado_manual": False,
        }

    def _guardar(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    def configurar(self, monto_base_usd: float = None, pausado_manual: bool = None):
        if monto_base_usd is not None:
            self.state["monto_base_usd"] = monto_base_usd
        if pausado_manual is not None:
            self.state["pausado_manual"] = pausado_manual
        self._guardar()

    def monto_para_riesgo(self, riesgo: str) -> float:
        base = self.state["monto_base_usd"]
        if riesgo == "high":
            return 0.0
        if riesgo == "medium":
            return base / 2.0
        return base

    def ejecutar_compra(self, precio: float, riesgo: str, razon: str = ""):
        if self.state.get("pausado_manual", False):
            return None
        monto = self.monto_para_riesgo(riesgo)
        if monto <= 0:
            return None
        cantidad = monto / precio
        compra = {
            "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "monto_usd": round(monto, 2),
            "precio": round(precio, 2),
            "cantidad": round(cantidad, 8),
            "riesgo": riesgo,
            "razon": razon,
        }
        self.state["compras"].append(compra)
        self._guardar()
        return compra

    def estado(self, precio_actual: float, riesgo: str = "low",
               razon: str = "", accion: str = "Continuar DCA normal",
               proxima_compra: str = "") -> EstadoInversion:
        compras = self.state["compras"]
        capital = sum(c["monto_usd"] for c in compras)
        cantidad_total = sum(c["cantidad"] for c in compras)
        valor = cantidad_total * precio_actual
        ganancia = valor - capital
        ganancia_pct = (ganancia / capital * 100) if capital > 0 else 0.0
        pausado = (riesgo == "high") or self.state.get("pausado_manual", False)
        return EstadoInversion(
            capital_invertido=round(capital, 2),
            valor_actual=round(valor, 2),
            ganancia=round(ganancia, 2),
            ganancia_pct=round(ganancia_pct, 2),
            riesgo=riesgo,
            accion=accion,
            razon=razon,
            proxima_compra=proxima_compra,
            pausado=pausado,
            compras=compras,
        )


if __name__ == "__main__":
    eng = DCAEngine(db_path="dca_state_test.json")
    eng.configurar(monto_base_usd=50.0)
    eng.ejecutar_compra(precio=30000.0, riesgo="low", razon="Mercado estable")
    st = eng.estado(precio_actual=32000.0, riesgo="low", accion="Continuar DCA normal")
    print(st)
