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


ANALYST_MASTER_SQL = """
CREATE TABLE IF NOT EXISTS analyst_master (

    analyst_id TEXT PRIMARY KEY,

    analyst_name TEXT NOT NULL,

    display_name TEXT,

    organization_name TEXT,

    active INTEGER NOT NULL DEFAULT 1,

    sort_order INTEGER NOT NULL DEFAULT 0,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (
        active IN (
            0,
            1
        )
    )

)
"""


ANALYST_SOURCE_SQL = """
CREATE TABLE IF NOT EXISTS analyst_source (

    source_id TEXT PRIMARY KEY,

    analyst_id TEXT NOT NULL,

    source_type TEXT NOT NULL,

    source_name TEXT NOT NULL,

    source_url TEXT NOT NULL,

    source_account_id TEXT,

    source_priority INTEGER NOT NULL DEFAULT 100,

    is_official INTEGER NOT NULL DEFAULT 0,

    is_enabled INTEGER NOT NULL DEFAULT 1,

    usage_mode TEXT NOT NULL DEFAULT 'METADATA_SUMMARY',

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (
        source_type IN (
            'YOUTUBE',
            'PODCAST',
            'WEBSITE',
            'OTHER'
        )
    ),

    CHECK (
        is_official IN (
            0,
            1
        )
    ),

    CHECK (
        is_enabled IN (
            0,
            1
        )
    ),

    CHECK (
        usage_mode IN (
            'METADATA_SUMMARY'
        )
    )

)
"""


ANALYST_COMMENT_SQL = """
CREATE TABLE IF NOT EXISTS analyst_comment (

    comment_id TEXT PRIMARY KEY,

    analyst_id TEXT NOT NULL,

    source_id TEXT NOT NULL,

    external_content_id TEXT,

    source_type TEXT NOT NULL,

    source_url TEXT NOT NULL,

    source_title TEXT NOT NULL,

    source_published_at TEXT,

    source_author TEXT,

    summary_text TEXT,

    summary_type TEXT NOT NULL DEFAULT 'SYSTEM_SUMMARY',

    content_hash TEXT,

    canonical_content_key TEXT,

    copyright_mode TEXT NOT NULL DEFAULT 'SUMMARY_ONLY',

    attribution_required INTEGER NOT NULL DEFAULT 1,

    review_status TEXT NOT NULL DEFAULT 'AUTO',

    publish_status TEXT NOT NULL DEFAULT 'READY',

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (
        source_type IN (
            'YOUTUBE',
            'PODCAST',
            'WEBSITE',
            'OTHER'
        )
    ),

    CHECK (
        summary_type IN (
            'SYSTEM_SUMMARY',
            'MANUAL_SUMMARY'
        )
    ),

    CHECK (
        copyright_mode IN (
            'SUMMARY_ONLY'
        )
    ),

    CHECK (
        attribution_required IN (
            0,
            1
        )
    ),

    CHECK (
        review_status IN (
            'AUTO',
            'REVIEWED',
            'REJECTED'
        )
    ),

    CHECK (
        publish_status IN (
            'READY',
            'HIDDEN'
        )
    )

)
"""


ANALYST_COMMENT_STOCK_SQL = """
CREATE TABLE IF NOT EXISTS analyst_comment_stock (

    comment_id TEXT NOT NULL,

    stock_id TEXT NOT NULL,

    mention_type TEXT NOT NULL DEFAULT 'MENTION',

    mention_order INTEGER,

    confidence REAL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        comment_id,
        stock_id
    ),

    CHECK (
        mention_type IN (
            'MENTION',
            'FOCUS'
        )
    ),

    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    )

)
"""


ANALYST_COMMENT_SECTOR_SQL = """
CREATE TABLE IF NOT EXISTS analyst_comment_sector (

    comment_id TEXT NOT NULL,

    sector_id TEXT NOT NULL,

    mention_order INTEGER,

    confidence REAL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        comment_id,
        sector_id
    ),

    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    )

)
"""


ANALYST_COMMENT_FACTOR_SQL = """
CREATE TABLE IF NOT EXISTS analyst_comment_factor (

    comment_id TEXT NOT NULL,

    factor_type TEXT NOT NULL,

    factor_key TEXT NOT NULL,

    factor_label TEXT,

    confidence REAL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        comment_id,
        factor_type,
        factor_key
    ),

    CHECK (
        factor_type IN (
            'FUNDAMENTAL',
            'CHIP',
            'TECHNICAL',
            'INDUSTRY',
            'MACRO',
            'EVENT'
        )
    ),

    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    )

)
"""


INDEX_SQL = [

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_master_active_sort
    ON analyst_master (
        active,
        sort_order
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_source_analyst
    ON analyst_source (
        analyst_id,
        is_enabled,
        source_priority
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_source_type
    ON analyst_source (
        source_type,
        is_enabled
    )
    """,

    """
    CREATE UNIQUE INDEX IF NOT EXISTS
        idx_analyst_source_analyst_url_unique
    ON analyst_source (
        analyst_id,
        source_url
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_comment_analyst_date
    ON analyst_comment (
        analyst_id,
        source_published_at
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_comment_source_date
    ON analyst_comment (
        source_id,
        source_published_at
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_comment_publish_date
    ON analyst_comment (
        publish_status,
        source_published_at
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_comment_review
    ON analyst_comment (
        review_status
    )
    """,

    """
    CREATE UNIQUE INDEX IF NOT EXISTS
        idx_analyst_comment_external_unique
    ON analyst_comment (
        source_id,
        external_content_id
    )
    WHERE external_content_id IS NOT NULL
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_comment_content_hash
    ON analyst_comment (
        content_hash
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_comment_canonical
    ON analyst_comment (
        canonical_content_key
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_comment_stock_stock
    ON analyst_comment_stock (
        stock_id,
        comment_id
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_comment_stock_comment
    ON analyst_comment_stock (
        comment_id,
        mention_order
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_comment_sector_sector
    ON analyst_comment_sector (
        sector_id,
        comment_id
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_comment_sector_comment
    ON analyst_comment_sector (
        comment_id,
        mention_order
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_comment_factor_type
    ON analyst_comment_factor (
        factor_type,
        factor_key
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
        idx_analyst_comment_factor_comment
    ON analyst_comment_factor (
        comment_id
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


def index_exists(
    conn,
    index_name: str,
) -> bool:

    row = (
        conn.execute(
            """
            SELECT name

            FROM sqlite_master

            WHERE type = 'index'
              AND name = ?
            """,
            (
                index_name,
            ),
        )
        .fetchone()
    )

    return (
        row is not None
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
            ANALYST_MASTER_SQL
        )

        conn.execute(
            ANALYST_SOURCE_SQL
        )

        conn.execute(
            ANALYST_COMMENT_SQL
        )

        conn.execute(
            ANALYST_COMMENT_STOCK_SQL
        )

        conn.execute(
            ANALYST_COMMENT_SECTOR_SQL
        )

        conn.execute(
            ANALYST_COMMENT_FACTOR_SQL
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

        "analyst_master",

        "analyst_source",

        "analyst_comment",

        "analyst_comment_stock",

        "analyst_comment_sector",

        "analyst_comment_factor",
    )

    required_indexes = (

        "idx_analyst_master_active_sort",

        "idx_analyst_source_analyst",

        "idx_analyst_source_type",

        "idx_analyst_source_analyst_url_unique",

        "idx_analyst_comment_analyst_date",

        "idx_analyst_comment_source_date",

        "idx_analyst_comment_publish_date",

        "idx_analyst_comment_review",

        "idx_analyst_comment_external_unique",

        "idx_analyst_comment_content_hash",

        "idx_analyst_comment_canonical",

        "idx_analyst_comment_stock_stock",

        "idx_analyst_comment_stock_comment",

        "idx_analyst_comment_sector_sector",

        "idx_analyst_comment_sector_comment",

        "idx_analyst_comment_factor_type",

        "idx_analyst_comment_factor_comment",
    )

    print()

    print(
        "=" * 70
    )

    print(
        "V3 ANALYST SCHEMA VERIFICATION"
    )

    print(
        "=" * 70
    )

    print()

    print(
        "Tables"
    )

    print(
        "-" * 70
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
            f"{table_name:<32} "
            f"| rows={row_count:,}"
        )

    print()

    print(
        "Indexes"
    )

    print(
        "-" * 70
    )

    for index_name in required_indexes:

        exists = (
            index_exists(
                conn,
                index_name,
            )
        )

        if not exists:

            raise RuntimeError(
                f"Missing index: {index_name}"
            )

        print(
            f"{index_name:<46} "
            f"| OK"
        )

    print()

    print(
        "[PASS] V3 analyst schema ready"
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
        "StockWaveScanner V3 - Analyst Schema Init"
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
                "Creating V3 analyst schema ..."
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
            "V3 ANALYST SCHEMA INIT OK"
        )

        print(
            "=" * 70
        )

        print()

        print(
            "No analyst data was inserted."
        )

        print(
            "No external source was accessed."
        )

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