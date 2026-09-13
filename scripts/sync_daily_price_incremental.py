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
SQL_ROWS_PER_STATEMENT = 100
MIN_ACTIVE_COVERAGE = 0.70
TAIPEI_TZ = timezone(timedelta(hours=8))

USER_AGENT = "Mozilla/5.0 StockWaveScanner-V2-Daily-Price/1.0"
TWSE_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
TPEX_URL = (
    "https://www.tpex.org.tw/web/stock/aftertrading/"
    "otc_quotes_no1430/stk_wn1430_result.php"
)
TPEX_REFERER = (
    "https://www.tpex.org.tw/zh-tw/mainboard/trading/info/mi-pricing.html"
)
DATASETS = {"TWSE": "stock_price_twse", "TPEX": "stock_price_tpex"}
SOURCES = {"TWSE": "TWSE_MI_INDEX", "TPEX": "TPEX_DAILY_CLOSE"}


@dataclass(frozen=True)
class PriceRow:
    market: str
    stock_id: str
    stock_name: str | None
    trade_date: str
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: int | None
    turnover: float | None
    trade_count: int | None
    source: str

    def db_tuple(self) -> tuple[Any, ...]:
        return (
            self.stock_id,
            self.trade_date,
            self.open,
            self.high,
            self.low,
            self.close,
            self.volume,
            self.turnover,
            self.trade_count,
            self.source,
        )


# ============================================================
# CLI / BASIC HELPERS
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Incrementally sync TWSE / TPEx daily prices into Turso DEV."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--through",
        metavar="YYYY-MM-DD",
        help="Sync through this Taiwan calendar date. Default: today UTC+8.",
    )
    group.add_argument(
        "--validate-date",
        metavar="YYYY-MM-DD",
        help=(
            "READ-ONLY: fetch and validate one known trading date without "
            "writing Turso."
        ),
    )
    return parser.parse_args()


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid date '{value}'. Expected YYYY-MM-DD."
        ) from exc


def taipei_today() -> date:
    return datetime.now(TAIPEI_TZ).date()


def daterange(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_number(value: Any) -> float | None:
    text = clean_text(value)
    if text is None:
        return None
    text = (
        text.replace(",", "")
        .replace("，", "")
        .replace("\u3000", "")
        .strip()
    )
    if text in {"-", "--", "---", "----", "N/A", "NA"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    number = parse_number(value)
    return None if number is None else int(number)


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


def find_field(fields: list[str], aliases: tuple[str, ...]) -> int | None:
    normalized = [normalize_field(field) for field in fields]
    wanted = {normalize_field(alias) for alias in aliases}
    for index, field in enumerate(normalized):
        if field in wanted:
            return index
    return None


def value_at(row: list[Any], index: int | None) -> Any:
    if index is None or index >= len(row):
        return None
    return row[index]


# ============================================================
# DEV SAFETY
# ============================================================

def load_dev_credentials() -> tuple[str, str]:
    load_dotenv(ENV_FILE)
    url = os.getenv("TURSO_DEV_DATABASE_URL", "").strip()
    token = os.getenv("TURSO_DEV_AUTH_TOKEN", "").strip()

    if not url:
        raise RuntimeError("TURSO_DEV_DATABASE_URL is missing from .env")
    if not token:
        raise RuntimeError("TURSO_DEV_AUTH_TOKEN is missing from .env")

    lower_url = url.lower()
    if "stockwave-dev" not in lower_url:
        raise RuntimeError(
            "SAFETY STOP: DEV URL does not point to stockwave-dev"
        )
    if "stockwave-prod" in lower_url:
        raise RuntimeError("SAFETY STOP: PROD database detected")
    return url, token


def mask_url(url: str) -> str:
    if "://" not in url:
        return "***"
    scheme, rest = url.split("://", 1)
    return f"{scheme}://{rest}"


# ============================================================
# HTTP
# ============================================================

def fetch_urllib(url: str, referer: str | None = None) -> bytes:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
        "Cache-Control": "no-cache",
    }
    if referer:
        headers["Referer"] = referer

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        data = response.read()
    if not data:
        raise RuntimeError("Empty HTTP response")
    return data


def fetch_curl(url: str, referer: str | None = None) -> bytes:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl not found")

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
        command.extend(["-e", referer])
    command.append(url)

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"curl failed: {error}")
    if not result.stdout:
        raise RuntimeError("Empty curl response")
    return result.stdout


def fetch_with_retry(url: str, referer: str | None = None) -> bytes:
    delays = [0, 3, 10, 30]
    errors: list[str] = []
    for attempt, delay in enumerate(delays, start=1):
        if delay:
            time.sleep(delay)
        for loader in (fetch_urllib, fetch_curl):
            try:
                return loader(url, referer)
            except Exception as exc:
                errors.append(
                    f"attempt={attempt} {loader.__name__}: {exc}"
                )
        if attempt < len(delays):
            print(f"    retrying HTTP ({attempt}/{len(delays)}) ...")
    raise RuntimeError(" | ".join(errors[-6:]))


def decode_json(data: bytes) -> dict[str, Any]:
    text = data.decode("utf-8-sig", errors="replace")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("JSON root is not an object")
    return payload


# ============================================================
# TWSE
# ============================================================

def twse_url(trade_date: date) -> str:
    query = urllib.parse.urlencode(
        {
            "date": trade_date.strftime("%Y%m%d"),
            "type": "ALLBUT0999",
            "response": "json",
        }
    )
    return f"{TWSE_URL}?{query}"


def find_twse_price_table(payload: dict[str, Any]) -> dict[str, Any] | None:
    tables = payload.get("tables", [])
    if not isinstance(tables, list):
        return None
    required = {"證券代號", "收盤價", "開盤價", "最高價", "最低價"}
    for table in tables:
        if not isinstance(table, dict):
            continue
        fields = table.get("fields", [])
        if isinstance(fields, list) and required.issubset(
            {normalize_field(field) for field in fields}
        ):
            return table
    return None


def fetch_twse_day(trade_date: date) -> list[PriceRow]:
    payload = decode_json(fetch_with_retry(twse_url(trade_date)))
    if str(payload.get("stat", "")).strip().upper() != "OK":
        return []

    table = find_twse_price_table(payload)
    if table is None:
        raise RuntimeError("TWSE price table not found")

    fields = [str(field) for field in table.get("fields", [])]
    data = table.get("data", [])
    if not isinstance(data, list):
        raise RuntimeError("TWSE table data is invalid")

    indexes = {
        "code": find_field(fields, ("證券代號",)),
        "name": find_field(fields, ("證券名稱",)),
        "volume": find_field(fields, ("成交股數",)),
        "turnover": find_field(fields, ("成交金額",)),
        "trade_count": find_field(fields, ("成交筆數",)),
        "open": find_field(fields, ("開盤價",)),
        "high": find_field(fields, ("最高價",)),
        "low": find_field(fields, ("最低價",)),
        "close": find_field(fields, ("收盤價",)),
    }
    missing = [
        key
        for key in ("code", "open", "high", "low", "close")
        if indexes[key] is None
    ]
    if missing:
        raise RuntimeError("TWSE required fields missing: " + ", ".join(missing))

    result: list[PriceRow] = []
    date_text = trade_date.isoformat()
    for row in data:
        if not isinstance(row, list):
            continue
        stock_id = clean_text(value_at(row, indexes["code"]))
        if stock_id is None or not stock_id.isdigit() or len(stock_id) != 4:
            continue
        close = parse_number(value_at(row, indexes["close"]))
        if close is None:
            continue
        result.append(
            PriceRow(
                "TWSE",
                stock_id,
                clean_text(value_at(row, indexes["name"])),
                date_text,
                parse_number(value_at(row, indexes["open"])),
                parse_number(value_at(row, indexes["high"])),
                parse_number(value_at(row, indexes["low"])),
                close,
                parse_int(value_at(row, indexes["volume"])),
                parse_number(value_at(row, indexes["turnover"])),
                parse_int(value_at(row, indexes["trade_count"])),
                SOURCES["TWSE"],
            )
        )
    return result


# ============================================================
# TPEX
# ============================================================

def tpex_url(trade_date: date) -> str:
    roc_date = (
        f"{trade_date.year - 1911}/"
        f"{trade_date.month:02d}/"
        f"{trade_date.day:02d}"
    )
    return f"{TPEX_URL}?l=zh-tw&d={roc_date}&se=EW&o=json"


def find_tpex_price_table(payload: dict[str, Any]) -> dict[str, Any] | None:
    tables = payload.get("tables", [])
    if not isinstance(tables, list):
        return None
    for table in tables:
        if not isinstance(table, dict):
            continue
        fields = table.get("fields", [])
        if not isinstance(fields, list):
            continue
        normalized = {normalize_field(field) for field in fields}
        has_code = "代號" in normalized or "證券代號" in normalized
        has_close = "收盤" in normalized or "收盤價" in normalized
        has_open = "開盤" in normalized or "開盤價" in normalized
        if has_code and has_close and has_open:
            return table
    return None


def fetch_tpex_day(trade_date: date) -> list[PriceRow]:
    payload = decode_json(
        fetch_with_retry(tpex_url(trade_date), referer=TPEX_REFERER)
    )
    table = find_tpex_price_table(payload)
    if table is None:
        tables = payload.get("tables", [])
        if not tables:
            return []
        if str(payload.get("stat", "")).lower() not in {"", "ok"}:
            return []
        raise RuntimeError("TPEx price table not found")

    fields = [str(field) for field in table.get("fields", [])]
    data = table.get("data", [])
    if not isinstance(data, list):
        raise RuntimeError("TPEx table data is invalid")

    indexes = {
        "code": find_field(fields, ("代號", "證券代號")),
        "name": find_field(fields, ("名稱", "證券名稱")),
        "close": find_field(fields, ("收盤", "收盤價")),
        "open": find_field(fields, ("開盤", "開盤價")),
        "high": find_field(fields, ("最高", "最高價")),
        "low": find_field(fields, ("最低", "最低價")),
        "volume": find_field(fields, ("成交股數", "成交量")),
        "turnover": find_field(fields, ("成交金額(元)", "成交金額")),
        "trade_count": find_field(fields, ("成交筆數",)),
    }
    missing = [
        key
        for key in ("code", "open", "high", "low", "close")
        if indexes[key] is None
    ]
    if missing:
        raise RuntimeError("TPEx required fields missing: " + ", ".join(missing))

    result: list[PriceRow] = []
    date_text = trade_date.isoformat()
    for row in data:
        if not isinstance(row, list):
            continue
        stock_id = clean_text(value_at(row, indexes["code"]))
        if stock_id is None or not stock_id.isdigit() or len(stock_id) != 4:
            continue
        close = parse_number(value_at(row, indexes["close"]))
        if close is None:
            continue
        result.append(
            PriceRow(
                "TPEX",
                stock_id,
                clean_text(value_at(row, indexes["name"])),
                date_text,
                parse_number(value_at(row, indexes["open"])),
                parse_number(value_at(row, indexes["high"])),
                parse_number(value_at(row, indexes["low"])),
                close,
                parse_int(value_at(row, indexes["volume"])),
                parse_number(value_at(row, indexes["turnover"])),
                parse_int(value_at(row, indexes["trade_count"])),
                SOURCES["TPEX"],
            )
        )
    return result


def fetch_market_day(market: str, trade_date: date) -> list[PriceRow]:
    if market == "TWSE":
        return fetch_twse_day(trade_date)
    if market == "TPEX":
        return fetch_tpex_day(trade_date)
    raise RuntimeError(f"Unsupported market: {market}")


# ============================================================
# TURSO READ / VALIDATION
# ============================================================

def scalar(conn, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return None if row is None else row[0]


def get_schema_version(conn) -> str | None:
    value = scalar(
        conn,
        "SELECT schema_value FROM schema_meta WHERE schema_key='schema_version'",
    )
    return None if value is None else str(value)


def get_common_stock_ids(conn, market: str) -> set[str]:
    rows = conn.execute(
        """
        SELECT stock_id
        FROM stock_master
        WHERE market = ? AND security_type = 'COMMON_STOCK'
        """,
        (market,),
    ).fetchall()
    return {str(row[0]).strip() for row in rows}


def get_active_common_count(conn, market: str) -> int:
    return int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM stock_master
            WHERE market = ?
              AND security_type = 'COMMON_STOCK'
              AND is_active = 1
            """,
            (market,),
        )
        or 0
    )


def get_latest_price_date(conn, market: str) -> str | None:
    value = scalar(
        conn,
        """
        SELECT MAX(p.trade_date)
        FROM stock_price_daily p
        INNER JOIN stock_master s ON s.stock_id = p.stock_id
        WHERE s.market = ? AND s.security_type = 'COMMON_STOCK'
        """,
        (market,),
    )
    return None if value is None else str(value)


def validate_price_rows(
    market: str,
    trade_date: date,
    rows: list[PriceRow],
) -> None:
    expected_date = trade_date.isoformat()
    seen: set[str] = set()
    for row in rows:
        if row.market != market or row.trade_date != expected_date:
            raise RuntimeError(f"{market} row market/date mismatch: {row.stock_id}")
        if row.stock_id in seen:
            raise RuntimeError(f"{market} duplicate stock_id: {row.stock_id}")
        seen.add(row.stock_id)

        if (
            row.open is None
            or row.high is None
            or row.low is None
            or min(row.open, row.high, row.low, row.close) <= 0
            or row.high < max(row.open, row.low, row.close)
            or row.low > min(row.open, row.high, row.close)
        ):
            raise RuntimeError(
                f"{market} invalid OHLC: {row.stock_id} "
                f"O={row.open} H={row.high} L={row.low} C={row.close}"
            )
        for field_name, value in (
            ("volume", row.volume),
            ("turnover", row.turnover),
            ("trade_count", row.trade_count),
        ):
            if value is not None and value < 0:
                raise RuntimeError(
                    f"{market} negative {field_name}: {row.stock_id}"
                )


def prepare_market_rows(
    conn,
    market: str,
    trade_date: date,
    raw_rows: list[PriceRow],
) -> tuple[list[PriceRow], int, int, float]:
    common_ids = get_common_stock_ids(conn, market)
    active_count = get_active_common_count(conn, market)
    if not common_ids or active_count <= 0:
        raise RuntimeError(f"{market} stock_master is not ready")

    eligible = [row for row in raw_rows if row.stock_id in common_ids]
    excluded = len(raw_rows) - len(eligible)
    validate_price_rows(market, trade_date, eligible)

    coverage = len(eligible) / active_count
    if raw_rows and coverage < MIN_ACTIVE_COVERAGE:
        raise RuntimeError(
            f"{market} eligible coverage too low on {trade_date}: "
            f"{len(eligible)}/{active_count} = {coverage:.2%}"
        )
    return eligible, active_count, excluded, coverage


def print_market_summary(
    market: str,
    raw_rows: list[PriceRow],
    eligible_rows: list[PriceRow],
    active_count: int,
    excluded: int,
    coverage: float,
) -> None:
    print(
        f"{market:<4} | source={len(raw_rows):,} "
        f"| eligible={len(eligible_rows):,} "
        f"| excluded={excluded:,} "
        f"| active={active_count:,} "
        f"| coverage={coverage:.2%}"
    )


# ============================================================
# TURSO WRITE
# ============================================================

PRICE_PREFIX_SQL = """
INSERT INTO stock_price_daily (
    stock_id, trade_date,
    open, high, low, close,
    volume, turnover, trade_count,
    source, created_at, updated_at
)
VALUES
"""
PRICE_VALUE_SQL = """
(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
"""
PRICE_SUFFIX_SQL = """
ON CONFLICT(stock_id, trade_date) DO NOTHING
"""


def flatten(rows: list[tuple[Any, ...]]) -> tuple[Any, ...]:
    values: list[Any] = []
    for row in rows:
        values.extend(row)
    return tuple(values)


def insert_price_rows(conn, rows: list[PriceRow]) -> None:
    tuples = [row.db_tuple() for row in rows]
    for start in range(0, len(tuples), SQL_ROWS_PER_STATEMENT):
        batch = tuples[start : start + SQL_ROWS_PER_STATEMENT]
        values_sql = ",\n".join(PRICE_VALUE_SQL for _ in batch)
        conn.execute(
            PRICE_PREFIX_SQL + values_sql + PRICE_SUFFIX_SQL,
            flatten(batch),
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
            dataset, last_data_date,
            last_success_at, last_attempt_at,
            status, records_processed, error_message, updated_at
        )
        VALUES (
            ?, ?,
            CASE WHEN ?='SUCCESS' THEN CURRENT_TIMESTAMP ELSE NULL END,
            CURRENT_TIMESTAMP,
            ?, ?, ?, CURRENT_TIMESTAMP
        )
        ON CONFLICT(dataset) DO UPDATE SET
            last_data_date = excluded.last_data_date,
            last_success_at = CASE
                WHEN excluded.status='SUCCESS' THEN CURRENT_TIMESTAMP
                ELSE sync_state.last_success_at
            END,
            last_attempt_at = CURRENT_TIMESTAMP,
            status = excluded.status,
            records_processed = excluded.records_processed,
            error_message = excluded.error_message,
            updated_at = CURRENT_TIMESTAMP
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


def verify_written_date(
    conn,
    market: str,
    trade_date: str,
    expected_rows: int,
) -> None:
    actual = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM stock_price_daily p
            INNER JOIN stock_master s ON s.stock_id = p.stock_id
            WHERE s.market = ?
              AND s.security_type = 'COMMON_STOCK'
              AND p.trade_date = ?
              AND p.source = ?
            """,
            (market, trade_date, SOURCES[market]),
        )
        or 0
    )
    if actual != expected_rows:
        raise RuntimeError(
            f"{market} DB row count mismatch for {trade_date}: "
            f"{actual} != {expected_rows}"
        )


def commit_trade_date(
    conn,
    trade_date: date,
    rows_by_market: dict[str, list[PriceRow]],
    processed: dict[str, int],
) -> None:
    date_text = trade_date.isoformat()
    next_processed = dict(processed)

    conn.execute("BEGIN")
    try:
        for market, rows in rows_by_market.items():
            if not rows:
                continue
            insert_price_rows(conn, rows)
            next_processed[market] += len(rows)
            update_sync_state(
                conn,
                DATASETS[market],
                date_text,
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

    for market, rows in rows_by_market.items():
        if rows:
            verify_written_date(conn, market, date_text, len(rows))
    processed.update(next_processed)


def mark_run_status(
    conn,
    cursors: dict[str, str],
    processed: dict[str, int],
    status: str,
    error_message: str | None = None,
) -> None:
    conn.execute("BEGIN")
    try:
        for market in ("TWSE", "TPEX"):
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
# RUN MODES
# ============================================================

def run_validation(conn, trade_date: date) -> None:
    if trade_date.weekday() >= 5:
        raise RuntimeError("--validate-date must be a known trading weekday")

    print()
    print("=" * 76)
    print("READ-ONLY SOURCE VALIDATION")
    print("=" * 76)
    print(f"Trade Date : {trade_date.isoformat()}")
    print("Turso Write: DISABLED")
    print()

    for index, market in enumerate(("TWSE", "TPEX")):
        if index:
            time.sleep(REQUEST_DELAY)
        raw_rows = fetch_market_day(market, trade_date)
        eligible, active_count, excluded, coverage = prepare_market_rows(
            conn, market, trade_date, raw_rows
        )
        if not raw_rows:
            raise RuntimeError(f"{market} returned no data for {trade_date}")
        if not eligible:
            raise RuntimeError(f"{market} returned no eligible COMMON_STOCK rows")
        print_market_summary(
            market,
            raw_rows,
            eligible,
            active_count,
            excluded,
            coverage,
        )

    print()
    print("[PASS] Official source fetch")
    print("[PASS] COMMON_STOCK filtering")
    print("[PASS] Duplicate / OHLC validation")
    print("[PASS] Turso DEV read connection")
    print("[PASS] No database rows were written")


def run_incremental(conn, through: date) -> None:
    cursors: dict[str, str] = {}
    for market in ("TWSE", "TPEX"):
        latest = get_latest_price_date(conn, market)
        if latest is None:
            raise RuntimeError(f"{market} historical price baseline is missing")
        cursors[market] = latest

    print()
    print("=" * 76)
    print("INCREMENTAL CURSOR")
    print("=" * 76)
    print(f"TWSE Last Data Date : {cursors['TWSE']}")
    print(f"TPEx Last Data Date : {cursors['TPEX']}")
    print(f"Through Date        : {through.isoformat()}")

    processed = {"TWSE": 0, "TPEX": 0}
    first_pending = min(
        parse_iso_date(cursors["TWSE"]),
        parse_iso_date(cursors["TPEX"]),
    ) + timedelta(days=1)

    if first_pending > through:
        print()
        print("[PASS] No pending calendar dates")
        mark_run_status(conn, cursors, processed, "SUCCESS")
        return

    try:
        for trade_date in daterange(first_pending, through):
            if trade_date.weekday() >= 5:
                continue

            date_text = trade_date.isoformat()
            needed = [
                market
                for market in ("TWSE", "TPEX")
                if date_text > cursors[market]
            ]
            if not needed:
                continue

            print()
            print(f"[{date_text}] checking {', '.join(needed)}")
            rows_by_market: dict[str, list[PriceRow]] = {}
            raw_counts: dict[str, int] = {}

            for index, market in enumerate(needed):
                if index:
                    time.sleep(REQUEST_DELAY)
                raw_rows = fetch_market_day(market, trade_date)
                raw_counts[market] = len(raw_rows)
                eligible, active_count, excluded, coverage = prepare_market_rows(
                    conn, market, trade_date, raw_rows
                )
                rows_by_market[market] = eligible
                print_market_summary(
                    market,
                    raw_rows,
                    eligible,
                    active_count,
                    excluded,
                    coverage,
                )

            if len(needed) == 2:
                has_twse = raw_counts["TWSE"] > 0
                has_tpex = raw_counts["TPEX"] > 0
                if has_twse != has_tpex:
                    raise RuntimeError(
                        f"Partial market data on {date_text}: "
                        f"TWSE={raw_counts['TWSE']}, TPEX={raw_counts['TPEX']}"
                    )

            if all(raw_counts[market] == 0 for market in needed):
                print(
                    "  [INFO] No official data. Holiday or data not published "
                    "yet; cursor unchanged."
                )
                continue

            for market in needed:
                if raw_counts[market] > 0 and not rows_by_market[market]:
                    raise RuntimeError(
                        f"{market} source has data but no eligible rows on "
                        f"{date_text}"
                    )

            commit_trade_date(conn, trade_date, rows_by_market, processed)
            for market, rows in rows_by_market.items():
                if rows:
                    cursors[market] = date_text

            print(
                f"  [PASS] committed {date_text} "
                f"TWSE={len(rows_by_market.get('TWSE', [])):,} "
                f"TPEx={len(rows_by_market.get('TPEX', [])):,}"
            )

        mark_run_status(conn, cursors, processed, "SUCCESS")

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
    print("DAILY PRICE INCREMENTAL RESULT")
    print("=" * 76)
    print(f"TWSE Last Data Date : {cursors['TWSE']}")
    print(f"TPEx Last Data Date : {cursors['TPEX']}")
    print(f"TWSE Rows This Run  : {processed['TWSE']:,}")
    print(f"TPEx Rows This Run  : {processed['TPEX']:,}")
    print("PROD Access         : DISABLED")


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    args = parse_args()
    print("=" * 76)
    print("StockWaveScanner V2 - Daily Price Incremental Pipeline")
    print("=" * 76)

    try:
        url, token = load_dev_credentials()
        print("Target      : DEV")
        print(f"Database    : {mask_url(url)}")
        print("PROD Access : DISABLED")

        conn = libsql.connect(database=url, auth_token=token)
        try:
            test = conn.execute("SELECT 1").fetchone()
            if not test or test[0] != 1:
                raise RuntimeError("Turso DEV connection validation failed")

            schema_version = get_schema_version(conn)
            if schema_version is None:
                raise RuntimeError("schema_meta/schema_version is missing")
            print(f"Schema      : {schema_version}")
            print("[PASS] Turso DEV connection")

            if args.validate_date:
                run_validation(conn, parse_iso_date(args.validate_date))
            else:
                through = (
                    parse_iso_date(args.through)
                    if args.through
                    else taipei_today()
                )
                if through > taipei_today():
                    raise RuntimeError(
                        "Through date cannot be later than today in Taiwan"
                    )
                run_incremental(conn, through)
        finally:
            conn.close()

        print()
        print("=" * 76)
        print("DAILY PRICE PIPELINE OK")
        print("=" * 76)
        return 0

    except KeyboardInterrupt:
        print()
        print("INTERRUPTED")
        print("No PROD database was accessed.")
        return 130
    except Exception as exc:
        print()
        print("=" * 76)
        print("ERROR")
        print("=" * 76)
        print(str(exc))
        print()
        print("No PROD database was accessed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
