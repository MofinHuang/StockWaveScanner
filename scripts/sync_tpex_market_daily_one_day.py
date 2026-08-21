from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import argparse
from datetime import datetime

from crawler.tpex_market_daily import SOURCE, download_day
from db.repository import crawl_success_exists


def parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期格式必須為 YYYY-MM-DD") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="同步 TPEx 單日全市場日 K")
    parser.add_argument("--date", required=True, type=parse_date)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    trade_date = args.date
    request_key = trade_date.strftime("%Y%m%d")

    if trade_date.weekday() >= 5:
        print(f"[SKIP] {trade_date} 為週末")
        return

    if not args.force and crawl_success_exists(SOURCE, request_key):
        print(f"[SKIP] {trade_date} 已有 SUCCESS")
        return

    count = download_day(trade_date)
    print(f"[OK] TPEx price {trade_date}: {count:,} rows")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        sys.exit(1)
