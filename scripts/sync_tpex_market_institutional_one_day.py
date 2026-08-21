from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import argparse
from datetime import datetime

from db.database import get_connection
from scripts.sync_tpex_market_institutional import sync_one_day


def parse_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期格式必須為 YYYY-MM-DD") from exc
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="同步 TPEx 單日全市場外資（交易日安全 wrapper）")
    parser.add_argument("--date", required=True, type=parse_date)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    conn = get_connection()
    try:
        has_price = conn.execute(
            "SELECT 1 FROM daily_prices WHERE market='TPEx' AND trade_date=? LIMIT 1",
            (args.date,),
        ).fetchone() is not None
    finally:
        conn.close()

    if not has_price:
        print(f"[SKIP] {args.date} TPEx 無 daily price，視為非交易日/無行情日")
        return

    sync_one_day(trade_date=args.date, force=args.force)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        sys.exit(1)
