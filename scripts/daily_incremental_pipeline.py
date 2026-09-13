from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import libsql
from dotenv import load_dotenv


# ============================================================
# PATH / ENV
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
ENV_FILE = ROOT / ".env"

TAIPEI_TZ = timezone(
    timedelta(hours=8)
)


# ============================================================
# DAILY PIPELINE ORDER
# ============================================================
#
# 正式順序：
#
# 1. Stock Master
# 2. Market Index
# 3. Daily Price
# 4. Institutional
#
# 原則：
#
# - 任一步 ERROR -> 後續全部停止
# - 不回跑 Historical Backfill
# - 不碰 PROD
# - Child process 固定使用目前這支程式的 Python
#   也就是 .venv\Scripts\python.exe
#
# ============================================================


@dataclass(frozen=True)
class PipelineStage:
    name: str
    script: str
    use_through: bool


STAGES = (
    PipelineStage(
        name="Stock Master",
        script="sync_stock_master.py",
        use_through=False,
    ),
    PipelineStage(
        name="Market Index",
        script="sync_market_index_incremental.py",
        use_through=True,
    ),
    PipelineStage(
        name="Daily Price",
        script="sync_daily_price_incremental.py",
        use_through=True,
    ),
    PipelineStage(
        name="Institutional",
        script="sync_institutional_incremental.py",
        use_through=True,
    ),
)


# ============================================================
# EXPECTED SYNC STATE
# ============================================================

EXPECTED_DATASETS = (
    "stock_master_twse",
    "stock_master_tpex",

    "market_index_twse",
    "market_index_tpex",

    "stock_price_twse",
    "stock_price_tpex",

    "institutional_twse",
    "institutional_tpex",
)


# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Run StockWaveScanner V2 "
            "Daily Incremental Pipeline."
        )
    )

    parser.add_argument(
        "--through",
        metavar="YYYY-MM-DD",
        help=(
            "Process data through this Taiwan date. "
            "Default: today UTC+8."
        ),
    )

    parser.add_argument(
        "--skip-stock-master",
        action="store_true",
        help=(
            "Skip Stock Master refresh. "
            "Intended only for manual retry/debug."
        ),
    )

    return parser.parse_args()


# ============================================================
# DATE
# ============================================================


def taipei_today() -> date:

    return datetime.now(
        TAIPEI_TZ
    ).date()


def parse_iso_date(
    value: str,
) -> date:

    try:

        return date.fromisoformat(
            value
        )

    except ValueError as exc:

        raise RuntimeError(
            f"Invalid date '{value}'. "
            "Expected YYYY-MM-DD."
        ) from exc


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
            "TURSO_DEV_DATABASE_URL "
            "is missing from .env"
        )

    if not token:

        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN "
            "is missing from .env"
        )

    lower_url = (
        url.lower()
    )

    if (
        "stockwave-dev"
        not in lower_url
    ):

        raise RuntimeError(
            "SAFETY STOP: "
            "TURSO_DEV_DATABASE_URL "
            "does not point to stockwave-dev"
        )

    if (
        "stockwave-prod"
        in lower_url
    ):

        raise RuntimeError(
            "SAFETY STOP: "
            "PROD database detected"
        )

    return (
        url,
        token,
    )


def mask_url(
    url: str,
) -> str:

    if "://" not in url:

        return "***"

    scheme, rest = (
        url.split(
            "://",
            1,
        )
    )

    return (
        f"{scheme}://{rest}"
    )


# ============================================================
# SCRIPT VALIDATION
# ============================================================


def validate_scripts() -> None:

    missing: list[str] = []

    for stage in STAGES:

        script_path = (
            SCRIPTS_DIR
            / stage.script
        )

        if not script_path.exists():

            missing.append(
                str(
                    script_path
                )
            )

    if missing:

        raise RuntimeError(
            "Required Daily Pipeline "
            "scripts are missing:\n"
            + "\n".join(
                missing
            )
        )


# ============================================================
# RUN CHILD SCRIPT
# ============================================================


def run_stage(
    stage: PipelineStage,
    through: date,
) -> float:

    script_path = (
        SCRIPTS_DIR
        / stage.script
    )

    command = [
        sys.executable,
        "-u",
        str(
            script_path
        ),
    ]

    if stage.use_through:

        command.extend(
            [
                "--through",
                through.isoformat(),
            ]
        )

    print()
    print(
        "=" * 80
    )

    print(
        f"START | {stage.name}"
    )

    print(
        "=" * 80
    )

    print(
        "Python : "
        f"{sys.executable}"
    )

    print(
        "Script : "
        f"{stage.script}"
    )

    if stage.use_through:

        print(
            "Through: "
            f"{through.isoformat()}"
        )

    print()

    started = time.perf_counter()

    env = os.environ.copy()

    env[
        "PYTHONUNBUFFERED"
    ] = "1"

    result = subprocess.run(
        command,
        cwd=str(
            ROOT
        ),
        env=env,
        check=False,
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    print()

    if result.returncode != 0:

        print(
            "=" * 80
        )

        print(
            f"FAILED | {stage.name}"
        )

        print(
            "=" * 80
        )

        print(
            f"Exit Code : "
            f"{result.returncode}"
        )

        print(
            f"Elapsed   : "
            f"{elapsed:.1f}s"
        )

        raise RuntimeError(
            f"{stage.name} failed "
            f"with exit code "
            f"{result.returncode}"
        )

    print(
        "=" * 80
    )

    print(
        f"PASS | {stage.name}"
    )

    print(
        "=" * 80
    )

    print(
        f"Elapsed : "
        f"{elapsed:.1f}s"
    )

    return elapsed


# ============================================================
# FINAL DEV HEALTH CHECK
# ============================================================


def verify_dev_state(
    url: str,
    token: str,
) -> None:

    print()
    print(
        "=" * 80
    )

    print(
        "FINAL DEV DATA STATE"
    )

    print(
        "=" * 80
    )

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
                "Final Turso DEV "
                "connection check failed"
            )

        rows = (
            conn.execute(
                """
                SELECT
                    dataset,
                    last_data_date,
                    status,
                    records_processed,
                    error_message

                FROM sync_state

                WHERE dataset IN (
                    'stock_master_twse',
                    'stock_master_tpex',

                    'market_index_twse',
                    'market_index_tpex',

                    'stock_price_twse',
                    'stock_price_tpex',

                    'institutional_twse',
                    'institutional_tpex'
                )

                ORDER BY
                    CASE dataset

                        WHEN 'stock_master_twse'
                            THEN 1

                        WHEN 'stock_master_tpex'
                            THEN 2

                        WHEN 'market_index_twse'
                            THEN 3

                        WHEN 'market_index_tpex'
                            THEN 4

                        WHEN 'stock_price_twse'
                            THEN 5

                        WHEN 'stock_price_tpex'
                            THEN 6

                        WHEN 'institutional_twse'
                            THEN 7

                        WHEN 'institutional_tpex'
                            THEN 8

                        ELSE 99
                    END
                """
            )
            .fetchall()
        )

        state = {
            str(
                row[0]
            ): row

            for row in rows
        }

        missing = [
            dataset

            for dataset
            in EXPECTED_DATASETS

            if dataset
            not in state
        ]

        if missing:

            raise RuntimeError(
                "Missing sync_state datasets: "
                + ", ".join(
                    missing
                )
            )

        failed: list[str] = []

        for dataset in EXPECTED_DATASETS:

            row = state[
                dataset
            ]

            data_date = (
                str(
                    row[1]
                )
                if row[1]
                is not None

                else "NULL"
            )

            status = (
                str(
                    row[2]
                )
            )

            records = (
                int(
                    row[3] or 0
                )
            )

            print(
                f"{dataset:<24} "
                f"| date="
                f"{data_date:<10} "
                f"| status="
                f"{status:<8} "
                f"| rows="
                f"{records:,}"
            )

            if status != "SUCCESS":

                failed.append(
                    (
                        f"{dataset}"
                        f"={status}"
                    )
                )

        if failed:

            raise RuntimeError(
                "Daily Pipeline has "
                "non-SUCCESS sync_state: "
                + ", ".join(
                    failed
                )
            )

        print()

        active_rows = (
            conn.execute(
                """
                SELECT
                    market,
                    COUNT(*)

                FROM stock_master

                WHERE is_active = 1
                  AND security_type =
                      'COMMON_STOCK'

                GROUP BY market

                ORDER BY market
                """
            )
            .fetchall()
        )

        print(
            "Active COMMON_STOCK:"
        )

        for row in active_rows:

            print(
                f"  {row[0]:<4} : "
                f"{int(row[1]):,}"
            )

        print()

        print(
            "[PASS] All Daily datasets "
            "have SUCCESS sync_state"
        )

        print(
            "[PASS] Final Turso DEV "
            "health check"
        )

    finally:

        conn.close()


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    args = parse_args()

    print(
        "=" * 80
    )

    print(
        "StockWaveScanner V2"
    )

    print(
        "DAILY INCREMENTAL PIPELINE"
    )

    print(
        "=" * 80
    )

    try:

        url, token = (
            load_dev_credentials()
        )

        validate_scripts()

        through = (
            parse_iso_date(
                args.through
            )

            if args.through

            else taipei_today()
        )

        today = (
            taipei_today()
        )

        if through > today:

            raise RuntimeError(
                "Through date cannot be "
                "later than today in Taiwan"
            )

        print(
            "Target      : DEV"
        )

        print(
            "Database    : "
            f"{mask_url(url)}"
        )

        print(
            "Through Date: "
            f"{through.isoformat()}"
        )

        print(
            "Python      : "
            f"{sys.executable}"
        )

        print(
            "PROD Access : DISABLED"
        )

        print()

        print(
            "Pipeline:"
        )

        stage_number = 0

        for stage in STAGES:

            if (
                stage.name
                == "Stock Master"

                and

                args.skip_stock_master
            ):

                print(
                    "  SKIP Stock Master"
                )

                continue

            stage_number += 1

            print(
                f"  {stage_number}. "
                f"{stage.name}"
            )

        pipeline_started = (
            time.perf_counter()
        )

        elapsed_by_stage: list[
            tuple[
                str,
                float,
            ]
        ] = []

        for stage in STAGES:

            if (
                stage.name
                == "Stock Master"

                and

                args.skip_stock_master
            ):

                continue

            elapsed = run_stage(
                stage,
                through,
            )

            elapsed_by_stage.append(
                (
                    stage.name,
                    elapsed,
                )
            )

        verify_dev_state(
            url,
            token,
        )

        total_elapsed = (
            time.perf_counter()
            - pipeline_started
        )

        print()
        print(
            "=" * 80
        )

        print(
            "DAILY PIPELINE SUMMARY"
        )

        print(
            "=" * 80
        )

        for name, elapsed in (
            elapsed_by_stage
        ):

            print(
                f"[PASS] "
                f"{name:<18} "
                f"{elapsed:>7.1f}s"
            )

        print()

        print(
            "Total Elapsed : "
            f"{total_elapsed:.1f}s"
        )

        print(
            "Through Date  : "
            f"{through.isoformat()}"
        )

        print(
            "Target        : DEV"
        )

        print(
            "PROD Access   : DISABLED"
        )

        print()
        print(
            "=" * 80
        )

        print(
            "DAILY INCREMENTAL PIPELINE OK"
        )

        print(
            "=" * 80
        )

        return 0

    except KeyboardInterrupt:

        print()
        print(
            "=" * 80
        )

        print(
            "PIPELINE INTERRUPTED"
        )

        print(
            "=" * 80
        )

        print(
            "No PROD database "
            "was accessed."
        )

        return 130

    except Exception as exc:

        print()
        print(
            "=" * 80
        )

        print(
            "DAILY PIPELINE ERROR"
        )

        print(
            "=" * 80
        )

        print(
            str(
                exc
            )
        )

        print()

        print(
            "Remaining stages "
            "were NOT executed."
        )

        print(
            "No PROD database "
            "was accessed."
        )

        return 1


if __name__ == "__main__":

    sys.exit(
        main()
    )