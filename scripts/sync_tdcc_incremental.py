from __future__ import annotations

import argparse
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

TDCC_OPENAPI_URL = (
    "https://openapi.tdcc.com.tw/v1/opendata/1-5"
)

TDCC_CSV_URL = (
    "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5"
)

TIMEOUT = 60

RETRY_DELAYS = (
    0,
    3,
    10,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36 "
    "StockWaveScanner-V2-TDCC/1.0"
)

MIN_RAW_ROWS = 50_000
MIN_COVERAGE = 0.90

DIST_BATCH = 120
SUMMARY_BATCH = 100

SYNC_DATASET = "tdcc_weekly"


# ============================================================
# TDCC LEVEL DEFINITION
# ============================================================
#
# 1  = 1 ~ 999 shares
# 2  = 1,000 ~ 5,000
# 3  = 5,001 ~ 10,000
#
# 12 = 400,001 ~ 600,000
# 13 = 600,001 ~ 800,000
# 14 = 800,001 ~ 1,000,000
# 15 = 1,000,001+
#
# 16 = adjustment
# 17 = total
#
# V2 Summary:
#
# large_holder_pct
#     400 lots+
#     level 12 ~ 15
#
# retail_holder_pct
#     <= 10 lots
#     level 1 ~ 3
# ============================================================

LARGE_LEVELS = {
    12,
    13,
    14,
    15,
}

RETAIL_LEVELS = {
    1,
    2,
    3,
}

REQUIRED_LEVELS = (
    LARGE_LEVELS
    | RETAIL_LEVELS
    | {17}
)


@dataclass(frozen=True)
class TdccRow:

    stock_id: str
    data_date: str

    holder_level: int

    holder_count: int | None
    shares: int | None
    percentage: float | None

    source: str

    def values(
        self,
    ) -> tuple[Any, ...]:

        return (
            self.stock_id,
            self.data_date,

            str(
                self.holder_level
            ),

            self.holder_count,
            self.shares,
            self.percentage,

            self.source,
        )


@dataclass(frozen=True)
class SummaryRow:

    stock_id: str
    data_date: str

    large_holder_pct: float
    retail_holder_pct: float

    large_holder_change: float | None
    retail_holder_change: float | None

    source: str

    def values(
        self,
    ) -> tuple[Any, ...]:

        return (
            self.stock_id,
            self.data_date,

            self.large_holder_pct,
            self.retail_holder_pct,

            self.large_holder_change,
            self.retail_holder_change,

            self.source,
        )


# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Sync latest official TDCC weekly "
            "snapshot to Turso DEV."
        )
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help=(
            "Fetch and validate only. "
            "Do not write Turso."
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

    if (
        not url
        or
        not token
    ):

        raise RuntimeError(
            "TURSO_DEV_DATABASE_URL / "
            "TURSO_DEV_AUTH_TOKEN missing"
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
            "only stockwave-dev is allowed"
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


# ============================================================
# HTTP
# ============================================================


def fetch_urllib(
    url: str,
) -> bytes:

    request = (
        urllib.request.Request(
            url,

            headers={
                "User-Agent":
                    USER_AGENT,

                "Accept":
                    "application/json,"
                    "text/csv,"
                    "text/plain,*/*",

                "Cache-Control":
                    "no-cache",
            },
        )
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT,
    ) as response:

        data = (
            response.read()
        )

    if not data:

        raise RuntimeError(
            "empty HTTP response"
        )

    return data


def fetch_curl(
    url: str,
) -> bytes:

    curl = (
        shutil.which(
            "curl.exe"
        )
        or
        shutil.which(
            "curl"
        )
    )

    if not curl:

        raise RuntimeError(
            "curl not found"
        )

    result = (
        subprocess.run(
            [
                curl,

                "--location",
                "--http1.1",
                "--fail",

                "--connect-timeout",
                "15",

                "--max-time",
                str(
                    TIMEOUT
                ),

                "-A",
                USER_AGENT,

                "-sS",

                url,
            ],

            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,

            check=False,
        )
    )

    if (
        result.returncode
        != 0
    ):

        raise RuntimeError(
            result.stderr
            .decode(
                "utf-8",
                errors="replace",
            )
            .strip()
        )

    if not result.stdout:

        raise RuntimeError(
            "empty curl response"
        )

    return result.stdout


def fetch(
    url: str,
    prefer_curl: bool = False,
) -> bytes:

    loaders = (
        (
            fetch_curl,
            fetch_urllib,
        )
        if prefer_curl
        else
        (
            fetch_urllib,
            fetch_curl,
        )
    )

    errors: list[str] = []

    for (
        attempt,
        delay,
    ) in enumerate(
        RETRY_DELAYS,
        start=1,
    ):

        if delay:

            time.sleep(
                delay
            )

        for loader in loaders:

            try:

                return loader(
                    url
                )

            except Exception as exc:

                errors.append(
                    f"attempt={attempt} "
                    f"{loader.__name__}: "
                    f"{exc}"
                )

        if (
            attempt
            <
            len(
                RETRY_DELAYS
            )
        ):

            print(
                "    retrying HTTP "
                f"({attempt}/"
                f"{len(RETRY_DELAYS)}) ..."
            )

    raise RuntimeError(
        " | ".join(
            errors[-6:]
        )
    )


# ============================================================
# VALUE HELPERS
# ============================================================


def decode_text(
    data: bytes,
) -> str:

    for encoding in (
        "utf-8-sig",
        "utf-8",
        "cp950",
        "big5",
    ):

        try:

            return data.decode(
                encoding
            )

        except UnicodeDecodeError:
            continue

    raise RuntimeError(
        "unable to decode TDCC payload"
    )


def clean(
    value: Any,
) -> str:

    if value is None:

        return ""

    return (
        str(
            value
        )
        .strip()
    )


def to_int(
    value: Any,
) -> int | None:

    text = (
        clean(
            value
        )
        .replace(
            ",",
            "",
        )
        .replace(
            "，",
            "",
        )
        .replace(
            " ",
            "",
        )
    )

    if text in {
        "",
        "-",
        "--",
        "N/A",
        "NA",
        "—",
    }:

        return None

    try:

        return int(
            text
        )

    except ValueError:

        try:

            return int(
                float(
                    text
                )
            )

        except ValueError:

            return None


def to_float(
    value: Any,
) -> float | None:

    text = (
        clean(
            value
        )
        .replace(
            ",",
            "",
        )
        .replace(
            "，",
            "",
        )
        .replace(
            "%",
            "",
        )
        .replace(
            " ",
            "",
        )
    )

    if text in {
        "",
        "-",
        "--",
        "N/A",
        "NA",
        "—",
    }:

        return None

    try:

        return float(
            text
        )

    except ValueError:

        return None


def to_date(
    value: Any,
) -> date:

    digits = "".join(
        ch

        for ch
        in clean(
            value
        )

        if ch.isdigit()
    )

    # Gregorian YYYYMMDD
    if len(
        digits
    ) == 8:

        return date(
            int(
                digits[:4]
            ),

            int(
                digits[4:6]
            ),

            int(
                digits[6:8]
            ),
        )

    # ROC YYYMMDD
    if len(
        digits
    ) == 7:

        return date(
            int(
                digits[:3]
            )
            + 1911,

            int(
                digits[3:5]
            ),

            int(
                digits[5:7]
            ),
        )

    raise RuntimeError(
        f"unexpected TDCC date: "
        f"{value!r}"
    )


# ============================================================
# NORMALIZE TDCC ROW
# ============================================================


def normalize(
    raw: dict[
        str,
        Any,
    ],
    source: str,
) -> TdccRow:

    fields = (
        "資料日期",
        "證券代號",
        "持股分級",
        "人數",
        "股數",
        "占集保庫存數比例%",
    )

    missing = [
        field

        for field
        in fields

        if field
        not in raw
    ]

    if missing:

        raise RuntimeError(
            "TDCC missing fields: "
            + ", ".join(
                missing
            )
        )

    stock_id = clean(
        raw[
            "證券代號"
        ]
    )

    level = to_int(
        raw[
            "持股分級"
        ]
    )

    holder_count = to_int(
        raw[
            "人數"
        ]
    )

    shares = to_int(
        raw[
            "股數"
        ]
    )

    percentage = to_float(
        raw[
            "占集保庫存數比例%"
        ]
    )

    if not stock_id:

        raise RuntimeError(
            "TDCC empty stock_id"
        )

    if (
        level is None
        or
        not 1 <= level <= 17
    ):

        raise RuntimeError(
            f"TDCC {stock_id} "
            "invalid holder level"
        )

    if (
        holder_count
        is not None
        and
        holder_count < 0
    ):

        raise RuntimeError(
            f"TDCC {stock_id} "
            "negative holder count"
        )

    if (
        shares is not None
        and
        shares < 0
    ):

        raise RuntimeError(
            f"TDCC {stock_id} "
            "negative shares"
        )

    if (
        percentage
        is not None
        and
        not 0
        <= percentage
        <= 100.5
    ):

        raise RuntimeError(
            f"TDCC {stock_id} "
            "invalid percentage="
            f"{percentage}"
        )

    return TdccRow(
        stock_id=stock_id,

        data_date=(
            to_date(
                raw[
                    "資料日期"
                ]
            )
            .isoformat()
        ),

        holder_level=level,

        holder_count=(
            holder_count
        ),

        shares=shares,

        percentage=(
            percentage
        ),

        source=source,
    )


# ============================================================
# OFFICIAL SOURCE
# ============================================================


def parse_openapi(
    data: bytes,
) -> list[TdccRow]:

    text = (
        decode_text(
            data
        )
    )

    if (
        text
        .lstrip()
        .startswith(
            "<"
        )
    ):

        raise RuntimeError(
            "TDCC OpenAPI returned HTML"
        )

    try:

        payload = (
            json.loads(
                text
            )
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "TDCC OpenAPI "
            f"invalid JSON: {exc}"
        ) from exc

    if not isinstance(
        payload,
        list,
    ):

        raise RuntimeError(
            "TDCC OpenAPI "
            "response is not array"
        )

    if (
        len(
            payload
        )
        <
        MIN_RAW_ROWS
    ):

        raise RuntimeError(
            "TDCC OpenAPI "
            "unexpected row count: "
            f"{len(payload):,}"
        )

    return [
        normalize(
            row,
            "TDCC_OPENAPI_1_5",
        )

        for row
        in payload

        if isinstance(
            row,
            dict,
        )
    ]


def parse_csv(
    data: bytes,
) -> list[TdccRow]:

    text = (
        decode_text(
            data
        )
    )

    if (
        text
        .lstrip()
        .startswith(
            "<"
        )
    ):

        raise RuntimeError(
            "TDCC CSV returned HTML"
        )

    raw_rows = list(
        csv.DictReader(
            io.StringIO(
                text
            )
        )
    )

    if (
        len(
            raw_rows
        )
        <
        MIN_RAW_ROWS
    ):

        raise RuntimeError(
            "TDCC CSV "
            "unexpected row count: "
            f"{len(raw_rows):,}"
        )

    return [
        normalize(
            row,
            "TDCC_OPENDATA_CSV_1_5",
        )

        for row
        in raw_rows
    ]


def fetch_latest(
) -> tuple[
    list[TdccRow],
    str,
]:

    # Primary:
    # TDCC OpenAPI

    try:

        rows = parse_openapi(
            fetch(
                TDCC_OPENAPI_URL
            )
        )

        return (
            rows,
            "TDCC_OPENAPI_1_5",
        )

    except Exception as exc:

        print(
            "    [WARN] "
            "TDCC OpenAPI failed: "
            f"{exc}"
        )

        print(
            "    Falling back to "
            "official TDCC CSV ..."
        )

    # Fallback:
    # Official TDCC CSV

    rows = parse_csv(
        fetch(
            TDCC_CSV_URL,
            prefer_curl=True,
        )
    )

    return (
        rows,
        "TDCC_OPENDATA_CSV_1_5",
    )


# ============================================================
# TURSO HELPERS
# ============================================================


def scalar(
    conn,
    sql: str,
    params: tuple[
        Any,
        ...,
    ] = (),
) -> Any:

    row = (
        conn.execute(
            sql,
            params,
        )
        .fetchone()
    )

    if row is None:

        return None

    return row[0]


def schema_version(
    conn,
) -> str | None:

    value = scalar(
        conn,
        """
        SELECT schema_value

        FROM schema_meta

        WHERE schema_key =
              'schema_version'
        """,
    )

    if value is None:

        return None

    return str(
        value
    )


def active_common_stocks(
    conn,
) -> set[str]:

    rows = (
        conn.execute(
            """
            SELECT stock_id

            FROM stock_master

            WHERE is_active = 1

              AND security_type =
                  'COMMON_STOCK'
            """
        )
        .fetchall()
    )

    return {
        clean(
            row[0]
        )

        for row
        in rows
    }


def latest_tdcc_date(
    conn,
) -> str | None:

    value = scalar(
        conn,
        """
        SELECT MAX(
            data_date
        )

        FROM tdcc_summary
        """,
    )

    if value is None:

        return None

    return str(
        value
    )


def previous_summary(
    conn,
    data_date: str | None,
) -> dict[
    str,
    tuple[
        float | None,
        float | None,
    ],
]:

    if data_date is None:

        return {}

    rows = (
        conn.execute(
            """
            SELECT
                stock_id,
                large_holder_pct,
                retail_holder_pct

            FROM tdcc_summary

            WHERE data_date = ?
            """,
            (
                data_date,
            ),
        )
        .fetchall()
    )

    return {
        str(
            row[0]
        ): (
            (
                None
                if row[1]
                is None
                else float(
                    row[1]
                )
            ),

            (
                None
                if row[2]
                is None
                else float(
                    row[2]
                )
            ),
        )

        for row
        in rows
    }


# ============================================================
# SOURCE VALIDATION
# ============================================================


def validate_structure(
    rows: list[
        TdccRow
    ],
) -> date:

    dates = {
        row.data_date

        for row
        in rows
    }

    if (
        len(
            dates
        )
        != 1
    ):

        raise RuntimeError(
            "TDCC latest source "
            "must contain exactly "
            "one data date"
        )

    seen: set[
        tuple[
            str,
            str,
            int,
        ]
    ] = set()

    for row in rows:

        key = (
            row.stock_id,
            row.data_date,
            row.holder_level,
        )

        if key in seen:

            raise RuntimeError(
                "TDCC duplicate: "
                f"{row.stock_id}/"
                f"{row.data_date}/"
                f"{row.holder_level}"
            )

        seen.add(
            key
        )

    return date.fromisoformat(
        next(
            iter(
                dates
            )
        )
    )


# ============================================================
# COMMON STOCK FILTER
# ============================================================


def filter_universe(
    rows: list[
        TdccRow
    ],
    universe: set[str],
) -> tuple[
    list[TdccRow],
    set[str],
    int,
    float,
]:

    filtered = [
        row

        for row
        in rows

        if row.stock_id
        in universe
    ]

    matched = {
        row.stock_id

        for row
        in filtered
    }

    excluded = {
        row.stock_id

        for row
        in rows

        if row.stock_id
        not in universe
    }

    coverage = (
        len(
            matched
        )
        /
        len(
            universe
        )

        if universe

        else 0.0
    )

    if (
        coverage
        <
        MIN_COVERAGE
    ):

        raise RuntimeError(
            "TDCC COMMON_STOCK "
            "coverage too low: "
            f"{coverage:.2%} "
            f"({len(matched):,}/"
            f"{len(universe):,})"
        )

    return (
        filtered,
        matched,
        len(
            excluded
        ),
        coverage,
    )


# ============================================================
# SUMMARY DERIVATION
# ============================================================


def derive_percentages(
    rows: list[
        TdccRow
    ],
) -> dict[
    str,
    tuple[
        float,
        float,
    ],
]:

    grouped: dict[
        str,
        dict[
            int,
            TdccRow,
        ],
    ] = {}

    for row in rows:

        grouped.setdefault(
            row.stock_id,
            {},
        )[
            row.holder_level
        ] = row

    result: dict[
        str,
        tuple[
            float,
            float,
        ],
    ] = {}

    for (
        stock_id,
        levels,
    ) in grouped.items():

        missing = (
            REQUIRED_LEVELS
            -
            set(
                levels
            )
        )

        if missing:

            raise RuntimeError(
                f"TDCC {stock_id} "
                "missing levels: "
                +
                ",".join(
                    str(
                        level
                    )

                    for level
                    in sorted(
                        missing
                    )
                )
            )

        percentages: dict[
            int,
            float,
        ] = {}

        for level in (
            LARGE_LEVELS
            |
            RETAIL_LEVELS
        ):

            percentage = (
                levels[
                    level
                ]
                .percentage
            )

            if (
                percentage
                is None
            ):

                raise RuntimeError(
                    f"TDCC {stock_id} "
                    f"level {level} "
                    "missing percentage"
                )

            percentages[
                level
            ] = percentage

        # level 17 = total
        total_pct = (
            levels[
                17
            ]
            .percentage
        )

        if (
            total_pct
            is not None
            and
            not 99.0
            <= total_pct
            <= 100.5
        ):

            raise RuntimeError(
                f"TDCC {stock_id} "
                "level-17 percentage "
                "unexpected: "
                f"{total_pct}"
            )

        large = round(
            sum(
                percentages[
                    level
                ]

                for level
                in LARGE_LEVELS
            ),
            4,
        )

        retail = round(
            sum(
                percentages[
                    level
                ]

                for level
                in RETAIL_LEVELS
            ),
            4,
        )

        result[
            stock_id
        ] = (
            large,
            retail,
        )

    return result


def make_summary_rows(
    current_date: date,

    current: dict[
        str,
        tuple[
            float,
            float,
        ],
    ],

    previous_date: str | None,

    previous: dict[
        str,
        tuple[
            float | None,
            float | None,
        ],
    ],

    source: str,
) -> tuple[
    list[SummaryRow],
    int | None,
    bool,
]:

    gap_days: int | None = (
        None
    )

    adjacent = False

    if (
        previous_date
        is not None
    ):

        gap_days = (
            current_date
            -
            date.fromisoformat(
                previous_date
            )
        ).days

        # Weekly data may shift slightly
        # due to holidays.
        adjacent = (
            4
            <= gap_days
            <= 10
        )

    result: list[
        SummaryRow
    ] = []

    for stock_id in sorted(
        current
    ):

        (
            large,
            retail,
        ) = current[
            stock_id
        ]

        large_change = None
        retail_change = None

        if (
            adjacent
            and
            stock_id
            in previous
        ):

            (
                previous_large,
                previous_retail,
            ) = previous[
                stock_id
            ]

            if (
                previous_large
                is not None
            ):

                large_change = round(
                    large
                    -
                    previous_large,
                    4,
                )

            if (
                previous_retail
                is not None
            ):

                retail_change = round(
                    retail
                    -
                    previous_retail,
                    4,
                )

        result.append(
            SummaryRow(
                stock_id=stock_id,

                data_date=(
                    current_date
                    .isoformat()
                ),

                large_holder_pct=(
                    large
                ),

                retail_holder_pct=(
                    retail
                ),

                large_holder_change=(
                    large_change
                ),

                retail_holder_change=(
                    retail_change
                ),

                source=source,
            )
        )

    return (
        result,
        gap_days,
        adjacent,
    )


# ============================================================
# SQL
# ============================================================


DIST_PREFIX = """
INSERT INTO tdcc_distribution (
    stock_id,
    data_date,
    holder_level,
    holder_count,
    shares,
    percentage,
    source,
    created_at,
    updated_at
)
VALUES
"""


DIST_VALUE = """
(
    ?, ?, ?, ?, ?, ?, ?,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
"""


DIST_SUFFIX = """
ON CONFLICT(
    stock_id,
    data_date,
    holder_level
)
DO UPDATE SET

    holder_count =
        excluded.holder_count,

    shares =
        excluded.shares,

    percentage =
        excluded.percentage,

    source =
        excluded.source,

    updated_at =
        CURRENT_TIMESTAMP
"""


SUMMARY_PREFIX = """
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
VALUES
"""


SUMMARY_VALUE = """
(
    ?, ?, ?, ?, ?, ?, ?,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
"""


SUMMARY_SUFFIX = """
ON CONFLICT(
    stock_id,
    data_date
)
DO UPDATE SET

    large_holder_pct =
        excluded.large_holder_pct,

    retail_holder_pct =
        excluded.retail_holder_pct,

    large_holder_change =
        excluded.large_holder_change,

    retail_holder_change =
        excluded.retail_holder_change,

    source =
        excluded.source,

    updated_at =
        CURRENT_TIMESTAMP
"""


def sql_for(
    prefix: str,
    value_sql: str,
    suffix: str,
    count: int,
) -> str:

    return (
        prefix
        +
        ",\n".join(
            value_sql

            for _ in range(
                count
            )
        )
        +
        suffix
    )


def flatten(
    rows: list[
        tuple[
            Any,
            ...,
        ]
    ],
) -> tuple[
    Any,
    ...,
]:

    values: list[Any] = []

    for row in rows:

        values.extend(
            row
        )

    return tuple(
        values
    )


# ============================================================
# SYNC STATE
# ============================================================


def update_sync_state(
    conn,
    data_date: str,
    count: int,
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
            SYNC_DATASET,
            data_date,
            count,
        ),
    )


# ============================================================
# WRITE
# ============================================================


def write_snapshot(
    conn,

    distribution: list[
        TdccRow
    ],

    summaries: list[
        SummaryRow
    ],

    data_date: str,
) -> None:

    conn.execute(
        "BEGIN"
    )

    try:

        # Raw TDCC distribution

        for start in range(
            0,
            len(
                distribution
            ),
            DIST_BATCH,
        ):

            batch = distribution[
                start:
                start
                + DIST_BATCH
            ]

            conn.execute(
                sql_for(
                    DIST_PREFIX,
                    DIST_VALUE,
                    DIST_SUFFIX,
                    len(
                        batch
                    ),
                ),

                flatten(
                    [
                        row.values()

                        for row
                        in batch
                    ]
                ),
            )

        # Derived TDCC summary

        for start in range(
            0,
            len(
                summaries
            ),
            SUMMARY_BATCH,
        ):

            batch = summaries[
                start:
                start
                + SUMMARY_BATCH
            ]

            conn.execute(
                sql_for(
                    SUMMARY_PREFIX,
                    SUMMARY_VALUE,
                    SUMMARY_SUFFIX,
                    len(
                        batch
                    ),
                ),

                flatten(
                    [
                        row.values()

                        for row
                        in batch
                    ]
                ),
            )

        update_sync_state(
            conn,
            data_date,
            len(
                summaries
            ),
        )

        conn.commit()

    except BaseException:

        try:

            conn.rollback()

        except Exception:
            pass

        raise


# ============================================================
# VERIFY WRITE
# ============================================================


def verify_written(
    conn,
    data_date: str,
) -> tuple[
    int,
    int,
]:

    distribution_count = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)

            FROM tdcc_distribution

            WHERE data_date = ?
            """,
            (
                data_date,
            ),
        )
        or 0
    )

    summary_count = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)

            FROM tdcc_summary

            WHERE data_date = ?
            """,
            (
                data_date,
            ),
        )
        or 0
    )

    return (
        distribution_count,
        summary_count,
    )


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    configure_console()

    args = (
        parse_args()
    )

    print(
        "=" * 76
    )

    print(
        "StockWaveScanner V2 - "
        "TDCC Weekly Incremental Pipeline"
    )

    print(
        "=" * 76
    )

    try:

        (
            url,
            token,
        ) = load_dev_credentials()

        print(
            "Target      : DEV"
        )

        print(
            "Database    : "
            f"{url}"
        )

        print(
            "PROD Access : DISABLED"
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
                    "Turso DEV connection failed"
                )

            version = (
                schema_version(
                    conn
                )
            )

            if version is None:

                raise RuntimeError(
                    "schema_meta/"
                    "schema_version missing"
                )

            print(
                "Schema      : "
                f"{version}"
            )

            print(
                "[PASS] "
                "Turso DEV connection"
            )

            cursor = (
                latest_tdcc_date(
                    conn
                )
            )

            universe = (
                active_common_stocks(
                    conn
                )
            )

            print()

            print(
                "Downloading latest "
                "official TDCC snapshot ..."
            )

            started = (
                time.perf_counter()
            )

            (
                raw_rows,
                source,
            ) = fetch_latest()

            source_date = (
                validate_structure(
                    raw_rows
                )
            )

            (
                distribution,
                matched,
                excluded,
                coverage,
            ) = filter_universe(
                raw_rows,
                universe,
            )

            current = (
                derive_percentages(
                    distribution
                )
            )

            previous = (
                previous_summary(
                    conn,
                    cursor,
                )
            )

            (
                summaries,
                gap_days,
                adjacent,
            ) = make_summary_rows(
                source_date,
                current,
                cursor,
                previous,
                source,
            )

            print(
                "[PASS] Official source     : "
                f"{source}"
            )

            print(
                "[PASS] Raw rows            : "
                f"{len(raw_rows):,}"
            )

            print(
                "[PASS] Snapshot date       : "
                f"{source_date.isoformat()}"
            )

            print(
                "[PASS] Active COMMON_STOCK : "
                f"{len(universe):,}"
            )

            print(
                "[PASS] TDCC matched stocks : "
                f"{len(matched):,}"
            )

            print(
                "[PASS] Coverage            : "
                f"{coverage:.2%}"
            )

            print(
                "[PASS] Excluded securities : "
                f"{excluded:,}"
            )

            print(
                "[PASS] Distribution rows   : "
                f"{len(distribution):,}"
            )

            print(
                "[PASS] Summary rows        : "
                f"{len(summaries):,}"
            )

            print(
                "Source Elapsed             : "
                f"{time.perf_counter() - started:.1f}s"
            )

            print()

            print(
                "=" * 76
            )

            print(
                "INCREMENTAL CURSOR"
            )

            print(
                "=" * 76
            )

            print(
                "Turso Last Data Date : "
                f"{cursor or 'EMPTY'}"
            )

            print(
                "TDCC Source Date     : "
                f"{source_date.isoformat()}"
            )

            if (
                gap_days
                is not None
            ):

                print(
                    "Gap Days             : "
                    f"{gap_days}"
                )

                if adjacent:

                    print(
                        "Change Semantics     : "
                        "ADJACENT_WEEK"
                    )

                else:

                    print(
                        "Change Semantics     : "
                        "GAP_DETECTED -> "
                        "change=NULL"
                    )

                    print(
                        "[WARN] Not an adjacent "
                        "weekly snapshot; "
                        "large/retail change "
                        "will not pretend "
                        "to be WoW."
                    )

            is_new = (
                cursor is None
                or
                source_date.isoformat()
                > cursor
            )

            print(
                "New Snapshot         : "
                f"{'YES' if is_new else 'NO'}"
            )

            # =================================================
            # READ ONLY VALIDATION
            # =================================================

            if args.validate_only:

                print()

                print(
                    "[PASS] READ-ONLY validation"
                )

                print(
                    "[PASS] No Turso rows "
                    "were written"
                )

                print()

                print(
                    "=" * 76
                )

                print(
                    "TDCC WEEKLY PIPELINE OK"
                )

                print(
                    "=" * 76
                )

                return 0

            # =================================================
            # NO NEW WEEK
            # =================================================

            if not is_new:

                print()

                print(
                    "[PASS] No new TDCC "
                    "weekly snapshot. "
                    "Nothing to write."
                )

                print()

                print(
                    "=" * 76
                )

                print(
                    "TDCC WEEKLY PIPELINE OK"
                )

                print(
                    "=" * 76
                )

                return 0

            # =================================================
            # WRITE
            # =================================================

            print()

            print(
                "Writing TDCC snapshot "
                "to Turso DEV ..."
            )

            write_started = (
                time.perf_counter()
            )

            write_snapshot(
                conn,

                distribution,

                summaries,

                source_date.isoformat(),
            )

            (
                distribution_count,
                summary_count,
            ) = verify_written(
                conn,
                source_date.isoformat(),
            )

            if (
                distribution_count
                != len(
                    distribution
                )
            ):

                raise RuntimeError(
                    "tdcc_distribution "
                    "verify failed: "
                    f"{distribution_count:,} "
                    "!= "
                    f"{len(distribution):,}"
                )

            if (
                summary_count
                != len(
                    summaries
                )
            ):

                raise RuntimeError(
                    "tdcc_summary "
                    "verify failed: "
                    f"{summary_count:,} "
                    "!= "
                    f"{len(summaries):,}"
                )

            print(
                "[PASS] tdcc_distribution : "
                f"{distribution_count:,}"
            )

            print(
                "[PASS] tdcc_summary      : "
                f"{summary_count:,}"
            )

            print(
                "DB Write Elapsed         : "
                f"{time.perf_counter() - write_started:.1f}s"
            )

            print(
                "PROD Access              : "
                "DISABLED"
            )

        finally:

            conn.close()

        print()

        print(
            "=" * 76
        )

        print(
            "TDCC WEEKLY PIPELINE OK"
        )

        print(
            "=" * 76
        )

        return 0

    except KeyboardInterrupt:

        print()

        print(
            "INTERRUPTED"
        )

        print(
            "No PROD database "
            "was accessed."
        )

        return 130

    except Exception as exc:

        print()

        print(
            "=" * 76
        )

        print(
            "ERROR"
        )

        print(
            "=" * 76
        )

        print(
            str(
                exc
            )
        )

        print()

        print(
            "No PROD database "
            "was accessed."
        )

        return 1


if __name__ == "__main__":

    sys.exit(
        main()
    )