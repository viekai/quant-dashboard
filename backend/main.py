import os
import secrets
from fastapi import FastAPI, Depends, HTTPException, Header, Cookie, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from database import Database
from models import StatusPush, PortfolioPush, NavPush, TradePush, SignalPush

DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN", "changeme")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "quant2026")

app = FastAPI(title="Quant Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db = Database()

# Session tokens for web login (in-memory, restarts clear sessions)
_valid_sessions: set[str] = set()

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


async def verify_session(session: str = Cookie(default="")):
    if session not in _valid_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")


# ---- Auth endpoints ----

@app.post("/api/auth/login")
async def login(request: Request, response: Response):
    body = await request.json()
    if body.get("password") != DASHBOARD_PASSWORD:
        raise HTTPException(status_code=401, detail="Wrong password")
    token = secrets.token_urlsafe(32)
    _valid_sessions.add(token)
    response.set_cookie(
        key="session", value=token, httponly=True,
        max_age=86400 * 30, samesite="lax",
    )
    return {"ok": True}


@app.get("/api/auth/check")
async def auth_check(session: str = Cookie(default="")):
    return {"authenticated": session in _valid_sessions}


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


# ---- Read endpoints (require session cookie) ----

@app.get("/api/status/latest")
async def get_status(_=Depends(verify_session)):
    data = db.get_latest_status()
    return data or {"message": "no data"}


@app.get("/api/portfolio/current")
async def get_portfolio(_=Depends(verify_session)):
    data = db.get_current_portfolio()
    return data or {"message": "no data"}


@app.get("/api/nav")
async def get_nav(days: int = 30, _=Depends(verify_session)):
    return db.get_nav(days)


@app.get("/api/trades")
async def get_trades(limit: int = 50, _=Depends(verify_session)):
    return db.get_trades(limit)


@app.get("/api/signal/latest")
async def get_signal(_=Depends(verify_session)):
    data = db.get_latest_signal()
    return data or {"message": "no data"}


@app.get("/api/factor/weights")
async def get_factor_weights(_=Depends(verify_session)):
    return FACTOR_WEIGHTS


# Static files served by nginx in production.
# For local dev: python -m uvicorn main:app, then open frontend/index.html directly.
