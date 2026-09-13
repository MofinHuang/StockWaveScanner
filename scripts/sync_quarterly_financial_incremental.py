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

TIMEOUT = 60
RETRY_DELAYS = (0, 3, 10)
BATCH_SIZE = 80
REPORT_TYPE = "GENERAL"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36 "
    "StockWaveScanner-V2-Quarterly-Financial/1.0"
)

TWSE_CSV_URL = (
    "https://mopsfin.twse.com.tw/"
    "opendata/t187ap06_L_ci.csv"
)

TWSE_OPENAPI_URL = (
    "https://openapi.twse.com.tw/v1/"
    "opendata/t187ap06_L_ci"
)

TPEX_CSV_URL = (
    "https://mopsfin.twse.com.tw/"
    "opendata/t187ap06_O_ci.csv"
)

MIN_SOURCE_ROWS = {
    "TWSE": 900,
    "TPEX": 700,
}

MIN_COVERAGE = {
    "TWSE": 0.90,
    "TPEX": 0.90,
}

DATASETS = {
    "TWSE": "quarterly_financial_twse_general",
    "TPEX": "quarterly_financial_tpex_general",
}


@dataclass(frozen=True)
class FinancialRow:
    stock_id: str
    market: str
    fiscal_year: int
    fiscal_quarter: int

    revenue: float | None
    gross_profit: float | None
    operating_income: float | None
    net_income: float | None
    eps: float | None

    gross_margin_pct: float | None
    operating_margin_pct: float | None
    net_margin_pct: float | None

    source: str
    source_date: str | None

    def values(self) -> tuple[Any, ...]:
        return (
            self.stock_id,
            self.fiscal_year,
            self.fiscal_quarter,
            REPORT_TYPE,

            self.revenue,
            self.gross_profit,
            self.operating_income,
            self.net_income,
            self.eps,

            self.gross_margin_pct,
            self.operating_margin_pct,
            self.net_margin_pct,

            self.source,
            self.source_date,
        )


@dataclass(frozen=True)
class SourceResult:
    market: str
    source: str
    raw_count: int
    fiscal_year: int
    fiscal_quarter: int

    rows: dict[str, FinancialRow]


# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Sync latest official Quarterly Financial "
            "GENERAL-industry snapshot into Turso DEV."
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

        if callable(reconfigure):

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

    if not url or not token:

        raise RuntimeError(
            "Missing Turso DEV credentials in .env"
        )

    lower_url = (
        url.lower()
    )

    if (
        "stockwave-dev"
        not in lower_url
        or
        "stockwave-prod"
        in lower_url
    ):

        raise RuntimeError(
            "SAFETY STOP: "
            "only stockwave-dev is allowed"
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
        or
        shutil.which(
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

    if result.returncode != 0:

        error = (
            result.stderr
            .decode(
                "utf-8",
                errors="replace",
            )
            .strip()
        )

        raise RuntimeError(
            error
        )

    if not result.stdout:

        raise RuntimeError(
            f"Empty response: {url}"
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
# TEXT / FIELD HELPERS
# ============================================================


def decode_bytes(
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
        "Unable to decode financial payload"
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
        .replace(
            "\u3000",
            " ",
        )
        .strip()
    )


def header_key(
    value: str,
) -> str:

    return (
        clean(
            value
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
            "％",
            "%",
        )
        .replace(
            " ",
            "",
        )
    )


def get_field(
    row: dict[str, Any],
    *candidates: str,
) -> Any:

    normalized = {
        header_key(
            key
        ): value

        for key, value
        in row.items()

        if key is not None
    }

    for candidate in candidates:

        key = (
            header_key(
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

    if (
        text.startswith(
            "("
        )
        and
        text.endswith(
            ")"
        )
    ):

        text = (
            "-"
            + text[1:-1]
        )

    try:

        return float(
            text
        )

    except ValueError:

        return None


# ============================================================
# PERIOD
# ============================================================


def parse_year(
    value: Any,
) -> int:

    digits = "".join(
        ch

        for ch
        in clean(
            value
        )

        if ch.isdigit()
    )

    if not digits:

        raise RuntimeError(
            f"Unexpected fiscal year: "
            f"{value!r}"
        )

    year = int(
        digits
    )

    if year < 1911:

        year += 1911

    if not (
        2000
        <= year
        <= 2200
    ):

        raise RuntimeError(
            f"Invalid fiscal year: "
            f"{value!r}"
        )

    return year


def parse_quarter(
    value: Any,
) -> int:

    digits = "".join(
        ch

        for ch
        in clean(
            value
        )

        if ch.isdigit()
    )

    if not digits:

        raise RuntimeError(
            f"Unexpected fiscal quarter: "
            f"{value!r}"
        )

    quarter = int(
        digits
    )

    if quarter not in (
        1,
        2,
        3,
        4,
    ):

        raise RuntimeError(
            f"Invalid fiscal quarter: "
            f"{value!r}"
        )

    return quarter


def period_key(
    year: int,
    quarter: int,
) -> int:

    return (
        year * 4
        + quarter
    )


def period_text(
    year: int,
    quarter: int,
) -> str:

    return (
        f"{year:04d}-Q{quarter}"
    )


# ============================================================
# SOURCE DATE
# ============================================================


def parse_source_date(
    value: Any,
) -> str | None:

    text = clean(
        value
    )

    if not text:

        return None

    digits = "".join(
        ch

        for ch
        in text

        if ch.isdigit()
    )

    try:

        if len(
            digits
        ) == 8:

            year = int(
                digits[:4]
            )

            month = int(
                digits[4:6]
            )

            day = int(
                digits[6:8]
            )

        elif len(
            digits
        ) == 7:

            year = (
                int(
                    digits[:3]
                )
                + 1911
            )

            month = int(
                digits[3:5]
            )

            day = int(
                digits[5:7]
            )

        else:

            parts = (
                text
                .replace(
                    ".",
                    "/",
                )
                .replace(
                    "-",
                    "/",
                )
                .split(
                    "/"
                )
            )

            if len(
                parts
            ) != 3:

                return None

            year = int(
                parts[0]
            )

            month = int(
                parts[1]
            )

            day = int(
                parts[2]
            )

            if year < 1911:

                year += 1911

        return date(
            year,
            month,
            day,
        ).isoformat()

    except ValueError:

        return None


# ============================================================
# NORMALIZATION
# ============================================================


def calc_pct(
    numerator: float | None,
    denominator: float | None,
) -> float | None:

    if (
        numerator is None
        or
        denominator is None
        or
        denominator == 0
    ):

        return None

    return round(
        numerator
        /
        denominator
        *
        100.0,
        6,
    )


def normalize_row(
    raw: dict[str, Any],
    market: str,
    source: str,
) -> FinancialRow:

    stock_id = clean(
        get_field(
            raw,
            "公司代號",
            "SecuritiesCompanyCode",
        )
    )

    if not stock_id:

        raise RuntimeError(
            f"{market}: "
            "missing 公司代號"
        )

    year = parse_year(
        get_field(
            raw,
            "年度",
            "Year",
        )
    )

    quarter = parse_quarter(
        get_field(
            raw,
            "季別",
            "Season",
            "Quarter",
        )
    )

    revenue = parse_number(
        get_field(
            raw,
            "營業收入",
        )
    )

    gross_profit = parse_number(
        get_field(
            raw,

            "營業毛利（毛損）",
            "營業毛利(毛損)",

            "營業毛利（毛損）淨額",
            "營業毛利(毛損)淨額",

            "營業毛利淨額（毛損）",
            "營業毛利淨額(毛損)",
        )
    )

    operating_income = parse_number(
        get_field(
            raw,

            "營業利益（損失）",
            "營業利益(損失)",
        )
    )

    net_income = parse_number(
        get_field(
            raw,

            "本期淨利（淨損）",
            "本期淨利(淨損)",
        )
    )

    eps = parse_number(
        get_field(
            raw,

            "基本每股盈餘（元）",
            "基本每股盈餘(元)",
            "基本每股盈餘",
        )
    )

    required = {
        "營業收入":
            revenue,

        "營業毛利":
            gross_profit,

        "營業利益":
            operating_income,

        "本期淨利":
            net_income,
    }

    for (
        label,
        value,
    ) in required.items():

        if value is None:

            raise RuntimeError(
                f"{market} "
                f"{stock_id}: "
                f"missing {label}"
            )

    return FinancialRow(
        stock_id=stock_id,
        market=market,

        fiscal_year=year,
        fiscal_quarter=quarter,

        revenue=revenue,
        gross_profit=gross_profit,
        operating_income=operating_income,
        net_income=net_income,
        eps=eps,

        gross_margin_pct=(
            calc_pct(
                gross_profit,
                revenue,
            )
        ),

        operating_margin_pct=(
            calc_pct(
                operating_income,
                revenue,
            )
        ),

        net_margin_pct=(
            calc_pct(
                net_income,
                revenue,
            )
        ),

        source=source,

        source_date=(
            parse_source_date(
                get_field(
                    raw,

                    "出表日期",
                    "資料日期",
                    "Date",
                )
            )
        ),
    )


# ============================================================
# SOURCE PARSER
# ============================================================


def make_source_result(
    market: str,
    source: str,
    raw_rows: list[
        dict[str, Any]
    ],
) -> SourceResult:

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
            f"{market} "
            "financial source count "
            "too low: "
            f"{len(raw_rows):,}"
        )

    rows: dict[
        str,
        FinancialRow,
    ] = {}

    periods: set[
        tuple[
            int,
            int,
        ]
    ] = set()

    for raw in raw_rows:

        row = normalize_row(
            raw,
            market,
            source,
        )

        if row.stock_id in rows:

            raise RuntimeError(
                f"{market} duplicate "
                f"stock_id="
                f"{row.stock_id}"
            )

        rows[
            row.stock_id
        ] = row

        periods.add(
            (
                row.fiscal_year,
                row.fiscal_quarter,
            )
        )

    if len(
        periods
    ) != 1:

        raise RuntimeError(
            f"{market} source "
            "contains multiple periods: "
            f"{sorted(periods)}"
        )

    (
        year,
        quarter,
    ) = next(
        iter(
            periods
        )
    )

    return SourceResult(
        market=market,
        source=source,
        raw_count=len(
            raw_rows
        ),

        fiscal_year=year,
        fiscal_quarter=quarter,

        rows=rows,
    )


def parse_csv_source(
    data: bytes,
    market: str,
    source: str,
) -> SourceResult:

    text = decode_bytes(
        data
    )

    lower = (
        text
        .lstrip()
        .lower()
    )

    if (
        lower.startswith(
            "<html"
        )
        or
        lower.startswith(
            "<!doctype"
        )
    ):

        raise RuntimeError(
            f"{market} "
            "financial CSV "
            "returned HTML"
        )

    raw_rows = list(
        csv.DictReader(
            io.StringIO(
                text
            )
        )
    )

    return make_source_result(
        market,
        source,
        raw_rows,
    )


def parse_twse_openapi(
    data: bytes,
) -> SourceResult:

    text = decode_bytes(
        data
    )

    if (
        text
        .lstrip()
        .startswith(
            "<"
        )
    ):

        raise RuntimeError(
            "TWSE Financial OpenAPI "
            "returned HTML"
        )

    try:

        payload = json.loads(
            text
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "TWSE Financial OpenAPI "
            f"invalid JSON: {exc}"
        ) from exc

    if not isinstance(
        payload,
        list,
    ):

        raise RuntimeError(
            "TWSE Financial OpenAPI "
            "response is not array"
        )

    raw_rows = [
        row

        for row
        in payload

        if isinstance(
            row,
            dict,
        )
    ]

    return make_source_result(
        "TWSE",

        (
            "TWSE_OPENAPI_"
            "T187AP06_L_CI_"
            "CUMULATIVE"
        ),

        raw_rows,
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

            "TWSE",

            (
                "TWSE_MOPS_CSV_"
                "T187AP06_L_CI_"
                "CUMULATIVE"
            ),
        )

    except Exception as exc:

        print(
            "    [WARN] "
            "TWSE MOPS CSV failed: "
            f"{exc}"
        )

        print(
            "    Falling back to "
            "TWSE OpenAPI ..."
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

        "TPEX",

        (
            "TPEX_MOPS_CSV_"
            "T187AP06_O_CI_"
            "CUMULATIVE"
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
        WHERE schema_key = 'schema_version'
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


def prepare_rows(
    conn,
    result: SourceResult,
) -> tuple[
    list[FinancialRow],
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

    coverage = (
        len(
            rows
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
            f"{result.market} "
            "quarterly financial "
            "coverage too low: "
            f"{coverage:.2%} "
            f"({len(rows):,}/"
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
# CURSOR
# ============================================================


def latest_period(
    conn,
    market: str,
) -> tuple[
    int,
    int,
] | None:

    row = (
        conn.execute(
            """
            SELECT
                q.fiscal_year,
                q.fiscal_quarter

            FROM quarterly_financial q

            INNER JOIN stock_master s
                ON s.stock_id =
                   q.stock_id

            WHERE s.market = ?
              AND q.report_type =
                  'GENERAL'

            ORDER BY
                q.fiscal_year DESC,
                q.fiscal_quarter DESC

            LIMIT 1
            """,
            (
                market,
            ),
        )
        .fetchone()
    )

    if row is None:

        return None

    return (
        int(
            row[0]
        ),

        int(
            row[1]
        ),
    )


def gap_semantics(
    market: str,

    cursor: tuple[
        int,
        int,
    ] | None,

    year: int,
    quarter: int,
) -> str:

    if cursor is None:

        return (
            "EMPTY -> SEED_LATEST"
        )

    gap = (
        period_key(
            year,
            quarter,
        )
        -
        period_key(
            *cursor
        )
    )

    if gap < 0:

        raise RuntimeError(
            f"{market} cursor "
            f"{period_text(*cursor)} "
            "is newer than source "
            f"{period_text(year, quarter)}"
        )

    if gap == 0:

        return (
            "UP_TO_DATE"
        )

    if gap == 1:

        return (
            "ADJACENT_QUARTER"
        )

    raise RuntimeError(
        f"{market} quarterly gap "
        "detected: "
        f"cursor="
        f"{period_text(*cursor)}, "
        f"source="
        f"{period_text(year, quarter)}, "
        f"gap={gap} quarters. "
        "Historical gap recovery required."
    )


# ============================================================
# INSERT
# ============================================================


INSERT_PREFIX = """
INSERT INTO quarterly_financial (
    stock_id,
    fiscal_year,
    fiscal_quarter,
    report_type,

    revenue,
    gross_profit,
    operating_income,
    net_income,
    eps,

    gross_margin_pct,
    operating_margin_pct,
    net_margin_pct,

    source,
    source_date,

    created_at,
    updated_at
)
VALUES
"""


INSERT_VALUE = """
(
    ?, ?, ?, ?,
    ?, ?, ?, ?, ?,
    ?, ?, ?,
    ?, ?,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
"""


INSERT_SUFFIX = """
ON CONFLICT(
    stock_id,
    fiscal_year,
    fiscal_quarter
)
DO UPDATE SET

    report_type =
        excluded.report_type,

    revenue =
        excluded.revenue,

    gross_profit =
        excluded.gross_profit,

    operating_income =
        excluded.operating_income,

    net_income =
        excluded.net_income,

    eps =
        excluded.eps,

    gross_margin_pct =
        excluded.gross_margin_pct,

    operating_margin_pct =
        excluded.operating_margin_pct,

    net_margin_pct =
        excluded.net_margin_pct,

    source =
        excluded.source,

    source_date =
        excluded.source_date,

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


def flatten(
    rows: list[
        FinancialRow
    ],
) -> tuple[
    Any,
    ...,
]:

    values: list[Any] = []

    for row in rows:

        values.extend(
            row.values()
        )

    return tuple(
        values
    )


# ============================================================
# SYNC STATE
# ============================================================


def update_sync_state(
    conn,
    market: str,
    year: int,
    quarter: int,
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
            DATASETS[
                market
            ],

            period_text(
                year,
                quarter,
            ),

            count,
        ),
    )


# ============================================================
# WRITE
# ============================================================


def write_market(
    conn,
    market: str,
    rows: list[
        FinancialRow
    ],
    year: int,
    quarter: int,
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
            BATCH_SIZE,
        ):

            batch = rows[
                start:
                start
                + BATCH_SIZE
            ]

            conn.execute(
                build_insert_sql(
                    len(
                        batch
                    )
                ),

                flatten(
                    batch
                ),
            )

        update_sync_state(
            conn,
            market,
            year,
            quarter,
            len(
                rows
            ),
        )

        conn.commit()

    except BaseException:

        try:

            conn.rollback()

        except Exception:
            pass

        raise


def verify(
    conn,
    market: str,
    year: int,
    quarter: int,
) -> int:

    value = scalar(
        conn,
        """
        SELECT COUNT(*)

        FROM quarterly_financial q

        INNER JOIN stock_master s
            ON s.stock_id =
               q.stock_id

        WHERE s.market = ?
          AND q.report_type =
              'GENERAL'
          AND q.fiscal_year = ?
          AND q.fiscal_quarter = ?
        """,
        (
            market,
            year,
            quarter,
        ),
    )

    return int(
        value
        or 0
    )


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    configure_console()

    options = (
        parse_args()
    )

    print(
        "=" * 76
    )

    print(
        "StockWaveScanner V2 - "
        "Quarterly Financial Incremental Pipeline"
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

        print(
            "Scope       : "
            "GENERAL industry only"
        )

        print(
            "Semantics   : "
            "Official cumulative quarterly filing"
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
                "Downloading latest official "
                "Quarterly Financial ..."
            )

            started = (
                time.perf_counter()
            )

            twse = load_twse()
            tpex = load_tpex()

            twse_period = (
                twse.fiscal_year,
                twse.fiscal_quarter,
            )

            tpex_period = (
                tpex.fiscal_year,
                tpex.fiscal_quarter,
            )

            if (
                twse_period
                !=
                tpex_period
            ):

                raise RuntimeError(
                    "Source period mismatch: "
                    f"TWSE="
                    f"{period_text(*twse_period)}, "
                    f"TPEX="
                    f"{period_text(*tpex_period)}"
                )

            (
                twse_rows,
                twse_excluded,
                twse_coverage,
            ) = prepare_rows(
                conn,
                twse,
            )

            (
                tpex_rows,
                tpex_excluded,
                tpex_coverage,
            ) = prepare_rows(
                conn,
                tpex,
            )

            (
                year,
                quarter,
            ) = twse_period

            print(
                f"TWSE | source="
                f"{twse.source} "
                f"| raw="
                f"{twse.raw_count:,} "
                f"| eligible="
                f"{len(twse_rows):,} "
                f"| excluded="
                f"{twse_excluded:,} "
                f"| coverage="
                f"{twse_coverage:.2%} "
                f"| missing_eps="
                f"{sum(row.eps is None for row in twse_rows):,}"
            )

            print(
                f"TPEX | source="
                f"{tpex.source} "
                f"| raw="
                f"{tpex.raw_count:,} "
                f"| eligible="
                f"{len(tpex_rows):,} "
                f"| excluded="
                f"{tpex_excluded:,} "
                f"| coverage="
                f"{tpex_coverage:.2%} "
                f"| missing_eps="
                f"{sum(row.eps is None for row in tpex_rows):,}"
            )

            print()

            print(
                "[PASS] Official source fetch"
            )

            print(
                "[PASS] Source schema validation"
            )

            print(
                "[PASS] Fiscal period normalization"
            )

            print(
                "[PASS] COMMON_STOCK filtering"
            )

            print(
                "[PASS] Margin derivation"
            )

            print(
                "Source Elapsed : "
                f"{time.perf_counter() - started:.1f}s"
            )

            cursors = {
                "TWSE":
                    latest_period(
                        conn,
                        "TWSE",
                    ),

                "TPEX":
                    latest_period(
                        conn,
                        "TPEX",
                    ),
            }

            semantics = {
                market:
                    gap_semantics(
                        market,

                        cursors[
                            market
                        ],

                        year,
                        quarter,
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
                "QUARTERLY FINANCIAL "
                "INCREMENTAL CURSOR"
            )

            print(
                "=" * 76
            )

            print(
                "Official Period : "
                f"{period_text(year, quarter)}"
            )

            for market in (
                "TWSE",
                "TPEX",
            ):

                cursor = (
                    cursors[
                        market
                    ]
                )

                print(
                    f"{market} Last Period : "
                    f"{period_text(*cursor) if cursor else 'EMPTY'}"
                )

                print(
                    f"{market} Semantics   : "
                    f"{semantics[market]}"
                )

            print()

            print(
                "[WARN] Scope currently "
                "covers GENERAL industry only."
            )

            print(
                "[WARN] Financial holding / bank / "
                "insurance / securities / other "
                "specialized schemas remain pending."
            )

            print(
                "[WARN] Missing specialized financial "
                "companies must not be treated as "
                "negative fundamentals."
            )

            print(
                "[WARN] t187ap06 is a cumulative "
                "income-statement snapshot for "
                "the filing quarter."
            )

            print(
                "[WARN] Historical 8-quarter backfill "
                "remains a separate task."
            )

            # ================================================
            # READ ONLY
            # ================================================

            if options.validate_only:

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
                    "QUARTERLY FINANCIAL "
                    "PIPELINE OK"
                )

                print(
                    "=" * 76
                )

                return 0

            # ================================================
            # WRITE
            # ================================================

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
                        f"[PASS] "
                        f"{market} "
                        f"{period_text(year, quarter)} "
                        "already synchronized"
                    )

                    continue

                print()

                print(
                    f"Writing {market} "
                    "Quarterly Financial "
                    f"{period_text(year, quarter)} ..."
                )

                write_started = (
                    time.perf_counter()
                )

                write_market(
                    conn,
                    market,

                    rows_by_market[
                        market
                    ],

                    year,
                    quarter,
                )

                written[
                    market
                ] = verify(
                    conn,
                    market,
                    year,
                    quarter,
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
                        f"{market} "
                        "DB verify mismatch: "
                        f"{written[market]:,} "
                        "!= "
                        f"{len(rows_by_market[market]):,}"
                    )

                print(
                    f"[PASS] "
                    f"{market} rows="
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
                "QUARTERLY FINANCIAL RESULT"
            )

            print(
                "=" * 76
            )

            print(
                "Period       : "
                f"{period_text(year, quarter)}"
            )

            print(
                "Report Type  : GENERAL"
            )

            print(
                "TWSE Rows    : "
                f"{written['TWSE']:,}"
            )

            print(
                "TPEx Rows    : "
                f"{written['TPEX']:,}"
            )

            print(
                "PROD Access  : DISABLED"
            )

        finally:

            conn.close()

        print()

        print(
            "=" * 76
        )

        print(
            "QUARTERLY FINANCIAL "
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