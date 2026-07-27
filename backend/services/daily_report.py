"""Reporte diario del motor de trading REAL, enviado a Telegram.

Para cada usuario con conexion REAL activa (testnet=False) se calcula, del
dia de hoy: cuanto gano, cuanto perdio, cuantas operaciones, y el saldo real
de la cuenta en Binance. Todo viene de Trade.pnl_usd, que se calcula sobre
fills reales de Binance -- nunca una estimacion.
"""
import os
import sys
import logging
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logger = logging.getLogger(__name__)


def _resumen_usuario(db, user_id: str) -> dict:
    from models import Trade
    inicio_dia = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cerradas = (
        db.query(Trade)
        .filter(Trade.user_id == user_id, Trade.status == "closed",
                Trade.exit_time >= inicio_dia)
        .all()
    )
    ganancia = sum((t.pnl_usd or 0.0) for t in cerradas if (t.pnl_usd or 0.0) > 0)
    perdida = sum((t.pnl_usd or 0.0) for t in cerradas if (t.pnl_usd or 0.0) < 0)
    total = len(cerradas)
    neto = ganancia + perdida
    promedio = (neto / total) if total > 0 else 0.0
    abiertas = (
        db.query(Trade)
        .filter(Trade.user_id == user_id, Trade.status == "open")
        .count()
    )
    return {
        "ganancia": round(ganancia, 2),
        "perdida": round(perdida, 2),
        "neto": round(neto, 2),
        "operaciones": total,
        "abiertas": abiertas,
        "promedio": round(promedio, 2),
    }


def _saldo_real(conn) -> float:
    try:
        from services.crypto import descifrar
        from services.binance import BinanceService
        svc = BinanceService(
            api_key=descifrar(conn.api_key_encrypted),
            api_secret=descifrar(conn.api_secret_encrypted),
            testnet=False,
        )
        real = svc.balance_total_usdt()
        return float(real.get("total_usdt", 0.0))
    except Exception as e:
        logger.warning(f"[daily_report] saldo no disponible: {e}")
        return None


def _formatear(nombre: str, r: dict, saldo) -> str:
    emoji = "📈" if r["neto"] >= 0 else "📉"
    saldo_txt = f"${saldo:,.2f}" if saldo is not None else "no disponible"
    return (
        f"{emoji} <b>{nombre}</b> (💵 dinero real)\n"
        f"Ganancia hoy: ${r['ganancia']:,.2f}\n"
        f"Perdida hoy: ${r['perdida']:,.2f}\n"
        f"Neto: ${r['neto']:+,.2f}\n"
        f"Operaciones: {r['operaciones']} (abiertas: {r['abiertas']})\n"
        f"Promedio/op: ${r['promedio']:+,.2f}\n"
        f"Saldo en Binance: {saldo_txt}"
    )


async def enviar_reporte_diario() -> dict:
    """Construye y envia el resumen diario de todas las cuentas reales."""
    from database import SessionLocal
    from models import User, ExchangeConnection, AlertConfig
    from services.telegram import send_telegram

    db = SessionLocal()
    secciones = []
    try:
        conexiones = (
            db.query(ExchangeConnection)
            .filter(ExchangeConnection.is_active == True,
                    ExchangeConnection.testnet == False)
            .all()
        )
        for conn in conexiones:
            try:
                user = db.query(User).filter(User.id == conn.user_id).first()
                if not user:
                    continue
                cfg = (
                    db.query(AlertConfig)
                    .filter(AlertConfig.user_id == user.id,
                            AlertConfig.alert_type == "daily_profit",
                            AlertConfig.channel == "telegram")
                    .first()
                )
                if cfg is not None and not cfg.is_active:
                    continue
                r = _resumen_usuario(db, user.id)
                saldo = _saldo_real(conn)
                secciones.append(_formatear(user.name or user.email, r, saldo))
            except Exception as e:
                logger.error(f"[daily_report] error usuario {conn.user_id}: {e}")

        if not secciones:
            msg = "📊 <b>Resumen Diario · QuantBot</b>\nSin cuentas reales activas hoy."
        else:
            fecha = datetime.now(timezone.utc).strftime("%d/%m/%Y")
            msg = f"📊 <b>Resumen Diario · QuantBot (dinero real)</b>\n{fecha}\n\n" + "\n\n".join(secciones)

        ok = await send_telegram(msg)
        return {"ok": ok, "usuarios": len(secciones)}
    finally:
        db.close()


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(enviar_reporte_diario()))
