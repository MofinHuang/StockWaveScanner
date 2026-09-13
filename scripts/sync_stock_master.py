from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
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


# ============================================================
# OFFICIAL SOURCES
# ============================================================
#
# Primary:
#
# TWSE:
# https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv
#
# TPEx:
# https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv
#
# TWSE OpenAPI is kept as fallback only.
#
# Reason:
#
# GitHub-hosted runners may occasionally receive a non-JSON
# response from openapi.twse.com.tw.
#
# The official MOPS CSV source contains the same company master
# dataset and is also the same source family already used for
# TPEx.
# ============================================================

TWSE_CSV_URL = (
    "https://mopsfin.twse.com.tw/"
    "opendata/t187ap03_L.csv"
)

TWSE_OPENAPI_URL = (
    "https://openapi.twse.com.tw/v1/"
    "opendata/t187ap03_L"
)

TPEX_CSV_URL = (
    "https://mopsfin.twse.com.tw/"
    "opendata/t187ap03_O.csv"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36 "
    "StockWaveScanner-V2-Stock-Master/2.0"
)


# ============================================================
# CONSOLE
# ============================================================


def configure_console() -> None:
    """
    Avoid Windows hosted-runner charmap errors when printing
    Chinese company names.

    Workflow also sets PYTHONUTF8/PYTHONIOENCODING, but the
    script protects itself as well.
    """

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


def load_dev_credentials() -> tuple[str, str]:

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
# HTTP
# ============================================================


def curl_path() -> str | None:

    return (
        shutil.which(
            "curl.exe"
        )
        or shutil.which(
            "curl"
        )
    )


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
        curl_path()
    )

    if not curl:
        raise RuntimeError(
            "curl was not found"
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
                "application/json,"
                "text/csv,"
                "text/plain,*/*"
            ),

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
            f"curl failed: "
            f"{error}"
        )

    if not result.stdout:
        raise RuntimeError(
            f"Empty response: "
            f"{url}"
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
# TEXT / RESPONSE
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
        "Unable to decode response"
    )


def validate_not_html(
    text: str,
    source: str,
) -> None:

    stripped = (
        text.lstrip()
    )

    prefix = (
        stripped[:200]
        .lower()
    )

    if (
        prefix.startswith(
            "<!doctype"
        )
        or
        prefix.startswith(
            "<html"
        )
        or
        "<html" in prefix
    ):

        raise RuntimeError(
            f"{source} returned HTML "
            "instead of data"
        )


# ============================================================
# NORMALIZATION
# ============================================================


def clean_text(
    value: Any,
) -> str | None:

    if value is None:
        return None

    text = (
        str(value)
        .strip()
    )

    if not text:
        return None

    return text


def parse_integer(
    value: Any,
) -> int | None:

    text = (
        clean_text(
            value
        )
    )

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
            float(
                text
            )
        )

    except ValueError:
        return None


def normalize_date(
    value: Any,
) -> str | None:

    text = (
        clean_text(
            value
        )
    )

    if text is None:
        return None

    text = (
        text
        .replace(".", "/")
        .replace("-", "/")
    )

    parts = (
        text.split("/")
    )

    try:

        # ROC / Gregorian with separators
        if len(parts) == 3:

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

            year = int(
                digits[:4]
            )

            month = int(
                digits[4:6]
            )

            day = int(
                digits[6:8]
            )

            return (
                f"{year:04d}-"
                f"{month:02d}-"
                f"{day:02d}"
            )

        # ROC YYYMMDD
        if len(digits) == 7:

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

            return (
                f"{year:04d}-"
                f"{month:02d}-"
                f"{day:02d}"
            )

        # Older ROC YYMMDD
        if len(digits) == 6:

            year = (
                int(
                    digits[:2]
                )
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
    row: dict[
        str,
        Any,
    ],
    candidates: tuple[
        str,
        ...,
    ],
) -> Any:

    for key in candidates:

        if key not in row:
            continue

        value = (
            row.get(
                key
            )
        )

        if (
            clean_text(
                value
            )
            is not None
        ):
            return value

    return None


def normalize_row(
    row: dict[
        str,
        Any,
    ],
    market: str,
) -> dict[
    str,
    Any,
]:

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
            f"{market}: "
            "missing stock_id"
        )

    if not stock_name:

        raise RuntimeError(
            f"{market} "
            f"{stock_id}: "
            "missing stock_name"
        )

    return {
        "stock_id":
            stock_id,

        "stock_name":
            stock_name,

        "short_name":
            short_name,

        "market":
            market,

        "security_type":
            "COMMON_STOCK",

        "industry_code":
            industry_code,

        "industry_name":
            None,

        "listed_date":
            normalize_date(
                listed_raw
            ),

        "issued_common_shares":
            parse_integer(
                shares_raw
            ),

        "source_date":
            normalize_date(
                source_raw
            ),

        "is_active":
            1,
    }


# ============================================================
# CSV
# ============================================================


def parse_csv_rows(
    raw: bytes,
    *,
    market: str,
    source_name: str,
    minimum_rows: int,
) -> list[
    dict[
        str,
        Any,
    ]
]:

    text = (
        decode_text(
            raw
        )
    )

    validate_not_html(
        text,
        source_name,
    )

    reader = csv.DictReader(
        io.StringIO(
            text
        )
    )

    rows = list(
        reader
    )

    if len(rows) < minimum_rows:

        raise RuntimeError(
            f"{source_name} "
            "record count too small: "
            f"{len(rows)}"
        )

    result = [
        normalize_row(
            row,
            market,
        )
        for row in rows
    ]

    return result


# ============================================================
# TWSE LOAD
# ============================================================


def load_twse_from_csv(
) -> list[
    dict[
        str,
        Any,
    ]
]:

    raw = fetch(
        TWSE_CSV_URL,
        prefer_curl=True,
    )

    return parse_csv_rows(
        raw,
        market="TWSE",
        source_name=(
            "TWSE MOPS CSV"
        ),
        minimum_rows=500,
    )


def load_twse_from_openapi(
) -> list[
    dict[
        str,
        Any,
    ]
]:

    raw = fetch(
        TWSE_OPENAPI_URL,
        prefer_curl=False,
    )

    text = (
        decode_text(
            raw
        )
    )

    validate_not_html(
        text,
        "TWSE OpenAPI",
    )

    try:

        payload = json.loads(
            text
        )

    except json.JSONDecodeError as exc:

        prefix = (
            text[:120]
            .replace(
                "\r",
                " ",
            )
            .replace(
                "\n",
                " ",
            )
        )

        raise RuntimeError(
            "TWSE OpenAPI invalid JSON: "
            f"{exc}; "
            f"response-prefix="
            f"{prefix!r}"
        ) from exc

    if not isinstance(
        payload,
        list,
    ):

        raise RuntimeError(
            "TWSE OpenAPI response "
            "is not a JSON array"
        )

    if len(payload) < 500:

        raise RuntimeError(
            "TWSE OpenAPI "
            "record count too small: "
            f"{len(payload)}"
        )

    return [
        normalize_row(
            row,
            "TWSE",
        )
        for row in payload
    ]


def load_twse(
) -> tuple[
    list[
        dict[
            str,
            Any,
        ]
    ],
    str,
]:

    # Primary:
    # Official MOPS CSV

    try:

        rows = (
            load_twse_from_csv()
        )

        return (
            rows,
            "TWSE_MOPS_CSV",
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

    # Fallback:
    # Official TWSE OpenAPI

    rows = (
        load_twse_from_openapi()
    )

    return (
        rows,
        "TWSE_OPENAPI",
    )


# ============================================================
# TPEX LOAD
# ============================================================


def load_tpex(
) -> tuple[
    list[
        dict[
            str,
            Any,
        ]
    ],
    str,
]:

    raw = fetch(
        TPEX_CSV_URL,
        prefer_curl=True,
    )

    rows = parse_csv_rows(
        raw,
        market="TPEX",
        source_name=(
            "TPEx MOPS CSV"
        ),
        minimum_rows=300,
    )

    return (
        rows,
        "TPEX_MOPS_CSV",
    )


# ============================================================
# SOURCE VALIDATION
# ============================================================


def validate_source_rows(
    twse_rows: list[
        dict[
            str,
            Any,
        ]
    ],
    tpex_rows: list[
        dict[
            str,
            Any,
        ]
    ],
) -> None:

    twse_ids = {
        row[
            "stock_id"
        ]
        for row in twse_rows
    }

    tpex_ids = {
        row[
            "stock_id"
        ]
        for row in tpex_rows
    }

    if (
        len(twse_ids)
        != len(twse_rows)
    ):

        raise RuntimeError(
            "TWSE contains "
            "duplicate stock_id"
        )

    if (
        len(tpex_ids)
        != len(tpex_rows)
    ):

        raise RuntimeError(
            "TPEx contains "
            "duplicate stock_id"
        )

    overlap = (
        twse_ids
        &
        tpex_ids
    )

    if overlap:

        sample = ", ".join(
            sorted(
                overlap
            )[:10]
        )

        raise RuntimeError(
            "Same stock_id exists "
            "in both TWSE and TPEx: "
            f"{sample}"
        )

    all_rows = (
        twse_rows
        +
        tpex_rows
    )

    invalid_ids = [
        row[
            "stock_id"
        ]

        for row
        in all_rows

        if not row[
            "stock_id"
        ]
    ]

    if invalid_ids:

        raise RuntimeError(
            "Invalid stock_id detected"
        )

    missing_names = [
        row[
            "stock_id"
        ]

        for row
        in all_rows

        if not row[
            "stock_name"
        ]
    ]

    if missing_names:

        raise RuntimeError(
            "Source rows contain "
            "missing stock_name"
        )


# ============================================================
# DATABASE UPSERT
# ============================================================


UPSERT_PREFIX = """
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
VALUES
"""


UPSERT_VALUE = """
(
    ?, ?, ?, ?, ?,
    ?, ?,
    ?, ?, ?,
    ?,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
"""


UPSERT_SUFFIX = """
ON CONFLICT(stock_id)
DO UPDATE SET

    stock_name =
        excluded.stock_name,

    short_name =
        excluded.short_name,

    market =
        excluded.market,

    security_type =
        excluded.security_type,

    industry_code =
        excluded.industry_code,

    industry_name =
        excluded.industry_name,

    listed_date =
        excluded.listed_date,

    issued_common_shares =
        excluded.issued_common_shares,

    source_date =
        excluded.source_date,

    is_active =
        excluded.is_active,

    updated_at =
        CURRENT_TIMESTAMP
"""


def row_tuple(
    row: dict[
        str,
        Any,
    ],
) -> tuple[
    Any,
    ...,
]:

    return (
        row[
            "stock_id"
        ],

        row[
            "stock_name"
        ],

        row[
            "short_name"
        ],

        row[
            "market"
        ],

        row[
            "security_type"
        ],

        row[
            "industry_code"
        ],

        row[
            "industry_name"
        ],

        row[
            "listed_date"
        ],

        row[
            "issued_common_shares"
        ],

        row[
            "source_date"
        ],

        row[
            "is_active"
        ],
    )


def build_upsert_sql(
    row_count: int,
) -> str:

    values_sql = (
        ",\n".join(
            UPSERT_VALUE

            for _ in range(
                row_count
            )
        )
    )

    return (
        UPSERT_PREFIX
        +
        values_sql
        +
        UPSERT_SUFFIX
    )


def flatten_rows(
    rows: list[
        dict[
            str,
            Any,
        ]
    ],
) -> tuple[
    Any,
    ...,
]:

    values: list[Any] = []

    for row in rows:

        values.extend(
            row_tuple(
                row
            )
        )

    return tuple(
        values
    )


def source_latest_date(
    rows: list[
        dict[
            str,
            Any,
        ]
    ],
) -> str | None:

    values = [
        row[
            "source_date"
        ]

        for row
        in rows

        if row[
            "source_date"
        ]
    ]

    if not values:
        return None

    return max(
        values
    )


# ============================================================
# SYNC STATE
# ============================================================


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
            dataset,
            last_data_date,
            records_processed,
        ),
    )


# ============================================================
# DATABASE SYNC
# ============================================================


def sync_database(
    conn,
    twse_rows: list[
        dict[
            str,
            Any,
        ]
    ],
    tpex_rows: list[
        dict[
            str,
            Any,
        ]
    ],
) -> None:

    all_rows = (
        twse_rows
        +
        tpex_rows
    )

    conn.execute(
        "BEGIN"
    )

    try:

        # ====================================================
        # Current snapshot strategy
        #
        # 1. Existing TWSE / TPEx rows -> inactive
        # 2. Current official rows -> upsert active
        #
        # Historical delisted stocks stay in stock_master.
        # ====================================================

        conn.execute(
            """
            UPDATE stock_master

            SET
                is_active = 0,
                updated_at =
                    CURRENT_TIMESTAMP

            WHERE market
                  IN ('TWSE', 'TPEX')
            """
        )

        # ====================================================
        # Batch UPSERT
        #
        # Previous executemany against remote Turso could take
        # several minutes because of many remote statements.
        #
        # Multi-row UPSERT greatly reduces round trips.
        # ====================================================

        for start in range(
            0,
            len(all_rows),
            SQL_ROWS_PER_STATEMENT,
        ):

            batch = all_rows[
                start:
                start
                + SQL_ROWS_PER_STATEMENT
            ]

            conn.execute(
                build_upsert_sql(
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
            "stock_master_twse",
            source_latest_date(
                twse_rows
            ),
            len(
                twse_rows
            ),
        )

        update_sync_state(
            conn,
            "stock_master_tpex",
            source_latest_date(
                tpex_rows
            ),
            len(
                tpex_rows
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
# DB HELPERS
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


# ============================================================
# DB VERIFICATION
# ============================================================


def verify_database(
    conn,
    expected_twse: int,
    expected_tpex: int,
) -> None:

    print()

    print(
        "=" * 70
    )

    print(
        "DATABASE VERIFICATION"
    )

    print(
        "=" * 70
    )

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
        or 0
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
        or 0
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
        or 0
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
        or 0
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

                    OR

                    TRIM(stock_name) = ''
                  )
            """,
        )
        or 0
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

    if (
        active_twse
        != expected_twse
    ):

        raise RuntimeError(
            "TWSE DB count mismatch: "
            f"{active_twse} "
            f"!= {expected_twse}"
        )

    if (
        active_tpex
        != expected_tpex
    ):

        raise RuntimeError(
            "TPEx DB count mismatch: "
            f"{active_tpex} "
            f"!= {expected_tpex}"
        )

    if (
        total_active
        !=
        (
            expected_twse
            +
            expected_tpex
        )
    ):

        raise RuntimeError(
            "Total active "
            "count mismatch"
        )

    if duplicate_count != 0:

        raise RuntimeError(
            "Duplicate stock_id detected"
        )

    if null_name_count != 0:

        raise RuntimeError(
            "Missing stock_name detected"
        )

    sync_rows = (
        conn.execute(
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
        )
        .fetchall()
    )

    print()

    print(
        "Sync State:"
    )

    for row in sync_rows:

        print(
            f"  {row[0]:<20} "
            f"| date={row[1]} "
            f"| status={row[2]} "
            f"| rows={row[3]}"
        )

    samples = (
        conn.execute(
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
        )
        .fetchall()
    )

    print()

    print(
        "Sample:"
    )

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

    configure_console()

    print(
        "=" * 70
    )

    print(
        "StockWaveScanner V2 - "
        "Stock Master Sync to Turso DEV"
    )

    print(
        "=" * 70
    )

    print()

    try:

        url, token = (
            load_dev_credentials()
        )

        print(
            "Environment : DEV"
        )

        print(
            "Database    : "
            f"{mask_url(url)}"
        )

        print(
            "PROD Access : DISABLED"
        )

        print()

        print(
            "Downloading official "
            "Stock Master ..."
        )

        started = (
            time.perf_counter()
        )

        twse_rows, twse_source = (
            load_twse()
        )

        print(
            f"[PASS] TWSE "
            f"records="
            f"{len(twse_rows):,} "
            f"| source="
            f"{twse_source}"
        )

        tpex_rows, tpex_source = (
            load_tpex()
        )

        print(
            f"[PASS] TPEx "
            f"records="
            f"{len(tpex_rows):,} "
            f"| source="
            f"{tpex_source}"
        )

        validate_source_rows(
            twse_rows,
            tpex_rows,
        )

        download_elapsed = (
            time.perf_counter()
            -
            started
        )

        print(
            "[PASS] Source validation"
        )

        print(
            f"Source Elapsed : "
            f"{download_elapsed:.1f}s"
        )

        print()

        print(
            "Connecting to "
            "Turso DEV ..."
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
                    "Turso DEV connection "
                    "validation failed"
                )

            print(
                "[PASS] "
                "Turso DEV connection"
            )

            print()

            print(
                "Synchronizing "
                "Stock Master ..."
            )

            sync_started = (
                time.perf_counter()
            )

            sync_database(
                conn,
                twse_rows,
                tpex_rows,
            )

            sync_elapsed = (
                time.perf_counter()
                -
                sync_started
            )

            print(
                "[PASS] "
                "Stock Master synchronized"
            )

            print(
                f"DB Sync Elapsed : "
                f"{sync_elapsed:.1f}s"
            )

            verify_database(
                conn,
                expected_twse=(
                    len(
                        twse_rows
                    )
                ),
                expected_tpex=(
                    len(
                        tpex_rows
                    )
                ),
            )

        finally:

            conn.close()

        total_elapsed = (
            time.perf_counter()
            -
            started
        )

        print()

        print(
            "=" * 70
        )

        print(
            "STOCK MASTER SYNC OK"
        )

        print(
            "=" * 70
        )

        print()

        print(
            "Official Stock Master "
            "is stored in stockwave-dev."
        )

        print(
            f"Total Elapsed : "
            f"{total_elapsed:.1f}s"
        )

        print(
            "No PROD database "
            "was accessed."
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
            "=" * 70
        )

        print(
            "ERROR"
        )

        print(
            "=" * 70
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