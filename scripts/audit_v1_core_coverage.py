from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DB_PATH = (
    ROOT.parent
    / "StockWaveScanner_V1_Data_Archive_20260912"
    / "stocks.db"
)


def qid(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def get_columns(
    conn: sqlite3.Connection,
    table: str,
) -> list[str]:
    rows = conn.execute(
        f"PRAGMA table_info({qid(table)})"
    ).fetchall()

    return [str(row[1]) for row in rows]


def print_columns(
    conn: sqlite3.Connection,
    table: str,
) -> None:
    print()
    print(f"{table} columns:")

    for column in get_columns(conn, table):
        print(f"  - {column}")


def audit_price(
    conn: sqlite3.Connection,
) -> None:
    print()
    print("=" * 78)
    print("1. DAILY PRICE COVERAGE")
    print("=" * 78)

    print_columns(conn, "daily_prices")

    summary = conn.execute(
        """
        SELECT
            COUNT(*) AS rows,
            COUNT(DISTINCT stock_id) AS stocks,
            COUNT(DISTINCT trade_date) AS dates,
            MIN(trade_date),
            MAX(trade_date)
        FROM daily_prices
        """
    ).fetchone()

    print()
    print(f"Rows           : {summary[0]:,}")
    print(f"Stocks         : {summary[1]:,}")
    print(f"Trade Dates    : {summary[2]:,}")
    print(f"Date Range     : {summary[3]} .. {summary[4]}")

    rows_per_stock = conn.execute(
        """
        SELECT
            stock_id,
            COUNT(*) AS cnt
        FROM daily_prices
        GROUP BY stock_id
        ORDER BY cnt
        """
    ).fetchall()

    counts = [
        int(row[1])
        for row in rows_per_stock
    ]

    if counts:
        sorted_counts = sorted(counts)

        def percentile(p: float) -> int:
            index = int(
                round(
                    (len(sorted_counts) - 1) * p
                )
            )
            return sorted_counts[index]

        print()
        print("Rows per stock:")
        print(f"  Min          : {min(counts):,}")
        print(f"  P25          : {percentile(0.25):,}")
        print(f"  Median       : {percentile(0.50):,}")
        print(f"  P75          : {percentile(0.75):,}")
        print(f"  P90          : {percentile(0.90):,}")
        print(f"  Max          : {max(counts):,}")

    thresholds = [
        1,
        5,
        20,
        30,
        60,
        120,
        200,
        250,
    ]

    print()
    print("Stocks with at least N price rows:")

    for threshold in thresholds:
        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT stock_id
                FROM daily_prices
                GROUP BY stock_id
                HAVING COUNT(*) >= ?
            )
            """,
            (threshold,),
        ).fetchone()[0]

        print(
            f"  >= {threshold:>3} rows : "
            f"{count:>5,}"
        )

    print()
    print("Daily market coverage:")

    daily_counts = conn.execute(
        """
        SELECT
            trade_date,
            COUNT(*) AS cnt
        FROM daily_prices
        GROUP BY trade_date
        ORDER BY trade_date
        """
    ).fetchall()

    if daily_counts:
        daily_values = [
            int(row[1])
            for row in daily_counts
        ]

        print(
            f"  Min stocks/day : "
            f"{min(daily_values):,}"
        )

        print(
            f"  Avg stocks/day : "
            f"{sum(daily_values) / len(daily_values):,.1f}"
        )

        print(
            f"  Max stocks/day : "
            f"{max(daily_values):,}"
        )

        print()
        print("  First 5 dates:")

        for row in daily_counts[:5]:
            print(
                f"    {row[0]} : {row[1]:,}"
            )

        print()
        print("  Last 5 dates:")

        for row in daily_counts[-5:]:
            print(
                f"    {row[0]} : {row[1]:,}"
            )


def audit_institutional(
    conn: sqlite3.Connection,
) -> None:
    print()
    print("=" * 78)
    print("2. INSTITUTIONAL COVERAGE")
    print("=" * 78)

    columns = get_columns(
        conn,
        "institutional_trades",
    )

    print_columns(
        conn,
        "institutional_trades",
    )

    summary = conn.execute(
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT stock_id),
            COUNT(DISTINCT trade_date),
            MIN(trade_date),
            MAX(trade_date)
        FROM institutional_trades
        """
    ).fetchone()

    print()
    print(f"Rows           : {summary[0]:,}")
    print(f"Stocks         : {summary[1]:,}")
    print(f"Trade Dates    : {summary[2]:,}")
    print(f"Date Range     : {summary[3]} .. {summary[4]}")

    daily_counts = conn.execute(
        """
        SELECT
            trade_date,
            COUNT(*) AS cnt
        FROM institutional_trades
        GROUP BY trade_date
        ORDER BY trade_date
        """
    ).fetchall()

    if daily_counts:
        values = [
            int(row[1])
            for row in daily_counts
        ]

        print()
        print("Stocks per trading day:")
        print(f"  Min          : {min(values):,}")
        print(
            f"  Avg          : "
            f"{sum(values) / len(values):,.1f}"
        )
        print(f"  Max          : {max(values):,}")

        print()
        print("Last 10 dates:")

        for row in daily_counts[-10:]:
            print(
                f"  {row[0]} : {row[1]:,}"
            )

    status_columns = [
        column
        for column in columns
        if "status" in column.lower()
    ]

    for status_column in status_columns:
        print()
        print(
            f"{status_column} distribution:"
        )

        rows = conn.execute(
            f"""
            SELECT
                {qid(status_column)},
                COUNT(*)
            FROM institutional_trades
            GROUP BY {qid(status_column)}
            ORDER BY COUNT(*) DESC
            """
        ).fetchall()

        for row in rows:
            print(
                f"  {row[0]} : {row[1]:,}"
            )

    numeric_candidates = [
        "foreign_buy",
        "foreign_sell",
        "foreign_net",
        "trust_buy",
        "trust_sell",
        "trust_net",
        "dealer_buy",
        "dealer_sell",
        "dealer_net",
    ]

    present = [
        column
        for column in numeric_candidates
        if column in columns
    ]

    if present:
        print()
        print("NULL audit:")

        for column in present:
            null_count = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM institutional_trades
                WHERE {qid(column)} IS NULL
                """
            ).fetchone()[0]

            print(
                f"  {column:<15}: "
                f"{null_count:,}"
            )


def audit_tdcc(
    conn: sqlite3.Connection,
) -> None:
    print()
    print("=" * 78)
    print("3. TDCC COVERAGE")
    print("=" * 78)

    print_columns(
        conn,
        "tdcc_holdings",
    )

    summary = conn.execute(
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT stock_id),
            COUNT(DISTINCT data_date),
            MIN(data_date),
            MAX(data_date)
        FROM tdcc_holdings
        """
    ).fetchone()

    print()
    print(f"Rows           : {summary[0]:,}")
    print(f"Stocks         : {summary[1]:,}")
    print(f"Data Dates     : {summary[2]:,}")
    print(f"Date Range     : {summary[3]} .. {summary[4]}")

    rows = conn.execute(
        """
        SELECT
            data_date,
            COUNT(*) AS rows,
            COUNT(DISTINCT stock_id) AS stocks
        FROM tdcc_holdings
        GROUP BY data_date
        ORDER BY data_date
        """
    ).fetchall()

    print()
    print("Coverage by TDCC date:")

    for row in rows:
        print(
            f"  {row[0]} : "
            f"rows={row[1]:,}, "
            f"stocks={row[2]:,}"
        )

    columns = get_columns(
        conn,
        "tdcc_holdings",
    )

    holder_column = None

    for candidate in (
        "holder_level",
        "holding_level",
        "level",
    ):
        if candidate in columns:
            holder_column = candidate
            break

    if holder_column:
        levels = conn.execute(
            f"""
            SELECT
                {qid(holder_column)},
                COUNT(*)
            FROM tdcc_holdings
            GROUP BY {qid(holder_column)}
            ORDER BY {qid(holder_column)}
            """
        ).fetchall()

        print()
        print("Holder level distribution:")

        for row in levels:
            print(
                f"  {row[0]} : {row[1]:,}"
            )


def main() -> int:
    print("=" * 78)
    print("StockWaveScanner V2 - V1 Core Coverage Audit")
    print("=" * 78)

    if not DB_PATH.exists():
        print()
        print("ERROR")
        print(f"Database not found: {DB_PATH}")
        return 1

    uri = (
        DB_PATH.resolve().as_uri()
        + "?mode=ro"
    )

    try:
        conn = sqlite3.connect(
            uri,
            uri=True,
            timeout=60,
        )

        conn.execute(
            "PRAGMA query_only = ON"
        )

        conn.execute(
            "PRAGMA busy_timeout = 60000"
        )

        try:
            audit_price(conn)
            audit_institutional(conn)
            audit_tdcc(conn)

        finally:
            conn.close()

        print()
        print("=" * 78)
        print("CORE COVERAGE AUDIT COMPLETE")
        print("=" * 78)
        print("Database remained READ ONLY.")

        return 0

    except Exception as exc:
        print()
        print("=" * 78)
        print("ERROR")
        print("=" * 78)
        print(exc)
        print()
        print("Database remained READ ONLY.")

        return 1


if __name__ == "__main__":
    sys.exit(main())