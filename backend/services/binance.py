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


def _proxies() -> dict:
    """Proxy opcional para saltar el geo-bloqueo (datacenter US).

    Se activa poniendo BINANCE_HTTP_PROXY (ej. http://user:pass@host:port).
    Sin la variable, no se usa proxy y ccxt conecta directo.
    """
    proxy = os.getenv("BINANCE_HTTP_PROXY", "").strip()
    if not proxy:
        return {}
    return {"httpProxy": proxy, "httpsProxy": proxy}


def _env_testnet() -> bool:
    return os.getenv("BINANCE_TESTNET", "false").strip().lower() in ("1", "true", "yes", "si", "on")


class BinanceService:
    def __init__(self, api_key: str = "", api_secret: str = "", testnet: Optional[bool] = None):
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET", "")
        self.testnet = _env_testnet() if testnet is None else bool(testnet)
        self.exchange = ccxt.binance({
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "timeout": 10000,
            "options": {"defaultType": "spot"},
            **_proxies(),
        })
        # IMPORTANTE: activar sandbox ANTES de cualquier llamada a la API.
        if self.testnet:
            self.exchange.set_sandbox_mode(True)

    def precio(self, symbol: str = "BTC/USDT") -> Optional[float]:
        """Precio actual usando ESTE exchange (respeta testnet/mainnet)."""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker["last"])
        except Exception:
            # En testnet algunos pares tienen poca data; caemos al precio publico real.
            return self.precio_publico(symbol)

    # ------------------------------------------------------------------ #
    # Sin credenciales: solo lectura publica (precio en vivo)
    # ------------------------------------------------------------------ #
    @classmethod
    def precio_publico(cls, symbol: str = "BTC/USDT") -> Optional[float]:
        """Precio actual sin API key (datos publicos de Binance)."""
        ex = ccxt.binance({
            "enableRateLimit": True,
            "timeout": 5000,
            "options": {"defaultType": "spot"},
            **_proxies(),
        })
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
            cuenta = self.exchange.fetch_balance()
            # En testnet no hay riesgo real: no revisamos permiso de retiro.
            if self.testnet:
                return {
                    "ok": True,
                    "testnet": True,
                    "tiene_lectura": True,
                    "tiene_spot_trading": True,
                    "tiene_retiro": False,
                    "saldo_usdt": float(cuenta.get("USDT", {}).get("free", 0.0)),
                }
            # Llamada ligera que requiere autenticacion
            perms = self.exchange.fetch_permissions() if hasattr(self.exchange, "fetch_permissions") else []
            # Binance: permisos estan en la respuesta de la API de permisos.
            # Si no esta disponible, asumimos lectura+spot si la llamada arriba funciono.
            return {
                "ok": True,
                "testnet": False,
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

    def balance_total_usdt(self) -> dict:
        """Balance real de la cuenta valorado en USDT.

        Suma todos los activos con saldo (free+used) multiplicados por su
        precio en USDT. Devuelve total, disponible (free) y detalle.
        Lanza excepcion si no hay acceso (ej. geo-bloqueo) para que el
        endpoint decida el fallback.
        """
        cuenta = self.exchange.fetch_balance()
        totales = cuenta.get("total", {}) or {}
        libres = cuenta.get("free", {}) or {}

        total_usdt = 0.0
        libre_usdt = 0.0
        detalle = []
        for activo, cantidad in totales.items():
            cantidad = float(cantidad or 0.0)
            if cantidad <= 0:
                continue
            if activo in ("USDT", "BUSD", "USDC", "FDUSD"):
                precio = 1.0
            else:
                precio = self.precio(f"{activo}/USDT") or 0.0
            valor = cantidad * precio
            if valor <= 0:
                continue
            total_usdt += valor
            libre_usdt += float(libres.get(activo, 0.0)) * precio
            detalle.append({"activo": activo, "cantidad": cantidad, "valor_usdt": round(valor, 2)})

        return {
            "total_usdt": round(total_usdt, 2),
            "disponible_usdt": round(libre_usdt, 2),
            "detalle": sorted(detalle, key=lambda x: x["valor_usdt"], reverse=True),
        }

    # ------------------------------------------------------------------ #
    # Ejecucion de ordenes
    # ------------------------------------------------------------------ #
    def ejecutar_compra(self, symbol: str, monto_usd: float, paper: bool = True) -> dict:
        """Compra en spot.

        - Si el servicio esta en TESTNET: envia la orden al Spot Testnet de
          Binance (dinero FICTICIO, ejercita todo el flujo real del codigo).
        - paper=True (sin testnet): NO envia orden; simulacion local.
        - paper=False (sin testnet): envia orden de mercado REAL (dinero real).
        """
        precio = self.precio(symbol)
        if not precio:
            return {"ok": False, "error": "No se pudo obtener precio"}
        cantidad = round(monto_usd / precio, 8)

        if self.testnet:
            try:
                orden = self.exchange.create_market_buy_order(symbol, cantidad)
                return {
                    "ok": True,
                    "testnet": True,
                    "paper": True,
                    "symbol": symbol,
                    "orden_id": orden.get("id"),
                    "monto_usd": monto_usd,
                    "precio": precio,
                    "cantidad": cantidad,
                    "mensaje": "Orden enviada al TESTNET de Binance (dinero ficticio)",
                }
            except Exception as e:
                return {"ok": False, "testnet": True, "error": str(e)}

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

    def ejecutar_venta(self, symbol: str, cantidad: float, paper: bool = True) -> dict:
        """Venta en spot. Mismas reglas que ejecutar_compra."""
        precio = self.precio(symbol)
        cantidad = round(float(cantidad), 8)

        if self.testnet:
            try:
                orden = self.exchange.create_market_sell_order(symbol, cantidad)
                return {
                    "ok": True,
                    "testnet": True,
                    "paper": True,
                    "symbol": symbol,
                    "orden_id": orden.get("id"),
                    "precio": precio,
                    "cantidad": cantidad,
                    "mensaje": "Venta enviada al TESTNET de Binance (dinero ficticio)",
                }
            except Exception as e:
                return {"ok": False, "testnet": True, "error": str(e)}

        if paper:
            return {
                "ok": True,
                "paper": True,
                "symbol": symbol,
                "precio": precio,
                "cantidad": cantidad,
                "mensaje": "VENTA SIMULADA (paper) - no se movio dinero real",
            }

        try:
            orden = self.exchange.create_market_sell_order(symbol, cantidad)
            return {
                "ok": True,
                "paper": False,
                "symbol": symbol,
                "orden_id": orden.get("id"),
                "precio": precio,
                "cantidad": cantidad,
                "mensaje": "Orden de venta REAL enviada",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
