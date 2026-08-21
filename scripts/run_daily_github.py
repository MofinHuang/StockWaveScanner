from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import deque
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


TAIPEI = ZoneInfo("Asia/Taipei")


def _now() -> str:
    return datetime.now(TAIPEI).isoformat(timespec="seconds")


def _run(command: list[str]) -> tuple[int, list[str]]:
    print("$", " ".join(command), flush=True)
    env = os.environ.copy()
    root = str(Path(__file__).resolve().parents[1])
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = root if not existing else root + os.pathsep + existing

    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    tail: deque[str] = deque(maxlen=25)
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="", flush=True)
        tail.append(line.rstrip())
    return proc.wait(), list(tail)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="StockWaveScanner GitHub Actions daily orchestrator"
    )
    parser.add_argument("--date", required=True, help="執行日 YYYY-MM-DD")
    parser.add_argument("--status-file", default="runtime/run_status.json")
    args = parser.parse_args()
    datetime.strptime(args.date, "%Y-%m-%d")

    status_path = Path(args.status_file)
    status_path.parent.mkdir(parents=True, exist_ok=True)

    py = sys.executable
    steps = [
        (
            "validate_db",
            [py, "scripts/validate_runtime_db.py", "--date", args.date],
        ),
        (
            "price_twse",
            [py, "scripts/sync_twse_market_daily_one_day.py", "--date", args.date],
        ),
        (
            "price_tpex",
            [py, "scripts/sync_tpex_market_daily_one_day.py", "--date", args.date],
        ),
        (
            "foreign_twse",
            [py, "scripts/sync_twse_market_institutional_one_day.py", "--date", args.date],
        ),
        (
            "foreign_tpex",
            [py, "scripts/sync_tpex_market_institutional_one_day.py", "--date", args.date],
        ),
        (
            "tdcc_latest",
            [py, "scripts/sync_tdcc_market_latest.py", "--run-date", args.date],
        ),
        (
            "ranking_snapshot",
            [py, "scripts/build_daily_snapshot.py", "--date", args.date, "--output-dir", "runtime"],
        ),
    ]

    state = {
        "requested_date": args.date,
        "started_at": _now(),
        "finished_at": None,
        "status": "RUNNING",
        "steps": [],
    }
    status_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = False
    for name, command in steps:
        if failed:
            state["steps"].append(
                {
                    "name": name,
                    "status": "BLOCKED",
                    "started_at": None,
                    "finished_at": None,
                    "return_code": None,
                    "log_tail": [],
                }
            )
            continue

        step = {
            "name": name,
            "status": "RUNNING",
            "started_at": _now(),
            "finished_at": None,
            "return_code": None,
            "log_tail": [],
        }
        state["steps"].append(step)
        status_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        code, tail = _run(command)
        step["finished_at"] = _now()
        step["return_code"] = code
        step["log_tail"] = tail
        if code == 0:
            step["status"] = "SUCCESS"
        else:
            step["status"] = "ERROR"
            failed = True
        status_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    state["finished_at"] = _now()
    state["status"] = "ERROR" if failed else "SUCCESS"
    status_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nDaily run status:", state["status"])
    for step in state["steps"]:
        print(f"  {step['name']:<20} {step['status']}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
