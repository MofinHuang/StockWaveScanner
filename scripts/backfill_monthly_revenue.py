from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import libsql
from dotenv import load_dotenv


# ============================================================
# BASIC CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

DEFAULT_FROM_MONTH = "2024-09"
DEFAULT_TO_MONTH = "2026-08"

TIMEOUT = 60

HTTP_RETRY_DELAYS = (
    0,
    2,
    5,
)

REQUEST_INTERVAL_SECONDS = 0.20

SQL_ROWS_PER_STATEMENT = 200

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36 "
    "StockWaveScanner-V2-Monthly-Revenue-Backfill/1.0"
)


# ============================================================
# OFFICIAL MOPS HISTORICAL SOURCE
# ============================================================

MOPS_BASE_URL = (
    "https://mopsov.twse.com.tw/"
    "nas/t21/{market}/"
    "t21sc03_{roc_year}_{month}_{company_type}.html"
)

MARKET_PATH = {
    "TWSE": "sii",
    "TPEX": "otc",
}

SOURCE_NAME = {
    "TWSE": "MOPS_T21_SII_HISTORICAL",
    "TPEX": "MOPS_T21_OTC_HISTORICAL",
}


# ============================================================
# VALIDATION
# ============================================================

#
# These are deliberately lower than current market counts.
#
# Historical months may contain fewer companies because:
# - later IPOs did not yet exist;
# - companies may have delisted;
# - stock_master preserves historical/inactive companies.
#
# The purpose of this threshold is detecting a broken HTML
# parser / blocked page, not requiring 2026 market coverage
# for a 2024 month.
#

MIN_COMMON_ROWS = {
    "TWSE": 800,
    "TPEX": 650,
}


SYNC_DATASETS = {
    "TWSE": "monthly_revenue_backfill_twse",
    "TPEX": "monthly_revenue_backfill_tpex",
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
class MonthMarketResult:

    market: str
    revenue_month: str

    domestic_count: int
    foreign_count: int

    source_count: int
    common_count: int
    excluded_count: int

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
            "Backfill official MOPS monthly revenue "
            "history into Turso DEV."
        )
    )

    parser.add_argument(
        "--from-month",
        default=DEFAULT_FROM_MONTH,
        help=(
            "First month YYYY-MM. "
            f"Default: {DEFAULT_FROM_MONTH}"
        ),
    )

    parser.add_argument(
        "--to-month",
        default=DEFAULT_TO_MONTH,
        help=(
            "Last month YYYY-MM. "
            f"Default: {DEFAULT_TO_MONTH}"
        ),
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help=(
            "Fetch and validate all months "
            "without writing Turso."
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

    if not url:

        raise RuntimeError(
            "TURSO_DEV_DATABASE_URL "
            "is missing"
        )

    if not token:

        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN "
            "is missing"
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
            "database is not stockwave-dev"
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
# MONTH HELPERS
# ============================================================


MONTH_PATTERN = re.compile(
    r"^\d{4}-\d{2}$"
)


def parse_month(
    value: str,
) -> tuple[int, int]:

    value = (
        value.strip()
    )

    if not MONTH_PATTERN.match(
        value
    ):

        raise RuntimeError(
            "Month must use YYYY-MM: "
            f"{value!r}"
        )

    year = int(
        value[:4]
    )

    month = int(
        value[5:7]
    )

    if not 1 <= month <= 12:

        raise RuntimeError(
            f"Invalid month: {value}"
        )

    if not 2000 <= year <= 2200:

        raise RuntimeError(
            f"Invalid year: {value}"
        )

    return (
        year,
        month,
    )


def month_index(
    value: str,
) -> int:

    (
        year,
        month,
    ) = parse_month(
        value
    )

    return (
        year * 12
        +
        month
    )


def format_month(
    year: int,
    month: int,
) -> str:

    return (
        f"{year:04d}-"
        f"{month:02d}"
    )


def month_range(
    start: str,
    end: str,
) -> list[str]:

    start_index = (
        month_index(
            start
        )
    )

    end_index = (
        month_index(
            end
        )
    )

    if (
        start_index
        >
        end_index
    ):

        raise RuntimeError(
            "--from-month must not "
            "be later than --to-month"
        )

    result: list[str] = []

    current = (
        start_index
    )

    while (
        current
        <=
        end_index
    ):

        year = (
            (current - 1)
            // 12
        )

        month = (
            (current - 1)
            % 12
            + 1
        )

        result.append(
            format_month(
                year,
                month,
            )
        )

        current += 1

    return result


def to_roc_year(
    year: int,
) -> int:

    roc_year = (
        year
        - 1911
    )

    if roc_year <= 0:

        raise RuntimeError(
            f"Invalid ROC year: {year}"
        )

    return roc_year


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
                    "text/html,"
                    "application/xhtml+xml,"
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

            "-H",
            (
                "Accept: "
                "text/html,"
                "application/xhtml+xml,"
                "text/plain,*/*"
            ),

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
) -> bytes:

    errors: list[str] = []

    #
    # MOPS works particularly well through
    # Windows curl / Schannel in our current project.
    #

    loaders = (
        fetch_curl,
        fetch_urllib,
    )

    for (
        attempt,
        delay,
    ) in enumerate(
        HTTP_RETRY_DELAYS,
        start=1,
    ):

        if delay:

            time.sleep(
                delay
            )

        for loader in loaders:

            try:

                data = loader(
                    url
                )

                time.sleep(
                    REQUEST_INTERVAL_SECONDS
                )

                return data

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
                "      retrying HTTP "
                f"({attempt}/"
                f"{len(HTTP_RETRY_DELAYS)}) ..."
            )

    raise RuntimeError(
        " | ".join(
            errors[-6:]
        )
    )


# ============================================================
# ENCODING
# ============================================================


def decode_mops_html(
    data: bytes,
) -> str:

    #
    # Historical T21 pages are traditionally Big5 / CP950.
    #
    # Try CP950 first because it contains a few characters
    # beyond strict Big5.
    #

    for encoding in (
        "cp950",
        "big5",
        "utf-8-sig",
        "utf-8",
    ):

        try:

            text = (
                data.decode(
                    encoding
                )
            )

            if (
                "<html"
                in text.lower()
                or
                "<table"
                in text.lower()
            ):

                return text

        except UnicodeDecodeError:
            continue

    #
    # Last-resort diagnostic decoding.
    #

    text = (
        data.decode(
            "cp950",
            errors="replace",
        )
    )

    if (
        "<html"
        not in text.lower()
        and
        "<table"
        not in text.lower()
    ):

        raise RuntimeError(
            "MOPS response does not "
            "appear to be HTML"
        )

    return text


# ============================================================
# HTML TABLE PARSER
# ============================================================


def normalize_html_text(
    value: str,
) -> str:

    value = (
        html.unescape(
            value
        )
    )

    value = (
        value
        .replace(
            "\u3000",
            " ",
        )
        .replace(
            "\xa0",
            " ",
        )
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return (
        value.strip()
    )


class RowParser(
    HTMLParser
):

    def __init__(
        self,
    ) -> None:

        super().__init__(
            convert_charrefs=True
        )

        self.rows: list[
            list[str]
        ] = []

        self._in_row = False
        self._in_cell = False

        self._row: list[str] = []
        self._cell: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs,
    ) -> None:

        tag = (
            tag.lower()
        )

        if tag == "tr":

            self._in_row = True
            self._row = []

        elif (
            self._in_row
            and
            tag in (
                "td",
                "th",
            )
        ):

            self._in_cell = True
            self._cell = []

        elif (
            self._in_cell
            and
            tag == "br"
        ):

            self._cell.append(
                " "
            )

    def handle_data(
        self,
        data: str,
    ) -> None:

        if self._in_cell:

            self._cell.append(
                data
            )

    def handle_endtag(
        self,
        tag: str,
    ) -> None:

        tag = (
            tag.lower()
        )

        if (
            tag
            in (
                "td",
                "th",
            )
            and
            self._in_cell
        ):

            self._row.append(
                normalize_html_text(
                    "".join(
                        self._cell
                    )
                )
            )

            self._cell = []
            self._in_cell = False

        elif (
            tag == "tr"
            and
            self._in_row
        ):

            if self._row:

                self.rows.append(
                    self._row
                )

            self._row = []
            self._in_row = False
            self._in_cell = False
            self._cell = []


# ============================================================
# VALUE PARSING
# ============================================================


SECURITY_CODE_PATTERN = re.compile(
    r"^[0-9A-Za-z]{4,8}$"
)


def clean_number_text(
    value: Any,
) -> str:

    return (
        str(
            value
            if value is not None
            else ""
        )
        .strip()
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


def parse_number(
    value: Any,
) -> float | None:

    text = (
        clean_number_text(
            value
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
            +
            text[1:-1]
        )

    try:

        return float(
            text
        )

    except ValueError:

        return None


# ============================================================
# HISTORICAL ROW PARSER
# ============================================================


def parse_company_row(
    cells: list[str],
    *,
    market: str,
    revenue_month: str,
) -> RevenueRow | None:

    #
    # Normal historical MOPS layout:
    #
    # 0 公司代號
    # 1 公司名稱
    # 2 當月營收
    # 3 上月營收
    # 4 去年當月營收
    # 5 上月比較增減(%)
    # 6 去年同月增減(%)
    # 7 當月累計營收
    # 8 去年累計營收
    # 9 前期比較增減(%)
    # 10 備註
    #
    # Some HTML tables may contain a leading structural cell,
    # so inspect the first few cells rather than hard-coding
    # company code at column zero.
    #

    max_start = min(
        3,
        len(
            cells
        ),
    )

    for start in range(
        max_start
    ):

        stock_id = (
            cells[
                start
            ]
            .strip()
        )

        if not SECURITY_CODE_PATTERN.fullmatch(
            stock_id
        ):

            continue

        if (
            len(
                cells
            )
            <
            start
            + 10
        ):

            continue

        stock_name = (
            cells[
                start
                + 1
            ]
            .strip()
        )

        revenue = parse_number(
            cells[
                start
                + 2
            ]
        )

        mom = parse_number(
            cells[
                start
                + 5
            ]
        )

        yoy = parse_number(
            cells[
                start
                + 6
            ]
        )

        cumulative = parse_number(
            cells[
                start
                + 7
            ]
        )

        cumulative_yoy = parse_number(
            cells[
                start
                + 9
            ]
        )

        #
        # Avoid interpreting unrelated numeric rows
        # as securities.
        #

        if (
            not stock_name
            or
            revenue is None
            or
            cumulative is None
        ):

            continue

        return RevenueRow(
            stock_id=stock_id,

            market=market,

            revenue_month=(
                revenue_month
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

            source=(
                SOURCE_NAME[
                    market
                ]
            ),
        )

    return None


def parse_historical_page(
    data: bytes,
    *,
    market: str,
    revenue_month: str,
) -> dict[
    str,
    RevenueRow,
]:

    text = (
        decode_mops_html(
            data
        )
    )

    lower = (
        text.lower()
    )

    if (
        "access denied"
        in lower
        or
        "service unavailable"
        in lower
    ):

        raise RuntimeError(
            "MOPS returned an "
            "error/block page"
        )

    parser = (
        RowParser()
    )

    parser.feed(
        text
    )

    result: dict[
        str,
        RevenueRow,
    ] = {}

    for cells in parser.rows:

        row = (
            parse_company_row(
                cells,

                market=market,

                revenue_month=(
                    revenue_month
                ),
            )
        )

        if row is None:

            continue

        if (
            row.stock_id
            in result
        ):

            raise RuntimeError(
                f"{market} "
                f"{revenue_month}: "
                "duplicate stock_id "
                f"{row.stock_id} "
                "inside one MOPS page"
            )

        result[
            row.stock_id
        ] = row

    return result


# ============================================================
# URL
# ============================================================


def historical_url(
    *,
    market: str,
    revenue_month: str,
    company_type: int,
) -> str:

    (
        year,
        month,
    ) = parse_month(
        revenue_month
    )

    if company_type not in (
        0,
        1,
    ):

        raise RuntimeError(
            "company_type must be 0 or 1"
        )

    return (
        MOPS_BASE_URL.format(
            market=(
                MARKET_PATH[
                    market
                ]
            ),

            roc_year=(
                to_roc_year(
                    year
                )
            ),

            month=month,

            company_type=(
                company_type
            ),
        )
    )


# ============================================================
# DATABASE HELPERS
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


def common_stock_ids(
    conn,
    market: str,
) -> set[str]:

    #
    # IMPORTANT:
    #
    # Do NOT restrict this historical backfill to is_active=1.
    #
    # Historical/inactive COMMON_STOCK records are retained so
    # future backtests do not unnecessarily introduce current-
    # survivor-only bias.
    #

    rows = (
        conn.execute(
            """
            SELECT stock_id

            FROM stock_master

            WHERE market = ?
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


def current_monthly_revenue_range(
    conn,
) -> tuple[
    str | None,
    str | None,
    int,
]:

    row = (
        conn.execute(
            """
            SELECT
                MIN(
                    revenue_month
                ),
                MAX(
                    revenue_month
                ),
                COUNT(*)

            FROM monthly_revenue
            """
        )
        .fetchone()
    )

    if row is None:

        return (
            None,
            None,
            0,
        )

    return (
        (
            None
            if row[0]
            is None
            else str(
                row[0]
            )
        ),

        (
            None
            if row[1]
            is None
            else str(
                row[1]
            )
        ),

        int(
            row[2]
            or 0
        ),
    )


# ============================================================
# FETCH ONE MARKET / MONTH
# ============================================================


def fetch_month_market(
    *,
    market: str,
    revenue_month: str,
    universe: set[str],
) -> MonthMarketResult:

    combined: dict[
        str,
        RevenueRow,
    ] = {}

    counts: dict[
        int,
        int,
    ] = {}

    for company_type in (
        0,
        1,
    ):

        url = (
            historical_url(
                market=market,

                revenue_month=(
                    revenue_month
                ),

                company_type=(
                    company_type
                ),
            )
        )

        data = fetch(
            url
        )

        rows = (
            parse_historical_page(
                data,

                market=market,

                revenue_month=(
                    revenue_month
                ),
            )
        )

        counts[
            company_type
        ] = len(
            rows
        )

        for (
            stock_id,
            row,
        ) in rows.items():

            if (
                stock_id
                in combined
            ):

                raise RuntimeError(
                    f"{market} "
                    f"{revenue_month}: "
                    f"{stock_id} appears "
                    "in both domestic and "
                    "foreign-company pages"
                )

            combined[
                stock_id
            ] = row

    selected = {
        stock_id: row

        for (
            stock_id,
            row,
        ) in combined.items()

        if stock_id
        in universe
    }

    excluded_count = (
        len(
            combined
        )
        -
        len(
            selected
        )
    )

    if (
        len(
            selected
        )
        <
        MIN_COMMON_ROWS[
            market
        ]
    ):

        raise RuntimeError(
            f"{market} "
            f"{revenue_month}: "
            "COMMON_STOCK row count "
            "too small: "
            f"{len(selected):,} "
            "< "
            f"{MIN_COMMON_ROWS[market]:,}"
        )

    return MonthMarketResult(
        market=market,

        revenue_month=(
            revenue_month
        ),

        domestic_count=(
            counts.get(
                0,
                0,
            )
        ),

        foreign_count=(
            counts.get(
                1,
                0,
            )
        ),

        source_count=(
            len(
                combined
            )
        ),

        common_count=(
            len(
                selected
            )
        ),

        excluded_count=(
            excluded_count
        ),

        rows=selected,
    )


# ============================================================
# FETCH FULL RANGE
# ============================================================


def fetch_history(
    conn,
    months: list[str],
) -> tuple[
    list[RevenueRow],
    dict[
        tuple[
            str,
            str,
        ],
        MonthMarketResult,
    ],
]:

    universe = {
        "TWSE":
            common_stock_ids(
                conn,
                "TWSE",
            ),

        "TPEX":
            common_stock_ids(
                conn,
                "TPEX",
            ),
    }

    print(
        "Stock Master COMMON_STOCK:"
    )

    print(
        "  TWSE : "
        f"{len(universe['TWSE']):,}"
    )

    print(
        "  TPEx : "
        f"{len(universe['TPEX']):,}"
    )

    print()

    all_rows: list[
        RevenueRow
    ] = []

    results: dict[
        tuple[
            str,
            str,
        ],
        MonthMarketResult,
    ] = {}

    seen_keys: set[
        tuple[
            str,
            str,
        ]
    ] = set()

    for (
        month_number,
        revenue_month,
    ) in enumerate(
        months,
        start=1,
    ):

        print(
            f"[{month_number:02d}/"
            f"{len(months):02d}] "
            f"{revenue_month}"
        )

        for market in (
            "TWSE",
            "TPEX",
        ):

            result = (
                fetch_month_market(
                    market=market,

                    revenue_month=(
                        revenue_month
                    ),

                    universe=(
                        universe[
                            market
                        ]
                    ),
                )
            )

            results[
                (
                    revenue_month,
                    market,
                )
            ] = result

            print(
                f"    {market:<4} "
                f"| domestic="
                f"{result.domestic_count:,} "
                f"| foreign="
                f"{result.foreign_count:,} "
                f"| source="
                f"{result.source_count:,} "
                f"| common="
                f"{result.common_count:,} "
                f"| excluded="
                f"{result.excluded_count:,}"
            )

            for row in (
                result.rows.values()
            ):

                key = (
                    row.stock_id,
                    row.revenue_month,
                )

                if key in seen_keys:

                    raise RuntimeError(
                        "Duplicate monthly revenue "
                        "key detected: "
                        f"{key}"
                    )

                seen_keys.add(
                    key
                )

                all_rows.append(
                    row
                )

    return (
        all_rows,
        results,
    )


# ============================================================
# EXISTING-LATEST CROSS CHECK
# ============================================================


def existing_month_rows(
    conn,
    revenue_month: str,
) -> dict[
    str,
    tuple[
        float | None,
        float | None,
    ],
]:

    rows = (
        conn.execute(
            """
            SELECT
                stock_id,
                revenue,
                cumulative_revenue

            FROM monthly_revenue

            WHERE revenue_month = ?
            """,
            (
                revenue_month,
            ),
        )
        .fetchall()
    )

    result: dict[
        str,
        tuple[
            float | None,
            float | None,
        ],
    ] = {}

    for row in rows:

        result[
            str(
                row[0]
            )
        ] = (
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

    return result


def numbers_equal(
    left: float | None,
    right: float | None,
) -> bool:

    if (
        left is None
        and
        right is None
    ):

        return True

    if (
        left is None
        or
        right is None
    ):

        return False

    return (
        abs(
            left
            -
            right
        )
        <= 0.5
    )


def cross_check_existing_latest(
    conn,
    *,
    fetched_rows: list[
        RevenueRow
    ],
    db_latest_month: str | None,
) -> None:

    if (
        db_latest_month
        is None
    ):

        print(
            "Existing latest cross-check : "
            "SKIPPED (DB empty)"
        )

        return

    fetched = {
        row.stock_id:
            row

        for row
        in fetched_rows

        if (
            row.revenue_month
            ==
            db_latest_month
        )
    }

    if not fetched:

        print(
            "Existing latest cross-check : "
            "SKIPPED "
            f"({db_latest_month} "
            "outside requested range)"
        )

        return

    existing = (
        existing_month_rows(
            conn,
            db_latest_month,
        )
    )

    overlap = (
        set(
            fetched
        )
        &
        set(
            existing
        )
    )

    revenue_mismatch = 0
    cumulative_mismatch = 0

    mismatch_samples: list[
        str
    ] = []

    for stock_id in sorted(
        overlap
    ):

        row = (
            fetched[
                stock_id
            ]
        )

        (
            db_revenue,
            db_cumulative,
        ) = existing[
            stock_id
        ]

        revenue_ok = (
            numbers_equal(
                row.revenue,
                db_revenue,
            )
        )

        cumulative_ok = (
            numbers_equal(
                row.cumulative_revenue,
                db_cumulative,
            )
        )

        if not revenue_ok:

            revenue_mismatch += 1

        if not cumulative_ok:

            cumulative_mismatch += 1

        if (
            (
                not revenue_ok
                or
                not cumulative_ok
            )
            and
            len(
                mismatch_samples
            )
            < 5
        ):

            mismatch_samples.append(
                stock_id
            )

    print(
        "Existing latest cross-check:"
    )

    print(
        "  Month                : "
        f"{db_latest_month}"
    )

    print(
        "  Overlap              : "
        f"{len(overlap):,}"
    )

    print(
        "  Revenue mismatch     : "
        f"{revenue_mismatch:,}"
    )

    print(
        "  Cumulative mismatch  : "
        f"{cumulative_mismatch:,}"
    )

    if mismatch_samples:

        print(
            "  Mismatch samples     : "
            + ", ".join(
                mismatch_samples
            )
        )

        print(
            "  [WARN] Historical MOPS "
            "currently differs from the "
            "previously seeded latest snapshot "
            "for these rows."
        )

        print(
            "  [WARN] Backfill UPSERT "
            "would refresh them to the current "
            "official historical values."
        )

    else:

        print(
            "  [PASS] Historical source "
            "matches existing latest snapshot"
        )


# ============================================================
# INSERT SQL
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

    values: list[
        Any
    ] = []

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
    last_month: str,
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
            SYNC_DATASETS[
                market
            ],

            last_month,

            count,
        ),
    )


# ============================================================
# WRITE
# ============================================================


def write_backfill(
    conn,
    *,
    rows: list[
        RevenueRow
    ],
    last_month: str,
) -> None:

    rows = sorted(
        rows,

        key=lambda row: (
            row.revenue_month,
            row.stock_id,
        ),
    )

    market_counts = {
        "TWSE": 0,
        "TPEX": 0,
    }

    for row in rows:

        market_counts[
            row.market
        ] += 1

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

        for market in (
            "TWSE",
            "TPEX",
        ):

            update_sync_state(
                conn,

                market=market,

                last_month=(
                    last_month
                ),

                count=(
                    market_counts[
                        market
                    ]
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


def verify_month_counts(
    conn,
    *,
    from_month: str,
    to_month: str,
) -> dict[
    str,
    int,
]:

    rows = (
        conn.execute(
            """
            SELECT
                revenue_month,
                COUNT(*)

            FROM monthly_revenue

            WHERE revenue_month >= ?
              AND revenue_month <= ?

            GROUP BY revenue_month

            ORDER BY revenue_month
            """,
            (
                from_month,
                to_month,
            ),
        )
        .fetchall()
    )

    return {
        str(
            row[0]
        ):
        int(
            row[1]
        )

        for row
        in rows
    }


# ============================================================
# SUMMARY
# ============================================================


def print_source_summary(
    months: list[str],
    results: dict[
        tuple[
            str,
            str,
        ],
        MonthMarketResult,
    ],
) -> None:

    print()

    print(
        "=" * 84
    )

    print(
        "MONTHLY REVENUE HISTORICAL SOURCE SUMMARY"
    )

    print(
        "=" * 84
    )

    print(
        "Month   | TWSE Common | TPEx Common | Total"
    )

    print(
        "-" * 84
    )

    for revenue_month in months:

        twse = (
            results[
                (
                    revenue_month,
                    "TWSE",
                )
            ]
        )

        tpex = (
            results[
                (
                    revenue_month,
                    "TPEX",
                )
            ]
        )

        total = (
            twse.common_count
            +
            tpex.common_count
        )

        print(
            f"{revenue_month} "
            f"| {twse.common_count:11,} "
            f"| {tpex.common_count:11,} "
            f"| {total:5,}"
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
        "=" * 84
    )

    print(
        "StockWaveScanner V2 - "
        "Monthly Revenue Historical Backfill"
    )

    print(
        "=" * 84
    )

    try:

        months = (
            month_range(
                args.from_month,
                args.to_month,
            )
        )

        if not months:

            raise RuntimeError(
                "No months selected"
            )

        url, token = (
            load_dev_credentials()
        )

        print(
            "Target        : DEV"
        )

        print(
            "Database      : "
            f"{url}"
        )

        print(
            "PROD Access   : DISABLED"
        )

        print(
            "From Month    : "
            f"{months[0]}"
        )

        print(
            "To Month      : "
            f"{months[-1]}"
        )

        print(
            "Month Count   : "
            f"{len(months)}"
        )

        print(
            "Source        : "
            "Official MOPS historical T21"
        )

        print(
            "Fetch Mode    : "
            "MONTH + MARKET batch, "
            "NOT per-stock crawler"
        )

        print(
            "Universe      : "
            "stock_master COMMON_STOCK "
            "(active + historical inactive)"
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
                "Schema        : "
                f"{version}"
            )

            print(
                "[PASS] Turso DEV connection"
            )

            (
                existing_min,
                existing_max,
                existing_count,
            ) = current_monthly_revenue_range(
                conn
            )

            print()

            print(
                "Current monthly_revenue:"
            )

            print(
                "  Min Month : "
                f"{existing_min or 'EMPTY'}"
            )

            print(
                "  Max Month : "
                f"{existing_max or 'EMPTY'}"
            )

            print(
                "  Rows      : "
                f"{existing_count:,}"
            )

            print()

            print(
                "Downloading official "
                "historical monthly revenue ..."
            )

            started = (
                time.perf_counter()
            )

            (
                fetched_rows,
                results,
            ) = fetch_history(
                conn,
                months,
            )

            source_elapsed = (
                time.perf_counter()
                -
                started
            )

            print_source_summary(
                months,
                results,
            )

            twse_total = sum(
                1

                for row
                in fetched_rows

                if row.market
                == "TWSE"
            )

            tpex_total = sum(
                1

                for row
                in fetched_rows

                if row.market
                == "TPEX"
            )

            print()

            print(
                "[PASS] All requested months fetched"
            )

            print(
                "[PASS] Duplicate key check"
            )

            print(
                "[PASS] COMMON_STOCK filtering"
            )

            print(
                "TWSE Backfill Rows : "
                f"{twse_total:,}"
            )

            print(
                "TPEx Backfill Rows : "
                f"{tpex_total:,}"
            )

            print(
                "Total Rows         : "
                f"{len(fetched_rows):,}"
            )

            print(
                "Source Elapsed     : "
                f"{source_elapsed:.1f}s"
            )

            print()

            cross_check_existing_latest(
                conn,

                fetched_rows=(
                    fetched_rows
                ),

                db_latest_month=(
                    existing_max
                ),
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
                    "[PASS] No Turso rows were written"
                )

                print(
                    "[PASS] PROD was not accessed"
                )

                print()

                print(
                    "=" * 84
                )

                print(
                    "MONTHLY REVENUE BACKFILL "
                    "VALIDATION OK"
                )

                print(
                    "=" * 84
                )

                return 0

            # =================================================
            # WRITE
            # =================================================

            print()

            print(
                "Writing Monthly Revenue history "
                "to Turso DEV ..."
            )

            write_started = (
                time.perf_counter()
            )

            write_backfill(
                conn,

                rows=(
                    fetched_rows
                ),

                last_month=(
                    months[-1]
                ),
            )

            db_counts = (
                verify_month_counts(
                    conn,

                    from_month=(
                        months[0]
                    ),

                    to_month=(
                        months[-1]
                    ),
                )
            )

            for revenue_month in months:

                expected = (
                    results[
                        (
                            revenue_month,
                            "TWSE",
                        )
                    ]
                    .common_count

                    +

                    results[
                        (
                            revenue_month,
                            "TPEX",
                        )
                    ]
                    .common_count
                )

                actual = (
                    db_counts.get(
                        revenue_month,
                        0,
                    )
                )

                #
                # >= instead of == because an earlier source or
                # manual import could legitimately contain a row
                # not present in today's historical snapshot.
                #

                if (
                    actual
                    <
                    expected
                ):

                    raise RuntimeError(
                        "DB verification failed "
                        f"for {revenue_month}: "
                        f"actual={actual:,}, "
                        f"expected_at_least="
                        f"{expected:,}"
                    )

            write_elapsed = (
                time.perf_counter()
                -
                write_started
            )

            print(
                "[PASS] Historical UPSERT completed"
            )

            print(
                "[PASS] All month counts verified"
            )

            print(
                "DB Write Elapsed : "
                f"{write_elapsed:.1f}s"
            )

            final_min, final_max, final_count = (
                current_monthly_revenue_range(
                    conn
                )
            )

            print()

            print(
                "=" * 84
            )

            print(
                "MONTHLY REVENUE BACKFILL RESULT"
            )

            print(
                "=" * 84
            )

            print(
                "DB Min Month : "
                f"{final_min}"
            )

            print(
                "DB Max Month : "
                f"{final_max}"
            )

            print(
                "DB Rows      : "
                f"{final_count:,}"
            )

            print(
                "PROD Access  : DISABLED"
            )

        finally:

            conn.close()

        print()

        print(
            "=" * 84
        )

        print(
            "MONTHLY REVENUE BACKFILL OK"
        )

        print(
            "=" * 84
        )

        return 0

    except KeyboardInterrupt:

        print()

        print(
            "INTERRUPTED"
        )

        print(
            "No PROD database was accessed."
        )

        return 130

    except Exception as exc:

        print()

        print(
            "=" * 84
        )

        print(
            "ERROR"
        )

        print(
            "=" * 84
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