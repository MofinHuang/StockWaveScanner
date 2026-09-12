from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]

ENV_FILE = ROOT / ".env"

STAGING_DB = (
    ROOT
    / "runtime"
    / "price_backfill.db"
)


EXCLUDED_ETF_IDS = {
    "0050",
    "0051",
    "0052",
    "0053",
    "0055",
    "0056",
    "0057",
    "0061",
}


HISTORICAL_COMMON_STOCKS = {
    "3202": {
        "name": "樺晟",
        "market": "TPEX",
    },
    "3426": {
        "name": "台興",
        "market": "TPEX",
    },
    "4945": {
        "name": "陞達科技",
        "market": "TPEX",
    },
    "6287": {
        "name": "元隆",
        "market": "TPEX",
    },
    "6457": {
        "name": "紘康",
        "market": "TPEX",
    },
    "6514": {
        "name": "芮特-KY",
        "market": "TPEX",
    },
    "6747": {
        "name": "亨泰光",
        "market": "TPEX",
    },
    "8420": {
        "name": "明揚",
        "market": "TPEX",
    },
    "2809": {
        "name": "京城銀",
        "market": "TWSE",
    },
    "2888": {
        "name": "新光金",
        "market": "TWSE",
    },
    "3454": {
        "name": "晶睿",
        "market": "TWSE",
    },
    "6288": {
        "name": "聯嘉",
        "market": "TWSE",
    },
}


def load_dev_credentials() -> tuple[str, str]:
    load_dotenv(
        ENV_FILE
    )

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

    if (
        "stockwave-dev"
        not in lower_url
        or "stockwave-prod"
        in lower_url
    ):
        raise RuntimeError(
            "SAFETY STOP: "
            "invalid DEV database URL"
        )

    return url, token


def load_stock_master() -> dict[str, dict[str, Any]]:
    url, token = (
        load_dev_credentials()
    )

    conn = libsql.connect(
        database=url,
        auth_token=token,
    )

    try:
        rows = conn.execute(
            """
            SELECT
                stock_id,
                stock_name,
                market,
                is_active
            FROM stock_master
            """
        ).fetchall()

        result: dict[
            str,
            dict[str, Any],
        ] = {}

        for row in rows:
            stock_id = str(
                row[0]
            ).strip()

            result[
                stock_id
            ] = {
                "name": row[1],
                "market": row[2],
                "is_active": int(
                    row[3]
                ),
            }

        return result

    finally:
        conn.close()


def percentile(
    values: list[int],
    p: float,
) -> int:
    if not values:
        return 0

    ordered = sorted(
        values
    )

    index = round(
        (len(ordered) - 1)
        * p
    )

    return ordered[
        int(index)
    ]


def main() -> int:
    print("=" * 76)
    print(
        "StockWaveScanner V2 - "
        "Historical Price Staging Audit"
    )
    print("=" * 76)
    print()

    try:
        if not STAGING_DB.exists():
            raise RuntimeError(
                f"Staging database not found: "
                f"{STAGING_DB}"
            )

        master = (
            load_stock_master()
        )

        print(
            f"Turso Stock Master : "
            f"{len(master):,}"
        )

        print(
            "Turso Write         : DISABLED"
        )

        print(
            f"Staging DB          : "
            f"{STAGING_DB}"
        )

        conn = sqlite3.connect(
            STAGING_DB
        )

        try:
            total_rows = conn.execute(
                """
                SELECT COUNT(*)
                FROM price_staging
                """
            ).fetchone()[0]

            duplicate_groups = (
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM (
                        SELECT
                            market,
                            stock_id,
                            trade_date,
                            COUNT(*) AS c
                        FROM price_staging
                        GROUP BY
                            market,
                            stock_id,
                            trade_date
                        HAVING COUNT(*) > 1
                    )
                    """
                ).fetchone()[0]
            )

            distinct_dates = (
                conn.execute(
                    """
                    SELECT COUNT(
                        DISTINCT trade_date
                    )
                    FROM price_staging
                    """
                ).fetchone()[0]
            )

            range_row = (
                conn.execute(
                    """
                    SELECT
                        MIN(trade_date),
                        MAX(trade_date)
                    FROM price_staging
                    """
                ).fetchone()
            )

            print()
            print("=" * 76)
            print("BASIC COVERAGE")
            print("=" * 76)

            print(
                f"Rows             : "
                f"{total_rows:,}"
            )

            print(
                f"Trade Dates      : "
                f"{distinct_dates:,}"
            )

            print(
                f"Date Range       : "
                f"{range_row[0]} "
                f".. {range_row[1]}"
            )

            print(
                f"Duplicate Groups : "
                f"{duplicate_groups:,}"
            )

            # ------------------------------------------------
            # Security classification
            # ------------------------------------------------

            securities = conn.execute(
                """
                SELECT
                    market,
                    stock_id,
                    MAX(stock_name),
                    COUNT(*),
                    MIN(trade_date),
                    MAX(trade_date)
                FROM price_staging
                GROUP BY
                    market,
                    stock_id
                ORDER BY
                    market,
                    stock_id
                """
            ).fetchall()

            unknown: list[
                tuple[Any, ...]
            ] = []

            unknown_historical: list[
                tuple[Any, ...]
            ] = []

            excluded_etf: list[
                tuple[Any, ...]
            ] = []

            for row in securities:
                stock_id = str(
                    row[1]
                ).strip()

                if stock_id in master:
                    continue

                if (
                    stock_id
                    in EXCLUDED_ETF_IDS
                ):
                    excluded_etf.append(
                        row
                    )
                    continue

                if (
                    stock_id
                    in HISTORICAL_COMMON_STOCKS
                ):
                    expected = (
                        HISTORICAL_COMMON_STOCKS[
                            stock_id
                        ]
                    )

                    if row[0] != expected[
                        "market"
                    ]:
                        raise RuntimeError(
                            "Historical stock "
                            "market mismatch: "
                            f"{stock_id}"
                        )

                    unknown_historical.append(
                        row
                    )
                    continue

                unknown.append(
                    row
                )

            print()
            print("=" * 76)
            print("SECURITY CLASSIFICATION")
            print("=" * 76)

            print(
                f"Current/Historical "
                f"Stock Master : "
                f"{len(master):,}"
            )

            print(
                f"Excluded ETF        : "
                f"{len(excluded_etf):,}"
            )

            print(
                f"Historical To Seed  : "
                f"{len(unknown_historical):,}"
            )

            print(
                f"Unclassified        : "
                f"{len(unknown):,}"
            )

            if excluded_etf:
                print()
                print("Excluded ETF:")

                for row in excluded_etf:
                    print(
                        f"  {row[0]} "
                        f"{row[1]} "
                        f"{row[2]} "
                        f"| rows={row[3]:,}"
                    )

            if unknown_historical:
                print()
                print(
                    "Historical Common Stocks:"
                )

                for row in (
                    unknown_historical
                ):
                    print(
                        f"  {row[0]} "
                        f"{row[1]} "
                        f"{row[2]} "
                        f"| {row[4]}"
                        f"..{row[5]} "
                        f"| rows={row[3]:,}"
                    )

            if unknown:
                print()
                print(
                    "UNCLASSIFIED SECURITIES:"
                )

                for row in unknown:
                    print(
                        f"  {row[0]} "
                        f"{row[1]} "
                        f"{row[2]} "
                        f"| rows={row[3]:,}"
                    )

                raise RuntimeError(
                    "Unclassified historical "
                    "securities remain"
                )

            # ------------------------------------------------
            # Eligible row count
            # ------------------------------------------------

            placeholders = ",".join(
                "?"
                for _ in EXCLUDED_ETF_IDS
            )

            excluded_ids = tuple(
                sorted(
                    EXCLUDED_ETF_IDS
                )
            )

            excluded_rows = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM price_staging
                WHERE stock_id IN (
                    {placeholders}
                )
                """,
                excluded_ids,
            ).fetchone()[0]

            eligible_rows = (
                total_rows
                - excluded_rows
            )

            print()
            print("=" * 76)
            print("V2 PRICE UNIVERSE")
            print("=" * 76)

            print(
                f"Staging Rows      : "
                f"{total_rows:,}"
            )

            print(
                f"ETF Excluded Rows : "
                f"{excluded_rows:,}"
            )

            print(
                f"Eligible Rows     : "
                f"{eligible_rows:,}"
            )

            # ------------------------------------------------
            # OHLC quality
            # ------------------------------------------------

            null_open = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM price_staging
                WHERE stock_id NOT IN (
                    {placeholders}
                )
                  AND open IS NULL
                """,
                excluded_ids,
            ).fetchone()[0]

            null_high = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM price_staging
                WHERE stock_id NOT IN (
                    {placeholders}
                )
                  AND high IS NULL
                """,
                excluded_ids,
            ).fetchone()[0]

            null_low = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM price_staging
                WHERE stock_id NOT IN (
                    {placeholders}
                )
                  AND low IS NULL
                """,
                excluded_ids,
            ).fetchone()[0]

            invalid_close = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM price_staging
                WHERE stock_id NOT IN (
                    {placeholders}
                )
                  AND (
                        close IS NULL
                        OR close <= 0
                  )
                """,
                excluded_ids,
            ).fetchone()[0]

            invalid_high_low = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM price_staging
                WHERE stock_id NOT IN (
                    {placeholders}
                )
                  AND high IS NOT NULL
                  AND low IS NOT NULL
                  AND high < low
                """,
                excluded_ids,
            ).fetchone()[0]

            invalid_high = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM price_staging
                WHERE stock_id NOT IN (
                    {placeholders}
                )
                  AND high IS NOT NULL
                  AND (
                        (
                            open IS NOT NULL
                            AND high < open
                        )
                        OR high < close
                  )
                """,
                excluded_ids,
            ).fetchone()[0]

            invalid_low = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM price_staging
                WHERE stock_id NOT IN (
                    {placeholders}
                )
                  AND low IS NOT NULL
                  AND (
                        (
                            open IS NOT NULL
                            AND low > open
                        )
                        OR low > close
                  )
                """,
                excluded_ids,
            ).fetchone()[0]

            print()
            print("=" * 76)
            print("OHLC QUALITY")
            print("=" * 76)

            print(
                f"NULL Open          : "
                f"{null_open:,}"
            )

            print(
                f"NULL High          : "
                f"{null_high:,}"
            )

            print(
                f"NULL Low           : "
                f"{null_low:,}"
            )

            print(
                f"Invalid Close      : "
                f"{invalid_close:,}"
            )

            print(
                f"High < Low         : "
                f"{invalid_high_low:,}"
            )

            print(
                f"High < Open/Close  : "
                f"{invalid_high:,}"
            )

            print(
                f"Low > Open/Close   : "
                f"{invalid_low:,}"
            )

            # ------------------------------------------------
            # Coverage by stock
            # ------------------------------------------------

            rows_per_stock = (
                conn.execute(
                    f"""
                    SELECT
                        stock_id,
                        COUNT(*) AS cnt
                    FROM price_staging
                    WHERE stock_id NOT IN (
                        {placeholders}
                    )
                    GROUP BY stock_id
                    """,
                    excluded_ids,
                ).fetchall()
            )

            counts = [
                int(row[1])
                for row in rows_per_stock
            ]

            count_by_stock = {
                str(row[0]): int(
                    row[1]
                )
                for row
                in rows_per_stock
            }

            print()
            print("=" * 76)
            print("PRICE COVERAGE")
            print("=" * 76)

            print(
                f"Eligible Securities : "
                f"{len(counts):,}"
            )

            print()
            print("Rows per security:")

            print(
                f"  Min    : "
                f"{min(counts):,}"
            )

            print(
                f"  P25    : "
                f"{percentile(counts, 0.25):,}"
            )

            print(
                f"  Median : "
                f"{percentile(counts, 0.50):,}"
            )

            print(
                f"  P75    : "
                f"{percentile(counts, 0.75):,}"
            )

            print(
                f"  P90    : "
                f"{percentile(counts, 0.90):,}"
            )

            print(
                f"  Max    : "
                f"{max(counts):,}"
            )

            print()
            print(
                "Securities with at least:"
            )

            for threshold in (
                30,
                60,
                120,
                240,
                400,
                480,
            ):
                count = sum(
                    1
                    for value in counts
                    if value >= threshold
                )

                print(
                    f"  >= {threshold:>3} days : "
                    f"{count:,}"
                )

            # ------------------------------------------------
            # Active-stock warm-up readiness
            # ------------------------------------------------

            active_ids = {
                stock_id
                for stock_id, data
                in master.items()
                if data["is_active"] == 1
            }

            active_with_prices = [
                count_by_stock[
                    stock_id
                ]
                for stock_id
                in active_ids
                if stock_id
                in count_by_stock
            ]

            active_no_price = [
                stock_id
                for stock_id
                in active_ids
                if stock_id
                not in count_by_stock
            ]

            active_120 = sum(
                1
                for value
                in active_with_prices
                if value >= 120
            )

            print()
            print("=" * 76)
            print("ACTIVE STOCK READINESS")
            print("=" * 76)

            print(
                f"Active Stock Master : "
                f"{len(active_ids):,}"
            )

            print(
                f"Active With Prices  : "
                f"{len(active_with_prices):,}"
            )

            print(
                f"Active No Price     : "
                f"{len(active_no_price):,}"
            )

            print(
                f"Active >=120 Days   : "
                f"{active_120:,}"
            )

            readiness_pct = (
                active_120
                / len(active_ids)
                * 100
                if active_ids
                else 0
            )

            print(
                f"Warm-up Ready %     : "
                f"{readiness_pct:.2f}%"
            )

            if active_no_price:
                print()
                print(
                    "Active without price:"
                )

                for stock_id in (
                    sorted(
                        active_no_price
                    )[:30]
                ):
                    data = master[
                        stock_id
                    ]

                    print(
                        f"  {stock_id} "
                        f"{data['name']} "
                        f"| {data['market']}"
                    )

            # ------------------------------------------------
            # Final decision
            # ------------------------------------------------

            print()
            print("=" * 76)
            print("AUDIT RESULT")
            print("=" * 76)

            fatal_issues = []

            if duplicate_groups != 0:
                fatal_issues.append(
                    "duplicate price keys"
                )

            if unknown:
                fatal_issues.append(
                    "unclassified securities"
                )

            if invalid_close != 0:
                fatal_issues.append(
                    "invalid close prices"
                )

            if invalid_high_low != 0:
                fatal_issues.append(
                    "high < low"
                )

            if invalid_high != 0:
                fatal_issues.append(
                    "high below open/close"
                )

            if invalid_low != 0:
                fatal_issues.append(
                    "low above open/close"
                )

            if fatal_issues:
                print(
                    "STATUS : FAIL"
                )

                for issue in fatal_issues:
                    print(
                        f"  - {issue}"
                    )

                return 2

            print(
                "STATUS : PASS"
            )

            print()
            print(
                f"Eligible Price Rows : "
                f"{eligible_rows:,}"
            )

            print(
                "Ready for Turso "
                "historical price migration."
            )

            print()
            print(
                "No Turso data was modified."
            )

            return 0

        finally:
            conn.close()

    except Exception as exc:
        print()
        print("=" * 76)
        print("ERROR")
        print("=" * 76)

        print(
            str(exc)
        )

        print()
        print(
            "No Turso data was modified."
        )

        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )