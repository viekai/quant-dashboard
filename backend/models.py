from pydantic import BaseModel
from typing import List, Dict


class StatusPush(BaseModel):
    timestamp: str
    qmt_running: bool = False
    kline_date: str = ""
    daily_task_done: bool = False
    stoploss_count: int = 0
    stoploss_list: List[str] = []
    signal_latest: str = ""
    disk_free_gb: float = 0.0


class Position(BaseModel):
    code: str
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


class SignalPush(BaseModel):
    timestamp: str
    signals: List[dict] = []
