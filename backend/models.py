from pydantic import BaseModel
from typing import List, Dict, Optional, Any


class TaskSubStep(BaseModel):
    step: str = ""
    result: str = ""


class TaskResult(BaseModel):
    name: str = ""
    status: str = "unknown"  # done, skipped, running, no_log, unknown
    subtasks: List[TaskSubStep] = []
    time: str = ""


class StatusPush(BaseModel):
    timestamp: str
    qmt_running: bool = False
    kline_date: str = ""
    daily_task_done: bool = False
    stoploss_count: int = 0
    stoploss_list: List[str] = []
    signal_latest: str = ""
    disk_free_gb: float = 0.0
    tasks: List[TaskResult] = []


# ---- Live pull models ----

class DBHealth(BaseModel):
    kline_last_date: str = ""
    kline_max_date: str = ""
    kline_consistent: bool = True
    kline_recent_counts: Dict[str, int] = {}
    financial_last_yq: str = ""
    db_size_mb: float = 0.0


class TaskDetail(BaseModel):
    schedule: str = ""
    status: str = "no_log"  # done, skipped, running, no_log, read_error
    completed_at: str = ""
    subtasks: List[TaskSubStep] = []


class HoldingsSummary(BaseModel):
    n_positions: int = 0
    pending_sells: List[str] = []
    blacklist_count: int = 0


class LiveStatusData(BaseModel):
    collected_at: str = ""
    system: Dict[str, Any] = {}
    database: Dict[str, Any] = {}
    tasks: Dict[str, Any] = {}
    holdings: Dict[str, Any] = {}


class LiveStatusResponse(BaseModel):
    source: str = "pull"  # pull or push_fallback
    cache_age_seconds: float = 0.0
    refreshing: bool = False
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class Position(BaseModel):
    code: str
    name: str = ""
    shares: int = 0
    cost_price: float = 0.0
    current_price: float = 0.0
    pnl_pct: float = 0.0


class PortfolioPush(BaseModel):
    timestamp: str
    positions: List[Position] = []
    blacklist: Dict[str, int] = {}


class NavRecord(BaseModel):
    date: str
    total_value: float
    daily_return: float = 0.0
    n_positions: int = 0


class NavPush(BaseModel):
    records: List[NavRecord]


class TradePush(BaseModel):
    timestamp: str
    trades: List[dict] = []


class BacktestNavPush(BaseModel):
    records: List[NavRecord]


class SignalPush(BaseModel):
    timestamp: str
    signals: List[dict] = []
