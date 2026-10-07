from __future__ import annotations

import os
import sys
from pathlib import Path

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

STOCK_ID = "2884"
STOCK_NAME = "玉山金"

#
# 玉山金官方投資人專區。
# 歷史自結資料實際來自官方公告 / 法說節點，
# 此 URL 作為本次歷史 Backfill 的來源識別。
#
SOURCE_URL = (
    "https://www.esunfhc.com/"
    "zh-tw/investor-relations/financials/"
    "monthly-operating-report"
)

YTD_TOLERANCE = 15.0


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
            "TURSO_DEV_DATABASE_URL "
            "is missing"
        )

    if not auth_token:

        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN "
            "is missing"
        )

    lower_url = database_url.lower()

    #
    # Backfill 僅允許 DEV。
    #
    if "stockwave-dev" not in lower_url:

        raise RuntimeError(
            "Backfill must use "
            "stockwave-dev database"
        )

    if "stockwave-prod" in lower_url:

        raise RuntimeError(
            "Production database detected. "
            "Backfill aborted."
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
        #
        # 2025-01
        #
        # 尚未取得足以直接採用的正式月自結資料。
        #
        # 即使數學上可以由：
        #
        # 2025-02 YTD 5749
        # - 2025-02 Monthly 2724
        # = 3025
        #
        # 反推出 1 月，
        # 仍不寫入資料庫。
        #

        {
            "stock_id": STOCK_ID,
            "data_month": "2025-02",
            "monthly_net_profit": 2724.0,
            "ytd_net_profit": 5749.0,
            "ytd_eps": 0.36,
            "source_note": "114年2月自結盈餘",
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-03",

            # 官方 Q1 累計節點。
            # 不以 YTD 差額反推單月值。
            "monthly_net_profit": None,

            "ytd_net_profit": 8792.0,
            "ytd_eps": 0.55,
            "source_note": "2025 Q1 Preliminary",
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-04",

            "monthly_net_profit": None,
            "ytd_net_profit": 11300.0,
            "ytd_eps": 0.71,
            "source_note": "截至114年4月自結",
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-05",

            "monthly_net_profit": 2850.0,
            "ytd_net_profit": 14152.0,
            "ytd_eps": 0.88,
            "source_note": "114年5月自結盈餘",
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-06",

            "monthly_net_profit": None,
            "ytd_net_profit": 16753.0,
            "ytd_eps": 1.05,
            "source_note": "2025 Q2 Preliminary",
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-07",

            "monthly_net_profit": None,
            "ytd_net_profit": 20210.0,
            "ytd_eps": 1.25,
            "source_note": "截至114年7月自結",
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-08",

            "monthly_net_profit": 3094.0,
            "ytd_net_profit": 23305.0,
            "ytd_eps": 1.44,
            "source_note": "114年8月自結盈餘",
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-09",

            "monthly_net_profit": 2897.0,
            "ytd_net_profit": 26202.0,
            "ytd_eps": 1.62,
            "source_note": "114年9月自結盈餘",
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-10",

            "monthly_net_profit": 3130.0,
            "ytd_net_profit": 29333.0,
            "ytd_eps": 1.81,
            "source_note": "114年10月自結盈餘",
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-11",

            "monthly_net_profit": 2944.0,
            "ytd_net_profit": 32277.0,
            "ytd_eps": 2.00,
            "source_note": "114年11月自結盈餘",
        },
        {
            "stock_id": STOCK_ID,
            "data_month": "2025-12",

            #
            # financial_holding_monthly
            # 使用「月自結」口徑。
            #
            # 不使用後續正式年報
            # 34,342 百萬元。
            #
            "monthly_net_profit": 2010.0,
            "ytd_net_profit": 34287.0,
            "ytd_eps": 2.12,
            "source_note": "114年12月自結盈餘",
        },
    ]


def validate_rows(
    rows,
):

    expected_months = {
        f"2025-{month:02d}"
        for month in range(
            2,
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
            "Unexpected E.SUN 2025 rows. "
            f"Missing={missing}, "
            f"Extra={extra}"
        )

    if len(rows) != 11:

        raise RuntimeError(
            "Expected 11 E.SUN rows "
            "for 2025-02 ~ 2025-12"
        )

    seen = set()

    previous = None

    print()
    print("=" * 70)
    print("YTD RECONCILIATION")
    print("=" * 70)

    for row in rows:

        data_month = row[
            "data_month"
        ]

        if data_month in seen:

            raise RuntimeError(
                f"Duplicate month: "
                f"{data_month}"
            )

        seen.add(
            data_month
        )

        ytd = row[
            "ytd_net_profit"
        ]

        eps = row[
            "ytd_eps"
        ]

        monthly = row[
            "monthly_net_profit"
        ]

        if ytd is None:

            raise RuntimeError(
                f"{data_month} "
                "ytd_net_profit is NULL"
            )

        if eps is None:

            raise RuntimeError(
                f"{data_month} "
                "ytd_eps is NULL"
            )

        if previous is None:

            print(
                f"{data_month} "
                f"Monthly={monthly} "
                f"YTD={ytd} "
                "[BASE]"
            )

            previous = row
            continue

        previous_ytd = previous[
            "ytd_net_profit"
        ]

        if ytd < previous_ytd:

            raise RuntimeError(
                f"{data_month} "
                "YTD decreased: "
                f"{previous_ytd} "
                f"-> {ytd}"
            )

        if monthly is None:

            print(
                f"{data_month} "
                f"PrevYTD={previous_ytd} "
                f"Monthly=NULL "
                f"YTD={ytd} "
                "[NO_MONTHLY]"
            )

        else:

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
                    f"{data_month} "
                    "YTD reconciliation "
                    "failed"
                )

        previous = row

    print()
    print(
        "[PASS] "
        "2025 source rows validated: "
        f"{len(rows)}/11"
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
                row[
                    "stock_id"
                ],
                row[
                    "data_month"
                ],
                row[
                    "monthly_net_profit"
                ],
                row[
                    "ytd_net_profit"
                ],
                row[
                    "ytd_eps"
                ],
                SOURCE_URL,
            ),
        )

        count += 1

    print()
    print(
        "[PASS] "
        f"2025 upserted rows: {count}"
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

    rows = []

    for row in result.fetchall():

        rows.append(
            {
                "stock_id": row[0],
                "data_month": row[1],
                "ytd_net_profit": row[2],
            }
        )

    return rows


def get_previous_year_row(
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
            get_previous_year_row(
                conn,
                data_month,
            )
        )

        #
        # 前一年同月份不存在。
        #
        # 例如：
        # 2026-01 對應 2025-01，
        # 而目前 2025-01 尚無正式資料。
        #
        if previous_ytd is None:

            conn.execute(
                """
                UPDATE
                    financial_holding_monthly
                SET
                    previous_year_ytd_net_profit =
                        NULL,

                    ytd_profit_yoy_pct =
                        NULL,

                    updated_at =
                        CURRENT_TIMESTAMP
                WHERE
                    stock_id = ?
                    AND data_month = ?
                """,
                (
                    STOCK_ID,
                    data_month,
                ),
            )

            print(
                f"{data_month} "
                "PrevYTD=NULL "
                "YoY=NULL "
                "[SKIP]"
            )

            skipped_count += 1
            continue

        #
        # 當期 YTD 本身缺資料，
        # 無法計算 YoY。
        #
        if current_ytd is None:

            conn.execute(
                """
                UPDATE
                    financial_holding_monthly
                SET
                    previous_year_ytd_net_profit =
                        ?,

                    ytd_profit_yoy_pct =
                        NULL,

                    updated_at =
                        CURRENT_TIMESTAMP
                WHERE
                    stock_id = ?
                    AND data_month = ?
                """,
                (
                    previous_ytd,
                    STOCK_ID,
                    data_month,
                ),
            )

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
                previous_year_ytd_net_profit =
                    ?,

                ytd_profit_yoy_pct =
                    ?,

                updated_at =
                    CURRENT_TIMESTAMP
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
            previous_year_ytd_net_profit,
            ytd_profit_yoy_pct,
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
            f"PrevYTD={row[4]} "
            f"YoY={row[5]} "
            f"Status={row[6]}"
        )

    months = {
        row[0]
        for row in rows
    }

    if "2025-01" in months:

        print()
        print(
            "[WARN] "
            "2025-01 already exists "
            "in DEV database."
        )

        print(
            "       "
            "This backfill did not "
            "create that row."
        )

    expected = {
        f"2025-{month:02d}"
        for month in range(
            2,
            13,
        )
    }

    missing = (
        expected
        - months
    )

    if missing:

        raise RuntimeError(
            "2025 verification failed. "
            f"Missing={sorted(missing)}"
        )

    print()
    print(
        "[PASS] "
        "2025-02 ~ 2025-12 "
        "verified"
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

        data_month = row[0]
        current_ytd = row[1]
        previous_ytd = row[2]
        yoy = row[3]

        print(
            f"{data_month} "
            f"YTD={current_ytd} "
            f"PrevYTD={previous_ytd} "
            f"YoY={yoy}"
        )

        #
        # 2026-01 因為沒有
        # 2025-01 正式歷史值，
        # PrevYTD / YoY 必須保留 NULL。
        #
        if data_month == "2026-01":

            if (
                previous_ytd is not None
                or yoy is not None
            ):

                raise RuntimeError(
                    "2026-01 should not "
                    "have YoY because "
                    "2025-01 is missing"
                )

            continue

        #
        # 2026-02 ~ 12：
        # 只要有當期資料，
        # 理論上都應能找到
        # 2025 同月 YTD。
        #
        if (
            current_ytd is not None
            and previous_ytd is None
        ):

            raise RuntimeError(
                f"{data_month} "
                "missing previous year YTD"
            )

    print()
    print(
        "[PASS] "
        "2026 YoY verification"
    )


def main():

    configure_console()

    print("=" * 70)

    print(
        "StockWaveScanner V3 - "
        "E.SUN Historical Backfill"
    )

    print("=" * 70)

    print()
    print(
        f"Stock: "
        f"{STOCK_ID} {STOCK_NAME}"
    )

    print(
        "Target: "
        "2025-02 ~ 2025-12"
    )

    print(
        "2025-01: "
        "WAITING_DATA"
    )

    #
    # 先完成所有來源資料驗證。
    #
    # 驗證失敗時，
    # 不建立 DB Connection，
    # 不允許部分寫入。
    #
    rows = build_2025_rows()

    validate_rows(
        rows
    )

    #
    # 所有來源資料驗證通過後，
    # 才允許連 DEV。
    #
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
        "E.SUN HISTORICAL BACKFILL OK"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )