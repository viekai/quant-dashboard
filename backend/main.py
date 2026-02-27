import asyncio
import json
import os
import secrets
import time
from fastapi import FastAPI, Depends, HTTPException, Header, Cookie, Response, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from database import Database
from models import (
    StatusPush, PortfolioPush, NavPush, TradePush, SignalPush, BacktestNavPush,
    LiveStatusResponse,
)

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
    "industry_momentum": 0.0,
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


@app.post("/api/push/backtest_nav")
async def push_backtest_nav(data: BacktestNavPush, _=Depends(verify_token)):
    db.save_backtest_nav([r.model_dump() for r in data.records])
    return {"ok": True, "count": len(data.records)}


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


@app.get("/api/nav/backtest")
async def get_backtest_nav(days: int = 30, _=Depends(verify_session)):
    return db.get_backtest_nav(days)


@app.get("/api/factor/weights")
async def get_factor_weights(_=Depends(verify_session)):
    return FACTOR_WEIGHTS


# ---- Live pull from ser9 via SSH ----

class PullCache:
    """In-memory cache for SSH pull results with TTL and fetch lock."""

    def __init__(self, ttl: float = 60.0, ssh_timeout: float = 20.0):
        self.ttl = ttl
        self.ssh_timeout = ssh_timeout
        self.data: dict | None = None
        self.fetched_at: float = 0.0
        self.fetching: bool = False
        self._lock = asyncio.Lock()

    def is_fresh(self) -> bool:
        return self.data is not None and (time.time() - self.fetched_at) < self.ttl

    @property
    def age(self) -> float:
        if self.fetched_at == 0:
            return -1
        return time.time() - self.fetched_at

    async def fetch(self) -> tuple[dict | None, str | None]:
        """Execute SSH chain to collect status from ser9. Returns (data, error)."""
        async with self._lock:
            # Double-check after acquiring lock
            if self.is_fresh():
                return self.data, None

            self.fetching = True
            try:
                # SSH chain: dashboard server → Mac Mini (port 6022) → ser9
                cmd = [
                    "ssh", "-o", "StrictHostKeyChecking=no",
                    "-o", f"ConnectTimeout=10",
                    "-p", "6022", "kai@localhost",
                    "ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "
                    "kai@192.168.50.233 "
                    "'cd C:\\Users\\kai\\quant_factor_model && "
                    "\"C:\\Program Files\\Python311\\python.exe\" scripts/collect_status.py'"
                ]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.ssh_timeout
                )

                if proc.returncode != 0:
                    err_msg = stderr.decode(errors="replace").strip()[:200]
                    return self.data, f"SSH failed (rc={proc.returncode}): {err_msg}"

                raw = stdout.decode(errors="replace").strip()
                if not raw:
                    return self.data, "Empty response from ser9"

                data = json.loads(raw)
                self.data = data
                self.fetched_at = time.time()
                return data, None

            except asyncio.TimeoutError:
                return self.data, f"SSH timeout ({self.ssh_timeout}s)"
            except json.JSONDecodeError as e:
                return self.data, f"Invalid JSON: {e}"
            except Exception as e:
                return self.data, f"SSH error: {e}"
            finally:
                self.fetching = False


_pull_cache = PullCache(ttl=60.0, ssh_timeout=20.0)


@app.get("/api/status/live")
async def get_live_status(
    force: int = Query(0, description="Force refresh (skip cache)"),
    _=Depends(verify_session),
):
    """Pull live status from ser9 via SSH, with 60s cache."""
    if not force and _pull_cache.is_fresh():
        return LiveStatusResponse(
            source="pull",
            cache_age_seconds=round(_pull_cache.age, 1),
            refreshing=False,
            data=_pull_cache.data,
        ).model_dump()

    data, error = await _pull_cache.fetch()

    if error and data is None:
        # No cached data at all, try push fallback
        push_data = db.get_latest_status()
        if push_data:
            return LiveStatusResponse(
                source="push_fallback",
                cache_age_seconds=-1,
                error=error,
                data=push_data,
            ).model_dump()
        return LiveStatusResponse(
            source="pull",
            error=error,
        ).model_dump()

    return LiveStatusResponse(
        source="pull",
        cache_age_seconds=round(_pull_cache.age, 1),
        refreshing=False,
        error=error,
        data=data,
    ).model_dump()


# Static files served by nginx in production.
# For local dev: python -m uvicorn main:app, then open frontend/index.html directly.
