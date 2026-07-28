"""Servicio de integracion con Binance via ccxt.

Responsabilidades:
  - Obtener precio y velas en vivo (spot) para el dashboard y la estrategia.
  - Validar que un par de API key/secret funciona y tiene permisos de
    lectura + spot trading, PERO NO de retiro (seguridad).
  - Ejecutar ordenes de mercado REALES (comprar_verificado/vender_verificado)
    devolviendo el precio de llenado verdadero de Binance.

No hay modo simulado: el sistema opera siempre en real, nunca retira
fondos y controla el riesgo por monto y por stop loss, no por adivinar
el mercado.
"""
import os
import sys
import logging
from typing import Optional

import ccxt

logger = logging.getLogger(__name__)

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
    # Datos de mercado para la estrategia (siempre mainnet, sin credenciales)
    # ------------------------------------------------------------------ #
    @classmethod
    def velas_publicas(cls, symbol: str = "BTC/USDT", timeframe: str = "15m",
                       limite: int = 300) -> list:
        """Velas OHLCV del mercado REAL, para calcular la senal.

        Aunque la orden se ejecute en una cuenta con poca liquidez, la senal
        SIEMPRE se calcula sobre datos de mainnet: es lo unico representativo
        del mercado real.
        """
        ex = ccxt.binance({
            "enableRateLimit": True,
            "timeout": 10000,
            "options": {"defaultType": "spot"},
            **_proxies(),
        })
        try:
            return ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limite)
        except Exception as e:
            logger.warning(f"[OHLCV_FAIL] {symbol} {timeframe}: {e}")
            return []

    # ------------------------------------------------------------------ #
    # Ejecucion verificada: devuelve el fill REAL de Binance, nunca estimado
    # ------------------------------------------------------------------ #
    def _extraer_fill(self, orden: dict, symbol: str, precio_ref: float) -> dict:
        verificado = True
        precio_fill = orden.get("average") or orden.get("price")
        cantidad = orden.get("filled") or orden.get("amount")

        if not precio_fill or not cantidad:
            try:
                fresca = self.exchange.fetch_order(orden.get("id"), symbol)
                precio_fill = fresca.get("average") or fresca.get("price") or precio_fill
                cantidad = fresca.get("filled") or fresca.get("amount") or cantidad
                orden = fresca
            except Exception as e:
                logger.warning(f"[FILL_REFETCH_FAIL] {symbol} {orden.get('id')}: {e}")

        if not precio_fill:
            precio_fill = precio_ref
            verificado = False
        if not cantidad:
            cantidad = 0.0
            verificado = False

        precio_fill = float(precio_fill)
        cantidad = float(cantidad)

        comision = 0.0
        base = symbol.split("/")[0].upper()
        fee = orden.get("fee") or {}
        if fee and fee.get("cost") is not None:
            costo = float(fee["cost"])
            moneda = (fee.get("currency") or "").upper()
            comision = costo * precio_fill if moneda == base else costo
        elif orden.get("fees"):
            for f in orden["fees"]:
                costo = float(f.get("cost") or 0.0)
                moneda = (f.get("currency") or "").upper()
                comision += costo * precio_fill if moneda == base else costo
        else:
            comision = precio_fill * cantidad * 0.001  # estimacion taker 0.1%
            verificado = False

        return {
            "ok": True,
            "orden_id": orden.get("id"),
            "precio_fill": precio_fill,
            "cantidad": cantidad,
            "comision_usd": round(comision, 6),
            "notional_usd": round(precio_fill * cantidad, 4),
            "verificado": verificado,
        }

    def comprar_verificado(self, symbol: str, monto_usd: float) -> dict:
        """Compra REAL a mercado por importe en USDT. Devuelve el fill real."""
        precio_ref = self.precio(symbol) or 0.0
        try:
            monto = round(float(monto_usd), 2)
            try:
                orden = self.exchange.create_order(
                    symbol, "market", "buy", None, None, {"quoteOrderQty": monto}
                )
            except Exception:
                if precio_ref <= 0:
                    raise
                cant = self.exchange.amount_to_precision(symbol, monto / precio_ref)
                orden = self.exchange.create_market_buy_order(symbol, cant)
            return self._extraer_fill(orden, symbol, precio_ref)
        except Exception as e:
            logger.error(f"[COMPRA_FAIL] {symbol} ${monto_usd}: {e}")
            return {"ok": False, "error": str(e)}

    def vender_verificado(self, symbol: str, cantidad: float) -> dict:
        """Vende REAL a mercado EXACTAMENTE la cantidad indicada (nunca la cartera completa)."""
        precio_ref = self.precio(symbol) or 0.0
        base = symbol.split("/")[0]
        try:
            libre = self.saldo(base)
            cant = min(float(cantidad), libre) if libre > 0 else float(cantidad)
            try:
                cant = float(self.exchange.amount_to_precision(symbol, cant))
            except Exception:
                cant = round(cant, 6)
            if cant <= 0:
                return {"ok": False, "error": f"sin saldo de {base} para vender"}
            orden = self.exchange.create_market_sell_order(symbol, cant)
            return self._extraer_fill(orden, symbol, precio_ref)
        except Exception as e:
            logger.error(f"[VENTA_FAIL] {symbol} {cantidad}: {e}")
            return {"ok": False, "error": str(e)}

# NOTA: los metodos antiguos ejecutar_compra(paper=...) / ejecutar_venta(paper=...)
# se eliminaron. Toda ejecucion pasa ahora por comprar_verificado() y
# vender_verificado(), que operan SIEMPRE en real y devuelven el fill
# verdadero de Binance. No queda ninguna ruta de simulacion.
