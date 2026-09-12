from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

ARCHIVE_DIR = (
    ROOT.parent
    / "StockWaveScanner_V1_Data_Archive_20260912"
)

DB_PATH = ARCHIVE_DIR / "stocks.db"

RUNTIME_DIR = ROOT / "runtime"

REPORT_PATH = RUNTIME_DIR / "v1_database_audit.json"


DATE_CANDIDATES = [
    "trade_date",
    "data_date",
    "date",
    "source_date",
    "revenue_month",
    "udt",
    "created_at",
    "updated_at",
]

STOCK_CANDIDATES = [
    "stock_id",
    "stock_no",
    "stock_code",
    "securitiescompanycode",
    "code",
    "security_code",
]

HOLDER_LEVEL_CANDIDATES = [
    "holder_level",
    "holding_level",
    "level",
]


def qid(name: str) -> str:
    """
    Safe SQLite identifier quote.
    """
    return '"' + name.replace('"', '""') + '"'


def format_number(value: int | None) -> str:
    if value is None:
        return "-"

    return f"{value:,}"


def format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:,.2f} {unit}"

        value /= 1024

    return f"{size:,} B"


def find_column(
    columns: list[str],
    candidates: list[str],
) -> str | None:
    mapping = {
        column.lower(): column
        for column in columns
    }

    for candidate in candidates:
        if candidate.lower() in mapping:
            return mapping[candidate.lower()]

    return None


def detect_category(
    table_name: str,
    columns: list[str],
) -> str:
    name = table_name.lower()
    cols = {column.lower() for column in columns}

    if (
        "tdcc" in name
        or "holder" in name
        or "holding" in name
        or "holder_level" in cols
        or "holding_level" in cols
    ):
        return "TDCC"

    institutional_words = [
        "institutional",
        "foreign",
        "trust",
        "dealer",
        "3insti",
    ]

    if any(word in name for word in institutional_words):
        return "INSTITUTIONAL"

    if (
        any("foreign" in column for column in cols)
        or any("trust" in column for column in cols)
        or any("dealer" in column for column in cols)
    ):
        return "INSTITUTIONAL"

    price_columns = {
        "open",
        "high",
        "low",
        "close",
    }

    if price_columns.issubset(cols):
        return "PRICE"

    if (
        "price" in name
        or "stock_day" in name
        or "market_daily" in name
    ):
        return "PRICE"

    if (
        "stock_master" in name
        or "stockmaster" in name
        or (
            "stock_id" in cols
            and (
                "stock_name" in cols
                or "stockname" in cols
            )
        )
    ):
        return "STOCK_MASTER"

    if "revenue" in name:
        return "REVENUE"

    if (
        "financial" in name
        or "income" in name
    ):
        return "FINANCIAL"

    return "OTHER"


def get_table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    return [str(row[0]) for row in rows]


def get_columns(
    conn: sqlite3.Connection,
    table_name: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"PRAGMA table_info({qid(table_name)})"
    ).fetchall()

    result = []

    for row in rows:
        result.append(
            {
                "cid": row[0],
                "name": row[1],
                "type": row[2],
                "notnull": row[3],
                "default": row[4],
                "pk": row[5],
            }
        )

    return result


def get_indexes(
    conn: sqlite3.Connection,
    table_name: str,
) -> list[str]:
    rows = conn.execute(
        f"PRAGMA index_list({qid(table_name)})"
    ).fetchall()

    return [
        str(row[1])
        for row in rows
    ]


def get_row_count(
    conn: sqlite3.Connection,
    table_name: str,
) -> int:
    row = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM {qid(table_name)}
        """
    ).fetchone()

    return int(row[0])


def get_date_range(
    conn: sqlite3.Connection,
    table_name: str,
    date_column: str | None,
) -> tuple[Any, Any]:
    if not date_column:
        return None, None

    row = conn.execute(
        f"""
        SELECT
            MIN({qid(date_column)}),
            MAX({qid(date_column)})
        FROM {qid(table_name)}
        WHERE {qid(date_column)} IS NOT NULL
        """
    ).fetchone()

    return row[0], row[1]


def get_distinct_stock_count(
    conn: sqlite3.Connection,
    table_name: str,
    stock_column: str | None,
) -> int | None:
    if not stock_column:
        return None

    row = conn.execute(
        f"""
        SELECT COUNT(
            DISTINCT {qid(stock_column)}
        )
        FROM {qid(table_name)}
        WHERE {qid(stock_column)} IS NOT NULL
        """
    ).fetchone()

    return int(row[0])


def get_null_count(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str | None,
) -> int | None:
    if not column_name:
        return None

    row = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM {qid(table_name)}
        WHERE {qid(column_name)} IS NULL
           OR TRIM(
                CAST({qid(column_name)} AS TEXT)
              ) = ''
        """
    ).fetchone()

    return int(row[0])


def get_duplicate_groups(
    conn: sqlite3.Connection,
    table_name: str,
    key_columns: list[str],
    row_count: int,
) -> int | str | None:
    if not key_columns:
        return None

    # 巨型資料表先避免做過度昂貴的 GROUP BY。
    # 若超過 5,000,000 rows，Phase 4 後續只針對
    # 確認要 Migration 的核心 table 再做完整 duplicate audit。
    if row_count > 5_000_000:
        return "SKIPPED_LARGE_TABLE"

    group_columns = ", ".join(
        qid(column)
        for column in key_columns
    )

    sql = f"""
        SELECT COUNT(*)
        FROM (
            SELECT
                {group_columns},
                COUNT(*) AS c
            FROM {qid(table_name)}
            GROUP BY {group_columns}
            HAVING COUNT(*) > 1
        )
    """

    row = conn.execute(sql).fetchone()

    return int(row[0])


def determine_key_columns(
    category: str,
    stock_column: str | None,
    date_column: str | None,
    columns: list[str],
) -> list[str]:
    if not stock_column:
        return []

    if category in {
        "PRICE",
        "INSTITUTIONAL",
        "REVENUE",
        "FINANCIAL",
    }:
        if date_column:
            return [
                stock_column,
                date_column,
            ]

    if category == "TDCC":
        holder_level = find_column(
            columns,
            HOLDER_LEVEL_CANDIDATES,
        )

        if date_column and holder_level:
            return [
                stock_column,
                date_column,
                holder_level,
            ]

    return []


def audit_table(
    conn: sqlite3.Connection,
    table_name: str,
) -> dict[str, Any]:
    started = time.time()

    column_info = get_columns(
        conn,
        table_name,
    )

    columns = [
        item["name"]
        for item in column_info
    ]

    category = detect_category(
        table_name,
        columns,
    )

    row_count = get_row_count(
        conn,
        table_name,
    )

    date_column = find_column(
        columns,
        DATE_CANDIDATES,
    )

    stock_column = find_column(
        columns,
        STOCK_CANDIDATES,
    )

    min_date, max_date = get_date_range(
        conn,
        table_name,
        date_column,
    )

    distinct_stocks = get_distinct_stock_count(
        conn,
        table_name,
        stock_column,
    )

    stock_nulls = get_null_count(
        conn,
        table_name,
        stock_column,
    )

    date_nulls = get_null_count(
        conn,
        table_name,
        date_column,
    )

    key_columns = determine_key_columns(
        category,
        stock_column,
        date_column,
        columns,
    )

    duplicate_groups = get_duplicate_groups(
        conn,
        table_name,
        key_columns,
        row_count,
    )

    indexes = get_indexes(
        conn,
        table_name,
    )

    elapsed = time.time() - started

    return {
        "table": table_name,
        "category": category,
        "row_count": row_count,
        "column_count": len(columns),
        "columns": column_info,
        "stock_column": stock_column,
        "date_column": date_column,
        "min_date": min_date,
        "max_date": max_date,
        "distinct_stocks": distinct_stocks,
        "stock_nulls": stock_nulls,
        "date_nulls": date_nulls,
        "candidate_key": key_columns,
        "duplicate_groups": duplicate_groups,
        "indexes": indexes,
        "elapsed_seconds": round(
            elapsed,
            3,
        ),
    }


def print_table_result(
    result: dict[str, Any],
) -> None:
    print()
    print(
        f"[{result['category']}] "
        f"{result['table']}"
    )

    print(
        f"    Rows           : "
        f"{format_number(result['row_count'])}"
    )

    print(
        f"    Columns        : "
        f"{result['column_count']}"
    )

    if result["stock_column"]:
        print(
            f"    Stock Column   : "
            f"{result['stock_column']}"
        )

        print(
            f"    Distinct Stocks: "
            f"{format_number(result['distinct_stocks'])}"
        )

        print(
            f"    Stock NULL     : "
            f"{format_number(result['stock_nulls'])}"
        )

    if result["date_column"]:
        print(
            f"    Date Column    : "
            f"{result['date_column']}"
        )

        print(
            f"    Date Range     : "
            f"{result['min_date']} "
            f".. {result['max_date']}"
        )

        print(
            f"    Date NULL      : "
            f"{format_number(result['date_nulls'])}"
        )

    if result["candidate_key"]:
        print(
            "    Candidate Key  : "
            + " + ".join(
                result["candidate_key"]
            )
        )

        print(
            f"    Duplicate Grps : "
            f"{result['duplicate_groups']}"
        )

    print(
        f"    Indexes        : "
        f"{len(result['indexes'])}"
    )

    print(
        f"    Audit Seconds  : "
        f"{result['elapsed_seconds']}"
    )


def print_core_summary(
    results: list[dict[str, Any]],
) -> None:
    print()
    print("=" * 78)
    print("CORE MIGRATION CANDIDATES")
    print("=" * 78)

    core_categories = {
        "PRICE",
        "INSTITUTIONAL",
        "TDCC",
        "STOCK_MASTER",
        "REVENUE",
        "FINANCIAL",
    }

    candidates = [
        result
        for result in results
        if result["category"] in core_categories
    ]

    if not candidates:
        print("No core migration candidate tables detected.")
        return

    for result in candidates:
        print(
            f"{result['category']:<14} | "
            f"{result['table']:<35} | "
            f"rows={format_number(result['row_count']):>12} | "
            f"stocks={format_number(result['distinct_stocks']):>8} | "
            f"{result['min_date']} .. {result['max_date']}"
        )


def print_category_summary(
    results: list[dict[str, Any]],
) -> None:
    summary: dict[str, dict[str, int]] = {}

    for result in results:
        category = result["category"]

        if category not in summary:
            summary[category] = {
                "tables": 0,
                "rows": 0,
            }

        summary[category]["tables"] += 1
        summary[category]["rows"] += int(
            result["row_count"]
        )

    print()
    print("=" * 78)
    print("CATEGORY SUMMARY")
    print("=" * 78)

    for category in sorted(summary):
        print(
            f"{category:<14} | "
            f"tables={summary[category]['tables']:<3} | "
            f"rows={format_number(summary[category]['rows'])}"
        )


def main() -> int:
    print("=" * 78)
    print("StockWaveScanner V2 - V1 Historical Database Audit")
    print("=" * 78)
    print()

    if not DB_PATH.exists():
        print("ERROR")
        print(
            f"V1 database not found:\n{DB_PATH}"
        )
        return 1

    db_size = DB_PATH.stat().st_size

    print(f"Database : {DB_PATH}")
    print(f"Size     : {format_size(db_size)}")
    print("Mode     : READ ONLY")
    print()

    RUNTIME_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # as_uri() 在 Windows 會產生：
    # file:///D:/...
    # 再加 mode=ro，SQLite 不允許此 connection 寫入。
    db_uri = (
        DB_PATH.resolve().as_uri()
        + "?mode=ro"
    )

    started = time.time()

    try:
        conn = sqlite3.connect(
            db_uri,
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
            sqlite_version = conn.execute(
                "SELECT sqlite_version()"
            ).fetchone()[0]

            tables = get_table_names(conn)

            print(
                f"SQLite   : {sqlite_version}"
            )

            print(
                f"Tables   : {len(tables)}"
            )

            print()
            print("=" * 78)
            print("TABLE AUDIT")
            print("=" * 78)

            results: list[dict[str, Any]] = []

            for index, table_name in enumerate(
                tables,
                start=1,
            ):
                print(
                    f"\nAuditing "
                    f"[{index}/{len(tables)}] "
                    f"{table_name} ..."
                )

                try:
                    result = audit_table(
                        conn,
                        table_name,
                    )

                    results.append(result)

                    print_table_result(result)

                except Exception as exc:
                    print(
                        f"[ERROR] {table_name}: {exc}"
                    )

                    results.append(
                        {
                            "table": table_name,
                            "category": "ERROR",
                            "error": str(exc),
                            "row_count": 0,
                            "distinct_stocks": None,
                            "min_date": None,
                            "max_date": None,
                        }
                    )

            print_core_summary(results)

            print_category_summary(results)

            elapsed = time.time() - started

            report = {
                "database": str(DB_PATH),
                "database_size_bytes": db_size,
                "sqlite_version": sqlite_version,
                "table_count": len(tables),
                "audit_seconds": round(
                    elapsed,
                    3,
                ),
                "tables": results,
            }

            REPORT_PATH.write_text(
                json.dumps(
                    report,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )

            print()
            print("=" * 78)
            print("AUDIT COMPLETE")
            print("=" * 78)

            print(
                f"Tables Audited : {len(tables)}"
            )

            print(
                f"Audit Seconds  : {elapsed:,.2f}"
            )

            print(
                f"Detailed Report: {REPORT_PATH}"
            )

            print()
            print(
                "Database remained READ ONLY."
            )

            return 0

        finally:
            conn.close()

    except Exception as exc:
        print()
        print("=" * 78)
        print("ERROR")
        print("=" * 78)
        print(exc)
        print()
        print(
            "No changes were made to the V1 database."
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())