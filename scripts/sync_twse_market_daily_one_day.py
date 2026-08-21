from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import argparse
from datetime import datetime

from crawler.twse_market_daily import SOURCE, download_day
from db.database import get_connection
from db.repository import crawl_success_exists


def parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期格式必須為 YYYY-MM-DD") from exc


def normalized_rows_exist(trade_date: str) -> bool:
    conn = get_connection()
    try:
        return (
            conn.execute(
                """
                SELECT 1
                FROM daily_prices
                WHERE market='TWSE' AND trade_date=?
                LIMIT 1
                """,
                (trade_date,),
            ).fetchone()
            is not None
        )
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="同步 TWSE 單日全市場日 K")
    parser.add_argument("--date", required=True, type=parse_date)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    trade_date = args.date
    date_text = trade_date.isoformat()
    request_key = trade_date.strftime("%Y%m%d")

    if trade_date.weekday() >= 5:
        print(f"[SKIP] {trade_date} 為週末")
        return

    has_success = crawl_success_exists(SOURCE, request_key)
    has_rows = normalized_rows_exist(date_text)

    if not args.force and has_success and has_rows:
        print(f"[SKIP] {trade_date} 已有 SUCCESS 且 daily_prices 已存在")
        return

    if not args.force and has_success and not has_rows:
        print(
            f"[RETRY] {trade_date} crawl log 為 SUCCESS，"
            "但 daily_prices 不存在；視為 stale SUCCESS，重新抓取"
        )

    count = download_day(trade_date)
    print(f"[OK] TWSE price {trade_date}: {count:,} rows")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        sys.exit(1)
