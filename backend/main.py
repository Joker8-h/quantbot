from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from database import engine, Base
from routes import auth, balance, alerts, admin, investment, exchange, paper, config as config_routes
import os
import logging

logger = logging.getLogger(__name__)

# Create tables
Base.metadata.create_all(bind=engine)


def _migrar_columnas():
    """Migracion ligera e idempotente: agrega columnas nuevas si faltan.

    create_all no altera tablas existentes, asi que agregamos a mano las
    columnas nuevas (ej. exchange_connections.testnet) sin perder datos.
    """
    from sqlalchemy import text, inspect
    try:
        insp = inspect(engine)
        cols = [c["name"] for c in insp.get_columns("exchange_connections")]
        if "testnet" not in cols:
            es_pg = "postgresql" in str(engine.url)
            default = "true" if es_pg else "1"
            with engine.begin() as conn:
                conn.execute(text(
                    f"ALTER TABLE exchange_connections ADD COLUMN testnet BOOLEAN DEFAULT {default}"
                ))
            logger.info("Migracion: columna testnet agregada a exchange_connections")
    except Exception as e:
        logger.warning(f"Migracion de columnas omitida: {e}")


_migrar_columnas()

app = FastAPI(title="QuantBot API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router)
app.include_router(balance.router)
app.include_router(alerts.router)
app.include_router(admin.router)
app.include_router(investment.router)
app.include_router(exchange.router)
app.include_router(paper.router)
app.include_router(config_routes.router)


# --------------------------------------------------------------------- #
# Scheduler: motor de paper trading (testnet) + resumen diario a Telegram
# --------------------------------------------------------------------- #
_scheduler = None


def _job_tick():
    try:
        from services.paper_engine import ejecutar_tick
        res = ejecutar_tick()
        logger.info(f"[scheduler] tick paper: {res}")
    except Exception as e:
        logger.error(f"[scheduler] tick fallo: {e}")


def _job_reporte():
    try:
        import asyncio
        from services.daily_report import enviar_reporte_diario
        res = asyncio.run(enviar_reporte_diario())
        logger.info(f"[scheduler] reporte diario: {res}")
    except Exception as e:
        logger.error(f"[scheduler] reporte fallo: {e}")


@app.on_event("startup")
def _iniciar_scheduler():
    global _scheduler
    if os.getenv("PAPER_ENGINE_ENABLED", "true").strip().lower() not in ("1", "true", "yes", "on", "si"):
        logger.info("[scheduler] deshabilitado por PAPER_ENGINE_ENABLED")
        return
    if _scheduler is not None:
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        tick_min = int(os.getenv("PAPER_TICK_MINUTOS", "15"))
        # Hora del resumen: 13:00 UTC = 8:00 AM Colombia
        rep_hora = int(os.getenv("PAPER_REPORTE_HORA_UTC", "13"))
        rep_min = int(os.getenv("PAPER_REPORTE_MIN_UTC", "0"))
        sch = BackgroundScheduler(timezone="UTC")
        sch.add_job(_job_tick, "interval", minutes=tick_min, id="paper_tick",
                    max_instances=1, coalesce=True)
        sch.add_job(_job_reporte, "cron", hour=rep_hora, minute=rep_min, id="paper_reporte",
                    max_instances=1, coalesce=True)
        sch.start()
        _scheduler = sch
        logger.info(f"[scheduler] activo (tick={tick_min}min, reporte={rep_hora:02d}:{rep_min:02d} UTC)")
    except Exception as e:
        logger.error(f"[scheduler] no se pudo iniciar: {e}")


@app.on_event("shutdown")
def _detener_scheduler():
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/diag/binance")
def diag_binance():
    """Diagnostico: ¿es Binance alcanzable desde este datacenter?

    Sirve para verificar el geo-bloqueo antes/despues de migrar de region.
    """
    import urllib.request
    out = {}
    try:
        ip = urllib.request.urlopen("https://api.ipify.org", timeout=8).read().decode("utf-8", "ignore")
        out["egress_ip"] = ip
    except Exception as e:
        out["egress_ip_error"] = str(e)[:200]
    try:
        r = urllib.request.urlopen(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=8
        )
        out["binance_http_status"] = r.status
        out["binance_body"] = r.read()[:120].decode("utf-8", "ignore")
    except Exception as e:
        out["binance_http_error"] = str(e)[:200]
    try:
        from services.binance import BinanceService
        out["precio_publico"] = BinanceService.precio_publico("BTC/USDT")
    except Exception as e:
        out["precio_error"] = str(e)[:200]
    return out


# Serve frontend static files
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.normpath(os.path.join(BACKEND_DIR, "..", "static"))
logger.info(f"Static dir: {STATIC_DIR} exists: {os.path.isdir(STATIC_DIR)}")

if os.path.isdir(STATIC_DIR):
    assets_dir = os.path.join(STATIC_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            return None
        file_path = os.path.join(STATIC_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
else:
    @app.get("/")
    def root():
        return {"message": "QuantBot API is running", "version": "1.0.0"}

