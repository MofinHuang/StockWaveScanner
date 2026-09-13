from __future__ import annotations

import argparse
import html
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

STAGE_DB = ROOT / "runtime" / "quarterly_financial_backfill.db"

PERIODS = (
    (2024, 3),
    (2024, 4),
    (2025, 1),
    (2025, 2),
    (2025, 3),
    (2025, 4),
    (2026, 1),
    (2026, 2),
)

BATCH_SIZE = 10
REQUEST_INTERVAL = 0.60
TIMEOUT = 60
RETRY_DELAYS = (
    0,
    5,
    15,
    30,
    60,
)

DB_BATCH_SIZE = 100

REPORT_TYPE = "GENERAL"

SOURCE = (
    "MOPSFIN_INCOME_STATEMENT_CUMULATIVE"
)

REPORT_URL = (
    "https://mopsfin.twse.com.tw/"
    "compare/report"
)

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36"
)

MIN_ROWS = {
    "TWSE": 800,
    "TPEX": 650,
}

SYNC_DATASET = {
    "TWSE":
        "quarterly_financial_backfill_twse_general",

    "TPEX":
        "quarterly_financial_backfill_tpex_general",
}

FIELD_LABELS = {
    "revenue": (
        "營業收入合計",
        "營業收入",
    ),

    "gross_profit": (
        "營業毛利（毛損）",
        "營業毛利(毛損)",

        "營業毛利（毛損）淨額",
        "營業毛利(毛損)淨額",
    ),

    "operating_income": (
        "營業利益（損失）",
        "營業利益(損失)",
    ),

    "net_income": (
        "本期淨利（淨損）",
        "本期淨利(淨損)",
    ),

    "eps": (
        "基本每股盈餘",
    ),
}


# ============================================================
# DATA MODEL
# ============================================================


@dataclass(frozen=True)
class Company:

    stock_id: str
    short_name: str
    market: str

    @property
    def form_value(
        self,
    ) -> str:

        return (
            f"{self.stock_id} "
            f"{self.short_name}"
        ).strip()


@dataclass(frozen=True)
class FinancialRow:

    stock_id: str
    market: str

    fiscal_year: int
    fiscal_quarter: int

    revenue: float
    gross_profit: float

    operating_income: float
    net_income: float

    eps: float

    gross_margin_pct: float | None
    operating_margin_pct: float | None
    net_margin_pct: float | None

    source: str = SOURCE
    source_date: str | None = None

    def stage_values(
        self,
    ) -> tuple[Any, ...]:

        return (
            self.stock_id,
            self.market,

            self.fiscal_year,
            self.fiscal_quarter,

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

    def turso_values(
        self,
    ) -> tuple[Any, ...]:

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


class NoBatchDataError(
    RuntimeError
):
    pass

class BatchSplitRequired(
    RuntimeError
):
    pass

class UnsupportedReportFormatError(
    RuntimeError
):
    pass

# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:

    parser = (
        argparse.ArgumentParser()
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
    )

    return (
        parser.parse_args()
    )


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
            "Missing Turso DEV credentials"
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
# VALUE HELPERS
# ============================================================


def normalize_text(
    value: str,
) -> str:

    value = (
        html.unescape(
            value
        )
        .replace(
            "\xa0",
            " ",
        )
        .replace(
            "\u3000",
            " ",
        )
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def label_key(
    value: str,
) -> str:

    return (
        normalize_text(
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
            "∕",
            "/",
        )
        .replace(
            "／",
            "/",
        )
        .replace(
            " ",
            "",
        )
    )


def parse_number(
    value: str,
) -> float | None:

    text = (
        normalize_text(
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
            +
            text[1:-1]
        )

    try:

        return float(
            text
        )

    except ValueError:

        return None


def pct(
    numerator: float,
    denominator: float,
) -> float | None:

    if denominator == 0:

        return None

    return round(
        numerator
        /
        denominator
        *
        100.0,
        6,
    )


def period_text(
    year: int,
    quarter: int,
) -> str:

    return (
        f"{year:04d}-"
        f"Q{quarter}"
    )


# ============================================================
# HTML PARSER
# ============================================================


class TableParser(
    HTMLParser
):

    def __init__(
        self,
    ) -> None:

        super().__init__(
            convert_charrefs=True
        )

        self.tables: list[
            list[
                list[str]
            ]
        ] = []

        self.depth = 0

        self.table: (
            list[
                list[str]
            ]
            | None
        ) = None

        self.row: (
            list[str]
            | None
        ) = None

        self.cell: (
            list[str]
            | None
        ) = None

    def handle_starttag(
        self,
        tag: str,
        attrs,
    ) -> None:

        tag = (
            tag.lower()
        )

        if tag == "table":

            self.depth += 1

            if (
                self.depth
                == 1
            ):

                self.table = []

            return

        if self.depth == 0:

            return

        if tag == "tr":

            if self.row is None:

                self.row = []

        elif (
            tag
            in (
                "td",
                "th",
            )
            and
            self.row
            is not None
        ):

            self.cell = []

        elif (
            tag == "br"
            and
            self.cell
            is not None
        ):

            self.cell.append(
                " "
            )

    def handle_data(
        self,
        data: str,
    ) -> None:

        if self.cell is not None:

            self.cell.append(
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
            self.cell
            is not None
            and
            self.row
            is not None
        ):

            self.row.append(
                normalize_text(
                    "".join(
                        self.cell
                    )
                )
            )

            self.cell = None

        elif (
            tag == "tr"
            and
            self.row
            is not None
        ):

            if (
                self.table
                is not None
                and
                any(
                    self.row
                )
            ):

                self.table.append(
                    self.row
                )

            self.row = None
            self.cell = None

        elif tag == "table":

            if self.depth == 1:

                if self.table:

                    self.tables.append(
                        self.table
                    )

                self.table = None

            if self.depth > 0:

                self.depth -= 1


# ============================================================
# HTTP
# ============================================================


def request_bytes(
    request: urllib.request.Request,
) -> bytes:

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

        try:

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

            time.sleep(
                REQUEST_INTERVAL
            )

            return data

        except Exception as exc:

            errors.append(
                f"attempt={attempt}: "
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
                "        retrying HTTP "
                f"({attempt}/"
                f"{len(RETRY_DELAYS)}) ..."
            )

    raise RuntimeError(
        " | ".join(
            errors
        )
    )


def post_report(
    companies: list[
        Company
    ],
    year: int,
    quarter: int,
) -> str:

    params = [
        (
            "compareItem",
            "IncomeStatement",
        ),

        (
            "ylabel",
            "",
        ),

        (
            "quarter",
            "true",
        ),

        (
            "revenue",
            "true",
        ),

        (
            "ys",
            f"{year:04d}{quarter}",
        ),

        (
            "qnumber",
            "",
        ),

        (
            "bcodeAvg",
            "false",
        ),

        (
            "companyAvg",
            "false",
        ),
    ]

    params.extend(
        (
            "companyId",
            company.form_value,
        )

        for company
        in companies
    )

    body = (
        urllib.parse.urlencode(
            params
        )
        .encode(
            "utf-8"
        )
    )

    request = urllib.request.Request(
        REPORT_URL,

        data=body,

        headers={
            "User-Agent":
                USER_AGENT,

            "Accept":
                "text/html, */*; q=0.01",

            "Content-Type":
                "application/"
                "x-www-form-urlencoded; "
                "charset=UTF-8",

            "Origin":
                "https://mopsfin.twse.com.tw",

            "Referer":
                "https://mopsfin.twse.com.tw/",

            "X-Requested-With":
                "XMLHttpRequest",
        },
    )

    return (
        request_bytes(
            request
        )
        .decode(
            "utf-8",
            errors="replace",
        )
    )


# ============================================================
# TABLE IDENTIFICATION
# ============================================================


def label_score(
    table: list[
        list[str]
    ],
) -> int:

    values = {
        label_key(
            cell
        )

        for row
        in table

        for cell
        in row
    }

    return sum(
        any(
            label_key(
                label
            )
            in values

            for label
            in labels
        )

        for labels
        in FIELD_LABELS.values()
    )


def requested_count(
    table: list[
        list[str]
    ],
    requested: set[str],
) -> int:

    text = "\n".join(
        " | ".join(
            row
        )

        for row
        in table
    )

    return sum(
        stock_id in text

        for stock_id
        in requested
    )


def select_tables(
    tables: list[
        list[
            list[str]
        ]
    ],
    requested: set[str],
) -> tuple[
    list[
        list[str]
    ],
    list[
        list[str]
    ],
]:

    if len(
        tables
    ) < 2:

        raise NoBatchDataError(
            "paired tables not returned"
        )

    label_table = max(
        tables,
        key=label_score,
    )

    actual_label_score = (
        label_score(
            label_table
        )
    )

    if (
        actual_label_score
        <
        len(
            FIELD_LABELS
        )
    ):

        raise UnsupportedReportFormatError(
            "unsupported GENERAL report format "
            f"(label_score="
            f"{actual_label_score}/"
            f"{len(FIELD_LABELS)})"
        )

    candidates = [
        table

        for table
        in tables

        if table
        is not label_table
    ]

    if not candidates:

        raise NoBatchDataError(
            "value table missing"
        )

    value_table = max(
        candidates,

        key=lambda table:
            requested_count(
                table,
                requested,
            ),
    )

    if (
        requested_count(
            value_table,
            requested,
        )
        == 0
    ):

        raise NoBatchDataError(
            "no requested companies returned"
        )

    if (
        len(
            label_table
        )
        !=
        len(
            value_table
        )
    ):

        raise RuntimeError(
            "label/value table "
            "row counts differ"
        )

    return (
        label_table,
        value_table,
    )


def find_label_row(
    label_table: list[
        list[str]
    ],
    candidates: tuple[
        str,
        ...,
    ],
) -> int:

    for candidate in candidates:

        wanted = (
            label_key(
                candidate
            )
        )

        for (
            index,
            row,
        ) in enumerate(
            label_table
        ):

            if any(
                label_key(
                    cell
                )
                ==
                wanted

                for cell
                in row
            ):

                return index

    raise RuntimeError(
        "Accounting row not found: "
        +
        " / ".join(
            candidates
        )
    )


def find_company_columns(
    value_table: list[
        list[str]
    ],
    requested: set[str],
) -> dict[
    str,
    int,
]:

    for row in value_table:

        columns: dict[
            str,
            int,
        ] = {}

        for (
            column,
            cell,
        ) in enumerate(
            row
        ):

            for stock_id in requested:

                if re.search(
                    rf"(^|\D)"
                    rf"{re.escape(stock_id)}"
                    rf"(\D|$)",
                    cell,
                ):

                    columns[
                        stock_id
                    ] = column

        if columns:

            return columns

    raise NoBatchDataError(
        "company header row not found"
    )


# ============================================================
# REPORT PARSER
# ============================================================


def parse_report(
    content: str,

    companies: list[
        Company
    ],

    year: int,
    quarter: int,
) -> list[
    FinancialRow
]:

    if (
        "SECURITY REASONS"
        in content
    ):

        raise RuntimeError(
            "MopsFin SECURITY REASONS page"
        )

    parser = (
        TableParser()
    )

    parser.feed(
        content
    )

    requested = {
        company.stock_id

        for company
        in companies
    }

    (
        labels,
        values,
    ) = select_tables(
        parser.tables,
        requested,
    )

    columns = (
        find_company_columns(
            values,
            requested,
        )
    )

    row_index = {
        name:
            find_label_row(
                labels,
                candidates,
            )

        for (
            name,
            candidates,
        ) in FIELD_LABELS.items()
    }

    market_by_id = {
        company.stock_id:
            company.market

        for company
        in companies
    }

    result: list[
        FinancialRow
    ] = []

    for (
        stock_id,
        column,
    ) in sorted(
        columns.items()
    ):

        parsed: dict[
            str,
            float | None,
        ] = {}

        for (
            field,
            index,
        ) in row_index.items():

            if (
                column
                >=
                len(
                    values[
                        index
                    ]
                )
            ):

                raise RuntimeError(
                    f"{stock_id} "
                    f"{field}: "
                    "column outside row"
                )

            parsed[
                field
            ] = parse_number(
                values[
                    index
                ][
                    column
                ]
            )

        if all(
            value is None

            for value
            in parsed.values()
        ):

            continue

        missing = [
            field

            for (
                field,
                value,
            ) in parsed.items()

            if value is None
        ]

        if missing:

            raise BatchSplitRequired(
                f"{stock_id} "
                f"{period_text(year, quarter)} "
                "batch schema mismatch: "
                +
                ", ".join(
                    missing
                )
            )

        revenue = float(
            parsed[
                "revenue"
            ]
        )

        gross_profit = float(
            parsed[
                "gross_profit"
            ]
        )

        operating_income = float(
            parsed[
                "operating_income"
            ]
        )

        net_income = float(
            parsed[
                "net_income"
            ]
        )

        eps = float(
            parsed[
                "eps"
            ]
        )

        result.append(
            FinancialRow(
                stock_id=stock_id,

                market=(
                    market_by_id[
                        stock_id
                    ]
                ),

                fiscal_year=year,
                fiscal_quarter=quarter,

                revenue=revenue,

                gross_profit=(
                    gross_profit
                ),

                operating_income=(
                    operating_income
                ),

                net_income=(
                    net_income
                ),

                eps=eps,

                gross_margin_pct=(
                    pct(
                        gross_profit,
                        revenue,
                    )
                ),

                operating_margin_pct=(
                    pct(
                        operating_income,
                        revenue,
                    )
                ),

                net_margin_pct=(
                    pct(
                        net_income,
                        revenue,
                    )
                ),
            )
        )

    return result


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


def load_universe(
    conn,
    market: str,
) -> list[
    Company
]:

    latest = (
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

    if latest is None:

        raise RuntimeError(
            "quarterly_financial "
            "GENERAL seed missing"
        )

    current = (
        conn.execute(
            """
            SELECT DISTINCT

                s.stock_id,

                COALESCE(
                    NULLIF(
                        TRIM(
                            s.short_name
                        ),
                        ''
                    ),
                    s.stock_name
                )

            FROM quarterly_financial q

            INNER JOIN stock_master s
                ON s.stock_id =
                   q.stock_id

            WHERE q.fiscal_year = ?
              AND q.fiscal_quarter = ?

              AND q.report_type =
                  'GENERAL'

              AND s.market = ?

              AND s.security_type =
                  'COMMON_STOCK'
            """,
            (
                int(
                    latest[0]
                ),

                int(
                    latest[1]
                ),

                market,
            ),
        )
        .fetchall()
    )

    # --------------------------------------------------------
    # Add historical inactive non-financial common stocks.
    #
    # This avoids using only today's surviving listed stocks
    # for historical backtest data.
    # --------------------------------------------------------

    inactive = (
        conn.execute(
            """
            SELECT

                stock_id,

                COALESCE(
                    NULLIF(
                        TRIM(
                            short_name
                        ),
                        ''
                    ),
                    stock_name
                )

            FROM stock_master

            WHERE market = ?

              AND security_type =
                  'COMMON_STOCK'

              AND is_active = 0

              AND COALESCE(
                    industry_code,
                    ''
                  ) <> '17'
            """,
            (
                market,
            ),
        )
        .fetchall()
    )

    merged: dict[
        str,
        Company,
    ] = {}

    for (
        stock_id,
        short_name,
    ) in (
        list(
            current
        )
        +
        list(
            inactive
        )
    ):

        stock_id = (
            str(
                stock_id
            )
            .strip()
        )

        short_name = (
            str(
                short_name
                or
                ""
            )
            .strip()
        )

        if not re.fullmatch(
            r"\d{4}",
            stock_id,
        ):

            continue

        if not short_name:

            continue

        merged[
            stock_id
        ] = Company(
            stock_id=stock_id,

            short_name=(
                short_name
            ),

            market=market,
        )

    return sorted(
        merged.values(),

        key=lambda company:
            company.stock_id,
    )


# ============================================================
# LOCAL STAGING
# ============================================================


def open_stage(
) -> sqlite3.Connection:

    STAGE_DB.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    conn = sqlite3.connect(
        STAGE_DB
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS
        quarterly_financial_stage (

            stock_id TEXT NOT NULL,
            market TEXT NOT NULL,

            fiscal_year INTEGER NOT NULL,
            fiscal_quarter INTEGER NOT NULL,

            revenue REAL NOT NULL,
            gross_profit REAL NOT NULL,

            operating_income REAL NOT NULL,
            net_income REAL NOT NULL,

            eps REAL NOT NULL,

            gross_margin_pct REAL,
            operating_margin_pct REAL,
            net_margin_pct REAL,

            source TEXT NOT NULL,
            source_date TEXT,

            PRIMARY KEY (
                stock_id,
                fiscal_year,
                fiscal_quarter
            )
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS
        stage_complete (

            market TEXT NOT NULL,

            fiscal_year INTEGER NOT NULL,
            fiscal_quarter INTEGER NOT NULL,

            row_count INTEGER NOT NULL,

            completed_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (
                market,
                fiscal_year,
                fiscal_quarter
            )
        )
        """
    )

    conn.commit()

    return conn


def stage_complete(
    conn: sqlite3.Connection,
    market: str,
    year: int,
    quarter: int,
) -> bool:

    row = (
        conn.execute(
            """
            SELECT 1

            FROM stage_complete

            WHERE market = ?
              AND fiscal_year = ?
              AND fiscal_quarter = ?
            """,
            (
                market,
                year,
                quarter,
            ),
        )
        .fetchone()
    )

    return (
        row is not None
    )


def stage_count(
    conn: sqlite3.Connection,
    market: str,
    year: int,
    quarter: int,
) -> int:

    row = (
        conn.execute(
            """
            SELECT COUNT(*)

            FROM quarterly_financial_stage

            WHERE market = ?
              AND fiscal_year = ?
              AND fiscal_quarter = ?
            """,
            (
                market,
                year,
                quarter,
            ),
        )
        .fetchone()
    )

    return int(
        row[0]
        or 0
    )


def save_stage(
    conn: sqlite3.Connection,

    market: str,

    year: int,
    quarter: int,

    rows: list[
        FinancialRow
    ],
) -> None:

    conn.execute(
        "BEGIN"
    )

    try:

        conn.execute(
            """
            DELETE FROM
                quarterly_financial_stage

            WHERE market = ?
              AND fiscal_year = ?
              AND fiscal_quarter = ?
            """,
            (
                market,
                year,
                quarter,
            ),
        )

        conn.executemany(
            """
            INSERT INTO
            quarterly_financial_stage (

                stock_id,
                market,

                fiscal_year,
                fiscal_quarter,

                revenue,
                gross_profit,

                operating_income,
                net_income,

                eps,

                gross_margin_pct,
                operating_margin_pct,
                net_margin_pct,

                source,
                source_date
            )

            VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            """,
            [
                row.stage_values()

                for row
                in rows
            ],
        )

        conn.execute(
            """
            INSERT INTO stage_complete (

                market,
                fiscal_year,
                fiscal_quarter,

                row_count,
                completed_at
            )

            VALUES (
                ?, ?, ?, ?,
                CURRENT_TIMESTAMP
            )

            ON CONFLICT(
                market,
                fiscal_year,
                fiscal_quarter
            )

            DO UPDATE SET

                row_count =
                    excluded.row_count,

                completed_at =
                    CURRENT_TIMESTAMP
            """,
            (
                market,
                year,
                quarter,
                len(
                    rows
                ),
            ),
        )

        conn.commit()

    except BaseException:

        conn.rollback()

        raise


def load_stage_period(
    conn: sqlite3.Connection,
    year: int,
    quarter: int,
) -> list[
    FinancialRow
]:

    rows = (
        conn.execute(
            """
            SELECT

                stock_id,
                market,

                fiscal_year,
                fiscal_quarter,

                revenue,
                gross_profit,

                operating_income,
                net_income,

                eps,

                gross_margin_pct,
                operating_margin_pct,
                net_margin_pct,

                source,
                source_date

            FROM quarterly_financial_stage

            WHERE fiscal_year = ?
              AND fiscal_quarter = ?

            ORDER BY
                market,
                stock_id
            """,
            (
                year,
                quarter,
            ),
        )
        .fetchall()
    )

    result: list[
        FinancialRow
    ] = []

    for row in rows:

        result.append(
            FinancialRow(
                stock_id=str(
                    row[0]
                ),

                market=str(
                    row[1]
                ),

                fiscal_year=int(
                    row[2]
                ),

                fiscal_quarter=int(
                    row[3]
                ),

                revenue=float(
                    row[4]
                ),

                gross_profit=float(
                    row[5]
                ),

                operating_income=float(
                    row[6]
                ),

                net_income=float(
                    row[7]
                ),

                eps=float(
                    row[8]
                ),

                gross_margin_pct=(
                    None
                    if row[9]
                    is None
                    else float(
                        row[9]
                    )
                ),

                operating_margin_pct=(
                    None
                    if row[10]
                    is None
                    else float(
                        row[10]
                    )
                ),

                net_margin_pct=(
                    None
                    if row[11]
                    is None
                    else float(
                        row[11]
                    )
                ),

                source=str(
                    row[12]
                ),

                source_date=(
                    None
                    if row[13]
                    is None
                    else str(
                        row[13]
                    )
                ),
            )
        )

    return result


# ============================================================
# RESILIENT FETCH
# ============================================================


def fetch_batch(
    companies: list[
        Company
    ],
    year: int,
    quarter: int,
) -> list[
    FinancialRow
]:

    try:

        return parse_report(
            post_report(
                companies,
                year,
                quarter,
            ),

            companies,
            year,
            quarter,
        )

    except (
        NoBatchDataError,
        BatchSplitRequired,
        UnsupportedReportFormatError,
    ) as exc:

        # ----------------------------------------------------
        # MopsFin multi-company comparison may mix companies
        # with different income-statement schemas.
        #
        # Split recursively until:
        #
        # 1. GENERAL companies can be parsed correctly.
        #
        # 2. A single company is confirmed as a non-GENERAL
        #    financial report format and is intentionally
        #    excluded from this GENERAL backfill.
        #
        # 3. A single GENERAL company still has missing values;
        #    that remains a real error and must stop.
        # ----------------------------------------------------

        if len(
            companies
        ) == 1:

            company = (
                companies[0]
            )

            if isinstance(
                exc,
                UnsupportedReportFormatError,
            ):

                print(
                    "        [SKIP] "
                    "non-GENERAL report: "
                    f"{company.stock_id} "
                    f"{company.short_name} "
                    f"| {exc}"
                )

                return []

            if isinstance(
                exc,
                NoBatchDataError,
            ):

                print(
                    "        [WARN] "
                    "no official report data: "
                    f"{company.stock_id} "
                    f"{company.short_name} "
                    f"| {exc}"
                )

                return []

            # ------------------------------------------------
            # BatchSplitRequired on a single company means
            # the company is already using the GENERAL schema,
            # but one of the required values is still missing.
            #
            # Do NOT silently skip this case.
            # ------------------------------------------------

            raise RuntimeError(
                f"{company.stock_id} "
                f"{period_text(year, quarter)} "
                "GENERAL report still cannot "
                "be parsed when queried alone: "
                f"{exc}"
            ) from exc

        middle = (
            len(
                companies
            )
            //
            2
        )

        left = (
            companies[
                :middle
            ]
        )

        right = (
            companies[
                middle:
            ]
        )

        print(
            "        [INFO] split batch "
            f"{len(companies)} -> "
            f"{len(left)} + "
            f"{len(right)} "
            f"| {exc}"
        )

        return (
            fetch_batch(
                left,
                year,
                quarter,
            )

            +

            fetch_batch(
                right,
                year,
                quarter,
            )
        )


def fetch_period_market(
    companies: list[
        Company
    ],

    market: str,

    year: int,
    quarter: int,
) -> list[
    FinancialRow
]:

    batches = [
        companies[
            index:
            index
            +
            BATCH_SIZE
        ]

        for index
        in range(
            0,
            len(
                companies
            ),
            BATCH_SIZE,
        )
    ]

    rows: list[
        FinancialRow
    ] = []

    seen: set[str] = set()

    for (
        batch_number,
        batch,
    ) in enumerate(
        batches,
        start=1,
    ):

        for row in fetch_batch(
            batch,
            year,
            quarter,
        ):

            if (
                row.stock_id
                in seen
            ):

                raise RuntimeError(
                    "Duplicate "
                    f"{row.stock_id} "
                    f"{period_text(year, quarter)}"
                )

            seen.add(
                row.stock_id
            )

            rows.append(
                row
            )

        if (
            batch_number == 1
            or
            batch_number % 20 == 0
            or
            batch_number
            ==
            len(
                batches
            )
        ):

            print(
                f"        batch "
                f"{batch_number:03d}/"
                f"{len(batches):03d} "
                f"| rows="
                f"{len(rows):,}"
            )

    if (
        len(
            rows
        )
        <
        MIN_ROWS[
            market
        ]
    ):

        raise RuntimeError(
            f"{market} "
            f"{period_text(year, quarter)} "
            "rows too small: "
            f"{len(rows):,} "
            "< "
            f"{MIN_ROWS[market]:,}"
        )

    return sorted(
        rows,

        key=lambda row:
            row.stock_id,
    )


# ============================================================
# LATEST PERIOD CROSS CHECK
# ============================================================


def equal(
    field: str,

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

    tolerance = (
        0.0001

        if field == "eps"

        else 0.5
    )

    return (
        abs(
            left
            -
            right
        )
        <= tolerance
    )


def cross_check_latest(
    turso,
    stage: sqlite3.Connection,
) -> None:

    latest = (
        turso.execute(
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

    if latest is None:

        raise RuntimeError(
            "Existing GENERAL "
            "latest period missing"
        )

    year = int(
        latest[0]
    )

    quarter = int(
        latest[1]
    )

    staged = {
        row.stock_id:
            row

        for row
        in load_stage_period(
            stage,
            year,
            quarter,
        )
    }

    db_rows = (
        turso.execute(
            """
            SELECT

                stock_id,

                revenue,
                gross_profit,

                operating_income,
                net_income,

                eps

            FROM quarterly_financial

            WHERE fiscal_year = ?
              AND fiscal_quarter = ?

              AND report_type =
                  'GENERAL'
            """,
            (
                year,
                quarter,
            ),
        )
        .fetchall()
    )

    overlap = 0
    mismatch = 0

    samples: list[str] = []

    for db_row in db_rows:

        stock_id = str(
            db_row[0]
        )

        if (
            stock_id
            not in staged
        ):

            continue

        overlap += 1

        source = (
            staged[
                stock_id
            ]
        )

        pairs = {
            "revenue": (
                source.revenue,

                None
                if db_row[1]
                is None
                else float(
                    db_row[1]
                ),
            ),

            "gross_profit": (
                source.gross_profit,

                None
                if db_row[2]
                is None
                else float(
                    db_row[2]
                ),
            ),

            "operating_income": (
                source.operating_income,

                None
                if db_row[3]
                is None
                else float(
                    db_row[3]
                ),
            ),

            "net_income": (
                source.net_income,

                None
                if db_row[4]
                is None
                else float(
                    db_row[4]
                ),
            ),

            "eps": (
                source.eps,

                None
                if db_row[5]
                is None
                else float(
                    db_row[5]
                ),
            ),
        }

        bad = False

        for (
            field,
            pair,
        ) in pairs.items():

            if not equal(
                field,
                pair[0],
                pair[1],
            ):

                mismatch += 1
                bad = True

        if (
            bad
            and
            len(
                samples
            )
            < 10
        ):

            samples.append(
                stock_id
            )

    print()

    print(
        "Existing latest cross-check:"
    )

    print(
        "  Period         : "
        f"{period_text(year, quarter)}"
    )

    print(
        "  Overlap        : "
        f"{overlap:,}"
    )

    print(
        "  Field mismatch : "
        f"{mismatch:,}"
    )

    if samples:

        print(
            "  Samples        : "
            +
            ", ".join(
                samples
            )
        )

    if (
        overlap == 0
        or
        mismatch != 0
    ):

        raise RuntimeError(
            "Latest-period MopsFin "
            "cross-check failed"
        )

    print(
        "  [PASS] MopsFin matches "
        "existing Turso latest period"
    )


# ============================================================
# TURSO UPSERT
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
    ?, ?, ?, ?, ?,
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
        COALESCE(
            excluded.source_date,
            quarterly_financial.source_date
        ),

    updated_at =
        CURRENT_TIMESTAMP
"""


def build_sql(
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
            row.turso_values()
        )

    return tuple(
        values
    )


def update_sync_state(
    conn,
    market: str,
    count: int,
) -> None:

    last_period = (
        period_text(
            *PERIODS[-1]
        )
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
            SYNC_DATASET[
                market
            ],

            last_period,

            count,
        ),
    )


def write_turso(
    turso,
    stage: sqlite3.Connection,
) -> int:

    rows: list[
        FinancialRow
    ] = []

    for (
        year,
        quarter,
    ) in PERIODS:

        rows.extend(
            load_stage_period(
                stage,
                year,
                quarter,
            )
        )

    rows.sort(
        key=lambda row: (
            row.fiscal_year,
            row.fiscal_quarter,
            row.market,
            row.stock_id,
        )
    )

    counts = {
        "TWSE":
            sum(
                row.market
                ==
                "TWSE"

                for row
                in rows
            ),

        "TPEX":
            sum(
                row.market
                ==
                "TPEX"

                for row
                in rows
            ),
    }

    turso.execute(
        "BEGIN"
    )

    try:

        for start in range(
            0,
            len(
                rows
            ),
            DB_BATCH_SIZE,
        ):

            batch = rows[
                start:
                start
                +
                DB_BATCH_SIZE
            ]

            turso.execute(
                build_sql(
                    len(
                        batch
                    )
                ),

                flatten(
                    batch
                ),
            )

        for market in (
            "TWSE",
            "TPEX",
        ):

            update_sync_state(
                turso,

                market,

                counts[
                    market
                ],
            )

        turso.commit()

    except BaseException:

        try:

            turso.rollback()

        except Exception:
            pass

        raise

    return len(
        rows
    )


# ============================================================
# STAGING VALIDATION
# ============================================================


def validate_stage(
    stage: sqlite3.Connection,
) -> None:

    print()

    print(
        "=" * 88
    )

    print(
        "QUARTERLY FINANCIAL "
        "STAGING SUMMARY"
    )

    print(
        "=" * 88
    )

    print(
        "Period   | TWSE Rows | "
        "TPEx Rows | Total"
    )

    print(
        "-" * 88
    )

    for (
        year,
        quarter,
    ) in PERIODS:

        if not stage_complete(
            stage,
            "TWSE",
            year,
            quarter,
        ):

            raise RuntimeError(
                "TWSE "
                f"{period_text(year, quarter)} "
                "staging incomplete"
            )

        if not stage_complete(
            stage,
            "TPEX",
            year,
            quarter,
        ):

            raise RuntimeError(
                "TPEX "
                f"{period_text(year, quarter)} "
                "staging incomplete"
            )

        twse = stage_count(
            stage,
            "TWSE",
            year,
            quarter,
        )

        tpex = stage_count(
            stage,
            "TPEX",
            year,
            quarter,
        )

        if (
            twse
            <
            MIN_ROWS[
                "TWSE"
            ]
            or
            tpex
            <
            MIN_ROWS[
                "TPEX"
            ]
        ):

            raise RuntimeError(
                f"{period_text(year, quarter)} "
                "staged rows too small"
            )

        print(
            f"{period_text(year, quarter):8} "
            f"| {twse:9,} "
            f"| {tpex:9,} "
            f"| {twse + tpex:5,}"
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
        "=" * 88
    )

    print(
        "StockWaveScanner V2 - "
        "Quarterly Financial Historical Backfill"
    )

    print(
        "=" * 88
    )

    try:

        (
            url,
            token,
        ) = load_dev_credentials()

        print(
            "Target        : DEV"
        )

        print(
            "PROD Access   : DISABLED"
        )

        print(
            "Scope         : "
            "GENERAL industry only"
        )

        print(
            "Semantics     : "
            "MopsFin IncomeStatement cumulative"
        )

        print(
            "Periods       : "
            "2024-Q3 .. 2026-Q2 "
            "(8 quarters)"
        )

        print(
            f"Batch Size    : "
            f"{BATCH_SIZE} companies"
        )

        print(
            f"Stage DB      : "
            f"{STAGE_DB}"
        )

        print(
            "Validate-only : "
            +
            (
                "YES"
                if args.validate_only
                else
                "NO"
            )
        )

        print(
            "[INFO] validate-only may write "
            "local staging SQLite, "
            "but never Turso."
        )

        turso = libsql.connect(
            database=url,
            auth_token=token,
        )

        stage = (
            open_stage()
        )

        try:

            test = (
                turso.execute(
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

            version = scalar(
                turso,

                """
                SELECT schema_value

                FROM schema_meta

                WHERE schema_key =
                      'schema_version'
                """,
            )

            if version is None:

                raise RuntimeError(
                    "schema version missing"
                )

            print(
                f"Schema        : "
                f"{version}"
            )

            print(
                "[PASS] Turso DEV connection"
            )

            universe = {
                "TWSE":
                    load_universe(
                        turso,
                        "TWSE",
                    ),

                "TPEX":
                    load_universe(
                        turso,
                        "TPEX",
                    ),
            }

            print()

            print(
                "Backfill GENERAL universe:"
            )

            print(
                f"  TWSE : "
                f"{len(universe['TWSE']):,}"
            )

            print(
                f"  TPEx : "
                f"{len(universe['TPEX']):,}"
            )

            started = (
                time.perf_counter()
            )

            for (
                period_number,
                (
                    year,
                    quarter,
                ),
            ) in enumerate(
                PERIODS,
                start=1,
            ):

                print()

                print(
                    f"[{period_number:02d}/"
                    f"{len(PERIODS):02d}] "
                    f"{period_text(year, quarter)}"
                )

                for market in (
                    "TWSE",
                    "TPEX",
                ):

                    if stage_complete(
                        stage,
                        market,
                        year,
                        quarter,
                    ):

                        count = stage_count(
                            stage,
                            market,
                            year,
                            quarter,
                        )

                        print(
                            f"    {market:<4} "
                            f"| STAGE CACHE "
                            f"| rows={count:,}"
                        )

                        continue

                    market_started = (
                        time.perf_counter()
                    )

                    print(
                        f"    {market:<4} "
                        f"| fetching "
                        f"{len(universe[market]):,} "
                        "companies ..."
                    )

                    rows = (
                        fetch_period_market(
                            universe[
                                market
                            ],

                            market,

                            year,
                            quarter,
                        )
                    )

                    save_stage(
                        stage,

                        market,

                        year,
                        quarter,

                        rows,
                    )

                    print(
                        f"    {market:<4} "
                        f"| [PASS] "
                        f"rows={len(rows):,} "
                        f"| elapsed="
                        f"{time.perf_counter() - market_started:.1f}s"
                    )

            elapsed = (
                time.perf_counter()
                -
                started
            )

            validate_stage(
                stage
            )

            cross_check_latest(
                turso,
                stage,
            )

            print()

            print(
                "Fetch / Stage Elapsed : "
                f"{elapsed:.1f}s"
            )

            # =================================================
            # READ ONLY TURSO
            # =================================================

            if args.validate_only:

                print()

                print(
                    "[PASS] "
                    "READ-ONLY Turso validation"
                )

                print(
                    "[PASS] "
                    "No Turso rows were written"
                )

                print(
                    "[PASS] Local staging cache "
                    "is ready for formal backfill"
                )

                print(
                    "[PASS] PROD was not accessed"
                )

                print()

                print(
                    "=" * 88
                )

                print(
                    "QUARTERLY FINANCIAL "
                    "BACKFILL VALIDATION OK"
                )

                print(
                    "=" * 88
                )

                return 0

            # =================================================
            # WRITE TURSO
            # =================================================

            print()

            print(
                "Writing staged Quarterly "
                "Financial history "
                "to Turso DEV ..."
            )

            write_started = (
                time.perf_counter()
            )

            written = write_turso(
                turso,
                stage,
            )

            print(
                "[PASS] Historical UPSERT completed"
            )

            print(
                "Staged Rows Written : "
                f"{written:,}"
            )

            print(
                "DB Write Elapsed    : "
                f"{time.perf_counter() - write_started:.1f}s"
            )

            min_row = (
                turso.execute(
                    """
                    SELECT
                        fiscal_year,
                        fiscal_quarter

                    FROM quarterly_financial

                    WHERE report_type =
                          'GENERAL'

                    ORDER BY
                        fiscal_year,
                        fiscal_quarter

                    LIMIT 1
                    """
                )
                .fetchone()
            )

            max_row = (
                turso.execute(
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

            total = int(
                scalar(
                    turso,

                    """
                    SELECT COUNT(*)

                    FROM quarterly_financial

                    WHERE report_type =
                          'GENERAL'
                    """,
                )
                or 0
            )

            print()

            print(
                "=" * 88
            )

            print(
                "QUARTERLY FINANCIAL "
                "BACKFILL RESULT"
            )

            print(
                "=" * 88
            )

            print(
                "DB Min Period : "
                +
                period_text(
                    int(
                        min_row[0]
                    ),
                    int(
                        min_row[1]
                    ),
                )
            )

            print(
                "DB Max Period : "
                +
                period_text(
                    int(
                        max_row[0]
                    ),
                    int(
                        max_row[1]
                    ),
                )
            )

            print(
                "DB GENERAL Rows : "
                f"{total:,}"
            )

            print(
                "PROD Access     : DISABLED"
            )

        finally:

            stage.close()
            turso.close()

        print()

        print(
            "=" * 88
        )

        print(
            "QUARTERLY FINANCIAL "
            "BACKFILL OK"
        )

        print(
            "=" * 88
        )

        return 0

    except KeyboardInterrupt:

        print()

        print(
            "INTERRUPTED"
        )

        print(
            "Completed local stage periods "
            "are preserved."
        )

        print(
            "No PROD database was accessed."
        )

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

        print()

        print(
            "Completed local stage periods "
            "are preserved."
        )

        print(
            "No PROD database was accessed."
        )

        return 1


if __name__ == "__main__":

    sys.exit(
        main()
    )