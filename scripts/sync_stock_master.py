from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

TWSE_URL = (
    "https://openapi.twse.com.tw/v1/"
    "opendata/t187ap03_L"
)

TPEX_URL = (
    "https://mopsfin.twse.com.tw/"
    "opendata/t187ap03_O.csv"
)

USER_AGENT = (
    "Mozilla/5.0 "
    "StockWaveScanner-V2-Stock-Master/1.0"
)

TIMEOUT = 60


# ============================================================
# DEV SAFETY
# ============================================================

def load_dev_credentials() -> tuple[str, str]:
    load_dotenv(ENV_FILE)

    url = os.getenv(
        "TURSO_DEV_DATABASE_URL",
        "",
    ).strip()

    token = os.getenv(
        "TURSO_DEV_AUTH_TOKEN",
        "",
    ).strip()

    if not url:
        raise RuntimeError(
            "TURSO_DEV_DATABASE_URL is missing from .env"
        )

    if not token:
        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN is missing from .env"
        )

    lower_url = url.lower()

    if "stockwave-dev" not in lower_url:
        raise RuntimeError(
            "SAFETY STOP: "
            "TURSO_DEV_DATABASE_URL "
            "does not point to stockwave-dev"
        )

    if "stockwave-prod" in lower_url:
        raise RuntimeError(
            "SAFETY STOP: PROD database detected"
        )

    return url, token


def mask_url(url: str) -> str:
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

def curl_path() -> str | None:
    return (
        shutil.which("curl.exe")
        or shutil.which("curl")
    )


def fetch_urllib(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT,
    ) as response:
        data = response.read()

    if not data:
        raise RuntimeError(
            f"Empty response: {url}"
        )

    return data


def fetch_curl(url: str) -> bytes:
    curl = curl_path()

    if not curl:
        raise RuntimeError(
            "curl was not found"
        )

    result = subprocess.run(
        [
            curl,
            "--location",
            "--http1.1",
            "--retry",
            "2",
            "--retry-all-errors",
            "--connect-timeout",
            "15",
            "--max-time",
            str(TIMEOUT),
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
        error = result.stderr.decode(
            "utf-8",
            errors="replace",
        ).strip()

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
    prefer_curl: bool = False,
) -> bytes:
    loaders = (
        [fetch_curl, fetch_urllib]
        if prefer_curl
        else [fetch_urllib, fetch_curl]
    )

    errors: list[str] = []

    for loader in loaders:
        try:
            return loader(url)
        except Exception as exc:
            errors.append(
                f"{loader.__name__}: {exc}"
            )

    raise RuntimeError(
        " | ".join(errors)
    )


def decode_text(data: bytes) -> str:
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
        "Unable to decode response"
    )


# ============================================================
# NORMALIZATION
# ============================================================

def clean_text(
    value: Any,
) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    return text


def parse_integer(
    value: Any,
) -> int | None:
    text = clean_text(value)

    if text is None:
        return None

    text = (
        text
        .replace(",", "")
        .replace("，", "")
    )

    if text in {
        "-",
        "--",
        "N/A",
        "NA",
    }:
        return None

    try:
        return int(
            float(text)
        )
    except ValueError:
        return None


def normalize_date(
    value: Any,
) -> str | None:
    """
    支援：
        1150911
        115/09/11
        20260911
        2026/09/11
        2026-09-11
    """

    text = clean_text(value)

    if text is None:
        return None

    text = (
        text
        .replace(".", "/")
        .replace("-", "/")
    )

    parts = text.split("/")

    try:
        # ROC / Gregorian with separators
        if len(parts) == 3:
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])

            if year < 1911:
                year += 1911

            return (
                f"{year:04d}-"
                f"{month:02d}-"
                f"{day:02d}"
            )

        digits = "".join(
            ch
            for ch in text
            if ch.isdigit()
        )

        # Gregorian YYYYMMDD
        if len(digits) == 8:
            year = int(digits[:4])
            month = int(digits[4:6])
            day = int(digits[6:8])

            return (
                f"{year:04d}-"
                f"{month:02d}-"
                f"{day:02d}"
            )

        # ROC YYYMMDD
        if len(digits) == 7:
            year = (
                int(digits[:3])
                + 1911
            )

            month = int(
                digits[3:5]
            )

            day = int(
                digits[5:7]
            )

            return (
                f"{year:04d}-"
                f"{month:02d}-"
                f"{day:02d}"
            )

        # Older ROC dates can be YYMMDD
        if len(digits) == 6:
            year = (
                int(digits[:2])
                + 1911
            )

            month = int(
                digits[2:4]
            )

            day = int(
                digits[4:6]
            )

            return (
                f"{year:04d}-"
                f"{month:02d}-"
                f"{day:02d}"
            )

    except ValueError:
        return None

    return None


def first_value(
    row: dict[str, Any],
    candidates: tuple[str, ...],
) -> Any:
    for key in candidates:
        if key in row:
            value = row.get(key)

            if clean_text(value) is not None:
                return value

    return None


def normalize_row(
    row: dict[str, Any],
    market: str,
) -> dict[str, Any]:
    stock_id = clean_text(
        first_value(
            row,
            (
                "公司代號",
                "SecuritiesCompanyCode",
                "Code",
            ),
        )
    )

    stock_name = clean_text(
        first_value(
            row,
            (
                "公司名稱",
                "CompanyName",
                "Name",
            ),
        )
    )

    short_name = clean_text(
        first_value(
            row,
            (
                "公司簡稱",
                "CompanyShortName",
            ),
        )
    )

    industry_code = clean_text(
        first_value(
            row,
            (
                "產業別",
                "產業類別",
                "IndustryCode",
            ),
        )
    )

    if market == "TWSE":
        listed_raw = first_value(
            row,
            (
                "上市日期",
                "掛牌日期",
            ),
        )
    else:
        listed_raw = first_value(
            row,
            (
                "上櫃日期",
                "掛牌日期",
            ),
        )

    source_raw = first_value(
        row,
        (
            "出表日期",
            "資料日期",
            "資料年月日",
            "Date",
        ),
    )

    shares_raw = first_value(
        row,
        (
            "已發行普通股數或TDR原股發行股數",
            "已發行普通股數",
        ),
    )

    if not stock_id:
        raise RuntimeError(
            f"{market}: missing stock_id"
        )

    if not stock_name:
        raise RuntimeError(
            f"{market} {stock_id}: "
            "missing stock_name"
        )

    return {
        "stock_id": stock_id,
        "stock_name": stock_name,
        "short_name": short_name,
        "market": market,
        "security_type": "COMMON_STOCK",
        "industry_code": industry_code,
        "industry_name": None,
        "listed_date": normalize_date(
            listed_raw
        ),
        "issued_common_shares": parse_integer(
            shares_raw
        ),
        "source_date": normalize_date(
            source_raw
        ),
        "is_active": 1,
    }


# ============================================================
# SOURCE LOADERS
# ============================================================

def load_twse() -> list[dict[str, Any]]:
    raw = fetch(
        TWSE_URL,
        prefer_curl=False,
    )

    try:
        payload = json.loads(
            decode_text(raw)
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"TWSE invalid JSON: {exc}"
        ) from exc

    if not isinstance(
        payload,
        list,
    ):
        raise RuntimeError(
            "TWSE response is not a JSON array"
        )

    if len(payload) < 500:
        raise RuntimeError(
            "TWSE record count too small: "
            f"{len(payload)}"
        )

    return [
        normalize_row(
            row,
            "TWSE",
        )
        for row in payload
    ]


def load_tpex() -> list[dict[str, Any]]:
    raw = fetch(
        TPEX_URL,
        prefer_curl=True,
    )

    text = decode_text(raw)

    rows = list(
        csv.DictReader(
            io.StringIO(text)
        )
    )

    if len(rows) < 300:
        raise RuntimeError(
            "TPEx record count too small: "
            f"{len(rows)}"
        )

    return [
        normalize_row(
            row,
            "TPEX",
        )
        for row in rows
    ]


# ============================================================
# VALIDATION
# ============================================================

def validate_source_rows(
    twse_rows: list[dict[str, Any]],
    tpex_rows: list[dict[str, Any]],
) -> None:
    twse_ids = {
        row["stock_id"]
        for row in twse_rows
    }

    tpex_ids = {
        row["stock_id"]
        for row in tpex_rows
    }

    if len(twse_ids) != len(
        twse_rows
    ):
        raise RuntimeError(
            "TWSE contains duplicate stock_id"
        )

    if len(tpex_ids) != len(
        tpex_rows
    ):
        raise RuntimeError(
            "TPEx contains duplicate stock_id"
        )

    overlap = (
        twse_ids
        & tpex_ids
    )

    if overlap:
        sample = ", ".join(
            sorted(overlap)[:10]
        )

        raise RuntimeError(
            "Same stock_id exists in both "
            "TWSE and TPEx: "
            f"{sample}"
        )

    all_rows = (
        twse_rows
        + tpex_rows
    )

    invalid_ids = [
        row["stock_id"]
        for row in all_rows
        if not row["stock_id"]
    ]

    if invalid_ids:
        raise RuntimeError(
            "Invalid stock_id detected"
        )


# ============================================================
# DATABASE
# ============================================================

UPSERT_SQL = """
INSERT INTO stock_master (
    stock_id,
    stock_name,
    short_name,
    market,
    security_type,
    industry_code,
    industry_name,
    listed_date,
    issued_common_shares,
    source_date,
    is_active,
    created_at,
    updated_at
)
VALUES (
    ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?, ?,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT(stock_id)
DO UPDATE SET
    stock_name = excluded.stock_name,
    short_name = excluded.short_name,
    market = excluded.market,
    security_type = excluded.security_type,
    industry_code = excluded.industry_code,
    industry_name = excluded.industry_name,
    listed_date = excluded.listed_date,
    issued_common_shares =
        excluded.issued_common_shares,
    source_date = excluded.source_date,
    is_active = excluded.is_active,
    updated_at = CURRENT_TIMESTAMP
"""


def row_tuple(
    row: dict[str, Any],
) -> tuple[Any, ...]:
    return (
        row["stock_id"],
        row["stock_name"],
        row["short_name"],
        row["market"],
        row["security_type"],
        row["industry_code"],
        row["industry_name"],
        row["listed_date"],
        row["issued_common_shares"],
        row["source_date"],
        row["is_active"],
    )


def source_latest_date(
    rows: list[dict[str, Any]],
) -> str | None:
    values = [
        row["source_date"]
        for row in rows
        if row["source_date"]
    ]

    if not values:
        return None

    return max(values)


def update_sync_state(
    conn,
    dataset: str,
    last_data_date: str | None,
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
            status = 'SUCCESS',
            records_processed =
                excluded.records_processed,
            error_message = NULL,
            updated_at =
                CURRENT_TIMESTAMP
        """,
        (
            dataset,
            last_data_date,
            records_processed,
        ),
    )


def sync_database(
    conn,
    twse_rows: list[dict[str, Any]],
    tpex_rows: list[dict[str, Any]],
) -> None:
    # Current snapshot strategy:
    # mark existing market rows inactive first,
    # then current official snapshot rows active.
    #
    # Transaction ensures partial update does not persist.

    conn.execute(
        "BEGIN"
    )

    try:
        conn.execute(
            """
            UPDATE stock_master
            SET
                is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE market IN ('TWSE', 'TPEX')
            """
        )

        conn.executemany(
            UPSERT_SQL,
            [
                row_tuple(row)
                for row in (
                    twse_rows
                    + tpex_rows
                )
            ],
        )

        update_sync_state(
            conn,
            "stock_master_twse",
            source_latest_date(
                twse_rows
            ),
            len(twse_rows),
        )

        update_sync_state(
            conn,
            "stock_master_tpex",
            source_latest_date(
                tpex_rows
            ),
            len(tpex_rows),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise


# ============================================================
# VERIFY
# ============================================================

def scalar(
    conn,
    sql: str,
    params: tuple[Any, ...] = (),
) -> Any:
    row = conn.execute(
        sql,
        params,
    ).fetchone()

    if row is None:
        return None

    return row[0]


def verify_database(
    conn,
    expected_twse: int,
    expected_tpex: int,
) -> None:
    print()
    print("=" * 70)
    print("DATABASE VERIFICATION")
    print("=" * 70)

    active_twse = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM stock_master
            WHERE market = 'TWSE'
              AND is_active = 1
            """,
        )
    )

    active_tpex = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM stock_master
            WHERE market = 'TPEX'
              AND is_active = 1
            """,
        )
    )

    total_active = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM stock_master
            WHERE is_active = 1
            """,
        )
    )

    duplicate_count = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM (
                SELECT stock_id
                FROM stock_master
                GROUP BY stock_id
                HAVING COUNT(*) > 1
            )
            """,
        )
    )

    null_name_count = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM stock_master
            WHERE is_active = 1
              AND (
                    stock_name IS NULL
                    OR TRIM(stock_name) = ''
              )
            """,
        )
    )

    print(
        f"TWSE Active     : "
        f"{active_twse:,}"
    )

    print(
        f"TPEx Active     : "
        f"{active_tpex:,}"
    )

    print(
        f"Total Active    : "
        f"{total_active:,}"
    )

    print(
        f"Duplicate IDs   : "
        f"{duplicate_count:,}"
    )

    print(
        f"Missing Names   : "
        f"{null_name_count:,}"
    )

    if active_twse != expected_twse:
        raise RuntimeError(
            "TWSE DB count mismatch: "
            f"{active_twse} != {expected_twse}"
        )

    if active_tpex != expected_tpex:
        raise RuntimeError(
            "TPEx DB count mismatch: "
            f"{active_tpex} != {expected_tpex}"
        )

    if total_active != (
        expected_twse
        + expected_tpex
    ):
        raise RuntimeError(
            "Total active count mismatch"
        )

    if duplicate_count != 0:
        raise RuntimeError(
            "Duplicate stock_id detected"
        )

    if null_name_count != 0:
        raise RuntimeError(
            "Missing stock_name detected"
        )

    sync_rows = conn.execute(
        """
        SELECT
            dataset,
            last_data_date,
            status,
            records_processed
        FROM sync_state
        WHERE dataset IN (
            'stock_master_twse',
            'stock_master_tpex'
        )
        ORDER BY dataset
        """
    ).fetchall()

    print()
    print("Sync State:")

    for row in sync_rows:
        print(
            f"  {row[0]:<20} "
            f"| date={row[1]} "
            f"| status={row[2]} "
            f"| rows={row[3]}"
        )

    samples = conn.execute(
        """
        SELECT
            stock_id,
            short_name,
            market,
            industry_code,
            listed_date
        FROM stock_master
        WHERE is_active = 1
        ORDER BY stock_id
        LIMIT 5
        """
    ).fetchall()

    print()
    print("Sample:")

    for row in samples:
        print(
            f"  {row[0]} "
            f"{row[1]} "
            f"| {row[2]} "
            f"| industry={row[3]} "
            f"| listed={row[4]}"
        )


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    print("=" * 70)
    print(
        "StockWaveScanner V2 - "
        "Stock Master Sync to Turso DEV"
    )
    print("=" * 70)
    print()

    try:
        url, token = (
            load_dev_credentials()
        )

        print("Environment : DEV")
        print(
            f"Database    : "
            f"{mask_url(url)}"
        )
        print("PROD Access : DISABLED")

        print()
        print(
            "Downloading official Stock Master ..."
        )

        twse_rows = load_twse()

        print(
            f"[PASS] TWSE "
            f"records={len(twse_rows):,}"
        )

        tpex_rows = load_tpex()

        print(
            f"[PASS] TPEx "
            f"records={len(tpex_rows):,}"
        )

        validate_source_rows(
            twse_rows,
            tpex_rows,
        )

        print(
            "[PASS] Source validation"
        )

        print()
        print(
            "Connecting to Turso DEV ..."
        )

        conn = libsql.connect(
            database=url,
            auth_token=token,
        )

        try:
            result = conn.execute(
                "SELECT 1"
            ).fetchone()

            if (
                not result
                or result[0] != 1
            ):
                raise RuntimeError(
                    "Turso DEV connection validation failed"
                )

            print(
                "[PASS] Turso DEV connection"
            )

            print()
            print(
                "Synchronizing Stock Master ..."
            )

            sync_database(
                conn,
                twse_rows,
                tpex_rows,
            )

            print(
                "[PASS] Stock Master synchronized"
            )

            verify_database(
                conn,
                expected_twse=len(
                    twse_rows
                ),
                expected_tpex=len(
                    tpex_rows
                ),
            )

        finally:
            conn.close()

        print()
        print("=" * 70)
        print(
            "STOCK MASTER SYNC OK"
        )
        print("=" * 70)

        print()
        print(
            "Official Stock Master is now "
            "stored in stockwave-dev."
        )

        print(
            "No PROD database was accessed."
        )

        return 0

    except Exception as exc:
        print()
        print("=" * 70)
        print("ERROR")
        print("=" * 70)
        print(str(exc))

        print()
        print(
            "No PROD database was accessed."
        )

        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )