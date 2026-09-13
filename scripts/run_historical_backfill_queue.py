from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

import libsql

from backfill_quarterly_financial import (
    load_dev_credentials,
    load_universe,
    period_text,
)


# ============================================================
# CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

SLICE_SCRIPT = (
    ROOT
    / "scripts"
    / "backfill_quarterly_financial_slice.py"
)

DEFAULT_LOOKBACK_QUARTERS = 8

DEFAULT_SLICE_SIZE = 100

DEFAULT_MAX_SLICES = 4

MARKETS = (
    "TWSE",
    "TPEX",
)


# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Run a small number of historical "
            "backfill slices from newest to oldest."
        )
    )

    parser.add_argument(
        "--lookback-quarters",
        type=int,
        default=(
            DEFAULT_LOOKBACK_QUARTERS
        ),
    )

    parser.add_argument(
        "--slice-size",
        type=int,
        default=(
            DEFAULT_SLICE_SIZE
        ),
    )

    parser.add_argument(
        "--max-slices",
        type=int,
        default=(
            DEFAULT_MAX_SLICES
        ),
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
# PERIOD
# ============================================================


def previous_quarter(
    year: int,
    quarter: int,
) -> tuple[int, int]:

    if quarter > 1:

        return (
            year,
            quarter - 1,
        )

    return (
        year - 1,
        4,
    )


def build_periods(
    latest_year: int,
    latest_quarter: int,
    count: int,
) -> list[
    tuple[
        int,
        int,
    ]
]:

    periods = []

    year = (
        latest_year
    )

    quarter = (
        latest_quarter
    )

    for _ in range(
        count
    ):

        periods.append(
            (
                year,
                quarter,
            )
        )

        (
            year,
            quarter,
        ) = previous_quarter(
            year,
            quarter,
        )

    return periods


# ============================================================
# DATASET
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


def latest_general_period(
    conn,
) -> tuple[int, int]:

    row = (
        conn.execute(
            """
            SELECT

                fiscal_year,
                fiscal_quarter

            FROM quarterly_financial

            WHERE report_type =
                  'GENERAL'

            ORDER BY

                fiscal_year DESC,
                fiscal_quarter DESC

            LIMIT 1
            """
        )
        .fetchone()
    )

    if row is None:

        raise RuntimeError(
            "quarterly_financial GENERAL "
            "contains no data"
        )

    return (
        int(
            row[0]
        ),
        int(
            row[1]
        ),
    )


def load_progress(
    conn,
    dataset: str,
) -> dict[str, Any]:

    row = (
        conn.execute(
            """
            SELECT

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

        return {
            "status":
                "PENDING",

            "records_processed":
                0,

            "error_message":
                None,
        }

    return {
        "status":
            str(
                row[0]
                or
                "PENDING"
            ),

        "records_processed":
            int(
                row[1]
                or
                0
            ),

        "error_message":
            (
                None
                if row[2]
                is None
                else str(
                    row[2]
                )
            ),
    }


# ============================================================
# RUN SLICE
# ============================================================


def run_slice(
    year: int,
    quarter: int,
    market: str,
    offset: int,
    slice_size: int,
) -> int:

    command = [
        sys.executable,

        str(
            SLICE_SCRIPT
        ),

        "--year",
        str(
            year
        ),

        "--quarter",
        str(
            quarter
        ),

        "--market",
        market,

        "--offset",
        str(
            offset
        ),

        "--limit",
        str(
            slice_size
        ),
    ]

    print()

    print(
        "=" * 88
    )

    print(
        "START SLICE"
    )

    print(
        "=" * 88
    )

    print(
        "Period : "
        f"{period_text(year, quarter)}"
    )

    print(
        f"Market : {market}"
    )

    print(
        f"Offset : {offset:,}"
    )

    print(
        f"Limit  : {slice_size:,}"
    )

    print()

    result = (
        subprocess.run(
            command,
            cwd=ROOT,
            check=False,
        )
    )

    return int(
        result.returncode
    )


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    configure_console()

    args = (
        parse_args()
    )

    lookback_quarters = max(
        1,
        args.lookback_quarters,
    )

    slice_size = max(
        10,
        args.slice_size,
    )

    max_slices = max(
        1,
        args.max_slices,
    )

    print(
        "=" * 88
    )

    print(
        "StockWaveScanner V2 - "
        "Historical Backfill Queue"
    )

    print(
        "=" * 88
    )

    print(
        "Target            : DEV"
    )

    print(
        "PROD Access       : DISABLED"
    )

    print(
        "Direction         : "
        "NEWEST -> OLDEST"
    )

    print(
        f"Lookback Quarters : "
        f"{lookback_quarters}"
    )

    print(
        f"Slice Size        : "
        f"{slice_size}"
    )

    print(
        f"Max Slices / Run  : "
        f"{max_slices}"
    )

    conn = None

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

        (
            latest_year,
            latest_quarter,
        ) = latest_general_period(
            conn
        )

        periods = (
            build_periods(
                latest_year,
                latest_quarter,
                lookback_quarters,
            )
        )

        print()

        print(
            "Latest GENERAL    : "
            f"{period_text(latest_year, latest_quarter)}"
        )

        print()

        print(
            "Queue:"
        )

        for (
            index,
            (
                year,
                quarter,
            ),
        ) in enumerate(
            periods,
            start=1,
        ):

            print(
                f"  {index:02d}. "
                f"{period_text(year, quarter)}"
            )

        slices_run = 0

        for (
            year,
            quarter,
        ) in periods:

            for market in MARKETS:

                if (
                    slices_run
                    >=
                    max_slices
                ):

                    break

                dataset = (
                    dataset_name(
                        year,
                        quarter,
                        market,
                    )
                )

                progress = (
                    load_progress(
                        conn,
                        dataset,
                    )
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

                processed = int(
                    progress[
                        "records_processed"
                    ]
                    or
                    0
                )

                status = (
                    progress[
                        "status"
                    ]
                )

                print()

                print(
                    f"{period_text(year, quarter)} "
                    f"{market} "
                    f"| status={status} "
                    f"| cursor="
                    f"{processed:,}/"
                    f"{total:,}"
                )

                if (
                    status
                    ==
                    "SUCCESS"
                ):

                    continue

                if (
                    processed
                    >=
                    total
                ):

                    # The slice runner will convert
                    # this to SUCCESS.
                    offset = total

                else:

                    offset = (
                        processed
                    )

                return_code = (
                    run_slice(
                        year,
                        quarter,
                        market,
                        offset,
                        slice_size,
                    )
                )

                slices_run += 1

                if return_code != 0:

                    print()

                    print(
                        "[STOP] Slice failed."
                    )

                    print(
                        "The next scheduled run "
                        "will retry the same cursor."
                    )

                    return (
                        return_code
                    )

                # ------------------------------------------------
                # Reload progress after child process wrote state.
                # ------------------------------------------------

                progress = (
                    load_progress(
                        conn,
                        dataset,
                    )
                )

                print()

                print(
                    "[PASS] Slice finished "
                    f"| status="
                    f"{progress['status']} "
                    f"| cursor="
                    f"{progress['records_processed']:,}"
                )

            if (
                slices_run
                >=
                max_slices
            ):

                break

        print()

        print(
            "=" * 88
        )

        print(
            "QUEUE RESULT"
        )

        print(
            "=" * 88
        )

        print(
            f"Slices Run   : "
            f"{slices_run}"
        )

        print(
            "PROD Access  : DISABLED"
        )

        if slices_run == 0:

            print(
                "[PASS] Requested historical "
                "queue is already complete"
            )

        else:

            print(
                "[PASS] Daily historical "
                "backfill work completed"
            )

        return 0

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

        print()

        print(
            "No PROD database was accessed."
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