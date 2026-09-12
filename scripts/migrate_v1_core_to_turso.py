from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]

ENV_FILE = ROOT / ".env"

V1_DB_PATH = (
    ROOT.parent
    / "StockWaveScanner_V1_Data_Archive_20260912"
    / "stocks.db"
)

BATCH_SIZE = 1000


# ============================================================
# SAFETY
# ============================================================

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


def mask_url(url: str) -> str:
    if "://" not in url:
        return "***"

    scheme, rest = url.split(
        "://",
        1,
    )

    return f"{scheme}://{rest}"


# ============================================================
# V1 READ ONLY DATABASE
# ============================================================

def connect_v1() -> sqlite3.Connection:
    if not V1_DB_PATH.exists():
        raise RuntimeError(
            f"V1 database not found: {V1_DB_PATH}"
        )

    uri = (
        V1_DB_PATH.resolve().as_uri()
        + "?mode=ro"
    )

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

    return conn


def table_columns(
    conn: sqlite3.Connection,
    table: str,
) -> set[str]:
    rows = conn.execute(
        f'PRAGMA table_info("{table}")'
    ).fetchall()

    return {
        str(row[1])
        for row in rows
    }


def validate_v1_schema(
    conn: sqlite3.Connection,
) -> None:
    required_institutional = {
        "stock_id",
        "trade_date",
        "foreign_buy",
        "foreign_sell",
        "foreign_net",
        "source",
    }

    required_tdcc = {
        "stock_id",
        "data_date",
        "large_holder_pct",
        "retail_holder_pct",
        "source",
    }

    institutional_columns = (
        table_columns(
            conn,
            "institutional_trades",
        )
    )

    tdcc_columns = (
        table_columns(
            conn,
            "tdcc_holdings",
        )
    )

    missing = (
        required_institutional
        - institutional_columns
    )

    if missing:
        raise RuntimeError(
            "V1 institutional_trades missing columns: "
            + ", ".join(
                sorted(missing)
            )
        )

    missing = (
        required_tdcc
        - tdcc_columns
    )

    if missing:
        raise RuntimeError(
            "V1 tdcc_holdings missing columns: "
            + ", ".join(
                sorted(missing)
            )
        )


# ============================================================
# HELPERS
# ============================================================

def scalar(
    conn,
    sql: str,
    params: tuple[Any, ...] = (),
) -> Any:
    row = conn.execute(
        sql,
        params,
    ).fetchone()

    if row is None:
        return None

    return row[0]


def tagged_source(
    source: Any,
) -> str:
    text = (
        str(source).strip()
        if source is not None
        else ""
    )

    if not text:
        text = "UNKNOWN"

    return f"V1_MIGRATION|{text}"


def number_or_none(
    value: Any,
) -> float | int | None:
    if value is None:
        return None

    return value


def foreign_status(
    foreign_buy: Any,
    foreign_sell: Any,
    foreign_net: Any,
) -> str:
    """
    V1 沒有保存 data_status。

    非 0 資料可確認有實際法人數值，因此標 STORED。

    三個欄位全部為 0 時，無法從 V1 DB 判斷：
        - 官方明確為 0
        - V1 當時推定為 0

    因此保守標為 INSUFFICIENT_DATA。
    """

    values = [
        foreign_buy,
        foreign_sell,
        foreign_net,
    ]

    if any(
        value is None
        for value in values
    ):
        return "INSUFFICIENT_DATA"

    if any(
        float(value) != 0
        for value in values
    ):
        return "STORED"

    return "INSUFFICIENT_DATA"


# ============================================================
# PREFLIGHT
# ============================================================

def get_v1_source_stock_ids(
    conn: sqlite3.Connection,
) -> set[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT stock_id
        FROM institutional_trades
        WHERE stock_id IS NOT NULL

        UNION

        SELECT DISTINCT stock_id
        FROM tdcc_holdings
        WHERE stock_id IS NOT NULL
        """
    ).fetchall()

    return {
        str(row[0]).strip()
        for row in rows
    }


def get_turso_stock_ids(
    conn,
) -> set[str]:
    rows = conn.execute(
        """
        SELECT stock_id
        FROM stock_master
        """
    ).fetchall()

    return {
        str(row[0]).strip()
        for row in rows
    }


def preflight(
    v1_conn: sqlite3.Connection,
    turso_conn,
) -> tuple[int, int]:
    print()
    print("=" * 72)
    print("PREFLIGHT")
    print("=" * 72)

    validate_v1_schema(
        v1_conn
    )

    institutional_count = int(
        scalar(
            v1_conn,
            """
            SELECT COUNT(*)
            FROM institutional_trades
            """,
        )
    )

    tdcc_count = int(
        scalar(
            v1_conn,
            """
            SELECT COUNT(*)
            FROM tdcc_holdings
            """,
        )
    )

    institutional_duplicates = int(
        scalar(
            v1_conn,
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    stock_id,
                    trade_date
                FROM institutional_trades
                GROUP BY
                    stock_id,
                    trade_date
                HAVING COUNT(*) > 1
            )
            """,
        )
    )

    tdcc_duplicates = int(
        scalar(
            v1_conn,
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    stock_id,
                    data_date
                FROM tdcc_holdings
                GROUP BY
                    stock_id,
                    data_date
                HAVING COUNT(*) > 1
            )
            """,
        )
    )

    print(
        f"Institutional Rows : "
        f"{institutional_count:,}"
    )

    print(
        f"TDCC Summary Rows  : "
        f"{tdcc_count:,}"
    )

    print(
        f"Institutional Dup  : "
        f"{institutional_duplicates:,}"
    )

    print(
        f"TDCC Duplicate     : "
        f"{tdcc_duplicates:,}"
    )

    if institutional_duplicates != 0:
        raise RuntimeError(
            "V1 institutional duplicate keys detected"
        )

    if tdcc_duplicates != 0:
        raise RuntimeError(
            "V1 TDCC duplicate keys detected"
        )

    source_stock_ids = (
        get_v1_source_stock_ids(
            v1_conn
        )
    )

    target_stock_ids = (
        get_turso_stock_ids(
            turso_conn
        )
    )

    missing_stock_ids = sorted(
        source_stock_ids
        - target_stock_ids
    )

    print(
        f"V1 Source Stocks   : "
        f"{len(source_stock_ids):,}"
    )

    print(
        f"Turso Stock Master : "
        f"{len(target_stock_ids):,}"
    )

    print(
        f"Missing FK Stocks  : "
        f"{len(missing_stock_ids):,}"
    )

    if missing_stock_ids:
        print()
        print(
            "Missing Stock IDs:"
        )

        for stock_id in missing_stock_ids[:30]:
            print(
                f"  {stock_id}"
            )

        if len(
            missing_stock_ids
        ) > 30:
            print(
                f"  ... and "
                f"{len(missing_stock_ids) - 30} more"
            )

        raise RuntimeError(
            "Migration stopped before writing data: "
            "V1 contains stock IDs not present in "
            "current Turso stock_master"
        )

    print()
    print(
        "[PASS] V1 schema"
    )

    print(
        "[PASS] Candidate keys"
    )

    print(
        "[PASS] Foreign key compatibility"
    )

    return (
        institutional_count,
        tdcc_count,
    )


# ============================================================
# INSTITUTIONAL
# ============================================================

INSTITUTIONAL_INSERT_SQL = """
INSERT INTO institutional_daily (
    stock_id,
    trade_date,

    foreign_buy,
    foreign_sell,
    foreign_net,

    trust_buy,
    trust_sell,
    trust_net,

    dealer_buy,
    dealer_sell,
    dealer_net,

    foreign_data_status,
    trust_data_status,
    dealer_data_status,

    source,

    created_at,
    updated_at
)
VALUES (
    ?, ?,
    ?, ?, ?,
    NULL, NULL, NULL,
    NULL, NULL, NULL,
    ?,
    'INSUFFICIENT_DATA',
    'INSUFFICIENT_DATA',
    ?,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT(stock_id, trade_date)
DO NOTHING
"""


def load_institutional_rows(
    conn: sqlite3.Connection,
) -> list[tuple[Any, ...]]:
    rows = conn.execute(
        """
        SELECT
            stock_id,
            trade_date,
            foreign_buy,
            foreign_sell,
            foreign_net,
            source
        FROM institutional_trades
        ORDER BY
            trade_date,
            stock_id
        """
    ).fetchall()

    result: list[
        tuple[Any, ...]
    ] = []

    for row in rows:
        stock_id = str(
            row[0]
        ).strip()

        trade_date = str(
            row[1]
        ).strip()

        foreign_buy = (
            number_or_none(
                row[2]
            )
        )

        foreign_sell = (
            number_or_none(
                row[3]
            )
        )

        foreign_net = (
            number_or_none(
                row[4]
            )
        )

        status = foreign_status(
            foreign_buy,
            foreign_sell,
            foreign_net,
        )

        result.append(
            (
                stock_id,
                trade_date,
                foreign_buy,
                foreign_sell,
                foreign_net,
                status,
                tagged_source(
                    row[5]
                ),
            )
        )

    return result


# ============================================================
# TDCC SUMMARY
# ============================================================

TDCC_INSERT_SQL = """
INSERT INTO tdcc_summary (
    stock_id,
    data_date,

    large_holder_pct,
    retail_holder_pct,

    large_holder_change,
    retail_holder_change,

    source,

    created_at,
    updated_at
)
VALUES (
    ?, ?,
    ?, ?,
    ?, ?,
    ?,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT(stock_id, data_date)
DO NOTHING
"""


def load_tdcc_rows(
    conn: sqlite3.Connection,
) -> list[tuple[Any, ...]]:
    rows = conn.execute(
        """
        SELECT
            stock_id,
            data_date,
            large_holder_pct,
            retail_holder_pct,
            source
        FROM tdcc_holdings
        ORDER BY
            stock_id,
            data_date
        """
    ).fetchall()

    result: list[
        tuple[Any, ...]
    ] = []

    previous_by_stock: dict[
        str,
        tuple[
            float | None,
            float | None,
        ]
    ] = {}

    for row in rows:
        stock_id = str(
            row[0]
        ).strip()

        data_date = str(
            row[1]
        ).strip()

        large_pct = (
            float(row[2])
            if row[2] is not None
            else None
        )

        retail_pct = (
            float(row[3])
            if row[3] is not None
            else None
        )

        previous = (
            previous_by_stock.get(
                stock_id
            )
        )

        large_change = None
        retail_change = None

        if previous is not None:
            previous_large = (
                previous[0]
            )

            previous_retail = (
                previous[1]
            )

            if (
                large_pct is not None
                and previous_large
                is not None
            ):
                large_change = (
                    large_pct
                    - previous_large
                )

            if (
                retail_pct is not None
                and previous_retail
                is not None
            ):
                retail_change = (
                    retail_pct
                    - previous_retail
                )

        previous_by_stock[
            stock_id
        ] = (
            large_pct,
            retail_pct,
        )

        result.append(
            (
                stock_id,
                data_date,
                large_pct,
                retail_pct,
                large_change,
                retail_change,
                tagged_source(
                    row[4]
                ),
            )
        )

    return result


# ============================================================
# BATCH WRITE
# ============================================================

def write_batches(
    conn,
    sql: str,
    rows: list[tuple[Any, ...]],
    label: str,
) -> None:
    total = len(rows)

    if total == 0:
        print(
            f"[WARN] {label}: no rows"
        )
        return

    print()
    print(
        f"Writing {label} ..."
    )

    processed = 0
    next_progress = 10_000

    for start in range(
        0,
        total,
        BATCH_SIZE,
    ):
        batch = rows[
            start:
            start + BATCH_SIZE
        ]

        conn.executemany(
            sql,
            batch,
        )

        conn.commit()

        processed += len(
            batch
        )

        if (
            processed
            >= next_progress
            or processed == total
        ):
            print(
                f"  {processed:,}"
                f" / "
                f"{total:,}"
            )

            while (
                next_progress
                <= processed
            ):
                next_progress += (
                    10_000
                )

    print(
        f"[PASS] {label} write complete"
    )


# ============================================================
# SYNC STATE
# ============================================================

def update_sync_state(
    conn,
    dataset: str,
    last_data_date: str | None,
    records_processed: int,
) -> None:
    conn.execute(
        """
        INSERT INTO sync_state (
            dataset,
            last_data_date,
            last_success_at,
            last_attempt_at,
            status,
            records_processed,
            error_message,
            updated_at
        )
        VALUES (
            ?,
            ?,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP,
            'SUCCESS',
            ?,
            NULL,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT(dataset)
        DO UPDATE SET
            last_data_date =
                excluded.last_data_date,
            last_success_at =
                CURRENT_TIMESTAMP,
            last_attempt_at =
                CURRENT_TIMESTAMP,
            status =
                'SUCCESS',
            records_processed =
                excluded.records_processed,
            error_message =
                NULL,
            updated_at =
                CURRENT_TIMESTAMP
        """,
        (
            dataset,
            last_data_date,
            records_processed,
        ),
    )


# ============================================================
# VERIFICATION
# ============================================================

def verify_institutional(
    conn,
    expected_source_rows: int,
) -> None:
    print()
    print("=" * 72)
    print("INSTITUTIONAL VERIFICATION")
    print("=" * 72)

    migrated_rows = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM institutional_daily
            WHERE source LIKE 'V1_MIGRATION|%'
            """,
        )
    )

    stored_rows = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM institutional_daily
            WHERE source LIKE 'V1_MIGRATION|%'
              AND foreign_data_status = 'STORED'
            """,
        )
    )

    insufficient_rows = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM institutional_daily
            WHERE source LIKE 'V1_MIGRATION|%'
              AND foreign_data_status =
                    'INSUFFICIENT_DATA'
            """,
        )
    )

    trust_non_null = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM institutional_daily
            WHERE source LIKE 'V1_MIGRATION|%'
              AND (
                    trust_buy IS NOT NULL
                    OR trust_sell IS NOT NULL
                    OR trust_net IS NOT NULL
              )
            """,
        )
    )

    dealer_non_null = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM institutional_daily
            WHERE source LIKE 'V1_MIGRATION|%'
              AND (
                    dealer_buy IS NOT NULL
                    OR dealer_sell IS NOT NULL
                    OR dealer_net IS NOT NULL
              )
            """,
        )
    )

    date_row = conn.execute(
        """
        SELECT
            MIN(trade_date),
            MAX(trade_date),
            COUNT(DISTINCT trade_date),
            COUNT(DISTINCT stock_id)
        FROM institutional_daily
        WHERE source LIKE 'V1_MIGRATION|%'
        """
    ).fetchone()

    print(
        f"Source Rows        : "
        f"{expected_source_rows:,}"
    )

    print(
        f"Migrated Rows      : "
        f"{migrated_rows:,}"
    )

    print(
        f"Foreign STORED     : "
        f"{stored_rows:,}"
    )

    print(
        f"Foreign INSUFFICIENT: "
        f"{insufficient_rows:,}"
    )

    print(
        f"Trust Non-NULL     : "
        f"{trust_non_null:,}"
    )

    print(
        f"Dealer Non-NULL    : "
        f"{dealer_non_null:,}"
    )

    print(
        f"Trade Dates        : "
        f"{date_row[2]:,}"
    )

    print(
        f"Stocks             : "
        f"{date_row[3]:,}"
    )

    print(
        f"Date Range         : "
        f"{date_row[0]} .. {date_row[1]}"
    )

    if migrated_rows != (
        expected_source_rows
    ):
        raise RuntimeError(
            "Institutional migrated row count mismatch"
        )

    if (
        stored_rows
        + insufficient_rows
        != migrated_rows
    ):
        raise RuntimeError(
            "Unexpected foreign_data_status found"
        )

    if trust_non_null != 0:
        raise RuntimeError(
            "V1 migration unexpectedly populated trust data"
        )

    if dealer_non_null != 0:
        raise RuntimeError(
            "V1 migration unexpectedly populated dealer data"
        )


def verify_tdcc(
    conn,
    expected_source_rows: int,
) -> None:
    print()
    print("=" * 72)
    print("TDCC SUMMARY VERIFICATION")
    print("=" * 72)

    migrated_rows = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM tdcc_summary
            WHERE source LIKE 'V1_MIGRATION|%'
            """,
        )
    )

    date_row = conn.execute(
        """
        SELECT
            MIN(data_date),
            MAX(data_date),
            COUNT(DISTINCT data_date),
            COUNT(DISTINCT stock_id)
        FROM tdcc_summary
        WHERE source LIKE 'V1_MIGRATION|%'
        """
    ).fetchone()

    change_rows = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM tdcc_summary
            WHERE source LIKE 'V1_MIGRATION|%'
              AND (
                    large_holder_change
                        IS NOT NULL
                    OR retail_holder_change
                        IS NOT NULL
              )
            """,
        )
    )

    print(
        f"Source Rows        : "
        f"{expected_source_rows:,}"
    )

    print(
        f"Migrated Rows      : "
        f"{migrated_rows:,}"
    )

    print(
        f"Data Dates         : "
        f"{date_row[2]:,}"
    )

    print(
        f"Stocks             : "
        f"{date_row[3]:,}"
    )

    print(
        f"Date Range         : "
        f"{date_row[0]} .. {date_row[1]}"
    )

    print(
        f"Rows With Change   : "
        f"{change_rows:,}"
    )

    if migrated_rows != (
        expected_source_rows
    ):
        raise RuntimeError(
            "TDCC migrated row count mismatch"
        )

    if int(
        date_row[2]
    ) != 12:
        raise RuntimeError(
            "Unexpected TDCC date count"
        )


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    print("=" * 72)
    print(
        "StockWaveScanner V2 - "
        "V1 Core Migration to Turso DEV"
    )
    print("=" * 72)
    print()

    print(
        f"V1 Database : "
        f"{V1_DB_PATH}"
    )

    print(
        "V1 Mode     : READ ONLY"
    )

    try:
        url, token = (
            load_dev_credentials()
        )

        print(
            "Target      : DEV"
        )

        print(
            f"Database    : "
            f"{mask_url(url)}"
        )

        print(
            "PROD Access : DISABLED"
        )

        v1_conn = (
            connect_v1()
        )

        turso_conn = libsql.connect(
            database=url,
            auth_token=token,
        )

        try:
            result = (
                turso_conn
                .execute(
                    "SELECT 1"
                )
                .fetchone()
            )

            if (
                not result
                or result[0] != 1
            ):
                raise RuntimeError(
                    "Turso DEV connection validation failed"
                )

            print()
            print(
                "[PASS] V1 READ ONLY connection"
            )

            print(
                "[PASS] Turso DEV connection"
            )

            try:
                turso_conn.execute(
                    "PRAGMA foreign_keys = ON"
                )
            except Exception:
                pass

            (
                institutional_count,
                tdcc_count,
            ) = preflight(
                v1_conn,
                turso_conn,
            )

            print()
            print(
                "Loading V1 Institutional ..."
            )

            institutional_rows = (
                load_institutional_rows(
                    v1_conn
                )
            )

            print(
                f"[PASS] Loaded "
                f"{len(institutional_rows):,} rows"
            )

            print()
            print(
                "Loading V1 TDCC Summary ..."
            )

            tdcc_rows = (
                load_tdcc_rows(
                    v1_conn
                )
            )

            print(
                f"[PASS] Loaded "
                f"{len(tdcc_rows):,} rows"
            )

            write_batches(
                turso_conn,
                INSTITUTIONAL_INSERT_SQL,
                institutional_rows,
                "Institutional",
            )

            write_batches(
                turso_conn,
                TDCC_INSERT_SQL,
                tdcc_rows,
                "TDCC Summary",
            )

            institutional_last_date = (
                scalar(
                    v1_conn,
                    """
                    SELECT MAX(trade_date)
                    FROM institutional_trades
                    """,
                )
            )

            tdcc_last_date = (
                scalar(
                    v1_conn,
                    """
                    SELECT MAX(data_date)
                    FROM tdcc_holdings
                    """,
                )
            )

            update_sync_state(
                turso_conn,
                "v1_institutional_migration",
                institutional_last_date,
                institutional_count,
            )

            update_sync_state(
                turso_conn,
                "v1_tdcc_summary_migration",
                tdcc_last_date,
                tdcc_count,
            )

            turso_conn.commit()

            verify_institutional(
                turso_conn,
                institutional_count,
            )

            verify_tdcc(
                turso_conn,
                tdcc_count,
            )

            print()
            print("=" * 72)
            print("SYNC STATE")
            print("=" * 72)

            sync_rows = (
                turso_conn
                .execute(
                    """
                    SELECT
                        dataset,
                        last_data_date,
                        status,
                        records_processed
                    FROM sync_state
                    WHERE dataset IN (
                        'v1_institutional_migration',
                        'v1_tdcc_summary_migration'
                    )
                    ORDER BY dataset
                    """
                )
                .fetchall()
            )

            for row in sync_rows:
                print(
                    f"{row[0]:<32} "
                    f"| date={row[1]} "
                    f"| status={row[2]} "
                    f"| rows={row[3]}"
                )

        finally:
            v1_conn.close()
            turso_conn.close()

        print()
        print("=" * 72)
        print(
            "V1 CORE MIGRATION OK"
        )
        print("=" * 72)

        print()
        print(
            "institutional_trades "
            "→ institutional_daily"
        )

        print(
            "tdcc_holdings "
            "→ tdcc_summary"
        )

        print()
        print(
            "V1 database remained READ ONLY."
        )

        print(
            "No PROD database was accessed."
        )

        return 0

    except Exception as exc:
        print()
        print("=" * 72)
        print("ERROR")
        print("=" * 72)
        print(str(exc))
        print()

        print(
            "Migration is idempotent; "
            "successfully committed batches can be safely rerun."
        )

        print(
            "V1 database remained READ ONLY."
        )

        print(
            "No PROD database was accessed."
        )

        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )