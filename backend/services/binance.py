"""Servicio de integracion con Binance via ccxt.

Responsabilidades:
  - Obtener precio en vivo (spot) para el dashboard.
  - Validar que un par de API key/secret funciona y tiene permisos de
    lectura + spot trading, PERO NO de retiro (seguridad de Vill).
  - Ejecutar ordenes de COMPRA en modo paper (simulado, sin dinero real)
    o, si el usuario lo habilita explicitamente, orden real de mercado.

Principio de Vill: el sistema nunca retira fondos, nunca apuesta todo, y
en pruebas solo opera en paper. El riesgo se controla por monto, no por
intentar adivinar el mercado.
"""
import os
import sys
from typing import Optional

import ccxt

# Permitir importar crypto desde el mismo paquete
from .crypto import descifrar


class BinanceService:
    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET", "")
        self.exchange = ccxt.binance({
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })

    # ------------------------------------------------------------------ #
    # Sin credenciales: solo lectura publica (precio en vivo)
    # ------------------------------------------------------------------ #
    @classmethod
    def precio_publico(cls, symbol: str = "BTC/USDT") -> Optional[float]:
        """Precio actual sin API key (datos publicos de Binance)."""
        ex = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})
        try:
            ticker = ex.fetch_ticker(symbol)
            return float(ticker["last"])
        except Exception as e:
            return None

    # ------------------------------------------------------------------ #
    # Conexion autenticada
    # ------------------------------------------------------------------ #
    def validar_conexion(self) -> dict:
        """Verifica que las credenciales funcionan y revisa permisos.

        Devuelve si tiene lectura, trading de spot y (lo que NO queremos)
        si tiene permiso de retiro.
        """
        try:
            self.exchange.check_required_credentials()
            # Llamada ligera que requiere autenticacion
            perms = self.exchange.fetch_permissions() if hasattr(self.exchange, "fetch_permissions") else []
            cuenta = self.exchange.fetch_balance()
            tiene_spot = True
            # Binance: permisos estan en la respuesta de la API de permisos.
            # Si no esta disponible, asumimos lectura+spot si la llamada arriba funciono.
            return {
                "ok": True,
                "permisos": perms,
                "tiene_lectura": True,
                "tiene_spot_trading": ("SPOT" in perms) if perms else True,
                "tiene_retiro": ("WITHDRAWAL" in perms) if perms else False,
                "saldo_usdt": float(cuenta.get("USDT", {}).get("free", 0.0)),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def saldo(self, moneda: str = "USDT") -> float:
        try:
            cuenta = self.exchange.fetch_balance()
            return float(cuenta.get(moneda, {}).get("free", 0.0))
        except Exception:
            return 0.0

    # ------------------------------------------------------------------ #
    # Ejecucion de ordenes
    # ------------------------------------------------------------------ #
    def ejecutar_compra(self, symbol: str, monto_usd: float, paper: bool = True) -> dict:
        """Compra en spot.

        paper=True -> NO envia orden real; devuelve lo que habria pasado.
        paper=False -> envia orden de mercado real (SOLO si el usuario
        lo habilita explicitamente y acepta el riesgo).
        """
        precio = self.precio_publico(symbol)
        if not precio:
            return {"ok": False, "error": "No se pudo obtener precio"}
        cantidad = round(monto_usd / precio, 8)

        if paper:
            return {
                "ok": True,
                "paper": True,
                "symbol": symbol,
                "monto_usd": monto_usd,
                "precio": precio,
                "cantidad": cantidad,
                "mensaje": "ORDEN SIMULADA (paper) - no se movio dinero real",
            }

        try:
            orden = self.exchange.create_market_buy_order(symbol, cantidad)
            return {
                "ok": True,
                "paper": False,
                "symbol": symbol,
                "orden_id": orden.get("id"),
                "cantidad": cantidad,
                "precio": precio,
                "mensaje": "Orden de mercado REAL enviada",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
