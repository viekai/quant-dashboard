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


LOG_DIR = Path(r"C:\Users\kai\logs\quant")


def _parse_task_log(log_path, task_name):
    """Parse a task log file and extract sub-task results."""
    result = {"name": task_name, "status": "unknown", "subtasks": [], "time": ""}
    if not log_path.exists():
        result["status"] = "no_log"
        return result

    try:
        raw = log_path.read_bytes()
        # Windows cmd outputs GBK; try both encodings
        for enc in ["utf-8", "gbk", "cp936"]:
            try:
                content = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            content = raw.decode("utf-8", errors="replace")
        lines = content.strip().splitlines()
    except Exception:
        result["status"] = "read_error"
        return result

    # Check if completed (has "Done" line)
    done_line = [l for l in lines if "Done" in l and "=====" in l]
    skip_line = [l for l in lines if "[SKIP]" in l]

    if skip_line:
        result["status"] = "skipped"
        result["subtasks"].append({"step": "交易日检查", "result": "非交易日，跳过"})
        return result

    # Extract completion time from last "===== Done 2026-02-24 22:08:22.11 ====="
    import re
    for l in reversed(lines):
        if "=====" in l and "Done" in l:
            m = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})', l)
            if m:
                result["time"] = f"{m.group(1)} {m.group(2)}"
                break

    if done_line:
        result["status"] = "done"
    elif lines:
        result["status"] = "running"

    # Parse sub-tasks from log content
    if task_name == "Rebalance":
        # sell-stoploss result
        if "No stocks to sell" in content:
            result["subtasks"].append({"step": "止损卖出", "result": "无待卖出"})
        elif "Pending sells (T+1):" in content:
            for l in lines:
                if "Pending sells" in l:
                    result["subtasks"].append({"step": "止损卖出", "result": l.split(":")[-1].strip()})
                    break
        elif "sell-stoploss" in content.lower():
            result["subtasks"].append({"step": "止损卖出", "result": "执行中"})

        # live rebalance result
        if "[DONE] Rebalance complete" in content:
            result["subtasks"].append({"step": "月度调仓", "result": "已完成"})
        elif "[INCOMPLETE]" in content:
            result["subtasks"].append({"step": "月度调仓", "result": "部分完成"})
        elif "target_weights.json" in content and ("already exists" in content or "信号已存在" in content):
            result["subtasks"].append({"step": "月度调仓", "result": "重试中"})
        elif "不在调仓窗口" in content or "非调仓窗口" in content:
            result["subtasks"].append({"step": "月度调仓", "result": "非调仓日"})
        elif "调仓完成" in content or "Rebalance complete" in content:
            result["subtasks"].append({"step": "月度调仓", "result": "已完成"})
        elif "live" in content.lower() and ("Rebalance check" in content or "rebalance" in content.lower()):
            result["subtasks"].append({"step": "月度调仓", "result": "执行中"})

    elif task_name == "Stoploss":
        # check-stoploss result
        if "触发止损" in content:
            triggered = [l for l in lines if "触发止损" in l]
            result["subtasks"].append({"step": "止损检查", "result": f"触发 {len(triggered)} 只"})
        elif "No stop-loss" in content or "无止损" in content or "stop_loss_triggered: 0" in content.lower():
            result["subtasks"].append({"step": "止损检查", "result": "无触发"})
        elif "check-stoploss" in content.lower():
            result["subtasks"].append({"step": "止损检查", "result": "执行中"})

        # snapshot result
        if "snapshot" in content.lower():
            if "Saved snapshot" in content or "snapshots.csv" in content:
                result["subtasks"].append({"step": "持仓快照", "result": "已保存"})
            else:
                result["subtasks"].append({"step": "持仓快照", "result": "执行中"})

    return result


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
        "disk_free_gb": 0.0,
        "tasks": [],
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

    # Parse today's task logs
    today_str = date.today().strftime("%Y-%m-%d")
    rebalance_log = LOG_DIR / f"rebalance_{today_str}.log"
    stoploss_log = LOG_DIR / f"stoploss_{today_str}.log"

    rebalance = _parse_task_log(rebalance_log, "Rebalance")
    stoploss = _parse_task_log(stoploss_log, "Stoploss")
    status["tasks"] = [rebalance, stoploss]

    # daily_task_done: ignore tasks that haven't triggered yet (no_log)
    triggered = [t for t in status["tasks"] if t["status"] != "no_log"]
    status["daily_task_done"] = (
        len(triggered) > 0 and
        all(t["status"] in ("done", "skipped") for t in triggered)
    )

    return status


def load_stock_names():
    """Load stock code → name mapping from baostock.db industry table."""
    names = {}
    db_path = PROJECT_DIR / "data" / "baostock.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            for row in conn.execute("SELECT code, code_name FROM industry WHERE code_name IS NOT NULL"):
                # industry table uses SH.600519 format
                names[row[0]] = row[1]
                # Also store lowercase variant for matching
                names[row[0].lower()] = row[1]
            conn.close()
        except Exception:
            pass
    return names


def get_stock_name(code, names):
    """Look up stock name, trying both original and upper/lower case."""
    return names.get(code, "") or names.get(code.upper(), "") or names.get(code.lower(), "")


def collect_portfolio():
    """Collect current portfolio from live snapshots or signal files."""
    names = load_stock_names()
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

    # Priority 0: live_holdings.json (from check-stoploss / live rebalance)
    holdings_path = PROJECT_DIR / "output" / "live_holdings.json"
    if holdings_path.exists():
        try:
            with open(holdings_path) as f:
                holdings = json.load(f)
            for p in holdings.get("positions", []):
                code = p.get("code", "")
                portfolio["positions"].append({
                    "code": code,
                    "name": get_stock_name(code, names),
                    "shares": int(p.get("shares", 0)),
                    "cost_price": float(p.get("cost_price", 0)),
                    "current_price": float(p.get("current_price", 0)),
                    "pnl_pct": float(p.get("pnl_pct", 0)),
                })
            if portfolio["positions"]:
                portfolio["timestamp"] = holdings.get("timestamp", portfolio["timestamp"])
                return portfolio
        except Exception as e:
            print(f"  Warning: live_holdings.json error: {e}")

        # Priority 1: live trading snapshots (real QMT positions)
    snapshot_path = PROJECT_DIR / "output" / "live_trading" / "snapshots.csv"
    if snapshot_path.exists():
        try:
            import csv
            with open(snapshot_path) as f:
                rows = list(csv.DictReader(f))
            if rows:
                latest = sorted(rows, key=lambda r: r.get("date", ""))[-1]
                positions_json = latest.get("positions_json", "[]")
                positions = json.loads(positions_json)

                # Get latest prices for PnL calc
                db_path = PROJECT_DIR / "data" / "baostock.db"
                latest_prices = {}
                if db_path.exists():
                    conn = sqlite3.connect(str(db_path))
                    for p in positions:
                        code = p.get("code", "")
                        for variant in [code, code.upper(), code.lower()]:
                            row = conn.execute(
                                "SELECT close FROM kline WHERE code=? ORDER BY date DESC LIMIT 1",
                                (variant,)
                            ).fetchone()
                            if row and row[0]:
                                latest_prices[code] = float(row[0])
                                break
                    conn.close()

                for p in positions:
                    code = p.get("code", "")
                    cost = float(p.get("cost_price", 0))
                    current = latest_prices.get(code, 0)
                    pnl_pct = (current - cost) / cost if cost > 0 and current > 0 else 0
                    portfolio["positions"].append({
                        "code": code,
                        "name": get_stock_name(code, names),
                        "shares": int(p.get("shares", 0)),
                        "cost_price": cost,
                        "current_price": current,
                        "pnl_pct": round(pnl_pct, 4),
                    })
                if portfolio["positions"]:
                    return portfolio
        except Exception as e:
            print(f"  Warning: snapshot portfolio error: {e}")

    # Priority 2: signal files (fallback)
    output_dir = PROJECT_DIR / "output"
    signal_files = sorted(output_dir.glob("live_signal_*.csv"), reverse=True)
    if signal_files:
        try:
            import csv
            with open(signal_files[0]) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get("code", "")
                    pos = {
                        "code": code,
                        "name": get_stock_name(code, names),
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
    """Collect nav records from live trading snapshots only."""
    records = []

    snapshot_path = PROJECT_DIR / "output" / "live_trading" / "snapshots.csv"
    if snapshot_path.exists():
        try:
            import csv
            with open(snapshot_path) as f:
                rows = list(csv.DictReader(f))
            prev_value = None
            for row in sorted(rows, key=lambda r: r.get("date", "")):
                total = float(row.get("total_asset", 0))
                daily_ret = 0.0
                if prev_value and prev_value > 0:
                    daily_ret = (total - prev_value) / prev_value
                records.append({
                    "date": row.get("date", ""),
                    "total_value": total,
                    "daily_return": round(daily_ret, 6),
                    "n_positions": int(float(row.get("n_positions", 0)))
                })
                prev_value = total
        except Exception as e:
            print(f"  Warning: nav collection error: {e}")

    return {"records": records}


def collect_backtest_nav():
    """Collect backtest NAV from backtest_results.csv for comparison overlay."""
    records = []
    bt_path = PROJECT_DIR / "output" / "backtest_results.csv"
    if not bt_path.exists():
        return {"records": records}

    try:
        import csv
        with open(bt_path) as f:
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
        print(f"  Warning: backtest nav collection error: {e}")

    return {"records": records}


def collect_signal():
    """Collect latest signal data from signal CSV and target_weights.json."""
    import re
    names = load_stock_names()
    signal = {
        "timestamp": datetime.now().isoformat(),
        "signals": [],
    }

    output_dir = PROJECT_DIR / "output"

    # Check target_weights.json (pending execution)
    tw_path = output_dir / "target_weights.json"
    has_pending = False
    if tw_path.exists():
        try:
            with open(tw_path) as f:
                tw = json.load(f)
            weights = tw.get("weights", {})
            if weights:
                has_pending = True
                for code, weight in sorted(
                    weights.items(), key=lambda x: -x[1]
                ):
                    signal["signals"].append({
                        "code": code,
                        "name": get_stock_name(code, names),
                        "weight": round(weight, 4),
                    })
        except Exception:
            pass

    # If no pending target_weights, read latest signal CSV
    if not has_pending:
        signal_files = sorted(output_dir.glob("live_signal_*.csv"), reverse=True)
        if signal_files:
            try:
                import csv
                with open(signal_files[0]) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        code = row.get("code", "")
                        weight = float(row.get("weight", 0))
                        signal["signals"].append({
                            "code": code,
                            "name": get_stock_name(code, names),
                            "weight": round(weight, 4),
                        })
            except Exception:
                pass

    return signal


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

    # Always push portfolio + signal (lightweight, always useful)
    print("\n[Portfolio]")
    portfolio = collect_portfolio()
    post_json(server, "/api/push/portfolio", portfolio)

    print("\n[Signal]")
    signal = collect_signal()
    if signal["signals"]:
        post_json(server, "/api/push/signal", signal)
    else:
        print("  (no signal data found)")

    if args.status_only:
        print("\nDone (status-only, skipped nav/backtest).")
        return

    # Push nav
    print("\n[NAV]")
    nav = collect_nav()
    if nav["records"]:
        post_json(server, "/api/push/nav", nav)
    else:
        print("  (no nav data found)")

    # Push backtest nav (for comparison overlay)
    print("\n[Backtest NAV]")
    bt_nav = collect_backtest_nav()
    if bt_nav["records"]:
        post_json(server, "/api/push/backtest_nav", bt_nav)
    else:
        print("  (no backtest data found)")

    print("\nDone.")


if __name__ == "__main__":
    main()
