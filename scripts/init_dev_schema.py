from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
SCHEMA_FILE = ROOT / "db" / "schema_v2.sql"


EXPECTED_TABLES = {
    "stock_master",
    "market_index_daily",
    "stock_price_daily",
    "institutional_daily",
    "tdcc_distribution",
    "tdcc_summary",
    "monthly_revenue",
    "quarterly_financial",
    "sync_state",
    "schema_meta",
}


EXPECTED_INSTITUTIONAL_STATUS_COLUMNS = {
    "foreign_data_status",
    "trust_data_status",
    "dealer_data_status",
}


STATUS_VALUES_SQL = """
CHECK (
    {column_name} IN (
        'STORED',
        'ZERO_INFERRED',
        'INSUFFICIENT_DATA'
    )
)
"""


def mask_url(url: str) -> str:
    if not url:
        return "(empty)"

    if "://" not in url:
        return "***"

    scheme, rest = url.split("://", 1)

    if "@" in rest:
        rest = rest.split("@", 1)[-1]

    return f"{scheme}://{rest}"


def load_dev_credentials() -> tuple[str, str]:
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
            "TURSO_DEV_DATABASE_URL is missing from .env"
        )

    if not token:
        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN is missing from .env"
        )

    # --------------------------------------------------------
    # Hard Safety Guard
    # --------------------------------------------------------

    lower_url = url.lower()

    if "stockwave-dev" not in lower_url:
        raise RuntimeError(
            "SAFETY STOP: "
            "TURSO_DEV_DATABASE_URL does not point to stockwave-dev"
        )

    if "stockwave-prod" in lower_url:
        raise RuntimeError(
            "SAFETY STOP: PROD database detected"
        )

    return url, token


def read_schema() -> str:
    if not SCHEMA_FILE.exists():
        raise RuntimeError(
            f"Schema file not found: {SCHEMA_FILE}"
        )

    sql = SCHEMA_FILE.read_text(
        encoding="utf-8",
    )

    if not sql.strip():
        raise RuntimeError(
            "schema_v2.sql is empty"
        )

    return sql


def split_sql_statements(
    sql: str,
) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []

    for raw_line in sql.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("--"):
            continue

        buffer.append(raw_line)

        candidate = "\n".join(
            buffer
        ).strip()

        if sqlite3.complete_statement(
            candidate
        ):
            statements.append(
                candidate
            )

            buffer = []

    remaining = "\n".join(
        buffer
    ).strip()

    if remaining:
        raise RuntimeError(
            "Schema contains an incomplete SQL statement:\n"
            f"{remaining}"
        )

    return statements


def table_exists(
    conn,
    table_name: str,
) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def get_table_columns(
    conn,
    table_name: str,
) -> set[str]:
    rows = conn.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    return {
        str(row[1])
        for row in rows
    }


def ensure_institutional_status_columns(
    conn,
) -> int:
    """
    Upgrade DRAFT-1 institutional_daily safely.

    Existing DRAFT-1 already contains:
        foreign_data_status

    DRAFT-2 additionally requires:
        trust_data_status
        dealer_data_status

    This function is idempotent because it checks
    PRAGMA table_info before ALTER TABLE.
    """

    if not table_exists(
        conn,
        "institutional_daily",
    ):
        return 0

    columns = get_table_columns(
        conn,
        "institutional_daily",
    )

    added = 0

    for column_name in sorted(
        EXPECTED_INSTITUTIONAL_STATUS_COLUMNS
    ):
        if column_name in columns:
            continue

        check_sql = (
            STATUS_VALUES_SQL.format(
                column_name=column_name
            )
            .strip()
        )

        sql = f"""
        ALTER TABLE institutional_daily
        ADD COLUMN {column_name}
            TEXT NOT NULL
            DEFAULT 'INSUFFICIENT_DATA'
            {check_sql}
        """

        print(
            f"[MIGRATE] Add "
            f"institutional_daily.{column_name}"
        )

        conn.execute(sql)

        added += 1

    return added


def fetch_table_names(
    conn,
) -> set[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    return {
        str(row[0])
        for row in rows
    }


def verify_schema(
    conn,
) -> None:
    actual_tables = fetch_table_names(
        conn
    )

    print()
    print("=" * 68)
    print("TABLE VERIFICATION")
    print("=" * 68)

    for table in sorted(
        EXPECTED_TABLES
    ):
        if table in actual_tables:
            print(
                f"[PASS] {table}"
            )
        else:
            print(
                f"[FAIL] {table}"
            )

    missing_tables = (
        EXPECTED_TABLES
        - actual_tables
    )

    if missing_tables:
        raise RuntimeError(
            "Missing tables: "
            + ", ".join(
                sorted(
                    missing_tables
                )
            )
        )

    institutional_columns = (
        get_table_columns(
            conn,
            "institutional_daily",
        )
    )

    print()
    print("=" * 68)
    print("INSTITUTIONAL STATUS VERIFICATION")
    print("=" * 68)

    for column in sorted(
        EXPECTED_INSTITUTIONAL_STATUS_COLUMNS
    ):
        if column in institutional_columns:
            print(
                f"[PASS] {column}"
            )
        else:
            print(
                f"[FAIL] {column}"
            )

    missing_status_columns = (
        EXPECTED_INSTITUTIONAL_STATUS_COLUMNS
        - institutional_columns
    )

    if missing_status_columns:
        raise RuntimeError(
            "Missing institutional status columns: "
            + ", ".join(
                sorted(
                    missing_status_columns
                )
            )
        )

    version_row = conn.execute(
        """
        SELECT schema_value
        FROM schema_meta
        WHERE schema_key = 'schema_version'
        """
    ).fetchone()

    if not version_row:
        raise RuntimeError(
            "schema_version was not found in schema_meta"
        )

    schema_version = str(
        version_row[0]
    )

    if schema_version != "V2.1-DRAFT-2":
        raise RuntimeError(
            "Unexpected schema version: "
            f"{schema_version}"
        )

    print()
    print(
        f"Schema Version : "
        f"{schema_version}"
    )

    print(
        f"Expected Tables: "
        f"{len(EXPECTED_TABLES)}"
    )

    print(
        f"Verified Tables: "
        f"{len(EXPECTED_TABLES)}"
    )


def main() -> int:
    print("=" * 68)
    print(
        "StockWaveScanner V2 - "
        "Turso DEV Schema Initialization / Upgrade"
    )
    print("=" * 68)
    print()

    try:
        url, token = (
            load_dev_credentials()
        )

        print(
            "Environment : DEV"
        )

        print(
            f"Database    : "
            f"{mask_url(url)}"
        )

        print(
            "PROD Access : DISABLED"
        )

        print()

        sql = read_schema()

        statements = (
            split_sql_statements(
                sql
            )
        )

        print(
            f"Schema File : "
            f"{SCHEMA_FILE.name}"
        )

        print(
            f"Statements  : "
            f"{len(statements)}"
        )

        print()
        print(
            "Connecting to Turso DEV ..."
        )

        conn = libsql.connect(
            database=url,
            auth_token=token,
        )

        try:
            result = conn.execute(
                "SELECT 1"
            ).fetchone()

            if (
                not result
                or result[0] != 1
            ):
                raise RuntimeError(
                    "Turso DEV SELECT 1 validation failed"
                )

            print(
                "[PASS] Turso DEV connection"
            )

            print()
            print(
                "Checking compatibility migrations ..."
            )

            migrated_columns = (
                ensure_institutional_status_columns(
                    conn
                )
            )

            if migrated_columns == 0:
                print(
                    "[PASS] No compatibility "
                    "column migration required"
                )
            else:
                print(
                    f"[PASS] Added "
                    f"{migrated_columns} "
                    f"compatibility column(s)"
                )

            conn.commit()

            print()
            print(
                "Applying canonical schema ..."
            )

            executed = 0

            for statement in statements:
                conn.execute(
                    statement
                )

                executed += 1

            conn.commit()

            print(
                f"[PASS] Schema applied "
                f"({executed} statements)"
            )

            verify_schema(
                conn
            )

            print()
            print("=" * 68)
            print(
                "TURSO DEV SCHEMA "
                "INITIALIZATION / UPGRADE OK"
            )
            print("=" * 68)

            print()
            print(
                "No table was dropped."
            )

            print(
                "No historical data was deleted."
            )

            print(
                "No PROD database was accessed."
            )

            return 0

        finally:
            conn.close()

    except Exception as exc:
        print()
        print("=" * 68)
        print("ERROR")
        print("=" * 68)
        print(str(exc))
        print()
        print(
            "No PROD database was accessed."
        )

        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )