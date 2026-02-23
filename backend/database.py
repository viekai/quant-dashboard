import json
import sqlite3
import os
from pathlib import Path


class Database:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path(__file__).parent / "data" / "dashboard.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_tables()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS nav (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                total_value REAL NOT NULL,
                daily_return REAL DEFAULT 0,
                n_positions INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS signal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL
            );
        """)
        conn.commit()
        conn.close()

    # -- Status --
    def save_status(self, data: dict):
        conn = self._conn()
        conn.execute(
            "INSERT INTO status (timestamp, data) VALUES (?, ?)",
            (data.get("timestamp", ""), json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    def get_latest_status(self) -> dict | None:
        conn = self._conn()
        row = conn.execute(
            "SELECT data FROM status ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return json.loads(row["data"]) if row else None

    # -- Portfolio --
    def save_portfolio(self, data: dict):
        conn = self._conn()
        conn.execute(
            "INSERT INTO portfolio (timestamp, data) VALUES (?, ?)",
            (data.get("timestamp", ""), json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    def get_current_portfolio(self) -> dict | None:
        conn = self._conn()
        row = conn.execute(
            "SELECT data FROM portfolio ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return json.loads(row["data"]) if row else None

    # -- NAV --
    def save_nav(self, records: list):
        conn = self._conn()
        for rec in records:
            conn.execute(
                """INSERT INTO nav (date, total_value, daily_return, n_positions)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(date) DO UPDATE SET
                     total_value=excluded.total_value,
                     daily_return=excluded.daily_return,
                     n_positions=excluded.n_positions""",
                (rec["date"], rec["total_value"], rec.get("daily_return", 0), rec.get("n_positions", 0)),
            )
        conn.commit()
        conn.close()

    def get_nav(self, days: int = 30) -> list:
        conn = self._conn()
        rows = conn.execute(
            "SELECT date, total_value, daily_return, n_positions FROM nav ORDER BY date DESC LIMIT ?",
            (days,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in reversed(rows)]

    # -- Trades --
    def save_trades(self, data: dict):
        conn = self._conn()
        conn.execute(
            "INSERT INTO trades (timestamp, data) VALUES (?, ?)",
            (data.get("timestamp", ""), json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    def get_trades(self, limit: int = 50) -> list:
        conn = self._conn()
        rows = conn.execute(
            "SELECT data FROM trades ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        results = []
        for row in rows:
            d = json.loads(row["data"])
            results.append(d)
        return results

    # -- Signal --
    def save_signal(self, data: dict):
        conn = self._conn()
        conn.execute(
            "INSERT INTO signal (timestamp, data) VALUES (?, ?)",
            (data.get("timestamp", ""), json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    def get_latest_signal(self) -> dict | None:
        conn = self._conn()
        row = conn.execute(
            "SELECT data FROM signal ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return json.loads(row["data"]) if row else None
