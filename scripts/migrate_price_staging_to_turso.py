from __future__ import annotations

import os
import sqlite3
import sys
import time
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


DATASET_NAME = (
    "historical_price_migration"
)

SQL_ROWS_PER_STATEMENT = 100


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


# ============================================================
# DEV SAFETY
# ============================================================

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
            "TURSO_DEV_DATABASE_URL "
            "is missing from .env"
        )

    if not token:
        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN "
            "is missing from .env"
        )

    lower_url = url.lower()

    if "stockwave-dev" not in lower_url:
        raise RuntimeError(
            "SAFETY STOP: "
            "DEV URL does not point "
            "to stockwave-dev"
        )

    if "stockwave-prod" in lower_url:
        raise RuntimeError(
            "SAFETY STOP: "
            "PROD database detected"
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
# STAGING
# ============================================================

def connect_staging() -> sqlite3.Connection:
    if not STAGING_DB.exists():
        raise RuntimeError(
            f"Staging DB not found: "
            f"{STAGING_DB}"
        )

    uri = (
        STAGING_DB.resolve().as_uri()
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

    return conn


def excluded_placeholders() -> str:
    return ",".join(
        "?"
        for _ in EXCLUDED_ETF_IDS
    )


def excluded_params() -> tuple[str, ...]:
    return tuple(
        sorted(
            EXCLUDED_ETF_IDS
        )
    )


def get_trade_dates(
    conn: sqlite3.Connection,
) -> list[str]:
    rows = conn.execute(
        f"""
        SELECT DISTINCT trade_date
        FROM price_staging
        WHERE stock_id NOT IN (
            {excluded_placeholders()}
        )
        ORDER BY trade_date
        """,
        excluded_params(),
    ).fetchall()

    return [
        str(row[0])
        for row in rows
    ]


def get_staging_summary(
    conn: sqlite3.Connection,
) -> tuple[int, int, str, str]:
    row = conn.execute(
        f"""
        SELECT
            COUNT(*),
            COUNT(DISTINCT stock_id),
            MIN(trade_date),
            MAX(trade_date)
        FROM price_staging
        WHERE stock_id NOT IN (
            {excluded_placeholders()}
        )
        """,
        excluded_params(),
    ).fetchone()

    return (
        int(row[0]),
        int(row[1]),
        str(row[2]),
        str(row[3]),
    )


def get_day_rows(
    conn: sqlite3.Connection,
    trade_date: str,
) -> list[tuple[Any, ...]]:
    rows = conn.execute(
        f"""
        SELECT
            stock_id,
            trade_date,

            open,
            high,
            low,
            close,

            volume,
            turnover,
            trade_count,

            source
        FROM price_staging
        WHERE trade_date = ?
          AND stock_id NOT IN (
              {excluded_placeholders()}
          )
        ORDER BY
            market,
            stock_id
        """,
        (
            trade_date,
            *excluded_params(),
        ),
    ).fetchall()

    return [
        tuple(row)
        for row in rows
    ]


# ============================================================
# TURSO HELPERS
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


def get_master_ids(
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


# ============================================================
# HISTORICAL STOCK MASTER
# ============================================================

def seed_historical_stock_master(
    conn,
) -> None:
    current_ids = (
        get_master_ids(conn)
    )

    missing = [
        stock_id
        for stock_id
        in sorted(
            HISTORICAL_COMMON_STOCKS
        )
        if stock_id
        not in current_ids
    ]

    print()
    print("=" * 76)
    print(
        "HISTORICAL STOCK MASTER"
    )
    print("=" * 76)

    if not missing:
        print(
            "[PASS] Historical Stock Master "
            "already complete"
        )
        return

    for stock_id in missing:
        meta = (
            HISTORICAL_COMMON_STOCKS[
                stock_id
            ]
        )

        conn.execute(
            """
            INSERT INTO stock_master (
                stock_id,
                stock_name,
                short_name,
                market,
                security_type,

                industry_code,
                industry_name,

                listed_date,
                issued_common_shares,
                source_date,

                is_active,

                created_at,
                updated_at
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                'COMMON_STOCK',

                NULL,
                NULL,

                NULL,
                NULL,
                NULL,

                0,

                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(stock_id)
            DO NOTHING
            """,
            (
                stock_id,
                meta["name"],
                meta["name"],
                meta["market"],
            ),
        )

        print(
            f"  {stock_id} "
            f"{meta['name']} "
            f"| {meta['market']} "
            f"| active=0"
        )

    conn.commit()

    print(
        f"[PASS] Seeded "
        f"{len(missing)} "
        f"historical stock(s)"
    )


def verify_master_compatibility(
    staging: sqlite3.Connection,
    turso,
) -> None:
    source_rows = staging.execute(
        f"""
        SELECT DISTINCT stock_id
        FROM price_staging
        WHERE stock_id NOT IN (
            {excluded_placeholders()}
        )
        """
        ,
        excluded_params(),
    ).fetchall()

    source_ids = {
        str(row[0]).strip()
        for row in source_rows
    }

    target_ids = (
        get_master_ids(turso)
    )

    missing = sorted(
        source_ids
        - target_ids
    )

    print()
    print(
        f"Eligible Securities : "
        f"{len(source_ids):,}"
    )

    print(
        f"Turso Stock Master  : "
        f"{len(target_ids):,}"
    )

    print(
        f"Missing FK IDs      : "
        f"{len(missing):,}"
    )

    if missing:
        for stock_id in missing[:30]:
            print(
                f"  {stock_id}"
            )

        raise RuntimeError(
            "Price migration stopped: "
            "eligible securities missing "
            "from stock_master"
        )

    print(
        "[PASS] Foreign key compatibility"
    )


# ============================================================
# RESUME STATE
# ============================================================

def get_resume_state(
    conn,
) -> tuple[str | None, int]:
    row = conn.execute(
        """
        SELECT
            last_data_date,
            records_processed
        FROM sync_state
        WHERE dataset = ?
        """,
        (DATASET_NAME,),
    ).fetchone()

    if not row:
        return None, 0

    last_date = (
        str(row[0])
        if row[0] is not None
        else None
    )

    records_processed = (
        int(row[1])
        if row[1] is not None
        else 0
    )

    return (
        last_date,
        records_processed,
    )


def update_sync_state(
    conn,
    last_data_date: str,
    records_processed: int,
    status: str,
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

            ?,

            ?,
            NULL,

            CURRENT_TIMESTAMP
        )
        ON CONFLICT(dataset)
        DO UPDATE SET
            last_data_date =
                excluded.last_data_date,

            last_success_at =
                CASE
                    WHEN excluded.status =
                         'SUCCESS'
                    THEN CURRENT_TIMESTAMP
                    ELSE sync_state.last_success_at
                END,

            last_attempt_at =
                CURRENT_TIMESTAMP,

            status =
                excluded.status,

            records_processed =
                excluded.records_processed,

            error_message =
                NULL,

            updated_at =
                CURRENT_TIMESTAMP
        """,
        (
            DATASET_NAME,
            last_data_date,
            status,
            records_processed,
        ),
    )


# ============================================================
# FAST MULTI-ROW INSERT
# ============================================================

PRICE_PREFIX_SQL = """
INSERT INTO stock_price_daily (
    stock_id,
    trade_date,

    open,
    high,
    low,
    close,

    volume,
    turnover,
    trade_count,

    source,

    created_at,
    updated_at
)
VALUES
"""


PRICE_VALUE_SQL = """
(
    ?, ?,
    ?, ?, ?, ?,
    ?, ?, ?,
    ?,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
"""


PRICE_SUFFIX_SQL = """
ON CONFLICT(
    stock_id,
    trade_date
)
DO NOTHING
"""


def flatten(
    rows: list[tuple[Any, ...]],
) -> tuple[Any, ...]:
    values: list[Any] = []

    for row in rows:
        values.extend(
            row
        )

    return tuple(values)


def build_insert_sql(
    row_count: int,
) -> str:
    values_sql = ",\n".join(
        PRICE_VALUE_SQL
        for _ in range(
            row_count
        )
    )

    return (
        PRICE_PREFIX_SQL
        + "\n"
        + values_sql
        + "\n"
        + PRICE_SUFFIX_SQL
    )


def write_trade_date(
    conn,
    rows: list[tuple[Any, ...]],
    trade_date: str,
    cumulative_rows: int,
    final_date: bool,
) -> int:
    if not rows:
        return cumulative_rows

    try:
        conn.execute(
            "BEGIN"
        )

        for start in range(
            0,
            len(rows),
            SQL_ROWS_PER_STATEMENT,
        ):
            batch = rows[
                start:
                start
                + SQL_ROWS_PER_STATEMENT
            ]

            sql = build_insert_sql(
                len(batch)
            )

            conn.execute(
                sql,
                flatten(batch),
            )

        new_cumulative = (
            cumulative_rows
            + len(rows)
        )

        status = (
            "SUCCESS"
            if final_date
            else "RUNNING"
        )

        update_sync_state(
            conn,
            trade_date,
            new_cumulative,
            status,
        )

        conn.commit()

        return new_cumulative

    except BaseException:
        try:
            conn.rollback()
        except Exception:
            pass

        raise


# ============================================================
# VERIFICATION
# ============================================================

def verify_historical_master(
    conn,
) -> None:
    print()
    print("=" * 76)
    print(
        "HISTORICAL MASTER VERIFICATION"
    )
    print("=" * 76)

    for stock_id in sorted(
        HISTORICAL_COMMON_STOCKS
    ):
        row = conn.execute(
            """
            SELECT
                stock_name,
                market,
                security_type,
                is_active
            FROM stock_master
            WHERE stock_id = ?
            """,
            (stock_id,),
        ).fetchone()

        if row is None:
            raise RuntimeError(
                "Historical stock missing: "
                f"{stock_id}"
            )

        if str(row[2]) != (
            "COMMON_STOCK"
        ):
            raise RuntimeError(
                "Unexpected security type: "
                f"{stock_id}"
            )

        if int(row[3]) != 0:
            raise RuntimeError(
                "Historical stock "
                "unexpectedly active: "
                f"{stock_id}"
            )

        print(
            f"[PASS] {stock_id} "
            f"{row[0]} "
            f"| {row[1]} "
            f"| active={row[3]}"
        )


def verify_price(
    conn,
    expected_rows: int,
    expected_dates: int,
    expected_min_date: str,
    expected_max_date: str,
) -> None:
    print()
    print("=" * 76)
    print(
        "PRICE MIGRATION VERIFICATION"
    )
    print("=" * 76)

    row = conn.execute(
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT stock_id),
            COUNT(DISTINCT trade_date),
            MIN(trade_date),
            MAX(trade_date)
        FROM stock_price_daily
        WHERE source IN (
            'TWSE_MI_INDEX',
            'TPEX_DAILY_CLOSE'
        )
        """
    ).fetchone()

    migrated_rows = int(
        row[0]
    )

    securities = int(
        row[1]
    )

    trade_dates = int(
        row[2]
    )

    min_date = row[3]
    max_date = row[4]

    print(
        f"Expected Rows : "
        f"{expected_rows:,}"
    )

    print(
        f"Migrated Rows : "
        f"{migrated_rows:,}"
    )

    print(
        f"Securities    : "
        f"{securities:,}"
    )

    print(
        f"Trade Dates   : "
        f"{trade_dates:,}"
    )

    print(
        f"Date Range    : "
        f"{min_date} .. "
        f"{max_date}"
    )

    if migrated_rows != (
        expected_rows
    ):
        raise RuntimeError(
            "Historical price row "
            "count mismatch"
        )

    if trade_dates != (
        expected_dates
    ):
        raise RuntimeError(
            "Historical price trade-date "
            "count mismatch"
        )

    if (
        min_date != expected_min_date
        or max_date
        != expected_max_date
    ):
        raise RuntimeError(
            "Historical price "
            "date range mismatch"
        )

    placeholders = ",".join(
        "?"
        for _ in EXCLUDED_ETF_IDS
    )

    excluded_count = int(
        scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM stock_price_daily
            WHERE stock_id IN (
                {placeholders}
            )
            """,
            tuple(
                sorted(
                    EXCLUDED_ETF_IDS
                )
            ),
        )
    )

    print(
        f"ETF Rows      : "
        f"{excluded_count:,}"
    )

    if excluded_count != 0:
        raise RuntimeError(
            "ETF rows found in "
            "stock_price_daily"
        )

    warmup_ready = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    p.stock_id
                FROM stock_price_daily p
                INNER JOIN stock_master s
                    ON s.stock_id =
                       p.stock_id
                WHERE s.is_active = 1
                  AND p.source IN (
                      'TWSE_MI_INDEX',
                      'TPEX_DAILY_CLOSE'
                  )
                GROUP BY
                    p.stock_id
                HAVING COUNT(*) >= 120
            )
            """,
        )
    )

    print(
        f"Active >=120 : "
        f"{warmup_ready:,}"
    )

    if warmup_ready != 1944:
        raise RuntimeError(
            "Unexpected active >=120 "
            "coverage count"
        )

    invalid_ohlc = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM stock_price_daily
            WHERE source IN (
                'TWSE_MI_INDEX',
                'TPEX_DAILY_CLOSE'
            )
              AND (
                    close IS NULL
                    OR close <= 0
                    OR high IS NULL
                    OR low IS NULL
                    OR open IS NULL
                    OR high < low
                    OR high < open
                    OR high < close
                    OR low > open
                    OR low > close
              )
            """,
        )
    )

    print(
        f"Invalid OHLC : "
        f"{invalid_ohlc:,}"
    )

    if invalid_ohlc != 0:
        raise RuntimeError(
            "Invalid OHLC detected "
            "after migration"
        )

    print()
    print(
        "[PASS] Historical price "
        "migration verified"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    print("=" * 76)
    print(
        "StockWaveScanner V2 - "
        "Historical Price Migration "
        "to Turso DEV"
    )
    print("=" * 76)
    print()

    print(
        f"Staging DB  : "
        f"{STAGING_DB}"
    )

    print(
        "Staging Mode: READ ONLY"
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

        staging = (
            connect_staging()
        )

        turso = libsql.connect(
            database=url,
            auth_token=token,
        )

        started = time.time()

        try:
            test = turso.execute(
                "SELECT 1"
            ).fetchone()

            if (
                not test
                or test[0] != 1
            ):
                raise RuntimeError(
                    "Turso DEV connection "
                    "validation failed"
                )

            print()
            print(
                "[PASS] Staging READ ONLY connection"
            )

            print(
                "[PASS] Turso DEV connection"
            )

            (
                expected_rows,
                expected_securities,
                expected_min_date,
                expected_max_date,
            ) = get_staging_summary(
                staging
            )

            trade_dates = (
                get_trade_dates(
                    staging
                )
            )

            print()
            print("=" * 76)
            print("PREFLIGHT")
            print("=" * 76)

            print(
                f"Eligible Rows       : "
                f"{expected_rows:,}"
            )

            print(
                f"Eligible Securities : "
                f"{expected_securities:,}"
            )

            print(
                f"Trade Dates         : "
                f"{len(trade_dates):,}"
            )

            print(
                f"Date Range          : "
                f"{expected_min_date} "
                f".. {expected_max_date}"
            )

            if expected_rows != 934366:
                raise RuntimeError(
                    "Unexpected staging "
                    "eligible row count"
                )

            if len(trade_dates) != 493:
                raise RuntimeError(
                    "Unexpected staging "
                    "trade-date count"
                )

            seed_historical_stock_master(
                turso
            )

            verify_master_compatibility(
                staging,
                turso,
            )

            (
                last_completed_date,
                cumulative_rows,
            ) = get_resume_state(
                turso
            )

            pending_dates = [
                trade_date
                for trade_date
                in trade_dates
                if (
                    last_completed_date
                    is None
                    or trade_date
                    > last_completed_date
                )
            ]

            print()
            print("=" * 76)
            print("RESUME STATE")
            print("=" * 76)

            print(
                f"Last Completed Date : "
                f"{last_completed_date}"
            )

            print(
                f"Committed Rows      : "
                f"{cumulative_rows:,}"
            )

            print(
                f"Remaining Dates     : "
                f"{len(pending_dates):,}"
            )

            if pending_dates:
                print(
                    f"Next Date           : "
                    f"{pending_dates[0]}"
                )

            if not pending_dates:
                print()
                print(
                    "[PASS] No pending "
                    "trade dates"
                )

            else:
                print()
                print("=" * 76)
                print("PRICE MIGRATION")
                print("=" * 76)

                total_pending = len(
                    pending_dates
                )

                for index, trade_date in enumerate(
                    pending_dates,
                    start=1,
                ):
                    rows = get_day_rows(
                        staging,
                        trade_date,
                    )

                    final_date = (
                        trade_date
                        == trade_dates[-1]
                    )

                    cumulative_rows = (
                        write_trade_date(
                            turso,
                            rows,
                            trade_date,
                            cumulative_rows,
                            final_date,
                        )
                    )

                    if (
                        index == 1
                        or index % 10 == 0
                        or index
                        == total_pending
                    ):
                        elapsed = (
                            time.time()
                            - started
                        )

                        rate = (
                            cumulative_rows
                            / elapsed
                            if elapsed > 0
                            else 0
                        )

                        percent = (
                            cumulative_rows
                            / expected_rows
                            * 100
                        )

                        print(
                            f"  Dates "
                            f"{index:,}/"
                            f"{total_pending:,}"
                            f" | {trade_date}"
                            f" | committed="
                            f"{cumulative_rows:,}"
                            f" | {percent:.2f}%"
                            f" | rate="
                            f"{rate:,.0f} rows/s"
                        )

            verify_historical_master(
                turso
            )

            verify_price(
                turso,
                expected_rows,
                len(trade_dates),
                expected_min_date,
                expected_max_date,
            )

            sync_row = turso.execute(
                """
                SELECT
                    last_data_date,
                    status,
                    records_processed
                FROM sync_state
                WHERE dataset = ?
                """,
                (DATASET_NAME,),
            ).fetchone()

            print()
            print("=" * 76)
            print("SYNC STATE")
            print("=" * 76)

            print(
                f"Dataset           : "
                f"{DATASET_NAME}"
            )

            print(
                f"Last Data Date    : "
                f"{sync_row[0]}"
            )

            print(
                f"Status            : "
                f"{sync_row[1]}"
            )

            print(
                f"Records Processed : "
                f"{int(sync_row[2]):,}"
            )

            total_seconds = (
                time.time()
                - started
            )

            print()
            print(
                f"Elapsed Seconds   : "
                f"{total_seconds:,.1f}"
            )

        finally:
            staging.close()
            turso.close()

        print()
        print("=" * 76)
        print(
            "HISTORICAL PRICE MIGRATION OK"
        )
        print("=" * 76)
        print()

        print(
            "934,366 eligible historical "
            "price rows are stored in Turso DEV."
        )

        print(
            "ETF securities were excluded."
        )

        print(
            "Historical delisted stocks "
            "were retained as inactive."
        )

        print(
            "Staging database remained READ ONLY."
        )

        print(
            "No PROD database was accessed."
        )

        return 0

    except KeyboardInterrupt:
        print()
        print()
        print("=" * 76)
        print(
            "MIGRATION INTERRUPTED"
        )
        print("=" * 76)

        print(
            "The current trade date was rolled back."
        )

        print(
            "Completed trade dates remain committed."
        )

        print(
            "Run the same command again to resume."
        )

        print(
            "No PROD database was accessed."
        )

        return 130

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
            "Completed trade dates remain committed."
        )

        print(
            "Run the same command again after "
            "the error is resolved."
        )

        print(
            "No PROD database was accessed."
        )

        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )