import os
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from database import Database
from models import StatusPush, PortfolioPush, NavPush, TradePush, SignalPush

DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN", "changeme")

app = FastAPI(title="Quant Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db = Database()

FACTOR_WEIGHTS = {
    "volatility_60d": 22.0,
    "pe_ttm": 21.0,
    "momentum_12_1": 16.7,
    "turnover_20d": 12.5,
    "profit_growth": 7.9,
    "pb": 6.6,
    "debt_ratio": 3.9,
    "revenue_growth": 3.7,
    "ps": 3.5,
    "roe": 2.1,
}


async def verify_token(authorization: str = Header(...)):
    if authorization != f"Bearer {DASHBOARD_TOKEN}":
        raise HTTPException(status_code=401, detail="Invalid token")


# ---- Push endpoints (require token) ----

@app.post("/api/push/status")
async def push_status(data: StatusPush, _=Depends(verify_token)):
    db.save_status(data.model_dump())
    return {"ok": True}


@app.post("/api/push/portfolio")
async def push_portfolio(data: PortfolioPush, _=Depends(verify_token)):
    db.save_portfolio(data.model_dump())
    return {"ok": True}


@app.post("/api/push/nav")
async def push_nav(data: NavPush, _=Depends(verify_token)):
    db.save_nav([r.model_dump() for r in data.records])
    return {"ok": True, "count": len(data.records)}


@app.post("/api/push/trades")
async def push_trades(data: TradePush, _=Depends(verify_token)):
    db.save_trades(data.model_dump())
    return {"ok": True}


@app.post("/api/push/signal")
async def push_signal(data: SignalPush, _=Depends(verify_token)):
    db.save_signal(data.model_dump())
    return {"ok": True}


# ---- Read endpoints (public) ----

@app.get("/api/status/latest")
async def get_status():
    data = db.get_latest_status()
    return data or {"message": "no data"}


@app.get("/api/portfolio/current")
async def get_portfolio():
    data = db.get_current_portfolio()
    return data or {"message": "no data"}


@app.get("/api/nav")
async def get_nav(days: int = 30):
    return db.get_nav(days)


@app.get("/api/trades")
async def get_trades(limit: int = 50):
    return db.get_trades(limit)


@app.get("/api/signal/latest")
async def get_signal():
    data = db.get_latest_signal()
    return data or {"message": "no data"}


@app.get("/api/factor/weights")
async def get_factor_weights():
    return FACTOR_WEIGHTS


# ---- Static files (frontend) ----

frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
