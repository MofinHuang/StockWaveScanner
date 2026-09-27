from __future__ import annotations

import os
import sys
from pathlib import Path

import libsql
from dotenv import load_dotenv


# ============================================================
# CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


# ============================================================
# CONSOLE
# ============================================================


def configure_console() -> None:

    for stream in (
        sys.stdout,
        sys.stderr,
    ):

        reconfigure = getattr(
            stream,
            "reconfigure",
            None,
        )

        if callable(
            reconfigure
        ):

            try:

                reconfigure(
                    encoding="utf-8",
                    errors="replace",
                )

            except Exception:
                pass


# ============================================================
# DEV SAFETY
# ============================================================


def load_dev_credentials(
) -> tuple[str, str]:

    load_dotenv(
        ENV_FILE
    )

    url = (
        os.getenv(
            "TURSO_DEV_DATABASE_URL",
            "",
        )
        .strip()
    )

    token = (
        os.getenv(
            "TURSO_DEV_AUTH_TOKEN",
            "",
        )
        .strip()
    )

    if not url:

        raise RuntimeError(
            "TURSO_DEV_DATABASE_URL is missing from .env"
        )

    if not token:

        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN is missing from .env"
        )

    lower_url = (
        url.lower()
    )

    if (
        "stockwave-dev"
        not in lower_url
    ):

        raise RuntimeError(
            "SAFETY STOP: database is not stockwave-dev"
        )

    if (
        "stockwave-prod"
        in lower_url
    ):

        raise RuntimeError(
            "SAFETY STOP: PROD database detected"
        )

    return (
        url,
        token,
    )


# ============================================================
# SCHEMA
# ============================================================


SECTOR_MASTER_SQL = """
CREATE TABLE IF NOT EXISTS sector_master (

    sector_id TEXT PRIMARY KEY,

    sector_name TEXT NOT NULL,

    sector_type TEXT NOT NULL,

    parent_sector_id TEXT,

    source TEXT,

    sort_order INTEGER NOT NULL DEFAULT 0,

    active INTEGER NOT NULL DEFAULT 1,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (
        sector_type IN (
            'INDUSTRY',
            'SUB_INDUSTRY',
            'THEME'
        )
    ),

    CHECK (
        active IN (
            0,
            1
        )
    )

)
"""


STOCK_SECTOR_REL_SQL = """
CREATE TABLE IF NOT EXISTS stock_sector_rel (

    stock_id TEXT NOT NULL,

    sector_id TEXT NOT NULL,

    is_primary INTEGER NOT NULL DEFAULT 0,

    source TEXT,

    effective_date TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        stock_id,
        sector_id
    ),

    CHECK (
        is_primary IN (
            0,
            1
        )
    )

)
"""


SECTOR_SNAPSHOT_DAILY_SQL = """
CREATE TABLE IF NOT EXISTS sector_snapshot_daily (

    trade_date TEXT NOT NULL,

    sector_id TEXT NOT NULL,

    stock_count INTEGER,

    up_count INTEGER,

    down_count INTEGER,

    above_ma20_count INTEGER,

    new_high_count INTEGER,

    foreign_net INTEGER,

    trust_net INTEGER,

    dealer_net INTEGER,

    large_holder_change REAL,

    sector_return_1d REAL,

    sector_return_5d REAL,

    sector_return_20d REAL,

    breadth_score REAL,

    technical_score REAL,

    status TEXT,

    model_version TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        trade_date,
        sector_id
    )

)
"""


INDEX_SQL = [

    """
    CREATE INDEX IF NOT EXISTS
        idx_sector_master_type_active
    ON sector_master (
        sector_type,
        active
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_sector_master_parent
    ON sector_master (
        parent_sector_id
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_stock_sector_rel_stock
    ON stock_sector_rel (
        stock_id
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_stock_sector_rel_sector
    ON stock_sector_rel (
        sector_id
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_stock_sector_rel_primary
    ON stock_sector_rel (
        stock_id,
        is_primary
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_sector_snapshot_daily_sector
    ON sector_snapshot_daily (
        sector_id,
        trade_date
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_sector_snapshot_daily_date
    ON sector_snapshot_daily (
        trade_date
    )
    """,
]


# ============================================================
# HELPERS
# ============================================================


def table_exists(
    conn,
    table_name: str,
) -> bool:

    row = (
        conn.execute(
            """
            SELECT name

            FROM sqlite_master

            WHERE type = 'table'
              AND name = ?
            """,
            (
                table_name,
            ),
        )
        .fetchone()
    )

    return (
        row is not None
    )


def count_rows(
    conn,
    table_name: str,
) -> int:

    row = (
        conn.execute(
            f"""
            SELECT COUNT(*)

            FROM {table_name}
            """
        )
        .fetchone()
    )

    if row is None:
        return 0

    return int(
        row[0]
        or 0
    )


# ============================================================
# CREATE SCHEMA
# ============================================================


def create_schema(
    conn,
) -> None:

    conn.execute(
        "BEGIN"
    )

    try:

        conn.execute(
            SECTOR_MASTER_SQL
        )

        conn.execute(
            STOCK_SECTOR_REL_SQL
        )

        conn.execute(
            SECTOR_SNAPSHOT_DAILY_SQL
        )

        for sql in INDEX_SQL:

            conn.execute(
                sql
            )

        conn.commit()

    except BaseException:

        try:

            conn.rollback()

        except Exception:
            pass

        raise


# ============================================================
# VERIFY
# ============================================================


def verify_schema(
    conn,
) -> None:

    tables = (

        "sector_master",

        "stock_sector_rel",

        "sector_snapshot_daily",
    )

    print()

    print(
        "=" * 70
    )

    print(
        "V3 SECTOR SCHEMA VERIFICATION"
    )

    print(
        "=" * 70
    )

    for table_name in tables:

        exists = (
            table_exists(
                conn,
                table_name,
            )
        )

        if not exists:

            raise RuntimeError(
                f"Missing table: {table_name}"
            )

        row_count = (
            count_rows(
                conn,
                table_name,
            )
        )

        print(
            f"{table_name:<28} "
            f"| rows={row_count:,}"
        )

    print()

    print(
        "[PASS] V3 sector schema ready"
    )


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    configure_console()

    print(
        "=" * 70
    )

    print(
        "StockWaveScanner V3 - Sector Schema Init"
    )

    print(
        "=" * 70
    )

    print()

    try:

        url, token = (
            load_dev_credentials()
        )

        print(
            "Environment : DEV"
        )

        print(
            "Database    : stockwave-dev"
        )

        print(
            "PROD Access : DISABLED"
        )

        print()

        conn = libsql.connect(
            database=url,
            auth_token=token,
        )

        try:

            test = (
                conn.execute(
                    "SELECT 1"
                )
                .fetchone()
            )

            if (
                not test
                or
                test[0] != 1
            ):

                raise RuntimeError(
                    "Turso DEV connection validation failed"
                )

            print(
                "[PASS] Turso DEV connection"
            )

            print()

            print(
                "Creating V3 sector schema ..."
            )

            create_schema(
                conn
            )

            print(
                "[PASS] Schema creation completed"
            )

            verify_schema(
                conn
            )

        finally:

            conn.close()

        print()

        print(
            "=" * 70
        )

        print(
            "V3 SECTOR SCHEMA INIT OK"
        )

        print(
            "=" * 70
        )

        print()

        print(
            "No PROD database was accessed."
        )

        return 0

    except Exception as exc:

        print()

        print(
            "=" * 70
        )

        print(
            "ERROR"
        )

        print(
            "=" * 70
        )

        print(
            str(
                exc
            )
        )

        print()

        print(
            "No PROD database was accessed."
        )

        return 1


if __name__ == "__main__":

    sys.exit(
        main()
    )