"""
Push quant system status to dashboard server.
Runs on ser9 after quant_daily.bat completes.

Usage:
    python push_status.py                    # push all data
    python push_status.py --status-only      # push status only
    python push_status.py --server URL       # custom server URL
"""

import os
import sys
import json
import subprocess
import sqlite3
import argparse
import urllib.request
import urllib.error
from datetime import datetime, date
from pathlib import Path

# Configuration
DEFAULT_SERVER = "http://39.96.211.212/quant"
TOKEN = os.environ.get("DASHBOARD_TOKEN", "changeme")
PROJECT_DIR = Path(r"C:\Users\kai\quant_factor_model")


def get_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}"
    }


def post_json(server, endpoint, data):
    """POST JSON data to server endpoint."""
    url = f"{server}{endpoint}"
    body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=get_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            print(f"  OK {endpoint}: {resp.status}")
            return result
    except urllib.error.HTTPError as e:
        print(f"  FAIL {endpoint}: HTTP {e.code} - {e.read().decode()}")
    except Exception as e:
        print(f"  FAIL {endpoint}: {e}")
    return None


def collect_status():
    """Collect system status information."""
    status = {
        "timestamp": datetime.now().isoformat(),
        "qmt_running": False,
        "kline_date": "",
        "daily_task_done": False,
        "stoploss_count": 0,
        "stoploss_list": [],
        "signal_latest": "",
        "disk_free_gb": 0.0
    }

    # Check QMT process
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq XtMiniQmt.exe"],
            capture_output=True, text=True, timeout=10
        )
        status["qmt_running"] = "XtMiniQmt.exe" in result.stdout
    except Exception:
        pass

    # Check latest kline date from database
    db_path = PROJECT_DIR / "data" / "baostock.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT value FROM sync_meta WHERE key='kline_last_date'")
            row = cursor.fetchone()
            if row:
                status["kline_date"] = row[0]
            conn.close()
        except Exception:
            pass

    # Check stoploss blacklist
    blacklist_path = PROJECT_DIR / "output" / "stoploss_blacklist.json"
    if blacklist_path.exists():
        try:
            with open(blacklist_path) as f:
                bl = json.load(f)
            if isinstance(bl, dict):
                status["stoploss_count"] = len(bl)
                status["stoploss_list"] = list(bl.keys())
            elif isinstance(bl, list):
                status["stoploss_count"] = len(bl)
                status["stoploss_list"] = bl
        except Exception:
            pass

    # Check latest signal file
    output_dir = PROJECT_DIR / "output"
    if output_dir.exists():
        signal_files = sorted(output_dir.glob("live_signal_*.csv"), reverse=True)
        if signal_files:
            status["signal_latest"] = signal_files[0].name

    # Check disk space (C: drive)
    try:
        result = subprocess.run(
            ["powershell", "-Command", "(Get-PSDrive C).Free / 1GB"],
            capture_output=True, text=True, timeout=10
        )
        status["disk_free_gb"] = round(float(result.stdout.strip()), 1)
    except Exception:
        pass

    # Check if today's task log exists
    today_str = date.today().strftime("%Y-%m-%d")
    log_dir = PROJECT_DIR / "logs"
    if log_dir.exists():
        today_logs = list(log_dir.glob(f"*{today_str}*"))
        status["daily_task_done"] = len(today_logs) > 0

    return status


def collect_portfolio():
    """Collect current portfolio from latest live signal or stoploss data."""
    portfolio = {
        "timestamp": datetime.now().isoformat(),
        "positions": [],
        "blacklist": {}
    }

    # Read stoploss blacklist for cooldown info
    blacklist_path = PROJECT_DIR / "output" / "stoploss_blacklist.json"
    if blacklist_path.exists():
        try:
            with open(blacklist_path) as f:
                bl = json.load(f)
            if isinstance(bl, dict):
                portfolio["blacklist"] = bl
        except Exception:
            pass

    # Try to read positions from latest output
    # The actual positions come from QMT or the latest signal
    output_dir = PROJECT_DIR / "output"
    signal_files = sorted(output_dir.glob("live_signal_*.csv"), reverse=True)
    if signal_files:
        try:
            import csv
            with open(signal_files[0]) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pos = {
                        "code": row.get("code", ""),
                        "shares": int(float(row.get("shares", 0))),
                        "cost_price": float(row.get("cost_price", 0)),
                        "current_price": float(row.get("current_price", 0)),
                        "pnl_pct": float(row.get("pnl_pct", 0))
                    }
                    portfolio["positions"].append(pos)
        except Exception:
            pass

    return portfolio


def collect_nav():
    """Collect nav records from backtest results or live tracking."""
    records = []

    # Try live nav tracking first
    nav_path = PROJECT_DIR / "output" / "live_nav.csv"
    if not nav_path.exists():
        # Fall back to backtest results
        nav_path = PROJECT_DIR / "output" / "backtest_results.csv"

    if nav_path.exists():
        try:
            import csv
            with open(nav_path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rec = {
                        "date": row.get("date", ""),
                        "total_value": float(row.get("total_value", row.get("portfolio_value", 0))),
                        "daily_return": float(row.get("daily_return", row.get("return", 0))),
                        "n_positions": int(float(row.get("n_positions", 0)))
                    }
                    records.append(rec)
        except Exception as e:
            print(f"  Warning: nav collection error: {e}")

    return {"records": records}


def main():
    parser = argparse.ArgumentParser(description="Push quant status to dashboard")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="Dashboard server URL")
    parser.add_argument("--status-only", action="store_true", help="Push status only")
    parser.add_argument("--token", default=None, help="API token (or set DASHBOARD_TOKEN env)")
    args = parser.parse_args()

    global TOKEN
    if args.token:
        TOKEN = args.token

    server = args.server.rstrip("/")
    print(f"Pushing to {server} ...")

    # Always push status
    print("\n[Status]")
    status = collect_status()
    post_json(server, "/api/push/status", status)

    if args.status_only:
        return

    # Push portfolio
    print("\n[Portfolio]")
    portfolio = collect_portfolio()
    post_json(server, "/api/push/portfolio", portfolio)

    # Push nav
    print("\n[NAV]")
    nav = collect_nav()
    if nav["records"]:
        post_json(server, "/api/push/nav", nav)
    else:
        print("  (no nav data found)")

    print("\nDone.")


if __name__ == "__main__":
    main()
