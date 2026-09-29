from __future__ import annotations

import os
import sys
from pathlib import Path

import libsql
from dotenv import load_dotenv

from parse_v3_financial_holding_mega import parse_mega


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


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


def sync_rows(
    conn,
    rows,
):

    sql = """
    INSERT INTO financial_holding_monthly (
        stock_id,
        data_month,
        monthly_net_profit,
        ytd_net_profit,
        ytd_eps,
        previous_year_ytd_net_profit,
        ytd_profit_yoy_pct,
        source_date,
        source_url,
        data_status,
        created_at,
        updated_at
    )
    VALUES (
        ?,
        ?,
        ?,
        ?,
        ?,
        NULL,
        NULL,
        NULL,
        ?,
        'STORED',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    )
    ON CONFLICT(stock_id, data_month)
    DO UPDATE SET
        monthly_net_profit = excluded.monthly_net_profit,
        ytd_net_profit = excluded.ytd_net_profit,
        ytd_eps = excluded.ytd_eps,
        source_url = excluded.source_url,
        data_status = excluded.data_status,
        updated_at = CURRENT_TIMESTAMP
    """

    for row in rows:

        conn.execute(
            sql,
            (
                row["stock_id"],
                row["data_month"],
                row["monthly_net_profit"],
                row["ytd_net_profit"],
                row["ytd_eps"],
                row["source_url"],
            ),
        )

    return len(rows)


def update_all_yoy(
    conn,
):

    rows = conn.execute(
        """
        SELECT
            stock_id,
            data_month,
            ytd_net_profit
        FROM financial_holding_monthly
        WHERE stock_id = '2886'
          AND ytd_net_profit IS NOT NULL
        ORDER BY data_month
        """
    ).fetchall()

    lookup = {
        row[1]: row[2]
        for row in rows
    }

    update_count = 0

    for row in rows:

        stock_id = row[0]
        data_month = row[1]
        current_ytd = row[2]

        year, month = (
            data_month.split("-")
        )

        previous_month = (
            f"{int(year) - 1}-{month}"
        )

        previous_ytd = lookup.get(
            previous_month
        )

        if previous_ytd is None:
            continue

        if previous_ytd == 0:

            yoy_pct = None

        else:

            yoy_pct = round(
                (
                    current_ytd
                    / previous_ytd
                    - 1
                )
                * 100,
                2,
            )

        conn.execute(
            """
            UPDATE financial_holding_monthly
            SET
                previous_year_ytd_net_profit = ?,
                ytd_profit_yoy_pct = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE stock_id = ?
              AND data_month = ?
            """,
            (
                previous_ytd,
                yoy_pct,
                stock_id,
                data_month,
            ),
        )

        update_count += 1

    return update_count


def verify(
    conn,
):

    return conn.execute(
        """
        SELECT
            data_month,
            monthly_net_profit,
            ytd_net_profit,
            ytd_eps,
            previous_year_ytd_net_profit,
            ytd_profit_yoy_pct
        FROM financial_holding_monthly
        WHERE stock_id = '2886'
        ORDER BY data_month DESC
        LIMIT 12
        """
    ).fetchall()


def main():

    configure_console()

    print("=" * 70)
    print(
        "StockWaveScanner V3 - "
        "Mega Historical Backfill"
    )
    print("=" * 70)

    conn = get_connection()

    try:

        rows = parse_mega()

        sync_count = sync_rows(
            conn,
            rows,
        )

        yoy_count = update_all_yoy(
            conn
        )

        conn.commit()

        print()
        print(
            f"[PASS] Mega backfill rows: "
            f"{sync_count}"
        )

        print(
            f"[PASS] Mega YoY rows: "
            f"{yoy_count}"
        )

        print()

        for row in verify(conn):

            yoy_text = (
                f"{row[5]:.2f}%"
                if row[5] is not None
                else "N/A"
            )

            prev_text = (
                row[4]
                if row[4] is not None
                else "N/A"
            )

            print(
                f"{row[0]} "
                f"Monthly={row[1]} "
                f"YTD={row[2]} "
                f"EPS={row[3]} "
                f"PrevYTD={prev_text} "
                f"YoY={yoy_text}"
            )

        print()
        print("=" * 70)
        print(
            "MEGA HISTORICAL BACKFILL OK"
        )
        print("=" * 70)

        return 0

    except Exception as exc:

        conn.rollback()

        print()
        print("ERROR")
        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return 1

    finally:

        conn.close()


if __name__ == "__main__":

    sys.exit(
        main()
    )