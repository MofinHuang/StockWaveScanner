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
from pathlib import Path
from typing import Any

import libsql
from dotenv import load_dotenv


# ============================================================
# BASIC CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

TIMEOUT = 60

HTTP_RETRY_DELAYS = (
    0,
    3,
    10,
)

SQL_ROWS_PER_STATEMENT = 100

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36 "
    "StockWaveScanner-V2-Monthly-Revenue/1.0"
)


# ============================================================
# OFFICIAL SOURCES
# ============================================================

TWSE_CSV_URL = (
    "https://mopsfin.twse.com.tw/"
    "opendata/t187ap05_L.csv"
)

TWSE_OPENAPI_URL = (
    "https://openapi.twse.com.tw/v1/"
    "opendata/t187ap05_L"
)

TPEX_CSV_URL = (
    "https://mopsfin.twse.com.tw/"
    "opendata/t187ap05_O.csv"
)


# ============================================================
# VALIDATION LIMITS
# ============================================================

MIN_SOURCE_ROWS = {
    "TWSE": 900,
    "TPEX": 700,
}

MIN_COVERAGE = {
    "TWSE": 0.90,
    "TPEX": 0.90,
}


# ============================================================
# SYNC STATE
# ============================================================

DATASETS = {
    "TWSE": "monthly_revenue_twse",
    "TPEX": "monthly_revenue_tpex",
}


# ============================================================
# DATA MODEL
# ============================================================


@dataclass(frozen=True)
class RevenueRow:

    stock_id: str
    market: str
    revenue_month: str

    revenue: float | None
    revenue_mom_pct: float | None
    revenue_yoy_pct: float | None

    cumulative_revenue: float | None
    cumulative_yoy_pct: float | None

    source: str

    def db_values(
        self,
    ) -> tuple[Any, ...]:

        return (
            self.stock_id,
            self.revenue_month,

            self.revenue,
            self.revenue_mom_pct,
            self.revenue_yoy_pct,

            self.cumulative_revenue,
            self.cumulative_yoy_pct,

            self.source,
        )


@dataclass(frozen=True)
class SourceResult:

    market: str
    source: str
    raw_count: int
    revenue_month: str

    rows: dict[
        str,
        RevenueRow,
    ]


# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Sync latest official monthly revenue "
            "snapshot into Turso DEV."
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

    request = urllib.request.Request(
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

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT,
    ) as response:

        data = (
            response.read()
        )

    if not data:

        raise RuntimeError(
            f"Empty response: {url}"
        )

    return data


def fetch_curl(
    url: str,
) -> bytes:

    curl = (
        shutil.which(
            "curl.exe"
        )
        or shutil.which(
            "curl"
        )
    )

    if not curl:

        raise RuntimeError(
            "curl not found"
        )

    result = subprocess.run(
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

    if (
        result.returncode
        != 0
    ):

        error = (
            result.stderr
            .decode(
                "utf-8",
                errors="replace",
            )
            .strip()
        )

        raise RuntimeError(
            f"curl failed: {error}"
        )

    if not result.stdout:

        raise RuntimeError(
            f"Empty response: {url}"
        )

    return result.stdout


def fetch(
    url: str,
    *,
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

    for attempt, delay in enumerate(
        HTTP_RETRY_DELAYS,
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
                HTTP_RETRY_DELAYS
            )
        ):

            print(
                "    retrying HTTP "
                f"({attempt}/"
                f"{len(HTTP_RETRY_DELAYS)}) ..."
            )

    raise RuntimeError(
        " | ".join(
            errors[-6:]
        )
    )


# ============================================================
# TEXT / VALUES
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
        "Unable to decode revenue payload"
    )


def clean_text(
    value: Any,
) -> str:

    if value is None:

        return ""

    return (
        str(
            value
        )
        .replace(
            "\u3000",
            " ",
        )
        .strip()
    )


def normalize_header(
    value: str,
) -> str:

    return (
        clean_text(
            value
        )
        .replace(
            "％",
            "%",
        )
        .replace(
            "（",
            "(",
        )
        .replace(
            "）",
            ")",
        )
        .replace(
            " ",
            "",
        )
    )


def get_field(
    row: dict[
        str,
        Any,
    ],
    *candidates: str,
) -> Any:

    normalized = {
        normalize_header(
            key
        ): value

        for key, value
        in row.items()

        if key is not None
    }

    for candidate in candidates:

        key = (
            normalize_header(
                candidate
            )
        )

        if key in normalized:

            return normalized[
                key
            ]

    return None


def parse_number(
    value: Any,
) -> float | None:

    text = (
        clean_text(
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
            "％",
            "",
        )
        .replace(
            " ",
            "",
        )
        .replace(
            "−",
            "-",
        )
        .replace(
            "－",
            "-",
        )
    )

    if text in {
        "",
        "-",
        "--",
        "---",
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


# ============================================================
# REVENUE MONTH
# ============================================================


def parse_revenue_month(
    value: Any,
) -> str:

    digits = "".join(
        ch

        for ch
        in clean_text(
            value
        )

        if ch.isdigit()
    )

    # ROC:
    #
    # 11508
    # ->
    # 2026-08

    if len(
        digits
    ) == 5:

        year = (
            int(
                digits[:3]
            )
            + 1911
        )

        month = int(
            digits[3:5]
        )

    # Gregorian:
    #
    # 202608
    # ->
    # 2026-08

    elif len(
        digits
    ) == 6:

        year = int(
            digits[:4]
        )

        month = int(
            digits[4:6]
        )

    else:

        raise RuntimeError(
            "Unexpected revenue month: "
            f"{value!r}"
        )

    if not 1 <= month <= 12:

        raise RuntimeError(
            "Invalid revenue month: "
            f"{value!r}"
        )

    return (
        f"{year:04d}-"
        f"{month:02d}"
    )


def month_index(
    value: str,
) -> int:

    year_text, month_text = (
        value.split(
            "-",
            1,
        )
    )

    return (
        int(
            year_text
        )
        * 12

        +
        int(
            month_text
        )
    )


def month_gap(
    previous: str,
    current: str,
) -> int:

    return (
        month_index(
            current
        )
        -
        month_index(
            previous
        )
    )


# ============================================================
# NORMALIZE ONE ROW
# ============================================================


def normalize_revenue_row(
    raw: dict[
        str,
        Any,
    ],
    *,
    market: str,
    source: str,
) -> RevenueRow:

    stock_id = clean_text(
        get_field(
            raw,
            "公司代號",
            "SecuritiesCompanyCode",
        )
    )

    month_raw = get_field(
        raw,
        "資料年月",
    )

    revenue = parse_number(
        get_field(
            raw,
            "營業收入-當月營收",
        )
    )

    mom = parse_number(
        get_field(
            raw,

            "營業收入-上月比較增減(%)",
            "營業收入-上月比較增減",
        )
    )

    yoy = parse_number(
        get_field(
            raw,

            "營業收入-去年同月增減(%)",
            "營業收入-去年同月增減",
        )
    )

    cumulative = parse_number(
        get_field(
            raw,

            "累計營業收入-當月累計營收",
        )
    )

    cumulative_yoy = parse_number(
        get_field(
            raw,

            "累計營業收入-前期比較增減(%)",
            "累計營業收入-前期比較增減",
        )
    )

    if not stock_id:

        raise RuntimeError(
            f"{market}: "
            "missing 公司代號"
        )

    if month_raw is None:

        raise RuntimeError(
            f"{market} {stock_id}: "
            "missing 資料年月"
        )

    if revenue is None:

        raise RuntimeError(
            f"{market} {stock_id}: "
            "missing 當月營收"
        )

    if cumulative is None:

        raise RuntimeError(
            f"{market} {stock_id}: "
            "missing 累計營收"
        )

    return RevenueRow(
        stock_id=stock_id,
        market=market,

        revenue_month=(
            parse_revenue_month(
                month_raw
            )
        ),

        revenue=revenue,

        revenue_mom_pct=mom,
        revenue_yoy_pct=yoy,

        cumulative_revenue=(
            cumulative
        ),

        cumulative_yoy_pct=(
            cumulative_yoy
        ),

        source=source,
    )


# ============================================================
# CSV SOURCE
# ============================================================


def parse_csv_source(
    data: bytes,
    *,
    market: str,
    source: str,
) -> SourceResult:

    text = (
        decode_text(
            data
        )
    )

    if (
        text
        .lstrip()
        .lower()
        .startswith(
            "<html"
        )
        or
        text
        .lstrip()
        .lower()
        .startswith(
            "<!doctype"
        )
    ):

        raise RuntimeError(
            f"{market} revenue CSV "
            "returned HTML"
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
        MIN_SOURCE_ROWS[
            market
        ]
    ):

        raise RuntimeError(
            f"{market} revenue "
            "source count too low: "
            f"{len(raw_rows):,}"
        )

    result: dict[
        str,
        RevenueRow,
    ] = {}

    months: set[
        str
    ] = set()

    for raw in raw_rows:

        row = (
            normalize_revenue_row(
                raw,
                market=market,
                source=source,
            )
        )

        if row.stock_id in result:

            raise RuntimeError(
                f"{market} duplicate "
                f"stock_id="
                f"{row.stock_id}"
            )

        result[
            row.stock_id
        ] = row

        months.add(
            row.revenue_month
        )

    if len(
        months
    ) != 1:

        raise RuntimeError(
            f"{market} revenue source "
            "contains multiple months: "
            f"{sorted(months)}"
        )

    return SourceResult(
        market=market,
        source=source,

        raw_count=(
            len(
                raw_rows
            )
        ),

        revenue_month=(
            next(
                iter(
                    months
                )
            )
        ),

        rows=result,
    )


# ============================================================
# TWSE OPENAPI FALLBACK
# ============================================================


def parse_twse_openapi(
    data: bytes,
) -> SourceResult:

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
            "TWSE Revenue OpenAPI "
            "returned HTML"
        )

    try:

        payload = json.loads(
            text
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "TWSE Revenue OpenAPI "
            f"invalid JSON: {exc}"
        ) from exc

    if not isinstance(
        payload,
        list,
    ):

        raise RuntimeError(
            "TWSE Revenue OpenAPI "
            "response is not array"
        )

    if (
        len(
            payload
        )
        <
        MIN_SOURCE_ROWS[
            "TWSE"
        ]
    ):

        raise RuntimeError(
            "TWSE Revenue OpenAPI "
            "row count too low: "
            f"{len(payload):,}"
        )

    result: dict[
        str,
        RevenueRow,
    ] = {}

    months: set[
        str
    ] = set()

    for raw in payload:

        if not isinstance(
            raw,
            dict,
        ):

            continue

        row = normalize_revenue_row(
            raw,
            market="TWSE",
            source=(
                "TWSE_OPENAPI_T187AP05_L"
            ),
        )

        if row.stock_id in result:

            raise RuntimeError(
                "TWSE Revenue OpenAPI "
                f"duplicate "
                f"{row.stock_id}"
            )

        result[
            row.stock_id
        ] = row

        months.add(
            row.revenue_month
        )

    if len(
        months
    ) != 1:

        raise RuntimeError(
            "TWSE Revenue OpenAPI "
            "contains multiple months"
        )

    return SourceResult(
        market="TWSE",

        source=(
            "TWSE_OPENAPI_T187AP05_L"
        ),

        raw_count=(
            len(
                payload
            )
        ),

        revenue_month=(
            next(
                iter(
                    months
                )
            )
        ),

        rows=result,
    )


# ============================================================
# SOURCE ROUTER
# ============================================================


def load_twse(
) -> SourceResult:

    try:

        return parse_csv_source(
            fetch(
                TWSE_CSV_URL,
                prefer_curl=True,
            ),

            market="TWSE",

            source=(
                "TWSE_MOPS_CSV_T187AP05_L"
            ),
        )

    except Exception as exc:

        print(
            "    [WARN] "
            "TWSE Revenue MOPS CSV failed: "
            f"{exc}"
        )

        print(
            "    Falling back to "
            "TWSE Revenue OpenAPI ..."
        )

    return parse_twse_openapi(
        fetch(
            TWSE_OPENAPI_URL
        )
    )


def load_tpex(
) -> SourceResult:

    return parse_csv_source(
        fetch(
            TPEX_CSV_URL,
            prefer_curl=True,
        ),

        market="TPEX",

        source=(
            "TPEX_MOPS_CSV_T187AP05_O"
        ),
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


def get_schema_version(
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


def active_common_ids(
    conn,
    market: str,
) -> set[str]:

    rows = (
        conn.execute(
            """
            SELECT stock_id

            FROM stock_master

            WHERE market = ?
              AND is_active = 1
              AND security_type =
                  'COMMON_STOCK'
            """,
            (
                market,
            ),
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


def get_latest_month(
    conn,
    market: str,
) -> str | None:

    value = scalar(
        conn,
        """
        SELECT MAX(
            r.revenue_month
        )

        FROM monthly_revenue r

        INNER JOIN stock_master s
            ON s.stock_id =
               r.stock_id

        WHERE s.market = ?
          AND s.security_type =
              'COMMON_STOCK'
        """,
        (
            market,
        ),
    )

    if value is None:

        return None

    return str(
        value
    )


# ============================================================
# FILTER CURRENT UNIVERSE
# ============================================================


def prepare_market_rows(
    conn,
    result: SourceResult,
) -> tuple[
    list[RevenueRow],
    int,
    float,
]:

    universe = (
        active_common_ids(
            conn,
            result.market,
        )
    )

    rows = [
        row

        for stock_id, row
        in result.rows.items()

        if stock_id
        in universe
    ]

    matched = {
        row.stock_id

        for row in rows
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

    excluded = len(
        set(
            result.rows
        )
        -
        universe
    )

    if (
        coverage
        <
        MIN_COVERAGE[
            result.market
        ]
    ):

        raise RuntimeError(
            f"{result.market} revenue "
            "coverage too low: "
            f"{coverage:.2%} "
            f"({len(matched):,}/"
            f"{len(universe):,})"
        )

    return (
        sorted(
            rows,
            key=lambda row:
                row.stock_id,
        ),

        excluded,

        coverage,
    )


# ============================================================
# GAP SAFETY
# ============================================================


def validate_incremental_gap(
    market: str,
    cursor: str | None,
    source_month: str,
) -> str:

    if cursor is None:

        return (
            "EMPTY -> SEED_LATEST"
        )

    gap = month_gap(
        cursor,
        source_month,
    )

    if gap < 0:

        raise RuntimeError(
            f"{market} DB cursor "
            f"{cursor} is newer than "
            f"official source "
            f"{source_month}"
        )

    if gap == 0:

        return (
            "UP_TO_DATE"
        )

    if gap == 1:

        return (
            "ADJACENT_MONTH"
        )

    # ========================================================
    # Important:
    #
    # t187ap05 is a latest-month snapshot.
    #
    # If the DB cursor is two or more months behind,
    # jumping directly to the newest month would silently
    # create a historical hole.
    #
    # Stop instead of pretending the incremental chain is
    # complete.
    # ========================================================

    raise RuntimeError(
        f"{market} monthly revenue "
        "gap detected: "
        f"cursor={cursor}, "
        f"source={source_month}, "
        f"gap={gap} months. "
        "Historical gap recovery is required "
        "before advancing the cursor."
    )


# ============================================================
# UPSERT SQL
# ============================================================


INSERT_PREFIX = """
INSERT INTO monthly_revenue (
    stock_id,
    revenue_month,

    revenue,
    revenue_mom_pct,
    revenue_yoy_pct,

    cumulative_revenue,
    cumulative_yoy_pct,

    source,

    created_at,
    updated_at
)
VALUES
"""


INSERT_VALUE = """
(
    ?, ?,

    ?, ?, ?,

    ?, ?,

    ?,

    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
"""


INSERT_SUFFIX = """
ON CONFLICT(
    stock_id,
    revenue_month
)
DO UPDATE SET

    revenue =
        excluded.revenue,

    revenue_mom_pct =
        excluded.revenue_mom_pct,

    revenue_yoy_pct =
        excluded.revenue_yoy_pct,

    cumulative_revenue =
        excluded.cumulative_revenue,

    cumulative_yoy_pct =
        excluded.cumulative_yoy_pct,

    source =
        excluded.source,

    updated_at =
        CURRENT_TIMESTAMP
"""


def build_insert_sql(
    count: int,
) -> str:

    return (
        INSERT_PREFIX

        +
        ",\n".join(
            INSERT_VALUE

            for _ in range(
                count
            )
        )

        +
        INSERT_SUFFIX
    )


def flatten_rows(
    rows: list[
        RevenueRow
    ],
) -> tuple[
    Any,
    ...,
]:

    values: list[Any] = []

    for row in rows:

        values.extend(
            row.db_values()
        )

    return tuple(
        values
    )


# ============================================================
# SYNC STATE
# ============================================================


def update_sync_state(
    conn,
    *,
    market: str,
    revenue_month: str,
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
            DATASETS[
                market
            ],

            revenue_month,

            records_processed,
        ),
    )


# ============================================================
# WRITE MARKET
# ============================================================


def write_market(
    conn,
    *,
    market: str,
    rows: list[
        RevenueRow
    ],
    revenue_month: str,
) -> None:

    conn.execute(
        "BEGIN"
    )

    try:

        for start in range(
            0,
            len(
                rows
            ),
            SQL_ROWS_PER_STATEMENT,
        ):

            batch = rows[
                start:
                start
                +
                SQL_ROWS_PER_STATEMENT
            ]

            conn.execute(
                build_insert_sql(
                    len(
                        batch
                    )
                ),

                flatten_rows(
                    batch
                ),
            )

        update_sync_state(
            conn,

            market=market,

            revenue_month=(
                revenue_month
            ),

            records_processed=(
                len(
                    rows
                )
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


def verify_market(
    conn,
    *,
    market: str,
    revenue_month: str,
) -> int:

    count = scalar(
        conn,
        """
        SELECT COUNT(*)

        FROM monthly_revenue r

        INNER JOIN stock_master s
            ON s.stock_id =
               r.stock_id

        WHERE s.market = ?
          AND s.security_type =
              'COMMON_STOCK'

          AND r.revenue_month = ?
        """,
        (
            market,
            revenue_month,
        ),
    )

    return int(
        count or 0
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
        "Monthly Revenue Incremental Pipeline"
    )

    print(
        "=" * 76
    )

    try:

        url, token = (
            load_dev_credentials()
        )

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
                    "Turso DEV "
                    "connection failed"
                )

            version = (
                get_schema_version(
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

            print()

            print(
                "Downloading latest "
                "official Monthly Revenue ..."
            )

            started = (
                time.perf_counter()
            )

            twse_source = (
                load_twse()
            )

            tpex_source = (
                load_tpex()
            )

            if (
                twse_source.revenue_month
                !=
                tpex_source.revenue_month
            ):

                raise RuntimeError(
                    "Monthly Revenue "
                    "source month mismatch: "
                    f"TWSE="
                    f"{twse_source.revenue_month}, "
                    f"TPEX="
                    f"{tpex_source.revenue_month}"
                )

            (
                twse_rows,
                twse_excluded,
                twse_coverage,
            ) = prepare_market_rows(
                conn,
                twse_source,
            )

            (
                tpex_rows,
                tpex_excluded,
                tpex_coverage,
            ) = prepare_market_rows(
                conn,
                tpex_source,
            )

            revenue_month = (
                twse_source
                .revenue_month
            )

            print(
                f"TWSE | source="
                f"{twse_source.source} "
                f"| raw="
                f"{twse_source.raw_count:,} "
                f"| eligible="
                f"{len(twse_rows):,} "
                f"| excluded="
                f"{twse_excluded:,} "
                f"| coverage="
                f"{twse_coverage:.2%}"
            )

            print(
                f"TPEX | source="
                f"{tpex_source.source} "
                f"| raw="
                f"{tpex_source.raw_count:,} "
                f"| eligible="
                f"{len(tpex_rows):,} "
                f"| excluded="
                f"{tpex_excluded:,} "
                f"| coverage="
                f"{tpex_coverage:.2%}"
            )

            print()

            print(
                "[PASS] Official source fetch"
            )

            print(
                "[PASS] Source schema validation"
            )

            print(
                "[PASS] Revenue month normalization"
            )

            print(
                "[PASS] COMMON_STOCK filtering"
            )

            print(
                "Source Elapsed : "
                f"{time.perf_counter() - started:.1f}s"
            )

            cursors = {
                "TWSE":
                    get_latest_month(
                        conn,
                        "TWSE",
                    ),

                "TPEX":
                    get_latest_month(
                        conn,
                        "TPEX",
                    ),
            }

            semantics = {
                market:
                    validate_incremental_gap(
                        market,
                        cursors[
                            market
                        ],
                        revenue_month,
                    )

                for market
                in (
                    "TWSE",
                    "TPEX",
                )
            }

            print()

            print(
                "=" * 76
            )

            print(
                "MONTHLY REVENUE "
                "INCREMENTAL CURSOR"
            )

            print(
                "=" * 76
            )

            print(
                "Official Revenue Month : "
                f"{revenue_month}"
            )

            print(
                "TWSE Last Month        : "
                f"{cursors['TWSE'] or 'EMPTY'}"
            )

            print(
                "TWSE Semantics         : "
                f"{semantics['TWSE']}"
            )

            print(
                "TPEx Last Month        : "
                f"{cursors['TPEX'] or 'EMPTY'}"
            )

            print(
                "TPEx Semantics         : "
                f"{semantics['TPEX']}"
            )

            if (
                cursors["TWSE"]
                is None
                or
                cursors["TPEX"]
                is None
            ):

                print()

                print(
                    "[WARN] Monthly Revenue "
                    "history is not yet complete."
                )

                print(
                    "[WARN] EMPTY cursor will "
                    "seed only the latest month."
                )

                print(
                    "[WARN] Historical 24-month "
                    "backfill remains a separate task."
                )

            # =================================================
            # READ ONLY
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
                    "MONTHLY REVENUE "
                    "PIPELINE OK"
                )

                print(
                    "=" * 76
                )

                return 0

            # =================================================
            # WRITE
            # =================================================

            rows_by_market = {
                "TWSE":
                    twse_rows,

                "TPEX":
                    tpex_rows,
            }

            written = {
                "TWSE": 0,
                "TPEX": 0,
            }

            for market in (
                "TWSE",
                "TPEX",
            ):

                if (
                    semantics[
                        market
                    ]
                    ==
                    "UP_TO_DATE"
                ):

                    print()

                    print(
                        f"[PASS] {market} "
                        f"{revenue_month} "
                        "already synchronized"
                    )

                    continue

                print()

                print(
                    f"Writing {market} "
                    f"Monthly Revenue "
                    f"{revenue_month} ..."
                )

                write_started = (
                    time.perf_counter()
                )

                write_market(
                    conn,

                    market=market,

                    rows=(
                        rows_by_market[
                            market
                        ]
                    ),

                    revenue_month=(
                        revenue_month
                    ),
                )

                written[
                    market
                ] = verify_market(
                    conn,

                    market=market,

                    revenue_month=(
                        revenue_month
                    ),
                )

                if (
                    written[
                        market
                    ]
                    !=
                    len(
                        rows_by_market[
                            market
                        ]
                    )
                ):

                    raise RuntimeError(
                        f"{market} DB verify "
                        "count mismatch: "
                        f"{written[market]:,} "
                        "!= "
                        f"{len(rows_by_market[market]):,}"
                    )

                print(
                    f"[PASS] {market} "
                    f"rows="
                    f"{written[market]:,}"
                )

                print(
                    f"{market} Write Elapsed : "
                    f"{time.perf_counter() - write_started:.1f}s"
                )

            print()

            print(
                "=" * 76
            )

            print(
                "MONTHLY REVENUE RESULT"
            )

            print(
                "=" * 76
            )

            print(
                "Revenue Month : "
                f"{revenue_month}"
            )

            print(
                "TWSE Rows     : "
                f"{written['TWSE']:,}"
            )

            print(
                "TPEx Rows     : "
                f"{written['TPEX']:,}"
            )

            print(
                "PROD Access   : DISABLED"
            )

        finally:

            conn.close()

        print()

        print(
            "=" * 76
        )

        print(
            "MONTHLY REVENUE "
            "PIPELINE OK"
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