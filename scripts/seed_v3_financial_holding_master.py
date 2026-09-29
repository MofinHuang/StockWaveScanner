from __future__ import annotations

import os
import sys
from pathlib import Path

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


FINANCIAL_HOLDINGS = [
    {
        "stock_id": "2880",
        "stock_name": "華南金",
        "holding_type": "BANK",
        "sort_order": 10,
    },
    {
        "stock_id": "2881",
        "stock_name": "富邦金",
        "holding_type": "INSURANCE",
        "sort_order": 20,
    },
    {
        "stock_id": "2882",
        "stock_name": "國泰金",
        "holding_type": "INSURANCE",
        "sort_order": 30,
    },
    {
        "stock_id": "2883",
        "stock_name": "凱基金",
        "holding_type": "MIXED",
        "sort_order": 40,
    },
    {
        "stock_id": "2884",
        "stock_name": "玉山金",
        "holding_type": "BANK",
        "sort_order": 50,
    },
    {
        "stock_id": "2885",
        "stock_name": "元大金",
        "holding_type": "SECURITIES",
        "sort_order": 60,
    },
    {
        "stock_id": "2886",
        "stock_name": "兆豐金",
        "holding_type": "BANK",
        "sort_order": 70,
    },
    {
        "stock_id": "2887",
        "stock_name": "台新新光金",
        "holding_type": "MIXED",
        "sort_order": 80,
    },
    {
        "stock_id": "2889",
        "stock_name": "國票金",
        "holding_type": "SECURITIES",
        "sort_order": 90,
    },
    {
        "stock_id": "2890",
        "stock_name": "永豐金",
        "holding_type": "BANK",
        "sort_order": 100,
    },
    {
        "stock_id": "2891",
        "stock_name": "中信金",
        "holding_type": "BANK",
        "sort_order": 110,
    },
    {
        "stock_id": "2892",
        "stock_name": "第一金",
        "holding_type": "BANK",
        "sort_order": 120,
    },
    {
        "stock_id": "5880",
        "stock_name": "合庫金",
        "holding_type": "BANK",
        "sort_order": 130,
    },
]


VALID_HOLDING_TYPES = {
    "BANK",
    "INSURANCE",
    "SECURITIES",
    "MIXED",
}


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


def validate_seed_data():

    stock_ids = set()

    for item in FINANCIAL_HOLDINGS:

        stock_id = item["stock_id"]
        stock_name = item["stock_name"]
        holding_type = item["holding_type"]

        if not stock_id:
            raise RuntimeError(
                "stock_id cannot be empty"
            )

        if not stock_name:
            raise RuntimeError(
                f"{stock_id}: stock_name cannot be empty"
            )

        if holding_type not in VALID_HOLDING_TYPES:
            raise RuntimeError(
                f"{stock_id}: invalid holding_type "
                f"{holding_type}"
            )

        if stock_id in stock_ids:
            raise RuntimeError(
                f"duplicate stock_id: {stock_id}"
            )

        stock_ids.add(stock_id)

    if len(FINANCIAL_HOLDINGS) != 13:
        raise RuntimeError(
            "Financial Holding Universe must contain 13 stocks"
        )


def seed_financial_holdings(conn):

    sql = """
    INSERT INTO financial_holding_master (
        stock_id,
        stock_name,
        holding_type,
        official_source_url,
        active,
        sort_order,
        created_at,
        updated_at
    )
    VALUES (
        ?,
        ?,
        ?,
        NULL,
        1,
        ?,
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    )
    ON CONFLICT(stock_id)
    DO UPDATE SET
        stock_name = excluded.stock_name,
        holding_type = excluded.holding_type,
        active = excluded.active,
        sort_order = excluded.sort_order,
        updated_at = CURRENT_TIMESTAMP
    """

    for item in FINANCIAL_HOLDINGS:

        conn.execute(
            sql,
            (
                item["stock_id"],
                item["stock_name"],
                item["holding_type"],
                item["sort_order"],
            ),
        )


def verify_seed(conn):

    rows = conn.execute(
        """
        SELECT
            stock_id,
            stock_name,
            holding_type,
            active,
            sort_order
        FROM financial_holding_master
        WHERE active = 1
        ORDER BY sort_order, stock_id
        """
    ).fetchall()

    if len(rows) != 13:
        raise RuntimeError(
            f"Expected 13 active financial holdings, "
            f"got {len(rows)}"
        )

    return rows


def main():

    configure_console()

    print("=" * 70)
    print("StockWaveScanner V3 - Financial Holding Master Seed")
    print("=" * 70)

    validate_seed_data()

    conn = get_connection()

    try:

        seed_financial_holdings(conn)

        conn.commit()

        rows = verify_seed(conn)

        print()
        print("[PASS] Financial Holding Master")
        print()

        for row in rows:

            stock_id = row[0]
            stock_name = row[1]
            holding_type = row[2]

            print(
                f"  {stock_id}  "
                f"{stock_name:<10} "
                f"{holding_type}"
            )

        print()
        print(
            f"Total: {len(rows)}"
        )

        print()
        print(
            "FINANCIAL HOLDING MASTER SEED OK"
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