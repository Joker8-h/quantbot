from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routes import auth, balance, alerts, admin

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


@app.get("/")
def root():
    return {"message": "QuantBot API is running", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
