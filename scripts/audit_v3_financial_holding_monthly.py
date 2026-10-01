from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


FINANCIAL_HOLDINGS = [
    ("2880", "華南金"),
    ("2881", "富邦金"),
    ("2882", "國泰金"),
    ("2883", "凱基金"),
    ("2884", "玉山金"),
    ("2885", "元大金"),
    ("2886", "兆豐金"),
    ("2887", "台新新光金"),
    ("2889", "國票金"),
    ("2890", "永豐金"),
    ("2891", "中信金"),
    ("2892", "第一金"),
    ("5880", "合庫金"),
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


def month_range(
    start_month,
    end_month,
):

    if not start_month or not end_month:
        return []

    start_year, start_mon = map(
        int,
        start_month.split("-"),
    )

    end_year, end_mon = map(
        int,
        end_month.split("-"),
    )

    result = []

    year = start_year
    month = start_mon

    while (
        year < end_year
        or (
            year == end_year
            and month <= end_mon
        )
    ):

        result.append(
            f"{year}-{month:02d}"
        )

        month += 1

        if month > 12:
            month = 1
            year += 1

    return result


def load_rows(
    conn,
    stock_id,
):

    return conn.execute(
        """
        SELECT
            stock_id,
            data_month,
            monthly_net_profit,
            ytd_net_profit,
            ytd_eps,
            previous_year_ytd_net_profit,
            ytd_profit_yoy_pct,
            source_url,
            data_status
        FROM financial_holding_monthly
        WHERE stock_id = ?
        ORDER BY data_month
        """,
        (
            stock_id,
        ),
    ).fetchall()


def group_by_year(
    rows,
):

    result = defaultdict(list)

    for row in rows:

        data_month = row[1]

        if not data_month:
            continue

        year = data_month[:4]

        result[year].append(
            data_month
        )

    return result


def count_field_coverage(
    rows,
    index,
):

    return sum(
        1
        for row in rows
        if row[index] is not None
    )


def audit_stock(
    stock_id,
    stock_name,
    rows,
):

    if not rows:

        return {
            "stock_id": stock_id,
            "stock_name": stock_name,
            "row_count": 0,
            "first_month": None,
            "latest_month": None,
            "missing_months": [],
            "year_summary": {},
            "monthly_count": 0,
            "ytd_count": 0,
            "eps_count": 0,
            "prev_ytd_count": 0,
            "yoy_count": 0,
        }

    months = [
        row[1]
        for row in rows
        if row[1]
    ]

    first_month = min(months)
    latest_month = max(months)

    expected_months = month_range(
        first_month,
        latest_month,
    )

    existing_months = set(
        months
    )

    missing_months = [
        month
        for month in expected_months
        if month not in existing_months
    ]

    grouped = group_by_year(
        rows
    )

    year_summary = {}

    for year, year_months in sorted(
        grouped.items()
    ):

        month_numbers = sorted(
            int(
                value.split("-")[1]
            )
            for value in year_months
        )

        missing_in_year = [
            f"{year}-{month:02d}"
            for month in range(
                min(month_numbers),
                max(month_numbers) + 1,
            )
            if month not in month_numbers
        ]

        year_summary[year] = {
            "count": len(
                year_months
            ),
            "months": sorted(
                year_months
            ),
            "missing": missing_in_year,
        }

    return {
        "stock_id": stock_id,
        "stock_name": stock_name,
        "row_count": len(
            rows
        ),
        "first_month": first_month,
        "latest_month": latest_month,
        "missing_months": missing_months,
        "year_summary": year_summary,
        "monthly_count": count_field_coverage(
            rows,
            2,
        ),
        "ytd_count": count_field_coverage(
            rows,
            3,
        ),
        "eps_count": count_field_coverage(
            rows,
            4,
        ),
        "prev_ytd_count": count_field_coverage(
            rows,
            5,
        ),
        "yoy_count": count_field_coverage(
            rows,
            6,
        ),
    }


def print_stock_report(
    result,
):

    print()
    print(
        "=" * 70
    )

    print(
        f"{result['stock_id']} "
        f"{result['stock_name']}"
    )

    print(
        "=" * 70
    )

    if result[
        "row_count"
    ] == 0:

        print(
            "Rows    : 0"
        )

        print(
            "Status  : NO DATA"
        )

        return

    print(
        f"Rows    : "
        f"{result['row_count']}"
    )

    print(
        f"Range   : "
        f"{result['first_month']} "
        f"~ "
        f"{result['latest_month']}"
    )

    print(
        f"Monthly : "
        f"{result['monthly_count']}"
        f"/{result['row_count']}"
    )

    print(
        f"YTD     : "
        f"{result['ytd_count']}"
        f"/{result['row_count']}"
    )

    print(
        f"EPS     : "
        f"{result['eps_count']}"
        f"/{result['row_count']}"
    )

    print(
        f"PrevYTD : "
        f"{result['prev_ytd_count']}"
        f"/{result['row_count']}"
    )

    print(
        f"YoY     : "
        f"{result['yoy_count']}"
        f"/{result['row_count']}"
    )

    print()

    print(
        "Year coverage:"
    )

    for year, info in result[
        "year_summary"
    ].items():

        print(
            f"  {year}: "
            f"{info['count']} months"
        )

        print(
            "    "
            + ", ".join(
                info["months"]
            )
        )

        if info[
            "missing"
        ]:

            print(
                "    Missing: "
                + ", ".join(
                    info[
                        "missing"
                    ]
                )
            )

    print()

    if result[
        "missing_months"
    ]:

        print(
            "Missing between "
            "first/latest:"
        )

        print(
            "  "
            + ", ".join(
                result[
                    "missing_months"
                ]
            )
        )

    else:

        print(
            "Missing between "
            "first/latest: None"
        )


def print_summary(
    results,
):

    print()
    print()
    print(
        "=" * 90
    )

    print(
        "FINANCIAL HOLDING MONTHLY "
        "COVERAGE SUMMARY"
    )

    print(
        "=" * 90
    )

    print(
        f"{'Stock':<12}"
        f"{'Rows':>6}"
        f"{'Range':>22}"
        f"{'Monthly':>10}"
        f"{'YTD':>8}"
        f"{'EPS':>8}"
        f"{'YoY':>8}"
    )

    print(
        "-" * 90
    )

    for result in results:

        stock_text = (
            f"{result['stock_id']} "
            f"{result['stock_name']}"
        )

        if result[
            "row_count"
        ] == 0:

            range_text = "NO DATA"

        else:

            range_text = (
                f"{result['first_month']}"
                f"~"
                f"{result['latest_month']}"
            )

        print(
            f"{stock_text:<12}"
            f"{result['row_count']:>6}"
            f"{range_text:>22}"
            f"{result['monthly_count']:>10}"
            f"{result['ytd_count']:>8}"
            f"{result['eps_count']:>8}"
            f"{result['yoy_count']:>8}"
        )

    print(
        "=" * 90
    )


def main():

    configure_console()

    print(
        "=" * 70
    )

    print(
        "StockWaveScanner V3 - "
        "Financial Holding Monthly Coverage Audit"
    )

    print(
        "=" * 70
    )

    conn = get_connection()

    try:

        results = []

        for (
            stock_id,
            stock_name,
        ) in FINANCIAL_HOLDINGS:

            rows = load_rows(
                conn,
                stock_id,
            )

            result = audit_stock(
                stock_id,
                stock_name,
                rows,
            )

            results.append(
                result
            )

            print_stock_report(
                result
            )

        print_summary(
            results
        )

        print()
        print(
            "AUDIT OK"
        )

        return 0

    except Exception as exc:

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

        conn.close()


if __name__ == "__main__":

    sys.exit(
        main()
    )