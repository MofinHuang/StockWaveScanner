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
    "monthly_revenue",
    "quarterly_financial",
    "sync_state",
    "schema_meta",
}


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

    url = os.getenv("TURSO_DEV_DATABASE_URL", "").strip()
    token = os.getenv("TURSO_DEV_AUTH_TOKEN", "").strip()

    if not url:
        raise RuntimeError(
            "TURSO_DEV_DATABASE_URL is missing from .env"
        )

    if not token:
        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN is missing from .env"
        )

    # --------------------------------------------------------
    # Hard safety guard:
    # 這支程式只允許操作 StockWaveScanner DEV Database。
    # --------------------------------------------------------
    if "stockwave-dev" not in url.lower():
        raise RuntimeError(
            "SAFETY STOP: "
            "TURSO_DEV_DATABASE_URL does not point to stockwave-dev"
        )

    if "stockwave-prod" in url.lower():
        raise RuntimeError(
            "SAFETY STOP: PROD database detected"
        )

    return url, token


def read_schema() -> str:
    if not SCHEMA_FILE.exists():
        raise RuntimeError(
            f"Schema file not found: {SCHEMA_FILE}"
        )

    sql = SCHEMA_FILE.read_text(encoding="utf-8")

    if not sql.strip():
        raise RuntimeError("schema_v2.sql is empty")

    return sql


def split_sql_statements(sql: str) -> list[str]:
    """
    將 schema SQL 拆成單一 statements。

    使用 sqlite3.complete_statement 判斷分號是否構成
    一個完整 SQLite statement，而不是用單純 split(';')。
    """

    statements: list[str] = []
    buffer: list[str] = []

    for raw_line in sql.splitlines():
        line = raw_line.strip()

        # schema_v2.sql 目前只有 -- 單行註解。
        if not line:
            continue

        if line.startswith("--"):
            continue

        buffer.append(raw_line)

        candidate = "\n".join(buffer).strip()

        if sqlite3.complete_statement(candidate):
            statements.append(candidate)
            buffer = []

    remaining = "\n".join(buffer).strip()

    if remaining:
        raise RuntimeError(
            "Schema contains an incomplete SQL statement:\n"
            f"{remaining}"
        )

    return statements


def fetch_table_names(conn) -> set[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    return {str(row[0]) for row in rows}


def verify_schema(conn) -> None:
    actual_tables = fetch_table_names(conn)

    print()
    print("=" * 64)
    print("TABLE VERIFICATION")
    print("=" * 64)

    for table in sorted(EXPECTED_TABLES):
        if table in actual_tables:
            print(f"[PASS] {table}")
        else:
            print(f"[FAIL] {table}")

    missing = EXPECTED_TABLES - actual_tables

    if missing:
        raise RuntimeError(
            "Missing tables: "
            + ", ".join(sorted(missing))
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

    schema_version = str(version_row[0])

    print()
    print(f"Schema Version : {schema_version}")
    print(f"Expected Tables: {len(EXPECTED_TABLES)}")
    print(f"Verified Tables: {len(EXPECTED_TABLES)}")


def main() -> int:
    print("=" * 64)
    print("StockWaveScanner V2 - Turso DEV Schema Initialization")
    print("=" * 64)
    print()

    try:
        url, token = load_dev_credentials()

        print("Environment : DEV")
        print(f"Database    : {mask_url(url)}")
        print("PROD Access : DISABLED")
        print()

        sql = read_schema()
        statements = split_sql_statements(sql)

        print(f"Schema File : {SCHEMA_FILE.name}")
        print(f"Statements  : {len(statements)}")
        print()

        print("Connecting to Turso DEV ...")

        conn = libsql.connect(
            database=url,
            auth_token=token,
        )

        try:
            result = conn.execute("SELECT 1").fetchone()

            if not result or result[0] != 1:
                raise RuntimeError(
                    "Turso DEV SELECT 1 validation failed"
                )

            print("[PASS] Turso DEV connection")
            print()

            print("Applying schema ...")

            executed = 0

            for statement in statements:
                conn.execute(statement)
                executed += 1

            conn.commit()

            print(
                f"[PASS] Schema applied "
                f"({executed} statements)"
            )

            verify_schema(conn)

            print()
            print("=" * 64)
            print("TURSO DEV SCHEMA INITIALIZATION OK")
            print("=" * 64)
            print()
            print("No PROD database was accessed.")

            return 0

        finally:
            conn.close()

    except Exception as exc:
        print()
        print("=" * 64)
        print("ERROR")
        print("=" * 64)
        print(str(exc))
        print()
        print("No PROD database was accessed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())