from __future__ import annotations

import os
import sys
from pathlib import Path

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

STOCK_ID = "2890"
STOCK_NAME = "永豐金"

SOURCE_URL = (
    "https://www.sinopac.com/"
)

YTD_TOLERANCE = 1.0


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

    load_dotenv(
        ENV_FILE
    )

    database_url = os.getenv(
        "TURSO_DEV_DATABASE_URL"
    )

    auth_token = os.getenv(
        "TURSO_DEV_AUTH_TOKEN"
    )

    if not database_url:

        raise RuntimeError(
            "TURSO_DEV_DATABASE_URL is missing"
        )

    if not auth_token:

        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN is missing"
        )

    lower_url = database_url.lower()

    if "stockwave-dev" not in lower_url:

        raise RuntimeError(
            "Backfill must use stockwave-dev database"
        )

    if "stockwave-prod" in lower_url:

        raise RuntimeError(
            "Production database detected. Backfill aborted."
        )

    print()
    print(
        "[PASS] DEV database safety check"
    )

    return libsql.connect(
        database_url,
        auth_token=auth_token,
    )


def build_2025_rows():

    return [
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-01",
            "monthly_net_profit": 2903.0,
            "ytd_net_profit": 2903.0,
            "ytd_eps": 0.23,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-02",
            "monthly_net_profit": 2442.0,
            "ytd_net_profit": 5345.0,
            "ytd_eps": 0.42,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-03",
            "monthly_net_profit": 1857.0,
            "ytd_net_profit": 7202.0,
            "ytd_eps": 0.57,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-04",
            "monthly_net_profit": 1825.0,
            "ytd_net_profit": 9027.0,
            "ytd_eps": 0.71,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-05",
            "monthly_net_profit": 1331.0,
            "ytd_net_profit": 10358.0,
            "ytd_eps": 0.82,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-06",
            "monthly_net_profit": 2320.0,
            "ytd_net_profit": 12678.0,
            "ytd_eps": 1.00,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-07",
            "monthly_net_profit": 2606.0,
            "ytd_net_profit": 15283.0,
            "ytd_eps": 1.20,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-08",
            "monthly_net_profit": 2790.0,
            "ytd_net_profit": 18073.0,
            "ytd_eps": 1.38,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-09",
            "monthly_net_profit": 2471.0,
            "ytd_net_profit": 20544.0,
            "ytd_eps": 1.57,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-10",
            "monthly_net_profit": 2401.0,
            "ytd_net_profit": 22945.0,
            "ytd_eps": 1.72,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-11",
            "monthly_net_profit": 1992.0,
            "ytd_net_profit": 24938.0,
            "ytd_eps": 1.87,
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-12",
            "monthly_net_profit": 1565.0,
            "ytd_net_profit": 26502.0,
            "ytd_eps": 1.97,
        },
    ]


def validate_rows(
    rows,
):

    expected_months = {
        f"2025-{month:02d}"
        for month in range(
            1,
            13,
        )
    }

    actual_months = {
        row["data_month"]
        for row in rows
    }

    if actual_months != expected_months:

        missing = sorted(
            expected_months
            - actual_months
        )

        extra = sorted(
            actual_months
            - expected_months
        )

        raise RuntimeError(
            "Unexpected SinoPac rows. "
            f"Missing={missing}, Extra={extra}"
        )

    if len(rows) != 12:

        raise RuntimeError(
            "Expected 12 SinoPac 2025 rows"
        )

    previous = None

    print()
    print("=" * 70)
    print("YTD RECONCILIATION")
    print("=" * 70)

    for row in rows:

        data_month = row[
            "data_month"
        ]

        monthly = row[
            "monthly_net_profit"
        ]

        ytd = row[
            "ytd_net_profit"
        ]

        eps = row[
            "ytd_eps"
        ]

        if monthly is None:

            raise RuntimeError(
                f"{data_month} monthly_net_profit is NULL"
            )

        if ytd is None:

            raise RuntimeError(
                f"{data_month} ytd_net_profit is NULL"
            )

        if eps is None:

            raise RuntimeError(
                f"{data_month} ytd_eps is NULL"
            )

        if previous is None:

            diff = round(
                ytd - monthly,
                2,
            )

            status = (
                "PASS"
                if abs(diff)
                <= YTD_TOLERANCE
                else "FAIL"
            )

            print(
                f"{data_month} "
                f"Monthly={monthly} "
                f"YTD={ytd} "
                f"Diff={diff} "
                f"[{status}]"
            )

            if (
                abs(diff)
                > YTD_TOLERANCE
            ):

                raise RuntimeError(
                    f"{data_month} base reconciliation failed"
                )

            previous = row
            continue

        previous_ytd = previous[
            "ytd_net_profit"
        ]

        expected_ytd = round(
            previous_ytd
            + monthly,
            2,
        )

        diff = round(
            ytd
            - expected_ytd,
            2,
        )

        status = (
            "PASS"
            if abs(diff)
            <= YTD_TOLERANCE
            else "FAIL"
        )

        print(
            f"{data_month} "
            f"PrevYTD={previous_ytd} "
            f"Monthly={monthly} "
            f"Expected={expected_ytd} "
            f"YTD={ytd} "
            f"Diff={diff} "
            f"[{status}]"
        )

        if (
            abs(diff)
            > YTD_TOLERANCE
        ):

            raise RuntimeError(
                f"{data_month} YTD reconciliation failed"
            )

        previous = row

    print()
    print(
        "[PASS] 2025 source rows validated: 12/12"
    )


def upsert_rows(
    conn,
    rows,
):

    sql = """
        INSERT INTO
            financial_holding_monthly
        (
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
        VALUES
        (
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
        ON CONFLICT(
            stock_id,
            data_month
        )
        DO UPDATE SET
            monthly_net_profit =
                excluded.monthly_net_profit,

            ytd_net_profit =
                excluded.ytd_net_profit,

            ytd_eps =
                excluded.ytd_eps,

            source_date =
                excluded.source_date,

            source_url =
                excluded.source_url,

            data_status =
                excluded.data_status,

            updated_at =
                CURRENT_TIMESTAMP
    """

    count = 0

    for row in rows:

        conn.execute(
            sql,
            (
                row["stock_id"],
                row["data_month"],
                row["monthly_net_profit"],
                row["ytd_net_profit"],
                row["ytd_eps"],
                SOURCE_URL,
            ),
        )

        count += 1

    print()
    print(
        f"[PASS] 2025 upserted rows: {count}"
    )


def get_2026_rows(
    conn,
):

    result = conn.execute(
        """
        SELECT
            stock_id,
            data_month,
            ytd_net_profit
        FROM
            financial_holding_monthly
        WHERE
            stock_id = ?
            AND data_month >= '2026-01'
            AND data_month <= '2026-12'
        ORDER BY
            data_month
        """,
        (
            STOCK_ID,
        ),
    )

    return [
        {
            "stock_id": row[0],
            "data_month": row[1],
            "ytd_net_profit": row[2],
        }
        for row in result.fetchall()
    ]


def get_previous_year_ytd(
    conn,
    data_month,
):

    year_text, month_text = (
        data_month.split("-")
    )

    previous_month = (
        f"{int(year_text) - 1}-"
        f"{month_text}"
    )

    result = conn.execute(
        """
        SELECT
            ytd_net_profit
        FROM
            financial_holding_monthly
        WHERE
            stock_id = ?
            AND data_month = ?
        LIMIT 1
        """,
        (
            STOCK_ID,
            previous_month,
        ),
    )

    row = result.fetchone()

    if row is None:

        return None

    return row[0]


def update_yoy_metrics(
    conn,
    current_rows,
):

    updated_count = 0
    skipped_count = 0

    print()
    print("=" * 70)
    print("UPDATE 2026 YOY")
    print("=" * 70)

    for row in current_rows:

        data_month = row[
            "data_month"
        ]

        current_ytd = row[
            "ytd_net_profit"
        ]

        previous_ytd = (
            get_previous_year_ytd(
                conn,
                data_month,
            )
        )

        if previous_ytd is None:

            print(
                f"{data_month} "
                "PrevYTD=NULL "
                "YoY=NULL "
                "[SKIP]"
            )

            skipped_count += 1
            continue

        if current_ytd is None:

            print(
                f"{data_month} "
                f"PrevYTD={previous_ytd} "
                "CurrentYTD=NULL "
                "YoY=NULL "
                "[SKIP]"
            )

            skipped_count += 1
            continue

        if previous_ytd == 0:

            yoy = None

        else:

            yoy = round(
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
            UPDATE
                financial_holding_monthly
            SET
                previous_year_ytd_net_profit = ?,
                ytd_profit_yoy_pct = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE
                stock_id = ?
                AND data_month = ?
            """,
            (
                previous_ytd,
                yoy,
                STOCK_ID,
                data_month,
            ),
        )

        print(
            f"{data_month} "
            f"YTD={current_ytd} "
            f"PrevYTD={previous_ytd} "
            f"YoY={yoy}% "
            "[UPDATED]"
        )

        updated_count += 1

    print()
    print(
        "[PASS] "
        f"2026 YoY updated rows: "
        f"{updated_count}"
    )

    print(
        "[INFO] "
        f"2026 YoY skipped rows: "
        f"{skipped_count}"
    )


def verify_2025(
    conn,
):

    result = conn.execute(
        """
        SELECT
            data_month,
            monthly_net_profit,
            ytd_net_profit,
            ytd_eps,
            data_status
        FROM
            financial_holding_monthly
        WHERE
            stock_id = ?
            AND data_month >= '2025-01'
            AND data_month <= '2025-12'
        ORDER BY
            data_month
        """,
        (
            STOCK_ID,
        ),
    )

    rows = result.fetchall()

    print()
    print("=" * 70)
    print("VERIFY 2025")
    print("=" * 70)

    for row in rows:

        print(
            f"{row[0]} "
            f"Monthly={row[1]} "
            f"YTD={row[2]} "
            f"EPS={row[3]} "
            f"Status={row[4]}"
        )

    if len(rows) != 12:

        raise RuntimeError(
            f"2025 verification failed: "
            f"expected 12 rows, got {len(rows)}"
        )

    print()
    print(
        "[PASS] 2025-01 ~ 2025-12 verified"
    )


def verify_2026(
    conn,
):

    result = conn.execute(
        """
        SELECT
            data_month,
            ytd_net_profit,
            previous_year_ytd_net_profit,
            ytd_profit_yoy_pct
        FROM
            financial_holding_monthly
        WHERE
            stock_id = ?
            AND data_month >= '2026-01'
            AND data_month <= '2026-12'
        ORDER BY
            data_month
        """,
        (
            STOCK_ID,
        ),
    )

    rows = result.fetchall()

    print()
    print("=" * 70)
    print("VERIFY 2026 YOY")
    print("=" * 70)

    if not rows:

        print(
            "NO 2026 ROWS"
        )

        return

    for row in rows:

        print(
            f"{row[0]} "
            f"YTD={row[1]} "
            f"PrevYTD={row[2]} "
            f"YoY={row[3]}"
        )

        if (
            row[1] is not None
            and row[2] is None
        ):

            raise RuntimeError(
                f"{row[0]} "
                "missing previous year YTD"
            )

    print()
    print(
        "[PASS] 2026 YoY verification"
    )


def main():

    configure_console()

    print("=" * 70)

    print(
        "StockWaveScanner V3 - "
        "SinoPac Historical Backfill"
    )

    print("=" * 70)

    print()
    print(
        f"Stock: {STOCK_ID} {STOCK_NAME}"
    )

    print(
        "Target: 2025-01 ~ 2025-12"
    )

    rows = build_2025_rows()

    #
    # 先完整驗證來源資料，
    # 通過後才允許連 DB。
    #
    validate_rows(
        rows
    )

    conn = get_connection()

    try:

        upsert_rows(
            conn,
            rows,
        )

        current_rows = (
            get_2026_rows(
                conn
            )
        )

        update_yoy_metrics(
            conn,
            current_rows,
        )

        conn.commit()

        print()
        print(
            "[PASS] DEV transaction committed"
        )

        verify_2025(
            conn
        )

        verify_2026(
            conn
        )

    except Exception:

        try:

            conn.rollback()

            print()
            print(
                "[ROLLBACK] "
                "DEV transaction rolled back"
            )

        except Exception:
            pass

        raise

    finally:

        conn.close()

    print()
    print("=" * 70)

    print(
        "SINOPAC HISTORICAL BACKFILL OK"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )