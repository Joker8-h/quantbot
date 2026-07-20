from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from database import engine, Base
from routes import auth, balance, alerts, admin, investment, exchange, config as config_routes
import os
import logging

logger = logging.getLogger(__name__)

# Create tables
Base.metadata.create_all(bind=engine)

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
app.include_router(config_routes.router)


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

