from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import argparse
from datetime import datetime

from crawler.tpex_market_institutional import SOURCE
from db.database import get_connection
from db.repository import crawl_success_exists
from scripts.sync_tpex_market_institutional import sync_one_day


REQUEST_KEY_PREFIX = "TPEX_QFII_STAT"


def parse_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期格式必須為 YYYY-MM-DD") from exc
    return value


def _has_price(trade_date: str) -> bool:
    conn = get_connection()
    try:
        return (
            conn.execute(
                """
                SELECT 1 FROM daily_prices
                WHERE market='TPEx' AND trade_date=?
                LIMIT 1
                """,
                (trade_date,),
            ).fetchone()
            is not None
        )
    finally:
        conn.close()


def _has_normalized_foreign(trade_date: str) -> bool:
    conn = get_connection()
    try:
        return (
            conn.execute(
                """
                SELECT 1 FROM institutional_trades
                WHERE market='TPEx' AND trade_date=?
                LIMIT 1
                """,
                (trade_date,),
            ).fetchone()
            is not None
        )
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="同步 TPEx 單日全市場外資（交易日安全 wrapper）")
    parser.add_argument("--date", required=True, type=parse_date)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not _has_price(args.date):
        print(f"[SKIP] {args.date} TPEx 無 daily price，視為非交易日/無行情日")
        return

    request_key = f"{REQUEST_KEY_PREFIX}:{args.date}"
    has_success = crawl_success_exists(SOURCE, request_key)
    has_rows = _has_normalized_foreign(args.date)

    if not args.force and has_success and has_rows:
        print(f"[SKIP] {args.date} 已有 SUCCESS 且 institutional_trades 已存在")
        return

    effective_force = args.force
    if not args.force and has_success and not has_rows:
        print(
            f"[RETRY] {args.date} crawl log 為 SUCCESS，"
            "但 institutional_trades 不存在；視為 stale SUCCESS，重新抓取"
        )
        effective_force = True

    sync_one_day(trade_date=args.date, force=effective_force)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        sys.exit(1)
