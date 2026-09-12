from __future__ import annotations

import csv
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

RUNTIME_DIR = ROOT / "runtime"
STAGING_DB = RUNTIME_DIR / "price_backfill.db"
UNKNOWN_CSV = RUNTIME_DIR / "price_unknown_securities.csv"

START_DATE = date(2024, 9, 1)
END_DATE = date(2026, 9, 11)

TIMEOUT = 45
REQUEST_DELAY = 0.35

USER_AGENT = (
    "Mozilla/5.0 "
    "StockWaveScanner-V2-Historical-Price/1.0"
)

TWSE_URL = (
    "https://www.twse.com.tw/"
    "rwd/zh/afterTrading/MI_INDEX"
)

TPEX_URL = (
    "https://www.tpex.org.tw/web/stock/"
    "aftertrading/otc_quotes_no1430/"
    "stk_wn1430_result.php"
)


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    return text


def parse_number(value: Any) -> float | None:
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


def parse_int(value: Any) -> int | None:
    number = parse_number(value)

    if number is None:
        return None

    return int(number)


def normalize_field(value: Any) -> str:
    if value is None:
        return ""

    return (
        str(value)
        .replace(" ", "")
        .replace("\u3000", "")
        .replace("\n", "")
        .replace("\r", "")
        .strip()
    )


def find_field(
    fields: list[str],
    aliases: tuple[str, ...],
) -> int | None:
    normalized = [
        normalize_field(field)
        for field in fields
    ]

    normalized_aliases = {
        normalize_field(alias)
        for alias in aliases
    }

    for index, field in enumerate(
        normalized
    ):
        if field in normalized_aliases:
            return index

    return None


def value_at(
    row: list[Any],
    index: int | None,
) -> Any:
    if index is None:
        return None

    if index >= len(row):
        return None

    return row[index]


# ============================================================
# HTTP
# ============================================================

def curl_path() -> str | None:
    return (
        shutil.which("curl.exe")
        or shutil.which("curl")
    )


def fetch_urllib(
    url: str,
    referer: str | None = None,
) -> bytes:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
        "Cache-Control": "no-cache",
    }

    if referer:
        headers["Referer"] = referer

    request = urllib.request.Request(
        url,
        headers=headers,
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
    referer: str | None = None,
) -> bytes:
    curl = curl_path()

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

    if referer:
        command.extend(
            ["-e", referer]
        )

    command.append(url)

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if result.returncode != 0:
        error = result.stderr.decode(
            "utf-8",
            errors="replace",
        ).strip()

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
    referer: str | None = None,
) -> bytes:
    delays = [0, 3, 10, 30]

    errors: list[str] = []

    for attempt, delay in enumerate(
        delays,
        start=1,
    ):
        if delay:
            time.sleep(delay)

        loaders = [
            fetch_urllib,
            fetch_curl,
        ]

        for loader in loaders:
            try:
                return loader(
                    url,
                    referer,
                )
            except Exception as exc:
                errors.append(
                    f"attempt={attempt} "
                    f"{loader.__name__}: {exc}"
                )

        if attempt < len(delays):
            print(
                f"    retrying HTTP "
                f"({attempt}/{len(delays)}) ..."
            )

    raise RuntimeError(
        " | ".join(
            errors[-6:]
        )
    )


def decode_json(
    data: bytes,
) -> dict[str, Any]:
    text = data.decode(
        "utf-8-sig",
        errors="replace",
    )

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON: {exc}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "JSON root is not an object"
        )

    return payload


# ============================================================
# TWSE
# ============================================================

def twse_url(
    trade_date: date,
) -> str:
    query = urllib.parse.urlencode(
        {
            "date": trade_date.strftime(
                "%Y%m%d"
            ),
            "type": "ALLBUT0999",
            "response": "json",
        }
    )

    return f"{TWSE_URL}?{query}"


def find_twse_price_table(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    tables = payload.get(
        "tables",
        [],
    )

    if not isinstance(
        tables,
        list,
    ):
        return None

    for table in tables:
        if not isinstance(
            table,
            dict,
        ):
            continue

        fields = table.get(
            "fields",
            [],
        )

        if not isinstance(
            fields,
            list,
        ):
            continue

        normalized = {
            normalize_field(field)
            for field in fields
        }

        if (
            "證券代號" in normalized
            and "收盤價" in normalized
            and "開盤價" in normalized
            and "最高價" in normalized
            and "最低價" in normalized
        ):
            return table

    return None


def fetch_twse_day(
    trade_date: date,
) -> list[tuple[Any, ...]]:
    raw = fetch_with_retry(
        twse_url(trade_date)
    )

    payload = decode_json(raw)

    stat = str(
        payload.get(
            "stat",
            "",
        )
    ).strip()

    if stat.upper() != "OK":
        return []

    table = find_twse_price_table(
        payload
    )

    if table is None:
        raise RuntimeError(
            "TWSE price table not found"
        )

    fields = [
        str(field)
        for field in table.get(
            "fields",
            []
        )
    ]

    data = table.get(
        "data",
        [],
    )

    if not isinstance(data, list):
        raise RuntimeError(
            "TWSE table data is invalid"
        )

    code_i = find_field(
        fields,
        ("證券代號",),
    )

    name_i = find_field(
        fields,
        ("證券名稱",),
    )

    volume_i = find_field(
        fields,
        ("成交股數",),
    )

    turnover_i = find_field(
        fields,
        ("成交金額",),
    )

    trade_count_i = find_field(
        fields,
        ("成交筆數",),
    )

    open_i = find_field(
        fields,
        ("開盤價",),
    )

    high_i = find_field(
        fields,
        ("最高價",),
    )

    low_i = find_field(
        fields,
        ("最低價",),
    )

    close_i = find_field(
        fields,
        ("收盤價",),
    )

    required = {
        "code": code_i,
        "open": open_i,
        "high": high_i,
        "low": low_i,
        "close": close_i,
    }

    missing = [
        name
        for name, index
        in required.items()
        if index is None
    ]

    if missing:
        raise RuntimeError(
            "TWSE required fields missing: "
            + ", ".join(missing)
        )

    result: list[
        tuple[Any, ...]
    ] = []

    date_text = trade_date.isoformat()

    for row in data:
        if not isinstance(
            row,
            list,
        ):
            continue

        stock_id = clean_text(
            value_at(
                row,
                code_i,
            )
        )

        if (
            stock_id is None
            or not stock_id.isdigit()
            or len(stock_id) != 4
        ):
            continue

        close = parse_number(
            value_at(
                row,
                close_i,
            )
        )

        if close is None:
            # 停止交易 / 無成交價格不建立 K 棒。
            continue

        result.append(
            (
                "TWSE",
                stock_id,
                clean_text(
                    value_at(
                        row,
                        name_i,
                    )
                ),
                date_text,
                parse_number(
                    value_at(
                        row,
                        open_i,
                    )
                ),
                parse_number(
                    value_at(
                        row,
                        high_i,
                    )
                ),
                parse_number(
                    value_at(
                        row,
                        low_i,
                    )
                ),
                close,
                parse_int(
                    value_at(
                        row,
                        volume_i,
                    )
                ),
                parse_number(
                    value_at(
                        row,
                        turnover_i,
                    )
                ),
                parse_int(
                    value_at(
                        row,
                        trade_count_i,
                    )
                ),
                "TWSE_MI_INDEX",
            )
        )

    return result


# ============================================================
# TPEX
# ============================================================

def to_roc_date(
    trade_date: date,
) -> str:
    roc_year = (
        trade_date.year
        - 1911
    )

    return (
        f"{roc_year}/"
        f"{trade_date.month:02d}/"
        f"{trade_date.day:02d}"
    )


def tpex_url(
    trade_date: date,
) -> str:
    # TPEx historical endpoint uses ROC date.
    roc_date = to_roc_date(
        trade_date
    )

    return (
        f"{TPEX_URL}"
        f"?l=zh-tw"
        f"&d={roc_date}"
        f"&se=EW"
        f"&o=json"
    )


def find_tpex_price_table(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    tables = payload.get(
        "tables",
        [],
    )

    if not isinstance(
        tables,
        list,
    ):
        return None

    for table in tables:
        if not isinstance(
            table,
            dict,
        ):
            continue

        fields = table.get(
            "fields",
            [],
        )

        if not isinstance(
            fields,
            list,
        ):
            continue

        normalized = {
            normalize_field(field)
            for field in fields
        }

        has_code = (
            "代號" in normalized
            or "證券代號" in normalized
        )

        has_close = (
            "收盤" in normalized
            or "收盤價" in normalized
        )

        has_open = (
            "開盤" in normalized
            or "開盤價" in normalized
        )

        if (
            has_code
            and has_close
            and has_open
        ):
            return table

    return None


def fetch_tpex_day(
    trade_date: date,
) -> list[tuple[Any, ...]]:
    referer = (
        "https://www.tpex.org.tw/"
        "zh-tw/mainboard/trading/info/"
        "mi-pricing.html"
    )

    raw = fetch_with_retry(
        tpex_url(trade_date),
        referer=referer,
    )

    payload = decode_json(raw)

    table = find_tpex_price_table(
        payload
    )

    if table is None:
        # 假日 / 無資料時 TPEx 可能回空 tables。
        tables = payload.get(
            "tables",
            [],
        )

        if not tables:
            return []

        stat = str(
            payload.get(
                "stat",
                "",
            )
        ).lower()

        if stat not in {
            "",
            "ok",
        }:
            return []

        raise RuntimeError(
            "TPEx price table not found"
        )

    fields = [
        str(field)
        for field in table.get(
            "fields",
            []
        )
    ]

    data = table.get(
        "data",
        [],
    )

    if not isinstance(data, list):
        raise RuntimeError(
            "TPEx table data is invalid"
        )

    code_i = find_field(
        fields,
        (
            "代號",
            "證券代號",
        ),
    )

    name_i = find_field(
        fields,
        (
            "名稱",
            "證券名稱",
        ),
    )

    close_i = find_field(
        fields,
        (
            "收盤",
            "收盤價",
        ),
    )

    open_i = find_field(
        fields,
        (
            "開盤",
            "開盤價",
        ),
    )

    high_i = find_field(
        fields,
        (
            "最高",
            "最高價",
        ),
    )

    low_i = find_field(
        fields,
        (
            "最低",
            "最低價",
        ),
    )

    volume_i = find_field(
        fields,
        (
            "成交股數",
            "成交量",
        ),
    )

    turnover_i = find_field(
        fields,
        (
            "成交金額(元)",
            "成交金額",
        ),
    )

    trade_count_i = find_field(
        fields,
        (
            "成交筆數",
        ),
    )

    required = {
        "code": code_i,
        "open": open_i,
        "high": high_i,
        "low": low_i,
        "close": close_i,
    }

    missing = [
        name
        for name, index
        in required.items()
        if index is None
    ]

    if missing:
        raise RuntimeError(
            "TPEx required fields missing: "
            + ", ".join(missing)
        )

    result: list[
        tuple[Any, ...]
    ] = []

    date_text = trade_date.isoformat()

    for row in data:
        if not isinstance(
            row,
            list,
        ):
            continue

        stock_id = clean_text(
            value_at(
                row,
                code_i,
            )
        )

        if (
            stock_id is None
            or not stock_id.isdigit()
            or len(stock_id) != 4
        ):
            continue

        close = parse_number(
            value_at(
                row,
                close_i,
            )
        )

        if close is None:
            continue

        result.append(
            (
                "TPEX",
                stock_id,
                clean_text(
                    value_at(
                        row,
                        name_i,
                    )
                ),
                date_text,
                parse_number(
                    value_at(
                        row,
                        open_i,
                    )
                ),
                parse_number(
                    value_at(
                        row,
                        high_i,
                    )
                ),
                parse_number(
                    value_at(
                        row,
                        low_i,
                    )
                ),
                close,
                parse_int(
                    value_at(
                        row,
                        volume_i,
                    )
                ),
                parse_number(
                    value_at(
                        row,
                        turnover_i,
                    )
                ),
                parse_int(
                    value_at(
                        row,
                        trade_count_i,
                    )
                ),
                "TPEX_DAILY_CLOSE",
            )
        )

    return result


# ============================================================
# STAGING DATABASE
# ============================================================

def connect_staging() -> sqlite3.Connection:
    RUNTIME_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    conn = sqlite3.connect(
        STAGING_DB
    )

    conn.execute(
        "PRAGMA journal_mode = WAL"
    )

    conn.execute(
        "PRAGMA synchronous = NORMAL"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS price_staging (
            market          TEXT NOT NULL,
            stock_id        TEXT NOT NULL,
            stock_name      TEXT,
            trade_date      TEXT NOT NULL,

            open            REAL,
            high            REAL,
            low             REAL,
            close           REAL NOT NULL,

            volume          INTEGER,
            turnover        REAL,
            trade_count     INTEGER,

            source          TEXT NOT NULL,

            PRIMARY KEY (
                market,
                stock_id,
                trade_date
            )
        )
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_price_staging_stock_date
        ON price_staging (
            stock_id,
            trade_date
        )
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_price_staging_date
        ON price_staging (
            trade_date
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fetch_log (
            market          TEXT NOT NULL,
            trade_date      TEXT NOT NULL,

            status          TEXT NOT NULL,
            row_count       INTEGER NOT NULL DEFAULT 0,
            error_message   TEXT,
            updated_at      TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (
                market,
                trade_date
            )
        )
        """
    )

    conn.commit()

    return conn


PRICE_INSERT_SQL = """
INSERT INTO price_staging (
    market,
    stock_id,
    stock_name,
    trade_date,
    open,
    high,
    low,
    close,
    volume,
    turnover,
    trade_count,
    source
)
VALUES (
    ?, ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?, ?
)
ON CONFLICT(
    market,
    stock_id,
    trade_date
)
DO UPDATE SET
    stock_name = excluded.stock_name,
    open = excluded.open,
    high = excluded.high,
    low = excluded.low,
    close = excluded.close,
    volume = excluded.volume,
    turnover = excluded.turnover,
    trade_count = excluded.trade_count,
    source = excluded.source
"""


def log_fetch(
    conn: sqlite3.Connection,
    market: str,
    trade_date: date,
    status: str,
    row_count: int,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO fetch_log (
            market,
            trade_date,
            status,
            row_count,
            error_message,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT(
            market,
            trade_date
        )
        DO UPDATE SET
            status = excluded.status,
            row_count = excluded.row_count,
            error_message =
                excluded.error_message,
            updated_at =
                CURRENT_TIMESTAMP
        """,
        (
            market,
            trade_date.isoformat(),
            status,
            row_count,
            error_message,
        ),
    )


def already_done(
    conn: sqlite3.Connection,
    market: str,
    trade_date: date,
) -> bool:
    row = conn.execute(
        """
        SELECT status
        FROM fetch_log
        WHERE market = ?
          AND trade_date = ?
        """,
        (
            market,
            trade_date.isoformat(),
        ),
    ).fetchone()

    if row is None:
        return False

    return row[0] in {
        "OK",
        "NO_DATA",
    }


def store_day(
    conn: sqlite3.Connection,
    market: str,
    trade_date: date,
    rows: list[tuple[Any, ...]],
) -> None:
    if rows:
        conn.executemany(
            PRICE_INSERT_SQL,
            rows,
        )

        log_fetch(
            conn,
            market,
            trade_date,
            "OK",
            len(rows),
        )

    else:
        log_fetch(
            conn,
            market,
            trade_date,
            "NO_DATA",
            0,
        )

    conn.commit()


# ============================================================
# TURSO READ-ONLY CLASSIFICATION
# ============================================================

def load_stock_master_ids() -> set[str]:
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

    if not url or not token:
        raise RuntimeError(
            "Turso DEV credentials missing"
        )

    lower_url = url.lower()

    if (
        "stockwave-dev"
        not in lower_url
        or "stockwave-prod"
        in lower_url
    ):
        raise RuntimeError(
            "SAFETY STOP: invalid DEV URL"
        )

    conn = libsql.connect(
        database=url,
        auth_token=token,
    )

    try:
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

    finally:
        conn.close()


# ============================================================
# DATE RANGE
# ============================================================

def weekday_dates(
    start: date,
    end: date,
) -> list[date]:
    result: list[date] = []

    current = start

    while current <= end:
        if current.weekday() < 5:
            result.append(
                current
            )

        current += timedelta(
            days=1
        )

    return result


# ============================================================
# AUDIT
# ============================================================

def export_unknown_securities(
    conn: sqlite3.Connection,
    known_ids: set[str],
) -> list[tuple[Any, ...]]:
    placeholders = ",".join(
        "?"
        for _ in known_ids
    )

    if not known_ids:
        raise RuntimeError(
            "Stock Master is empty"
        )

    sql = f"""
        SELECT
            market,
            stock_id,
            MAX(stock_name) AS stock_name,
            MIN(trade_date) AS first_date,
            MAX(trade_date) AS last_date,
            COUNT(*) AS row_count
        FROM price_staging
        WHERE stock_id NOT IN (
            {placeholders}
        )
        GROUP BY
            market,
            stock_id
        ORDER BY
            market,
            stock_id
    """

    rows = conn.execute(
        sql,
        tuple(
            sorted(known_ids)
        ),
    ).fetchall()

    with UNKNOWN_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.writer(
            file
        )

        writer.writerow(
            [
                "market",
                "stock_id",
                "stock_name",
                "first_date",
                "last_date",
                "row_count",
            ]
        )

        writer.writerows(
            rows
        )

    return rows


def print_summary(
    conn: sqlite3.Connection,
    known_ids: set[str],
) -> None:
    print()
    print("=" * 76)
    print("STAGING SUMMARY")
    print("=" * 76)

    for market in (
        "TWSE",
        "TPEX",
    ):
        row = conn.execute(
            """
            SELECT
                COUNT(*),
                COUNT(DISTINCT stock_id),
                COUNT(DISTINCT trade_date),
                MIN(trade_date),
                MAX(trade_date)
            FROM price_staging
            WHERE market = ?
            """,
            (market,),
        ).fetchone()

        print()
        print(market)

        print(
            f"  Rows        : "
            f"{row[0]:,}"
        )

        print(
            f"  Securities  : "
            f"{row[1]:,}"
        )

        print(
            f"  Trade Dates : "
            f"{row[2]:,}"
        )

        print(
            f"  Date Range  : "
            f"{row[3]} .. {row[4]}"
        )

        fetch = conn.execute(
            """
            SELECT
                status,
                COUNT(*)
            FROM fetch_log
            WHERE market = ?
            GROUP BY status
            ORDER BY status
            """,
            (market,),
        ).fetchall()

        print(
            "  Fetch Log:"
        )

        for status, count in fetch:
            print(
                f"    {status:<8}: "
                f"{count:,}"
            )

    total = conn.execute(
        """
        SELECT COUNT(*)
        FROM price_staging
        """
    ).fetchone()[0]

    known_rows = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM price_staging
        WHERE stock_id IN (
            {",".join("?" for _ in known_ids)}
        )
        """,
        tuple(
            sorted(known_ids)
        ),
    ).fetchone()[0]

    unknown = export_unknown_securities(
        conn,
        known_ids,
    )

    print()
    print(
        f"Total Staging Rows : "
        f"{total:,}"
    )

    print(
        f"Known Master Rows   : "
        f"{known_rows:,}"
    )

    print(
        f"Unknown Securities  : "
        f"{len(unknown):,}"
    )

    print(
        f"Unknown Report      : "
        f"{UNKNOWN_CSV}"
    )

    if unknown:
        print()
        print(
            "Unknown sample:"
        )

        for row in unknown[:20]:
            print(
                f"  {row[0]} "
                f"{row[1]} "
                f"{row[2]} "
                f"| {row[3]}..{row[4]} "
                f"| rows={row[5]}"
            )


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    print("=" * 76)
    print(
        "StockWaveScanner V2 - "
        "Historical Price Staging Backfill"
    )
    print("=" * 76)

    print()
    print(
        f"Range      : "
        f"{START_DATE} .. {END_DATE}"
    )

    print(
        "Method     : "
        "Whole-market daily batch"
    )

    print(
        "Turso Write: DISABLED"
    )

    print(
        f"Staging DB : "
        f"{STAGING_DB}"
    )

    print()

    try:
        known_ids = (
            load_stock_master_ids()
        )

        print(
            f"[PASS] Turso DEV "
            f"Stock Master loaded: "
            f"{len(known_ids):,}"
        )

        staging = (
            connect_staging()
        )

        try:
            dates = weekday_dates(
                START_DATE,
                END_DATE,
            )

            print(
                f"Weekdays   : "
                f"{len(dates):,}"
            )

            print()
            print(
                "Starting / resuming download ..."
            )

            work_total = (
                len(dates)
                * 2
            )

            work_done = 0

            new_requests = 0
            errors = 0

            for trade_date in dates:
                tasks = [
                    (
                        "TWSE",
                        fetch_twse_day,
                    ),
                    (
                        "TPEX",
                        fetch_tpex_day,
                    ),
                ]

                for market, loader in tasks:
                    work_done += 1

                    if already_done(
                        staging,
                        market,
                        trade_date,
                    ):
                        continue

                    try:
                        rows = loader(
                            trade_date
                        )

                        store_day(
                            staging,
                            market,
                            trade_date,
                            rows,
                        )

                        new_requests += 1

                    except Exception as exc:
                        errors += 1

                        log_fetch(
                            staging,
                            market,
                            trade_date,
                            "ERROR",
                            0,
                            str(exc)[:1000],
                        )

                        staging.commit()

                        print()
                        print(
                            f"[ERROR] "
                            f"{market} "
                            f"{trade_date}: "
                            f"{exc}"
                        )

                    time.sleep(
                        REQUEST_DELAY
                    )

                if (
                    work_done % 40 == 0
                    or trade_date
                    == dates[-1]
                ):
                    staged_rows = (
                        staging.execute(
                            """
                            SELECT COUNT(*)
                            FROM price_staging
                            """
                        ).fetchone()[0]
                    )

                    print(
                        f"  Progress "
                        f"{work_done:,}/"
                        f"{work_total:,}"
                        f" | date={trade_date}"
                        f" | rows="
                        f"{staged_rows:,}"
                        f" | errors={errors:,}"
                    )

            print_summary(
                staging,
                known_ids,
            )

            error_rows = (
                staging.execute(
                    """
                    SELECT
                        market,
                        trade_date,
                        error_message
                    FROM fetch_log
                    WHERE status = 'ERROR'
                    ORDER BY
                        trade_date,
                        market
                    """
                ).fetchall()
            )

            print()
            print("=" * 76)

            if error_rows:
                print(
                    "BACKFILL COMPLETED "
                    "WITH ERRORS"
                )

                print("=" * 76)

                print(
                    f"Error Dates : "
                    f"{len(error_rows):,}"
                )

                print()
                print(
                    "First errors:"
                )

                for row in error_rows[:20]:
                    print(
                        f"  {row[0]} "
                        f"{row[1]} "
                        f"| {row[2]}"
                    )

                print()
                print(
                    "Re-run this same command "
                    "to retry ERROR dates."
                )

                return 2

            print(
                "PRICE STAGING BACKFILL OK"
            )

            print("=" * 76)

            print()
            print(
                "Historical data is staged locally."
            )

            print(
                "No historical price rows "
                "were written to Turso."
            )

            return 0

        finally:
            staging.close()

    except Exception as exc:
        print()
        print("=" * 76)
        print("ERROR")
        print("=" * 76)
        print(str(exc))

        print()
        print(
            "Existing staging data "
            "remains available for resume."
        )

        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )