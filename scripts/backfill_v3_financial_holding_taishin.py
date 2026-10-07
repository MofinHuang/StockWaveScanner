from __future__ import annotations

import os
import sys
from pathlib import Path

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

STOCK_ID = "2887"
STOCK_NAME = "台新新光金"

YTD_TOLERANCE = 10.0

OLD_REVENUE_URL = (
    "https://www.taishinholdings.com.tw/"
    "tsh/relations/finance/revenue/index.html"
)

NEW_MAJOR_URL = (
    "https://www.tsholdings.com.tw/"
    "tsh/relations/major/"
)


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


def build_2025_rows():

    return [
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-01",
            "monthly_net_profit": 1590.0,
            "ytd_net_profit": 1590.0,
            "ytd_eps": 0.11,
            "source_url": OLD_REVENUE_URL,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-02",
            "monthly_net_profit": 2010.0,
            "ytd_net_profit": 3600.0,
            "ytd_eps": 0.25,
            "source_url": OLD_REVENUE_URL,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-03",
            "monthly_net_profit": 1130.0,
            "ytd_net_profit": 4730.0,
            "ytd_eps": 0.33,
            "source_url": OLD_REVENUE_URL,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-04",
            "monthly_net_profit": 1270.0,
            "ytd_net_profit": 6000.0,
            "ytd_eps": 0.41,
            "source_url": OLD_REVENUE_URL,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-05",
            "monthly_net_profit": 560.0,
            "ytd_net_profit": 6560.0,
            "ytd_eps": 0.44,
            "source_url": OLD_REVENUE_URL,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-06",
            "monthly_net_profit": 3670.0,
            "ytd_net_profit": 10220.0,
            "ytd_eps": 0.71,
            "source_url": OLD_REVENUE_URL,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-07",
            "monthly_net_profit": 3620.0,
            "ytd_net_profit": 13840.0,
            "ytd_eps": 0.92,
            "source_url": NEW_MAJOR_URL,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-08",
            "monthly_net_profit": 4700.0,
            "ytd_net_profit": 18540.0,
            "ytd_eps": 1.13,
            "source_url": NEW_MAJOR_URL,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-09",
            "monthly_net_profit": 4090.0,
            "ytd_net_profit": 22630.0,
            "ytd_eps": 1.30,
            "source_url": NEW_MAJOR_URL,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-10",
            "monthly_net_profit": 6070.0,
            "ytd_net_profit": 28700.0,
            "ytd_eps": 1.57,
            "source_url": NEW_MAJOR_URL,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-11",
            "monthly_net_profit": 5200.0,
            "ytd_net_profit": 33900.0,
            "ytd_eps": 1.79,
            "source_url": NEW_MAJOR_URL,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-12",
            "monthly_net_profit": 3460.0,
            "ytd_net_profit": 37360.0,
            "ytd_eps": 1.91,
            "source_url": NEW_MAJOR_URL,
        },
    ]


def validate_rows(rows):

    expected_months = [
        f"2025-{month:02d}"
        for month in range(1, 13)
    ]

    actual_months = [
        row["data_month"]
        for row in rows
    ]

    if actual_months != expected_months:

        raise RuntimeError(
            "2025 month coverage invalid\n"
            f"Expected: {expected_months}\n"
            f"Actual  : {actual_months}"
        )

    if len(rows) != 12:

        raise RuntimeError(
            f"Expected 12 rows, got {len(rows)}"
        )

    previous_ytd = 0.0

    print()
    print("=" * 70)
    print("YTD RECONCILIATION")
    print("=" * 70)

    for row in rows:

        for field in (
            "monthly_net_profit",
            "ytd_net_profit",
            "ytd_eps",
        ):

            if row[field] is None:

                raise RuntimeError(
                    f"{row['data_month']} "
                    f"{field} is NULL"
                )

        monthly = row[
            "monthly_net_profit"
        ]

        ytd = row[
            "ytd_net_profit"
        ]

        expected_ytd = round(
            previous_ytd + monthly,
            2,
        )

        diff = round(
            ytd - expected_ytd,
            2,
        )

        if abs(diff) > YTD_TOLERANCE:

            raise RuntimeError(
                f"{row['data_month']} "
                f"YTD reconciliation failed: "
                f"Prev={previous_ytd}, "
                f"Monthly={monthly}, "
                f"Expected={expected_ytd}, "
                f"Actual={ytd}, "
                f"Diff={diff}"
            )

        print(
            f"{row['data_month']} "
            f"Prev={previous_ytd:.1f} "
            f"Monthly={monthly:.1f} "
            f"Expected={expected_ytd:.1f} "
            f"Actual={ytd:.1f} "
            f"Diff={diff:.1f} "
            "[PASS]"
        )

        previous_ytd = ytd


def upsert_rows(
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


def get_2026_rows(
    conn,
):

    result = conn.execute(
        """
        SELECT
            stock_id,
            data_month,
            ytd_net_profit
        FROM financial_holding_monthly
        WHERE stock_id = ?
          AND data_month >= '2026-01'
          AND data_month <= '2026-12'
          AND ytd_net_profit IS NOT NULL
        ORDER BY data_month
        """,
        (
            STOCK_ID,
        ),
    ).fetchall()

    return [
        {
            "stock_id": row[0],
            "data_month": row[1],
            "ytd_net_profit": row[2],
        }
        for row in result
    ]


def update_yoy_metrics(
    conn,
    rows,
):

    update_sql = """
    UPDATE financial_holding_monthly
    SET
        previous_year_ytd_net_profit = ?,
        ytd_profit_yoy_pct = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE stock_id = ?
      AND data_month = ?
    """

    update_count = 0

    for row in rows:

        stock_id = row[
            "stock_id"
        ]

        data_month = row[
            "data_month"
        ]

        current_ytd = row[
            "ytd_net_profit"
        ]

        year, month = (
            data_month.split("-")
        )

        previous_month = (
            f"{int(year) - 1}-{month}"
        )

        previous_row = conn.execute(
            """
            SELECT
                ytd_net_profit
            FROM financial_holding_monthly
            WHERE stock_id = ?
              AND data_month = ?
              AND ytd_net_profit IS NOT NULL
            LIMIT 1
            """,
            (
                stock_id,
                previous_month,
            ),
        ).fetchone()

        if previous_row is None:

            print(
                f"[WARN] {data_month} "
                f"previous YTD not found"
            )

            continue

        previous_ytd = previous_row[0]

        if previous_ytd == 0:

            yoy_pct = None

        else:

            yoy_pct = round(
                (
                    (
                        current_ytd
                        / previous_ytd
                    )
                    - 1
                )
                * 100,
                2,
            )

        conn.execute(
            update_sql,
            (
                previous_ytd,
                yoy_pct,
                stock_id,
                data_month,
            ),
        )

        update_count += 1

    return update_count


def verify_2025(
    conn,
):

    return conn.execute(
        """
        SELECT
            data_month,
            monthly_net_profit,
            ytd_net_profit,
            ytd_eps
        FROM financial_holding_monthly
        WHERE stock_id = ?
          AND data_month >= '2025-01'
          AND data_month <= '2025-12'
        ORDER BY data_month
        """,
        (
            STOCK_ID,
        ),
    ).fetchall()


def verify_2026(
    conn,
):

    return conn.execute(
        """
        SELECT
            data_month,
            ytd_net_profit,
            previous_year_ytd_net_profit,
            ytd_profit_yoy_pct
        FROM financial_holding_monthly
        WHERE stock_id = ?
          AND data_month >= '2026-01'
          AND data_month <= '2026-12'
        ORDER BY data_month
        """,
        (
            STOCK_ID,
        ),
    ).fetchall()


def print_verify_2025(
    rows,
):

    print()
    print("=" * 70)
    print("VERIFY 2025")
    print("=" * 70)

    if len(rows) != 12:

        raise RuntimeError(
            f"DEV verify failed: "
            f"2025 rows={len(rows)}, "
            f"expected=12"
        )

    for row in rows:

        print(
            f"{row[0]} "
            f"Monthly={row[1]} "
            f"YTD={row[2]} "
            f"EPS={row[3]}"
        )


def print_verify_2026(
    rows,
):

    print()
    print("=" * 70)
    print("VERIFY 2026 YOY")
    print("=" * 70)

    for row in rows:

        yoy_text = (
            f"{row[3]:.2f}%"
            if row[3] is not None
            else "N/A"
        )

        print(
            f"{row[0]} "
            f"YTD={row[1]} "
            f"PrevYTD={row[2]} "
            f"YoY={yoy_text}"
        )


def main():

    configure_console()

    print("=" * 70)

    print(
        "StockWaveScanner V3 - "
        "Taishin Historical Backfill"
    )

    print("=" * 70)

    rows = build_2025_rows()

    #
    # 先完整驗證。
    # 尚未連線 Turso。
    #
    validate_rows(
        rows
    )

    print()
    print(
        "[PASS] 2025 source rows "
        "validated: 12/12"
    )

    #
    # 驗證全部成功後，
    # 才允許連線 DEV。
    #
    conn = get_connection()

    try:

        insert_count = upsert_rows(
            conn,
            rows,
        )

        rows_2026 = get_2026_rows(
            conn
        )

        yoy_count = update_yoy_metrics(
            conn,
            rows_2026,
        )

        #
        # Atomic：
        # 所有 DB 工作完成後
        # 最後才 commit。
        #
        conn.commit()

        print()
        print(
            f"[PASS] 2025 upserted rows: "
            f"{insert_count}"
        )

        print(
            f"[PASS] 2026 YoY updated rows: "
            f"{yoy_count}"
        )

        verify_2025_rows = verify_2025(
            conn
        )

        verify_2026_rows = verify_2026(
            conn
        )

        print_verify_2025(
            verify_2025_rows
        )

        print_verify_2026(
            verify_2026_rows
        )

        print()
        print("=" * 70)
        print(
            "TAISHIN HISTORICAL BACKFILL OK"
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