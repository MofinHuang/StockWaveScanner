from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import argparse
from config import DATABASE_PATH
from db.database import get_connection


REQUIRED_TABLES = {
    "stocks",
    "daily_prices",
    "institutional_trades",
    "tdcc_holdings",
    "crawl_logs",
    "raw_responses",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="檢查 GitHub daily run 所需 SQLite DB")
    parser.add_argument("--date", required=True, help="執行日 YYYY-MM-DD；僅用於明確記錄本次檢查")
    args = parser.parse_args()

    path = Path(DATABASE_PATH)
    if not path.exists():
        raise RuntimeError(
            f"找不到資料庫：{path}. 請先建立 GitHub Release data-latest 並上傳 stocks-db.zip。"
        )

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        existing = {str(row["name"]) for row in rows}
        missing = sorted(REQUIRED_TABLES - existing)
        if missing:
            raise RuntimeError(f"資料庫缺少必要 tables: {missing}")

        quick_check = conn.execute("PRAGMA quick_check").fetchone()[0]
        if str(quick_check).lower() != "ok":
            raise RuntimeError(f"SQLite quick_check failed: {quick_check}")

        active = conn.execute(
            "SELECT COUNT(*) FROM stocks WHERE is_active=1 AND market IN ('TWSE','TPEx')"
        ).fetchone()[0]
        latest_price = conn.execute(
            "SELECT MAX(trade_date) FROM daily_prices WHERE trade_date <= ?",
            (args.date,),
        ).fetchone()[0]

        print(f"[OK] database={path}")
        print(f"[OK] active_stocks={active}")
        print(f"[OK] latest_price_on_or_before_{args.date}={latest_price}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
