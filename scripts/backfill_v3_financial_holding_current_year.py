from __future__ import annotations

import sys

from parse_v3_financial_holding_yuanta import parse_yuanta
from parse_v3_financial_holding_cathay import parse_cathay
from parse_v3_financial_holding_fubon import parse_fubon
from parse_v3_financial_holding_taishin import parse_taishin
from parse_v3_financial_holding_huanan_mops import parse_huanan_mops
from parse_v3_financial_holding_esun import parse_esun
from parse_v3_financial_holding_mega import parse_mega
from parse_v3_financial_holding_sinopac import parse_sinopac
from parse_v3_financial_holding_ctbc import parse_ctbc
from parse_v3_financial_holding_first import parse_first
from parse_v3_financial_holding_kgi import parse_kgi
from parse_v3_financial_holding_ibf import parse_ibf
from parse_v3_financial_holding_tcf import parse_tcf

from sync_v3_financial_holding_monthly import (
    configure_console,
    get_connection,
    sync_rows,
    update_yoy_metrics,
)


TARGET_YEAR = 2026


COLLECTORS = [
    ("2880", "華南金", parse_huanan_mops),
    ("2881", "富邦金", parse_fubon),
    ("2882", "國泰金", parse_cathay),
    ("2883", "凱基金", parse_kgi),
    ("2884", "玉山金", parse_esun),
    ("2885", "元大金", parse_yuanta),
    ("2886", "兆豐金", parse_mega),
    ("2887", "台新新光金", parse_taishin),
    ("2889", "國票金", parse_ibf),
    ("2890", "永豐金", parse_sinopac),
    ("2891", "中信金", parse_ctbc),
    ("2892", "第一金", parse_first),
    ("5880", "合庫金", parse_tcf),
]


def filter_target_year(
    rows,
):

    prefix = f"{TARGET_YEAR}-"

    result = [
        row
        for row in rows
        if (
            row.get("data_month")
            and row["data_month"].startswith(
                prefix
            )
        )
    ]

    result.sort(
        key=lambda x: x[
            "data_month"
        ]
    )

    return result


def print_rows(
    stock_id,
    stock_name,
    rows,
):

    print()
    print(
        f"[{stock_id}] "
        f"{stock_name}"
    )

    if not rows:

        print(
            f"  No {TARGET_YEAR} rows"
        )

        return

    for row in rows:

        print(
            "  "
            f"{row['data_month']} "
            f"Monthly="
            f"{row['monthly_net_profit']} "
            f"YTD="
            f"{row['ytd_net_profit']} "
            f"EPS="
            f"{row['ytd_eps']}"
        )


def verify_current_year(
    conn,
    stock_id,
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
        WHERE stock_id = ?
          AND data_month LIKE ?
        ORDER BY data_month
        """,
        (
            stock_id,
            f"{TARGET_YEAR}-%",
        ),
    ).fetchall()


def main():

    configure_console()

    print(
        "=" * 70
    )

    print(
        "StockWaveScanner V3 - "
        "Financial Holding Current Year Backfill"
    )

    print(
        "=" * 70
    )

    print()
    print(
        f"Target Year: "
        f"{TARGET_YEAR}"
    )

    conn = None

    try:

        all_rows = []

        sync_counts = {}

        for (
            stock_id,
            stock_name,
            collector,
        ) in COLLECTORS:

            print()
            print(
                "-" * 70
            )

            print(
                f"[COLLECT] "
                f"{stock_id} "
                f"{stock_name}"
            )

            raw_rows = collector()

            target_rows = (
                filter_target_year(
                    raw_rows
                )
            )

            print_rows(
                stock_id,
                stock_name,
                target_rows,
            )

            if not target_rows:

                sync_counts[
                    stock_id
                ] = 0

                continue

            sync_counts[
                stock_id
            ] = 0

            all_rows.extend(
                target_rows
            )
            
        print()
        print(
            "=" * 70
        )

        print(
            "CONNECT TURSO DEV"
        )

        print(
            "=" * 70
        )

        conn = get_connection()    

        for (
            stock_id,
            stock_name,
            _,
        ) in COLLECTORS:

            stock_rows = [
                row
                for row in all_rows
                if row["stock_id"] == stock_id
            ]

            if not stock_rows:

                sync_counts[
                    stock_id
                ] = 0

                continue

            count = sync_rows(
                conn,
                stock_rows,
            )

            sync_counts[
                stock_id
            ] = count

            print(
                f"[PASS] "
                f"{stock_id} "
                f"{stock_name} "
                f"synced rows: "
                f"{count}"
            )

        yoy_count = (
            update_yoy_metrics(
                conn,
                all_rows,
            )
        )

        conn.commit()

        print()
        print()
        print(
            "=" * 70
        )

        print(
            "CURRENT YEAR BACKFILL RESULT"
        )

        print(
            "=" * 70
        )

        for (
            stock_id,
            stock_name,
            _,
        ) in COLLECTORS:

            count = sync_counts.get(
                stock_id,
                0,
            )

            print(
                f"{stock_id} "
                f"{stock_name:<8} "
                f"synced={count}"
            )

        print()

        print(
            f"YoY updated rows: "
            f"{yoy_count}"
        )

        print()
        print(
            "=" * 70
        )

        print(
            "DATABASE CURRENT YEAR COVERAGE"
        )

        print(
            "=" * 70
        )

        for (
            stock_id,
            stock_name,
            _,
        ) in COLLECTORS:

            rows = verify_current_year(
                conn,
                stock_id,
            )

            months = [
                row[0]
                for row in rows
            ]

            if months:

                month_text = ", ".join(
                    months
                )

            else:

                month_text = "NO DATA"

            print(
                f"{stock_id} "
                f"{stock_name:<8} "
                f"{len(rows):>2} months : "
                f"{month_text}"
            )

        print()
        print(
            "=" * 70
        )

        print(
            "FINANCIAL HOLDING "
            "CURRENT YEAR BACKFILL OK"
        )

        print(
            "=" * 70
        )

        return 0

    except Exception as exc:

        if conn is not None:

            try:
                conn.rollback()
            except Exception:
                pass

        print()
        print(
            "ERROR"
        )

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return 1

    finally:

        if conn is not None:

            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":

    sys.exit(
        main()
    )