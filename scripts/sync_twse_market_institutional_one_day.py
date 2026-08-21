from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import argparse
from datetime import datetime

from crawler.twse_market_institutional import SOURCE, download_day
from db.database import get_connection
from db.repository import crawl_success_exists


def parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期格式必須為 YYYY-MM-DD") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="同步 TWSE 單日全市場外資")
    parser.add_argument("--date", required=True, type=parse_date)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    trade_date = args.date
    request_key = trade_date.strftime("%Y%m%d")

    if trade_date.weekday() >= 5:
        print(f"[SKIP] {trade_date} 為週末")
        return

    conn = get_connection()
    try:
        has_price = conn.execute(
            "SELECT 1 FROM daily_prices WHERE market='TWSE' AND trade_date=? LIMIT 1",
            (trade_date.isoformat(),),
        ).fetchone() is not None
    finally:
        conn.close()

    if not has_price:
        print(f"[SKIP] {trade_date} TWSE 無 daily price，視為非交易日/無行情日")
        return

    if not args.force and crawl_success_exists(SOURCE, request_key):
        print(f"[SKIP] {trade_date} 已有 SUCCESS")
        return

    count = download_day(trade_date)
    print(f"[OK] TWSE foreign {trade_date}: {count:,} rows")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        sys.exit(1)
