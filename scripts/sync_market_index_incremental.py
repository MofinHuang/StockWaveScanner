from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

TIMEOUT = 45
REQUEST_DELAY = 0.35

TAIPEI_TZ = timezone(timedelta(hours=8))

USER_AGENT = (
    "Mozilla/5.0 "
    "StockWaveScanner-V2-Market-Index/1.0"
)

TWSE_CURRENT_URL = (
    "https://openapi.twse.com.tw/v1/"
    "indicesReport/MI_5MINS_HIST"
)

TWSE_HISTORY_URL = (
    "https://www.twse.com.tw/"
    "indicesReport/MI_5MINS_HIST"
)

TPEX_CURRENT_URL = (
    "https://www.tpex.org.tw/"
    "openapi/v1/tpex_index"
)

TPEX_HISTORY_URL = (
    "https://www.tpex.org.tw/"
    "www/zh-tw/indexInfo/inx"
)


# StockWaveScanner 內部統一代碼
INDEX_CODES = {
    "TWSE": "TAIEX",
    "TPEX": "TPEX",
}


DATASETS = {
    "TWSE": "market_index_twse",
    "TPEX": "market_index_tpex",
}


CURRENT_SOURCES = {
    "TWSE": "TWSE_OPENAPI_MI_5MINS_HIST",
    "TPEX": "TPEX_OPENAPI_TPEX_INDEX",
}


HISTORY_SOURCES = {
    "TWSE": "TWSE_MI_5MINS_HIST_MONTHLY",
    "TPEX": "TPEX_INDEX_MONTHLY",
}


@dataclass(frozen=True)
class IndexRow:
    market: str
    index_code: str
    trade_date: str

    open: float
    high: float
    low: float
    close: float

    volume: float | None
    turnover: float | None

    source: str

    def db_tuple(self) -> tuple[Any, ...]:
        return (
            self.market,
            self.index_code,
            self.trade_date,
            self.open,
            self.high,
            self.low,
            self.close,
            self.volume,
            self.turnover,
            self.source,
        )


# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Incrementally sync TWSE / TPEx "
            "market indices into Turso DEV."
        )
    )

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "--through",
        metavar="YYYY-MM-DD",
        help=(
            "Sync through this Taiwan calendar date. "
            "Default: today UTC+8."
        ),
    )

    group.add_argument(
        "--validate-date",
        metavar="YYYY-MM-DD",
        help=(
            "READ-ONLY: fetch and validate one known "
            "trading date without writing Turso."
        ),
    )

    return parser.parse_args()


# ============================================================
# DATE / VALUE HELPERS
# ============================================================


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid date '{value}'. "
            "Expected YYYY-MM-DD."
        ) from exc


def taipei_today() -> date:
    return datetime.now(TAIPEI_TZ).date()


def first_day_of_month(value: date) -> date:
    return value.replace(day=1)


def next_month(value: date) -> date:
    if value.month == 12:
        return date(
            value.year + 1,
            1,
            1,
        )

    return date(
        value.year,
        value.month + 1,
        1,
    )


def month_range(
    start: date,
    end: date,
) -> Iterable[date]:

    current = first_day_of_month(start)
    final = first_day_of_month(end)

    while current <= final:
        yield current
        current = next_month(current)


def clean_text(
    value: Any,
) -> str | None:

    if value is None:
        return None

    text = str(value).strip()

    return text or None


def parse_number(
    value: Any,
) -> float | None:

    text = clean_text(value)

    if text is None:
        return None

    text = (
        text
        .replace(",", "")
        .replace("，", "")
        .replace("\u3000", "")
        .strip()
    )

    if text in {
        "-",
        "--",
        "---",
        "----",
        "N/A",
        "NA",
    }:
        return None

    try:
        return float(text)

    except ValueError:
        return None


# ============================================================
# DATE NORMALIZATION
# ============================================================


def parse_twse_current_date(
    value: Any,
) -> date:

    text = clean_text(value)

    if text is None:
        raise RuntimeError(
            "TWSE current index row has empty Date"
        )

    digits = "".join(
        ch
        for ch in text
        if ch.isdigit()
    )

    # 例如：
    # 1150911
    if len(digits) != 7:
        raise RuntimeError(
            f"Unexpected TWSE current Date: {text}"
        )

    year = int(digits[:3]) + 1911
    month = int(digits[3:5])
    day = int(digits[5:7])

    return date(
        year,
        month,
        day,
    )


def parse_twse_history_date(
    value: Any,
) -> date:

    text = clean_text(value)

    if text is None:
        raise RuntimeError(
            "TWSE historical index row "
            "has empty date"
        )

    parts = (
        text
        .replace("-", "/")
        .split("/")
    )

    # 例如：
    # 115/09/11
    if len(parts) != 3:
        raise RuntimeError(
            "Unexpected TWSE historical "
            f"date: {text}"
        )

    year = int(parts[0]) + 1911
    month = int(parts[1])
    day = int(parts[2])

    return date(
        year,
        month,
        day,
    )


def parse_tpex_date(
    value: Any,
) -> date:

    text = clean_text(value)

    if text is None:
        raise RuntimeError(
            "TPEx index row has empty date"
        )

    # Historical 可能：
    # 2026/09/11
    # 115/09/11
    if "/" in text or "-" in text:

        parts = (
            text
            .replace("-", "/")
            .split("/")
        )

        if len(parts) != 3:
            raise RuntimeError(
                f"Unexpected TPEx date: {text}"
            )

        year = int(parts[0])

        if year < 1911:
            year += 1911

        return date(
            year,
            int(parts[1]),
            int(parts[2]),
        )

    digits = "".join(
        ch
        for ch in text
        if ch.isdigit()
    )

    # Current：
    # 20260911
    if len(digits) == 8:

        return date(
            int(digits[:4]),
            int(digits[4:6]),
            int(digits[6:8]),
        )

    # 防呆：
    # 1150911
    if len(digits) == 7:

        return date(
            int(digits[:3]) + 1911,
            int(digits[3:5]),
            int(digits[5:7]),
        )

    raise RuntimeError(
        f"Unexpected TPEx date: {text}"
    )


# ============================================================
# DEV SAFETY
# ============================================================


def load_dev_credentials() -> tuple[str, str]:

    load_dotenv(ENV_FILE)

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

    lower_url = url.lower()

    if "stockwave-dev" not in lower_url:
        raise RuntimeError(
            "SAFETY STOP: DEV URL does not "
            "point to stockwave-dev"
        )

    if "stockwave-prod" in lower_url:
        raise RuntimeError(
            "SAFETY STOP: "
            "PROD database detected"
        )

    return url, token


def mask_url(
    url: str,
) -> str:

    if "://" not in url:
        return "***"

    scheme, rest = url.split(
        "://",
        1,
    )

    return f"{scheme}://{rest}"


# ============================================================
# HTTP
# ============================================================


def fetch_urllib(
    url: str,
    method: str = "GET",
    form: dict[str, str] | None = None,
) -> bytes:

    body = None

    if method.upper() == "POST":

        body = urllib.parse.urlencode(
            form or {}
        ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        method=method.upper(),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/json,"
                "text/plain,*/*"
            ),
            "Cache-Control": "no-cache",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT,
    ) as response:

        data = response.read()

    if not data:
        raise RuntimeError(
            "Empty HTTP response"
        )

    return data


def fetch_curl(
    url: str,
    method: str = "GET",
    form: dict[str, str] | None = None,
) -> bytes:

    curl = (
        shutil.which("curl.exe")
        or shutil.which("curl")
    )

    if not curl:
        raise RuntimeError(
            "curl not found"
        )

    command = [
        curl,
        "--location",
        "--http1.1",
        "--fail",
        "--connect-timeout",
        "15",
        "--max-time",
        str(TIMEOUT),
        "-A",
        USER_AGENT,
        "-sS",
    ]

    if method.upper() == "POST":

        command.extend(
            [
                "-X",
                "POST",
            ]
        )

        for key, value in (
            form or {}
        ).items():

            command.extend(
                [
                    "--data-urlencode",
                    f"{key}={value}",
                ]
            )

    command.append(url)

    result = subprocess.run(
        command,
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
            f"curl failed: {error}"
        )

    if not result.stdout:
        raise RuntimeError(
            "Empty curl response"
        )

    return result.stdout


def fetch_with_retry(
    url: str,
    method: str = "GET",
    form: dict[str, str] | None = None,
    prefer_curl: bool = False,
) -> bytes:

    delays = [
        0,
        3,
        10,
        30,
    ]

    errors: list[str] = []

    if prefer_curl:
        loaders = (
            fetch_curl,
            fetch_urllib,
        )
    else:
        loaders = (
            fetch_urllib,
            fetch_curl,
        )

    for attempt, delay in enumerate(
        delays,
        start=1,
    ):

        if delay:
            time.sleep(delay)

        for loader in loaders:

            try:
                return loader(
                    url,
                    method,
                    form,
                )

            except Exception as exc:

                errors.append(
                    f"attempt={attempt} "
                    f"{loader.__name__}: "
                    f"{exc}"
                )

        if attempt < len(delays):

            print(
                "    retrying HTTP "
                f"({attempt}/{len(delays)}) ..."
            )

    raise RuntimeError(
        " | ".join(
            errors[-6:]
        )
    )


def decode_json(
    data: bytes,
) -> Any:

    text = data.decode(
        "utf-8-sig",
        errors="replace",
    )

    try:
        return json.loads(text)

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            f"Invalid JSON: {exc}"
        ) from exc


# ============================================================
# INDEX NORMALIZATION
# ============================================================


def build_index_row(
    market: str,
    trade_date: date,
    open_value: Any,
    high_value: Any,
    low_value: Any,
    close_value: Any,
    source: str,
) -> IndexRow:

    open_price = parse_number(
        open_value
    )

    high_price = parse_number(
        high_value
    )

    low_price = parse_number(
        low_value
    )

    close_price = parse_number(
        close_value
    )

    if None in (
        open_price,
        high_price,
        low_price,
        close_price,
    ):

        raise RuntimeError(
            f"{market} index has "
            "missing OHLC on "
            f"{trade_date.isoformat()}"
        )

    row = IndexRow(
        market=market,
        index_code=INDEX_CODES[market],
        trade_date=trade_date.isoformat(),
        open=float(open_price),
        high=float(high_price),
        low=float(low_price),
        close=float(close_price),
        volume=None,
        turnover=None,
        source=source,
    )

    validate_index_row(row)

    return row


def validate_index_row(
    row: IndexRow,
) -> None:

    values = (
        row.open,
        row.high,
        row.low,
        row.close,
    )

    if min(values) <= 0:

        raise RuntimeError(
            f"{row.market} "
            "non-positive OHLC on "
            f"{row.trade_date}: "
            f"{values}"
        )

    if row.high < max(
        row.open,
        row.low,
        row.close,
    ):

        raise RuntimeError(
            f"{row.market} "
            "invalid high on "
            f"{row.trade_date}: "
            f"{values}"
        )

    if row.low > min(
        row.open,
        row.high,
        row.close,
    ):

        raise RuntimeError(
            f"{row.market} "
            "invalid low on "
            f"{row.trade_date}: "
            f"{values}"
        )


def validate_unique_rows(
    market: str,
    rows: list[IndexRow],
) -> None:

    seen: set[
        tuple[
            str,
            str,
            str,
        ]
    ] = set()

    for row in rows:

        key = (
            row.market,
            row.index_code,
            row.trade_date,
        )

        if key in seen:

            raise RuntimeError(
                f"{market} duplicate "
                "market/index/date: "
                f"{row.trade_date}"
            )

        seen.add(key)

        validate_index_row(row)


# ============================================================
# TWSE CURRENT
# ============================================================


def fetch_twse_current() -> list[IndexRow]:

    payload = decode_json(
        fetch_with_retry(
            TWSE_CURRENT_URL
        )
    )

    if not isinstance(
        payload,
        list,
    ):
        raise RuntimeError(
            "TWSE current index response "
            "is not a JSON array"
        )

    if not payload:
        raise RuntimeError(
            "TWSE current index response "
            "is empty"
        )

    result: list[IndexRow] = []

    for item in payload:

        if not isinstance(
            item,
            dict,
        ):
            continue

        required = (
            "Date",
            "OpeningIndex",
            "HighestIndex",
            "LowestIndex",
            "ClosingIndex",
        )

        missing = [
            field
            for field in required
            if field not in item
        ]

        if missing:

            raise RuntimeError(
                "TWSE current index "
                "missing fields: "
                + ", ".join(missing)
            )

        trade_date = (
            parse_twse_current_date(
                item["Date"]
            )
        )

        result.append(
            build_index_row(
                "TWSE",
                trade_date,
                item["OpeningIndex"],
                item["HighestIndex"],
                item["LowestIndex"],
                item["ClosingIndex"],
                CURRENT_SOURCES["TWSE"],
            )
        )

    validate_unique_rows(
        "TWSE",
        result,
    )

    return sorted(
        result,
        key=lambda row: row.trade_date,
    )


# ============================================================
# TWSE HISTORICAL MONTH
# ============================================================


def fetch_twse_history_month(
    month_start: date,
) -> list[IndexRow]:

    query = urllib.parse.urlencode(
        {
            "response": "json",
            "date": (
                month_start
                .strftime("%Y%m01")
            ),
        }
    )

    url = (
        f"{TWSE_HISTORY_URL}"
        f"?{query}"
    )

    payload = decode_json(
        fetch_with_retry(url)
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "TWSE historical index "
            "response is not an object"
        )

    stat = (
        str(
            payload.get(
                "stat",
                "",
            )
        )
        .strip()
        .upper()
    )

    if stat != "OK":
        return []

    rows = payload.get(
        "data",
        [],
    )

    if not isinstance(
        rows,
        list,
    ):
        raise RuntimeError(
            "TWSE historical index "
            "data is invalid"
        )

    result: list[IndexRow] = []

    for item in rows:

        if (
            not isinstance(
                item,
                list,
            )
            or len(item) < 5
        ):
            continue

        trade_date = (
            parse_twse_history_date(
                item[0]
            )
        )

        result.append(
            build_index_row(
                "TWSE",
                trade_date,
                item[1],
                item[2],
                item[3],
                item[4],
                HISTORY_SOURCES["TWSE"],
            )
        )

    validate_unique_rows(
        "TWSE",
        result,
    )

    return sorted(
        result,
        key=lambda row: row.trade_date,
    )


# ============================================================
# TPEX CURRENT
# ============================================================


def fetch_tpex_current() -> list[IndexRow]:

    payload = decode_json(
        fetch_with_retry(
            TPEX_CURRENT_URL,
            prefer_curl=True,
        )
    )

    if not isinstance(
        payload,
        list,
    ):
        raise RuntimeError(
            "TPEx current index response "
            "is not a JSON array"
        )

    if not payload:
        raise RuntimeError(
            "TPEx current index response "
            "is empty"
        )

    result: list[IndexRow] = []

    for item in payload:

        if not isinstance(
            item,
            dict,
        ):
            continue

        required = (
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
        )

        missing = [
            field
            for field in required
            if field not in item
        ]

        if missing:

            raise RuntimeError(
                "TPEx current index "
                "missing fields: "
                + ", ".join(missing)
            )

        trade_date = (
            parse_tpex_date(
                item["Date"]
            )
        )

        result.append(
            build_index_row(
                "TPEX",
                trade_date,
                item["Open"],
                item["High"],
                item["Low"],
                item["Close"],
                CURRENT_SOURCES["TPEX"],
            )
        )

    validate_unique_rows(
        "TPEX",
        result,
    )

    return sorted(
        result,
        key=lambda row: row.trade_date,
    )


# ============================================================
# TPEX HISTORICAL MONTH
# ============================================================


def fetch_tpex_history_month(
    month_start: date,
) -> list[IndexRow]:

    form = {
        "date": (
            month_start
            .strftime("%Y/%m/01")
        ),
        "response": "json",
    }

    payload = decode_json(
        fetch_with_retry(
            TPEX_HISTORY_URL,
            method="POST",
            form=form,
            prefer_curl=True,
        )
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "TPEx historical index "
            "response is not an object"
        )

    stat = (
        str(
            payload.get(
                "stat",
                "",
            )
        )
        .strip()
        .lower()
    )

    if stat != "ok":
        return []

    tables = payload.get(
        "tables",
        [],
    )

    if (
        not isinstance(
            tables,
            list,
        )
        or not tables
    ):
        return []

    table = tables[0]

    if not isinstance(
        table,
        dict,
    ):
        raise RuntimeError(
            "TPEx historical index "
            "table is invalid"
        )

    rows = table.get(
        "data",
        [],
    )

    if not isinstance(
        rows,
        list,
    ):
        raise RuntimeError(
            "TPEx historical index "
            "data is invalid"
        )

    result: list[IndexRow] = []

    for item in rows:

        if (
            not isinstance(
                item,
                list,
            )
            or len(item) < 5
        ):
            continue

        trade_date = (
            parse_tpex_date(
                item[0]
            )
        )

        result.append(
            build_index_row(
                "TPEX",
                trade_date,
                item[1],
                item[2],
                item[3],
                item[4],
                HISTORY_SOURCES["TPEX"],
            )
        )

    validate_unique_rows(
        "TPEX",
        result,
    )

    return sorted(
        result,
        key=lambda row: row.trade_date,
    )


# ============================================================
# FETCH PLAN
# ============================================================


def is_current_month(
    month_start: date,
) -> bool:

    today = taipei_today()

    return (
        month_start.year
        == today.year

        and

        month_start.month
        == today.month
    )


def fetch_market_month(
    market: str,
    month_start: date,
) -> list[IndexRow]:

    if is_current_month(
        month_start
    ):

        if market == "TWSE":
            return fetch_twse_current()

        if market == "TPEX":
            return fetch_tpex_current()

    else:

        if market == "TWSE":
            return (
                fetch_twse_history_month(
                    month_start
                )
            )

        if market == "TPEX":
            return (
                fetch_tpex_history_month(
                    month_start
                )
            )

    raise RuntimeError(
        f"Unsupported market: {market}"
    )


def fetch_market_range(
    market: str,
    start: date,
    through: date,
) -> list[IndexRow]:

    rows: list[IndexRow] = []

    for month_start in month_range(
        start,
        through,
    ):

        month_rows = (
            fetch_market_month(
                market,
                month_start,
            )
        )

        for row in month_rows:

            row_date = (
                parse_iso_date(
                    row.trade_date
                )
            )

            if (
                start
                <= row_date
                <= through
            ):
                rows.append(row)

        time.sleep(
            REQUEST_DELAY
        )

    validate_unique_rows(
        market,
        rows,
    )

    return sorted(
        rows,
        key=lambda row: row.trade_date,
    )


# ============================================================
# TURSO READ
# ============================================================


def scalar(
    conn,
    sql: str,
    params: tuple[Any, ...] = (),
) -> Any:

    row = (
        conn
        .execute(
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

    return str(value)


def get_latest_index_date(
    conn,
    market: str,
) -> str | None:

    value = scalar(
        conn,
        """
        SELECT MAX(trade_date)
        FROM market_index_daily
        WHERE market = ?
          AND index_code = ?
        """,
        (
            market,
            INDEX_CODES[market],
        ),
    )

    if value is None:
        return None

    return str(value)


# ============================================================
# TURSO WRITE
# ============================================================


INDEX_INSERT_SQL = """
INSERT INTO market_index_daily (
    market,
    index_code,
    trade_date,

    open,
    high,
    low,
    close,

    volume,
    turnover,

    source,

    created_at,
    updated_at
)
VALUES (
    ?,
    ?,
    ?,

    ?,
    ?,
    ?,
    ?,

    ?,
    ?,

    ?,

    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT(
    market,
    index_code,
    trade_date
)
DO NOTHING
"""


def insert_index_row(
    conn,
    row: IndexRow,
) -> None:

    conn.execute(
        INDEX_INSERT_SQL,
        row.db_tuple(),
    )


def update_sync_state(
    conn,
    dataset: str,
    last_data_date: str | None,
    records_processed: int,
    status: str,
    error_message: str | None = None,
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

            CASE
                WHEN ? = 'SUCCESS'
                THEN CURRENT_TIMESTAMP
                ELSE NULL
            END,

            CURRENT_TIMESTAMP,

            ?,
            ?,
            ?,

            CURRENT_TIMESTAMP
        )
        ON CONFLICT(dataset)
        DO UPDATE SET

            last_data_date =
                excluded.last_data_date,

            last_success_at =
                CASE
                    WHEN excluded.status = 'SUCCESS'
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
                excluded.error_message,

            updated_at =
                CURRENT_TIMESTAMP
        """,
        (
            dataset,
            last_data_date,
            status,
            status,
            records_processed,
            error_message,
        ),
    )


def verify_written_row(
    conn,
    row: IndexRow,
) -> None:

    count = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM market_index_daily
            WHERE market = ?
              AND index_code = ?
              AND trade_date = ?
            """,
            (
                row.market,
                row.index_code,
                row.trade_date,
            ),
        )
        or 0
    )

    if count != 1:

        raise RuntimeError(
            f"{row.market} "
            "DB verification failed for "
            f"{row.trade_date}: "
            f"{count}"
        )


def commit_rows(
    conn,
    rows_by_market: dict[
        str,
        list[IndexRow],
    ],
    cursors: dict[
        str,
        str | None,
    ],
    processed: dict[
        str,
        int,
    ],
) -> None:

    next_cursors = dict(
        cursors
    )

    next_processed = dict(
        processed
    )

    conn.execute(
        "BEGIN"
    )

    try:

        for market in (
            "TWSE",
            "TPEX",
        ):

            rows = (
                rows_by_market.get(
                    market,
                    [],
                )
            )

            for row in rows:

                insert_index_row(
                    conn,
                    row,
                )

                next_cursors[
                    market
                ] = row.trade_date

                next_processed[
                    market
                ] += 1

            update_sync_state(
                conn,
                DATASETS[market],
                next_cursors[market],
                next_processed[market],
                "SUCCESS",
            )

        conn.commit()

    except BaseException:

        try:
            conn.rollback()
        except Exception:
            pass

        raise

    for market in (
        "TWSE",
        "TPEX",
    ):

        for row in (
            rows_by_market.get(
                market,
                [],
            )
        ):

            verify_written_row(
                conn,
                row,
            )

    cursors.update(
        next_cursors
    )

    processed.update(
        next_processed
    )


def mark_run_status(
    conn,
    cursors: dict[
        str,
        str | None,
    ],
    processed: dict[
        str,
        int,
    ],
    status: str,
    error_message: str | None = None,
) -> None:

    conn.execute(
        "BEGIN"
    )

    try:

        for market in (
            "TWSE",
            "TPEX",
        ):

            update_sync_state(
                conn,
                DATASETS[market],
                cursors[market],
                processed[market],
                status,
                error_message,
            )

        conn.commit()

    except BaseException:

        try:
            conn.rollback()
        except Exception:
            pass

        raise


# ============================================================
# READ-ONLY VALIDATION
# ============================================================


def run_validation(
    conn,
    trade_date: date,
) -> None:

    if trade_date.weekday() >= 5:

        raise RuntimeError(
            "--validate-date must be "
            "a known trading weekday"
        )

    print()
    print("=" * 76)
    print(
        "READ-ONLY MARKET INDEX VALIDATION"
    )
    print("=" * 76)

    print(
        "Trade Date : "
        f"{trade_date.isoformat()}"
    )

    print(
        "Turso Write: DISABLED"
    )

    print()

    selected: dict[
        str,
        IndexRow,
    ] = {}

    for index, market in enumerate(
        (
            "TWSE",
            "TPEX",
        )
    ):

        if index:
            time.sleep(
                REQUEST_DELAY
            )

        month_rows = (
            fetch_market_month(
                market,
                first_day_of_month(
                    trade_date
                ),
            )
        )

        row = next(
            (
                item
                for item in month_rows
                if (
                    item.trade_date
                    == trade_date.isoformat()
                )
            ),
            None,
        )

        if row is None:

            raise RuntimeError(
                f"{market} returned no "
                "index data for "
                f"{trade_date.isoformat()}"
            )

        selected[
            market
        ] = row

        print(
            f"{market:<4} "
            f"| index={row.index_code:<5} "
            f"| O={row.open:.2f} "
            f"H={row.high:.2f} "
            f"L={row.low:.2f} "
            f"C={row.close:.2f} "
            f"| source_rows="
            f"{len(month_rows)}"
        )

    if set(
        selected
    ) != {
        "TWSE",
        "TPEX",
    }:

        raise RuntimeError(
            "Both TWSE and TPEx "
            "index rows are required"
        )

    print()

    print(
        "[PASS] Official source fetch"
    )

    print(
        "[PASS] Date normalization"
    )

    print(
        "[PASS] Duplicate / OHLC validation"
    )

    print(
        "[PASS] Turso DEV read connection"
    )

    print(
        "[PASS] No database rows were written"
    )


# ============================================================
# INCREMENTAL
# ============================================================


def run_incremental(
    conn,
    through: date,
) -> None:

    cursors: dict[
        str,
        str | None,
    ] = {

        market: (
            get_latest_index_date(
                conn,
                market,
            )
        )

        for market in (
            "TWSE",
            "TPEX",
        )
    }

    print()

    print("=" * 76)

    print(
        "MARKET INDEX "
        "INCREMENTAL CURSOR"
    )

    print("=" * 76)

    print(
        "TWSE Last Data Date : "
        f"{cursors['TWSE'] or 'EMPTY'}"
    )

    print(
        "TPEx Last Data Date : "
        f"{cursors['TPEX'] or 'EMPTY'}"
    )

    print(
        "Through Date        : "
        f"{through.isoformat()}"
    )

    processed = {
        "TWSE": 0,
        "TPEX": 0,
    }

    start_candidates: list[
        date
    ] = []

    for market in (
        "TWSE",
        "TPEX",
    ):

        cursor = cursors[
            market
        ]

        if cursor is None:

            # 第一次 Daily Pipeline 執行時，
            # 只 seed 目標月份。
            #
            # 2～5 年 Historical Backfill
            # 保留為獨立流程，
            # 不讓 Daily Pipeline 偷偷變成
            # Historical Backfill。
            start_candidates.append(
                first_day_of_month(
                    through
                )
            )

        else:

            start_candidates.append(
                parse_iso_date(
                    cursor
                )
                + timedelta(days=1)
            )

    fetch_start = min(
        start_candidates
    )

    if fetch_start > through:

        print()

        print(
            "[PASS] "
            "No pending calendar dates"
        )

        mark_run_status(
            conn,
            cursors,
            processed,
            "SUCCESS",
        )

        return

    try:

        source_rows: dict[
            str,
            list[IndexRow],
        ] = {}

        for index, market in enumerate(
            (
                "TWSE",
                "TPEX",
            )
        ):

            if index:

                time.sleep(
                    REQUEST_DELAY
                )

            source_rows[
                market
            ] = fetch_market_range(
                market,
                fetch_start,
                through,
            )

        available_dates = {

            market: {
                row.trade_date
                for row in rows
            }

            for (
                market,
                rows,
            ) in source_rows.items()
        }

        # 台股上市 / 上櫃交易日應一致。
        #
        # 只有兩邊官方來源都確認存在
        # 的日期才允許往前推進，
        # 避免其中一個來源提早發布造成
        # 半套 Market Regime。
        common_dates = (
            available_dates["TWSE"]
            &
            available_dates["TPEX"]
        )

        rows_by_market: dict[
            str,
            list[IndexRow],
        ] = {
            "TWSE": [],
            "TPEX": [],
        }

        for market in (
            "TWSE",
            "TPEX",
        ):

            cursor = cursors[
                market
            ]

            for row in (
                source_rows[
                    market
                ]
            ):

                if (
                    row.trade_date
                    not in common_dates
                ):
                    continue

                if (
                    cursor is not None
                    and
                    row.trade_date
                    <= cursor
                ):
                    continue

                rows_by_market[
                    market
                ].append(row)

        if (
            not rows_by_market["TWSE"]
            and
            not rows_by_market["TPEX"]
        ):

            print()

            print(
                "[PASS] No new common "
                "trading-date index rows. "
                "Weekend, holiday, or "
                "latest data not published yet."
            )

            mark_run_status(
                conn,
                cursors,
                processed,
                "SUCCESS",
            )

            return

        print()

        for market in (
            "TWSE",
            "TPEX",
        ):

            rows = rows_by_market[
                market
            ]

            if rows:

                print(
                    f"{market:<4} "
                    f"| pending="
                    f"{len(rows):,} "
                    f"| "
                    f"{rows[0].trade_date} "
                    f".. "
                    f"{rows[-1].trade_date}"
                )

            else:

                print(
                    f"{market:<4} "
                    "| pending=0"
                )

        commit_rows(
            conn,
            rows_by_market,
            cursors,
            processed,
        )

    except Exception as exc:

        try:

            mark_run_status(
                conn,
                cursors,
                processed,
                "FAILED",
                str(exc)[:1000],
            )

        except Exception:
            pass

        raise

    print()

    print("=" * 76)

    print(
        "MARKET INDEX "
        "INCREMENTAL RESULT"
    )

    print("=" * 76)

    print(
        "TWSE Last Data Date : "
        f"{cursors['TWSE'] or 'EMPTY'}"
    )

    print(
        "TPEx Last Data Date : "
        f"{cursors['TPEX'] or 'EMPTY'}"
    )

    print(
        "TWSE Rows This Run  : "
        f"{processed['TWSE']:,}"
    )

    print(
        "TPEx Rows This Run  : "
        f"{processed['TPEX']:,}"
    )

    print(
        "PROD Access         : "
        "DISABLED"
    )


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    args = parse_args()

    print("=" * 76)

    print(
        "StockWaveScanner V2 - "
        "Market Index Incremental Pipeline"
    )

    print("=" * 76)

    try:

        url, token = (
            load_dev_credentials()
        )

        print(
            "Target      : DEV"
        )

        print(
            "Database    : "
            f"{mask_url(url)}"
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
                conn
                .execute(
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
                    "Turso DEV connection "
                    "validation failed"
                )

            schema_version = (
                get_schema_version(
                    conn
                )
            )

            if schema_version is None:

                raise RuntimeError(
                    "schema_meta/"
                    "schema_version "
                    "is missing"
                )

            print(
                "Schema      : "
                f"{schema_version}"
            )

            print(
                "[PASS] "
                "Turso DEV connection"
            )

            if args.validate_date:

                run_validation(
                    conn,
                    parse_iso_date(
                        args.validate_date
                    ),
                )

            else:

                if args.through:

                    through = (
                        parse_iso_date(
                            args.through
                        )
                    )

                else:

                    through = (
                        taipei_today()
                    )

                if (
                    through
                    > taipei_today()
                ):

                    raise RuntimeError(
                        "Through date cannot "
                        "be later than today "
                        "in Taiwan"
                    )

                run_incremental(
                    conn,
                    through,
                )

        finally:

            conn.close()

        print()

        print("=" * 76)

        print(
            "MARKET INDEX PIPELINE OK"
        )

        print("=" * 76)

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

        print("=" * 76)

        print(
            "ERROR"
        )

        print("=" * 76)

        print(
            str(exc)
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