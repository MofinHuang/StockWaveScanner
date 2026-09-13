from __future__ import annotations

import argparse
import sys
import time
from typing import Any

import libsql

from backfill_quarterly_financial import (
    Company,
    FinancialRow,
    build_sql,
    fetch_batch,
    flatten,
    load_dev_credentials,
    load_universe,
    period_text,
)


# ============================================================
# CONFIG
# ============================================================

FETCH_BATCH_SIZE = 10

REPORT_TYPE = "GENERAL"


# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Process one small Quarterly Financial "
            "historical backfill slice."
        )
    )

    parser.add_argument(
        "--year",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--quarter",
        type=int,
        required=True,
        choices=(
            1,
            2,
            3,
            4,
        ),
    )

    parser.add_argument(
        "--market",
        type=str,
        required=True,
        choices=(
            "TWSE",
            "TPEX",
        ),
    )

    parser.add_argument(
        "--offset",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
    )

    return parser.parse_args()


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
# DATASET NAME
# ============================================================


def dataset_name(
    year: int,
    quarter: int,
    market: str,
) -> str:

    return (
        "qfin_hist_"
        f"{year:04d}_"
        f"q{quarter}_"
        f"{market.lower()}"
    )


# ============================================================
# DATABASE
# ============================================================


def existing_stock_ids(
    conn,
    year: int,
    quarter: int,
    stock_ids: list[str],
) -> set[str]:

    if not stock_ids:

        return set()

    placeholders = ",".join(
        "?"
        for _ in stock_ids
    )

    sql = f"""
        SELECT stock_id

        FROM quarterly_financial

        WHERE fiscal_year = ?
          AND fiscal_quarter = ?
          AND report_type = ?
          AND stock_id IN (
              {placeholders}
          )
    """

    params: tuple[Any, ...] = (
        year,
        quarter,
        REPORT_TYPE,
        *stock_ids,
    )

    rows = (
        conn.execute(
            sql,
            params,
        )
        .fetchall()
    )

    return {
        str(
            row[0]
        )

        for row
        in rows
    }


def write_rows(
    conn,
    rows: list[
        FinancialRow
    ],
) -> int:

    if not rows:

        return 0

    sql = build_sql(
        len(
            rows
        )
    )

    conn.execute(
        sql,
        flatten(
            rows
        ),
    )

    conn.commit()

    return len(
        rows
    )


# ============================================================
# SYNC STATE
# ============================================================


def load_progress(
    conn,
    dataset: str,
) -> dict[str, Any] | None:

    row = (
        conn.execute(
            """
            SELECT

                dataset,
                last_data_date,
                last_success_at,
                last_attempt_at,

                status,
                records_processed,
                error_message

            FROM sync_state

            WHERE dataset = ?
            """,
            (
                dataset,
            ),
        )
        .fetchone()
    )

    if row is None:

        return None

    return {
        "dataset":
            str(
                row[0]
            ),

        "last_data_date":
            (
                None
                if row[1]
                is None
                else str(
                    row[1]
                )
            ),

        "last_success_at":
            row[2],

        "last_attempt_at":
            row[3],

        "status":
            (
                None
                if row[4]
                is None
                else str(
                    row[4]
                )
            ),

        "records_processed":
            int(
                row[5]
                or
                0
            ),

        "error_message":
            (
                None
                if row[6]
                is None
                else str(
                    row[6]
                )
            ),
    }


def mark_attempt(
    conn,
    dataset: str,
    period: str,
    processed: int,
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

            NULL,
            CURRENT_TIMESTAMP,

            'RUNNING',
            ?,

            NULL,
            CURRENT_TIMESTAMP
        )

        ON CONFLICT(dataset)

        DO UPDATE SET

            last_data_date =
                excluded.last_data_date,

            last_attempt_at =
                CURRENT_TIMESTAMP,

            status =
                'RUNNING',

            records_processed =
                excluded.records_processed,

            error_message =
                NULL,

            updated_at =
                CURRENT_TIMESTAMP
        """,
        (
            dataset,
            period,
            processed,
        ),
    )

    conn.commit()


def mark_progress(
    conn,
    dataset: str,
    period: str,
    processed: int,
    completed: bool,
) -> None:

    status = (
        "SUCCESS"
        if completed
        else
        "PARTIAL"
    )

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
                CURRENT_TIMESTAMP,

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
            dataset,
            period,
            status,
            processed,
        ),
    )

    conn.commit()


def mark_failure(
    conn,
    dataset: str,
    period: str,
    processed: int,
    error_message: str,
) -> None:

    message = (
        error_message[
            :1500
        ]
    )

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

            NULL,
            CURRENT_TIMESTAMP,

            'FAILED',
            ?,

            ?,
            CURRENT_TIMESTAMP
        )

        ON CONFLICT(dataset)

        DO UPDATE SET

            last_data_date =
                excluded.last_data_date,

            last_attempt_at =
                CURRENT_TIMESTAMP,

            status =
                'FAILED',

            records_processed =
                excluded.records_processed,

            error_message =
                excluded.error_message,

            updated_at =
                CURRENT_TIMESTAMP
        """,
        (
            dataset,
            period,
            processed,
            message,
        ),
    )

    conn.commit()


# ============================================================
# FETCH ONE SMALL BATCH
# ============================================================


def process_company_batch(
    conn,
    companies: list[
        Company
    ],
    year: int,
    quarter: int,
) -> tuple[
    int,
    int,
]:

    stock_ids = [
        company.stock_id
        for company
        in companies
    ]

    existing = (
        existing_stock_ids(
            conn,
            year,
            quarter,
            stock_ids,
        )
    )

    missing_companies = [
        company

        for company
        in companies

        if company.stock_id
        not in existing
    ]

    if not missing_companies:

        return (
            0,
            len(
                companies
            ),
        )

    rows = (
        fetch_batch(
            missing_companies,
            year,
            quarter,
        )
    )

    written = (
        write_rows(
            conn,
            rows,
        )
    )

    return (
        written,
        len(
            companies
        ),
    )


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    configure_console()

    args = parse_args()

    year = (
        args.year
    )

    quarter = (
        args.quarter
    )

    market = (
        args.market
        .upper()
    )

    offset = max(
        0,
        args.offset,
    )

    limit = max(
        1,
        args.limit,
    )

    dataset = (
        dataset_name(
            year,
            quarter,
            market,
        )
    )

    period = (
        period_text(
            year,
            quarter,
        )
    )

    print(
        "=" * 88
    )

    print(
        "StockWaveScanner V2 - "
        "Quarterly Financial Slice Backfill"
    )

    print(
        "=" * 88
    )

    print(
        f"Target       : DEV"
    )

    print(
        f"PROD Access  : DISABLED"
    )

    print(
        f"Period       : {period}"
    )

    print(
        f"Market       : {market}"
    )

    print(
        f"Offset       : {offset:,}"
    )

    print(
        f"Limit        : {limit:,}"
    )

    print(
        f"Dataset      : {dataset}"
    )

    url = None
    token = None
    conn = None

    original_progress = offset

    started = (
        time.perf_counter()
    )

    try:

        (
            url,
            token,
        ) = load_dev_credentials()

        conn = libsql.connect(
            database=url,
            auth_token=token,
        )

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
                "Turso DEV connection failed"
            )

        print(
            "[PASS] Turso DEV connection"
        )

        universe = (
            load_universe(
                conn,
                market,
            )
        )

        total = len(
            universe
        )

        print(
            f"Universe     : {total:,}"
        )

        progress = (
            load_progress(
                conn,
                dataset,
            )
        )

        if progress:

            print(
                "Saved Status : "
                f"{progress['status']}"
            )

            print(
                "Saved Cursor : "
                f"{progress['records_processed']:,}"
            )

        if offset >= total:

            mark_progress(
                conn,
                dataset,
                period,
                total,
                True,
            )

            print()

            print(
                "[PASS] Dataset already complete"
            )

            return 0

        end_offset = min(
            total,
            offset
            +
            limit,
        )

        selected = (
            universe[
                offset:
                end_offset
            ]
        )

        if not selected:

            mark_progress(
                conn,
                dataset,
                period,
                total,
                True,
            )

            print()

            print(
                "[PASS] Nothing to process"
            )

            return 0

        print(
            "Slice        : "
            f"{offset:,}.."
            f"{end_offset - 1:,}"
        )

        print(
            "Stock Range  : "
            f"{selected[0].stock_id} "
            f".. "
            f"{selected[-1].stock_id}"
        )

        mark_attempt(
            conn,
            dataset,
            period,
            offset,
        )

        total_written = 0

        processed = offset

        slice_batches = [
            selected[
                index:
                index
                +
                FETCH_BATCH_SIZE
            ]

            for index
            in range(
                0,
                len(
                    selected
                ),
                FETCH_BATCH_SIZE,
            )
        ]

        for (
            batch_number,
            companies,
        ) in enumerate(
            slice_batches,
            start=1,
        ):

            batch_started = (
                time.perf_counter()
            )

            written, consumed = (
                process_company_batch(
                    conn,
                    companies,
                    year,
                    quarter,
                )
            )

            total_written += (
                written
            )

            processed += (
                consumed
            )

            print(
                f"  Batch "
                f"{batch_number:02d}/"
                f"{len(slice_batches):02d} "
                f"| processed="
                f"{processed:,}/"
                f"{total:,} "
                f"| written="
                f"{written:,} "
                f"| elapsed="
                f"{time.perf_counter() - batch_started:.1f}s"
            )

        completed = (
            processed
            >=
            total
        )

        mark_progress(
            conn,
            dataset,
            period,
            processed,
            completed,
        )

        print()

        print(
            "=" * 88
        )

        print(
            "SLICE RESULT"
        )

        print(
            "=" * 88
        )

        print(
            f"Period          : {period}"
        )

        print(
            f"Market          : {market}"
        )

        print(
            f"Universe        : {total:,}"
        )

        print(
            f"Slice Start     : {offset:,}"
        )

        print(
            f"Slice End       : {processed:,}"
        )

        print(
            f"Rows Written    : {total_written:,}"
        )

        print(
            f"Status          : "
            f"{'SUCCESS' if completed else 'PARTIAL'}"
        )

        print(
            f"Elapsed         : "
            f"{time.perf_counter() - started:.1f}s"
        )

        print(
            f"PROD Access     : DISABLED"
        )

        return 0

    except KeyboardInterrupt:

        print()

        print(
            "INTERRUPTED"
        )

        if conn is not None:

            try:

                mark_failure(
                    conn,
                    dataset,
                    period,
                    original_progress,
                    "Interrupted",
                )

            except Exception:
                pass

        return 130

    except Exception as exc:

        print()

        print(
            "=" * 88
        )

        print(
            "ERROR"
        )

        print(
            "=" * 88
        )

        print(
            str(
                exc
            )
        )

        if conn is not None:

            try:

                mark_failure(
                    conn,
                    dataset,
                    period,
                    original_progress,
                    str(
                        exc
                    ),
                )

            except Exception as state_exc:

                print(
                    "Unable to save failure state: "
                    f"{state_exc}"
                )

        print()

        print(
            "Previously committed batches "
            "remain in Turso DEV."
        )

        print(
            "PROD was not accessed."
        )

        return 1

    finally:

        if conn is not None:

            try:

                conn.close()

            except Exception:
                pass


if __name__ == "__main__":

    sys.exit(
        main()
    )