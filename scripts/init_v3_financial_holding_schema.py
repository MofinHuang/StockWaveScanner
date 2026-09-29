from __future__ import annotations

import os
import sys
from pathlib import Path

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


DDL_LIST = [
    """
    CREATE TABLE IF NOT EXISTS financial_holding_master (
        stock_id TEXT PRIMARY KEY,
        stock_name TEXT NOT NULL,

        holding_type TEXT NOT NULL DEFAULT 'MIXED',

        official_source_url TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        sort_order INTEGER NOT NULL DEFAULT 0,

        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS financial_holding_monthly (
        stock_id TEXT NOT NULL,
        data_month TEXT NOT NULL,

        monthly_net_profit REAL,
        ytd_net_profit REAL,
        ytd_eps REAL,

        previous_year_ytd_net_profit REAL,
        ytd_profit_yoy_pct REAL,

        source_date TEXT,
        source_url TEXT,

        data_status TEXT NOT NULL DEFAULT 'STORED',

        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

        PRIMARY KEY (
            stock_id,
            data_month
        )
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS
        idx_financial_holding_monthly_stock_month
    ON financial_holding_monthly (
        stock_id,
        data_month
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS
        idx_financial_holding_monthly_month
    ON financial_holding_monthly (
        data_month
    )
    """,
]


def configure_console():

    for stream in (
        sys.stdout,
        sys.stderr,
    ):

        reconfigure = getattr(
            stream,
            "reconfigure",
            None,
        )

        if callable(reconfigure):

            try:

                reconfigure(
                    encoding="utf-8",
                    errors="replace",
                )

            except Exception:

                pass


def get_connection():

    load_dotenv(ENV_FILE)

    url = os.getenv(
        "TURSO_DEV_DATABASE_URL",
        "",
    ).strip()

    token = os.getenv(
        "TURSO_DEV_AUTH_TOKEN",
        "",
    ).strip()

    if not url:
        raise RuntimeError(
            "TURSO_DEV_DATABASE_URL missing"
        )

    if not token:
        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN missing"
        )

    lower_url = url.lower()

    if "stockwave-dev" not in lower_url:
        raise RuntimeError(
            "SAFETY STOP: DEV database required"
        )

    if "stockwave-prod" in lower_url:
        raise RuntimeError(
            "SAFETY STOP: PROD database detected"
        )

    return libsql.connect(
        database=url,
        auth_token=token,
    )


def main():

    configure_console()

    print("=" * 70)
    print("StockWaveScanner V3 - Financial Holding Schema Init")
    print("=" * 70)

    conn = get_connection()

    try:

        for ddl in DDL_LIST:
            conn.execute(ddl)

        conn.commit()

        tables = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name IN (
                    'financial_holding_master',
                    'financial_holding_monthly'
              )
            ORDER BY name
            """
        ).fetchall()

        print()
        print("[PASS] Tables")

        for row in tables:
            print(
                f"  {row[0]}"
            )

        print()
        print(
            "FINANCIAL HOLDING SCHEMA INIT OK"
        )

        return 0

    except Exception as exc:

        print()
        print("ERROR")
        print(
            f"{type(exc).__name__}: {exc}"
        )

        return 1

    finally:

        conn.close()


if __name__ == "__main__":

    sys.exit(
        main()
    )