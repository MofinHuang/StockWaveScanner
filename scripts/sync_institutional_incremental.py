from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import libsql
from dotenv import load_dotenv


# ============================================================
# BASIC CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

TIMEOUT = 45
REQUEST_INTERVAL = 1.2
SQL_ROWS_PER_STATEMENT = 50

TAIPEI_TZ = timezone(
    timedelta(hours=8)
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36 "
    "StockWaveScanner-V2-Institutional/1.0"
)


# ============================================================
# OFFICIAL SOURCES
# ============================================================

TWSE_T86_URL = (
    "https://www.twse.com.tw/"
    "rwd/zh/fund/T86"
)

TPEX_CURRENT_URL = (
    "https://www.tpex.org.tw/"
    "openapi/v1/tpex_3insti_daily_trading"
)

TPEX_HISTORY_URL = (
    "https://www.tpex.org.tw/"
    "www/zh-tw/insti/dailyTrade"
)

TPEX_REFERER = (
    "https://www.tpex.org.tw/"
    "zh-tw/mainboard/trading/"
    "major-institutional/detail/day.html"
)


# ============================================================
# DATASET NAMES
# ============================================================

DATASETS = {
    "TWSE": "institutional_twse",
    "TPEX": "institutional_tpex",
}


# ============================================================
# SOURCE SANITY LIMITS
# ============================================================
#
# 注意：
#
# 法人報表 != 行情完整清單。
#
# 尤其 TPEx Historical dailyTrade
# 可能不會列出所有當日有成交普通股。
#
# 因此：
#
# 不再用：
#
# source / traded >= 90%
#
# 當作 API 成敗條件。
#
# 改成：
#
# 1. 官方來源本身必須有合理筆數
# 2. 已回傳股票 -> STORED
# 3. 當日有成交但來源沒列 -> INSUFFICIENT_DATA
#
# Missing 不可推論成 0。
# ============================================================

MIN_SOURCE_ROWS = {
    "TWSE_T86": 1000,
    "TPEX_OPENAPI": 800,
    "TPEX_HISTORY": 700,
}


@dataclass(frozen=True)
class InstitutionalRow:
    stock_id: str
    trade_date: str

    foreign_buy: int | None
    foreign_sell: int | None
    foreign_net: int | None

    trust_buy: int | None
    trust_sell: int | None
    trust_net: int | None

    dealer_buy: int | None
    dealer_sell: int | None
    dealer_net: int | None

    foreign_status: str
    trust_status: str
    dealer_status: str

    source: str

    def db_tuple(
        self,
    ) -> tuple[Any, ...]:

        return (
            self.stock_id,
            self.trade_date,

            self.foreign_buy,
            self.foreign_sell,
            self.foreign_net,

            self.trust_buy,
            self.trust_sell,
            self.trust_net,

            self.dealer_buy,
            self.dealer_sell,
            self.dealer_net,

            self.foreign_status,
            self.trust_status,
            self.dealer_status,

            self.source,
        )


@dataclass(frozen=True)
class FetchResult:
    market: str
    trade_date: date
    source_name: str

    rows: dict[
        str,
        InstitutionalRow,
    ]

    raw_count: int


# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Incrementally sync TWSE / TPEx "
            "institutional trading into Turso DEV."
        )
    )

    group = (
        parser.add_mutually_exclusive_group()
    )

    group.add_argument(
        "--through",
        metavar="YYYY-MM-DD",
        help=(
            "Sync through this Taiwan date. "
            "Default: today UTC+8."
        ),
    )

    group.add_argument(
        "--validate-date",
        metavar="YYYY-MM-DD",
        help=(
            "READ ONLY: validate one known "
            "trading date without writing Turso."
        ),
    )

    return parser.parse_args()


# ============================================================
# DATE HELPERS
# ============================================================


def taipei_today() -> date:

    return datetime.now(
        TAIPEI_TZ
    ).date()


def parse_iso_date(
    value: str,
) -> date:

    try:
        return date.fromisoformat(
            value
        )

    except ValueError as exc:

        raise RuntimeError(
            f"Invalid date '{value}'. "
            "Expected YYYY-MM-DD."
        ) from exc


def to_roc_date(
    value: date,
) -> str:

    return (
        f"{value.year - 1911:03d}/"
        f"{value.month:02d}/"
        f"{value.day:02d}"
    )


def parse_roc_compact_date(
    value: Any,
) -> date | None:

    text = str(
        value or ""
    ).strip()

    digits = "".join(
        ch
        for ch in text
        if ch.isdigit()
    )

    # 1150911
    if len(digits) == 7:

        try:

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

        except ValueError:
            return None

    # 20260911
    if len(digits) == 8:

        try:

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

        except ValueError:
            return None

    return None


def parse_roc_slash_date(
    value: Any,
) -> date | None:

    text = str(
        value or ""
    ).strip()

    if not text:
        return None

    parts = (
        text
        .replace("-", "/")
        .split("/")
    )

    if len(parts) != 3:
        return None

    try:

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
        )

    except ValueError:
        return None


# ============================================================
# VALUE HELPERS
# ============================================================


def clean_text(
    value: Any,
) -> str:

    if value is None:
        return ""

    return (
        str(value)
        .replace(
            "\u3000",
            " ",
        )
        .strip()
    )


def parse_int(
    value: Any,
) -> int | None:

    text = clean_text(
        value
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

    text = (
        text
        .replace(",", "")
        .replace("，", "")
        .replace(" ", "")
        .replace("−", "-")
        .replace("－", "-")
        .replace("＋", "+")
    )

    if (
        text.startswith("(")
        and
        text.endswith(")")
    ):

        text = (
            "-"
            + text[1:-1]
        )

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
            "DEV URL does not point "
            "to stockwave-dev"
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
    headers: dict[
        str,
        str,
    ] | None = None,
) -> bytes:

    request_headers = {
        "User-Agent":
            USER_AGENT,

        "Accept":
            "application/json,"
            "text/plain,*/*",

        "Cache-Control":
            "no-cache",
    }

    request_headers.update(
        headers or {}
    )

    request = (
        urllib.request.Request(
            url,
            method="GET",
            headers=request_headers,
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
            "Empty HTTP response"
        )

    return data


def fetch_curl(
    url: str,
    headers: dict[
        str,
        str,
    ] | None = None,
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

    command = [
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
    ]

    for key, value in (
        headers or {}
    ).items():

        command.extend(
            [
                "-H",
                f"{key}: {value}",
            ]
        )

    command.append(
        url
    )

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
            f"curl failed: "
            f"{error}"
        )

    if not result.stdout:

        raise RuntimeError(
            "Empty curl response"
        )

    return result.stdout


def fetch_with_retry(
    url: str,
    *,
    headers: dict[
        str,
        str,
    ] | None = None,
    prefer_curl: bool = False,
) -> bytes:

    delays = [
        0,
        3,
        10,
    ]

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
        delays,
        start=1,
    ):

        if delay:
            time.sleep(
                delay
            )

        for loader in loaders:

            try:

                return loader(
                    url,
                    headers,
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
                f"({attempt}/"
                f"{len(delays)}) ..."
            )

    raise RuntimeError(
        " | ".join(
            errors[-6:]
        )
    )


def decode_json(
    data: bytes,
) -> Any:

    for encoding in (
        "utf-8-sig",
        "utf-8",
        "cp950",
        "big5",
    ):

        try:

            text = (
                data.decode(
                    encoding
                )
            )

        except UnicodeDecodeError:
            continue

        try:

            return json.loads(
                text
            )

        except json.JSONDecodeError as exc:

            raise RuntimeError(
                f"Invalid JSON: "
                f"{exc}"
            ) from exc

    raise RuntimeError(
        "Unable to decode response"
    )


# ============================================================
# NORMALIZED KEY HELPERS
# ============================================================


def normalize_key(
    value: str,
) -> str:

    return re.sub(
        r"[^a-z0-9]",
        "",
        value.lower(),
    )


def find_dict_value(
    row: dict[
        str,
        Any,
    ],
    predicate,
) -> Any:

    for key, value in (
        row.items()
    ):

        normalized = (
            normalize_key(
                key
            )
        )

        if predicate(
            normalized
        ):

            return value

    return None


# ============================================================
# COMPONENT VALIDATION
# ============================================================


def validate_component(
    *,
    market: str,
    trade_date: str,
    stock_id: str,
    label: str,

    buy: int | None,
    sell: int | None,
    net: int | None,
) -> None:

    if (
        buy is None
        or
        sell is None
        or
        net is None
    ):

        raise RuntimeError(
            f"{market} "
            f"{trade_date} "
            f"{stock_id} "
            f"missing {label} value"
        )

    if (
        buy < 0
        or
        sell < 0
    ):

        raise RuntimeError(
            f"{market} "
            f"{trade_date} "
            f"{stock_id} "
            f"invalid {label} buy/sell"
        )

    if (
        buy - sell
        != net
    ):

        raise RuntimeError(
            f"{market} "
            f"{trade_date} "
            f"{stock_id} "
            f"{label} arithmetic mismatch: "
            f"{buy} - {sell} != {net}"
        )


def build_row(
    *,
    market: str,
    stock_id: str,
    trade_date: date,
    source: str,

    foreign_buy: Any,
    foreign_sell: Any,
    foreign_net: Any,

    trust_buy: Any,
    trust_sell: Any,
    trust_net: Any,

    dealer_buy: Any,
    dealer_sell: Any,
    dealer_net: Any,

    official_total: Any = None,
) -> InstitutionalRow:

    fb = parse_int(
        foreign_buy
    )

    fs = parse_int(
        foreign_sell
    )

    fn = parse_int(
        foreign_net
    )

    tb = parse_int(
        trust_buy
    )

    ts = parse_int(
        trust_sell
    )

    tn = parse_int(
        trust_net
    )

    db = parse_int(
        dealer_buy
    )

    ds = parse_int(
        dealer_sell
    )

    dn = parse_int(
        dealer_net
    )

    trade_date_text = (
        trade_date.isoformat()
    )

    validate_component(
        market=market,
        trade_date=trade_date_text,
        stock_id=stock_id,
        label="foreign",

        buy=fb,
        sell=fs,
        net=fn,
    )

    validate_component(
        market=market,
        trade_date=trade_date_text,
        stock_id=stock_id,
        label="trust",

        buy=tb,
        sell=ts,
        net=tn,
    )

    validate_component(
        market=market,
        trade_date=trade_date_text,
        stock_id=stock_id,
        label="dealer",

        buy=db,
        sell=ds,
        net=dn,
    )

    total = parse_int(
        official_total
    )

    # 官方三大法人 Total：
    #
    # foreign =
    # 外資及陸資
    # 不含外資自營商
    #
    # +
    #
    # trust
    #
    # +
    #
    # dealer
    #
    # Foreign Dealers 不納入三大法人 Total。
    if (
        total is not None
        and
        fn + tn + dn
        != total
    ):

        raise RuntimeError(
            f"{market} "
            f"{trade_date_text} "
            f"{stock_id} "
            "institutional total mismatch: "
            f"{fn} + {tn} + {dn} "
            f"!= {total}"
        )

    return InstitutionalRow(
        stock_id=stock_id,
        trade_date=trade_date_text,

        foreign_buy=fb,
        foreign_sell=fs,
        foreign_net=fn,

        trust_buy=tb,
        trust_sell=ts,
        trust_net=tn,

        dealer_buy=db,
        dealer_sell=ds,
        dealer_net=dn,

        foreign_status="STORED",
        trust_status="STORED",
        dealer_status="STORED",

        source=source,
    )


def build_missing_row(
    *,
    stock_id: str,
    trade_date: date,
    source: str,
) -> InstitutionalRow:

    return InstitutionalRow(
        stock_id=stock_id,

        trade_date=(
            trade_date.isoformat()
        ),

        foreign_buy=None,
        foreign_sell=None,
        foreign_net=None,

        trust_buy=None,
        trust_sell=None,
        trust_net=None,

        dealer_buy=None,
        dealer_sell=None,
        dealer_net=None,

        foreign_status=(
            "INSUFFICIENT_DATA"
        ),

        trust_status=(
            "INSUFFICIENT_DATA"
        ),

        dealer_status=(
            "INSUFFICIENT_DATA"
        ),

        source=(
            f"{source}_MISSING"
        ),
    )


# ============================================================
# TWSE T86
# ============================================================


def fetch_twse_source(
    trade_date: date,
) -> FetchResult:

    query = urllib.parse.urlencode(
        {
            "date":
                trade_date.strftime(
                    "%Y%m%d"
                ),

            "selectType":
                "ALLBUT0999",

            "response":
                "json",
        }
    )

    payload = decode_json(
        fetch_with_retry(
            f"{TWSE_T86_URL}"
            f"?{query}"
        )
    )

    if not isinstance(
        payload,
        dict,
    ):

        raise RuntimeError(
            "TWSE T86 response "
            "is not JSON object"
        )

    if (
        str(
            payload.get(
                "stat",
                "",
            )
        ).upper()
        != "OK"
    ):

        raise RuntimeError(
            "TWSE T86 no data for "
            f"{trade_date.isoformat()}: "
            f"{payload.get('stat')}"
        )

    fields = payload.get(
        "fields"
    )

    raw_rows = payload.get(
        "data"
    )

    if (
        not isinstance(
            fields,
            list,
        )
        or
        not isinstance(
            raw_rows,
            list,
        )
    ):

        raise RuntimeError(
            "TWSE T86 "
            "fields/data invalid"
        )

    raw_count = len(
        raw_rows
    )

    if (
        raw_count
        <
        MIN_SOURCE_ROWS[
            "TWSE_T86"
        ]
    ):

        raise RuntimeError(
            "TWSE T86 source count "
            f"too low: {raw_count}"
        )

    required = {
        "證券代號",

        "外陸資買進股數(不含外資自營商)",
        "外陸資賣出股數(不含外資自營商)",
        "外陸資買賣超股數(不含外資自營商)",

        "投信買進股數",
        "投信賣出股數",
        "投信買賣超股數",

        "自營商買賣超股數",

        "自營商買進股數(自行買賣)",
        "自營商賣出股數(自行買賣)",
        "自營商買賣超股數(自行買賣)",

        "自營商買進股數(避險)",
        "自營商賣出股數(避險)",
        "自營商買賣超股數(避險)",
    }

    missing_fields = sorted(
        required
        - set(fields)
    )

    if missing_fields:

        raise RuntimeError(
            "TWSE T86 missing fields: "
            + ", ".join(
                missing_fields
            )
        )

    idx = {
        field:
            fields.index(
                field
            )

        for field in required
    }

    total_idx = None

    if (
        "三大法人買賣超股數"
        in fields
    ):

        total_idx = (
            fields.index(
                "三大法人買賣超股數"
            )
        )

    result: dict[
        str,
        InstitutionalRow,
    ] = {}

    for raw in raw_rows:

        if not isinstance(
            raw,
            list,
        ):
            continue

        stock_id = clean_text(
            raw[
                idx[
                    "證券代號"
                ]
            ]
        )

        if not stock_id:
            continue

        if stock_id in result:

            raise RuntimeError(
                "TWSE duplicate "
                f"stock_id={stock_id} "
                f"on {trade_date.isoformat()}"
            )

        dealer_prop_buy = (
            parse_int(
                raw[
                    idx[
                        "自營商買進股數(自行買賣)"
                    ]
                ]
            )
        )

        dealer_prop_sell = (
            parse_int(
                raw[
                    idx[
                        "自營商賣出股數(自行買賣)"
                    ]
                ]
            )
        )

        dealer_prop_net = (
            parse_int(
                raw[
                    idx[
                        "自營商買賣超股數(自行買賣)"
                    ]
                ]
            )
        )

        dealer_hedge_buy = (
            parse_int(
                raw[
                    idx[
                        "自營商買進股數(避險)"
                    ]
                ]
            )
        )

        dealer_hedge_sell = (
            parse_int(
                raw[
                    idx[
                        "自營商賣出股數(避險)"
                    ]
                ]
            )
        )

        dealer_hedge_net = (
            parse_int(
                raw[
                    idx[
                        "自營商買賣超股數(避險)"
                    ]
                ]
            )
        )

        dealer_total_net = (
            parse_int(
                raw[
                    idx[
                        "自營商買賣超股數"
                    ]
                ]
            )
        )

        dealer_values = (
            dealer_prop_buy,
            dealer_prop_sell,
            dealer_prop_net,

            dealer_hedge_buy,
            dealer_hedge_sell,
            dealer_hedge_net,

            dealer_total_net,
        )

        if any(
            value is None
            for value
            in dealer_values
        ):

            raise RuntimeError(
                "TWSE "
                f"{stock_id} "
                "dealer component missing "
                f"on {trade_date.isoformat()}"
            )

        dealer_buy = (
            dealer_prop_buy
            + dealer_hedge_buy
        )

        dealer_sell = (
            dealer_prop_sell
            + dealer_hedge_sell
        )

        computed_net = (
            dealer_prop_net
            + dealer_hedge_net
        )

        if (
            computed_net
            != dealer_total_net
        ):

            raise RuntimeError(
                "TWSE "
                f"{stock_id} "
                "dealer total mismatch "
                f"on {trade_date.isoformat()}"
            )

        official_total = (
            raw[
                total_idx
            ]
            if total_idx is not None
            else None
        )

        result[
            stock_id
        ] = build_row(
            market="TWSE",
            stock_id=stock_id,
            trade_date=trade_date,
            source="TWSE_T86",

            foreign_buy=(
                raw[
                    idx[
                        "外陸資買進股數(不含外資自營商)"
                    ]
                ]
            ),

            foreign_sell=(
                raw[
                    idx[
                        "外陸資賣出股數(不含外資自營商)"
                    ]
                ]
            ),

            foreign_net=(
                raw[
                    idx[
                        "外陸資買賣超股數(不含外資自營商)"
                    ]
                ]
            ),

            trust_buy=(
                raw[
                    idx[
                        "投信買進股數"
                    ]
                ]
            ),

            trust_sell=(
                raw[
                    idx[
                        "投信賣出股數"
                    ]
                ]
            ),

            trust_net=(
                raw[
                    idx[
                        "投信買賣超股數"
                    ]
                ]
            ),

            dealer_buy=dealer_buy,
            dealer_sell=dealer_sell,
            dealer_net=dealer_total_net,

            official_total=(
                official_total
            ),
        )

    return FetchResult(
        market="TWSE",
        trade_date=trade_date,
        source_name="TWSE_T86",
        rows=result,
        raw_count=raw_count,
    )


# ============================================================
# TPEX CURRENT OPENAPI
# ============================================================


def get_tpex_openapi_value(
    raw: dict[
        str,
        Any,
    ],
    *,
    group: str,
    field: str,
) -> Any:

    def predicate(
        key: str,
    ) -> bool:

        if group == "foreign":

            is_group = (
                "foreigninvestors"
                in key

                and

                "mainland"
                in key

                and

                "dealersexcluded"
                in key
            )

        elif group == "trust":

            is_group = (
                "securitiesinvestmenttrustcompanies"
                in key
            )

        elif group == "dealer":

            # 避免 Foreign Dealers
            is_group = (
                key.startswith(
                    "dealers"
                )
                and
                "foreign"
                not in key
            )

        else:
            return False

        if not is_group:
            return False

        if field == "buy":

            return (
                key.endswith(
                    "totalbuy"
                )
                or
                key.endswith(
                    "buy"
                )
            )

        if field == "sell":

            return (
                key.endswith(
                    "totalsell"
                )
                or
                key.endswith(
                    "sell"
                )
            )

        if field == "net":

            return (
                key.endswith(
                    "difference"
                )
            )

        return False

    return find_dict_value(
        raw,
        predicate,
    )


def fetch_tpex_current_snapshot(
) -> FetchResult:

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
            "TPEx OpenAPI response "
            "is not JSON array"
        )

    raw_count = len(
        payload
    )

    if (
        raw_count
        <
        MIN_SOURCE_ROWS[
            "TPEX_OPENAPI"
        ]
    ):

        raise RuntimeError(
            "TPEx OpenAPI source count "
            f"too low: {raw_count}"
        )

    response_dates: set[
        date
    ] = set()

    result: dict[
        str,
        InstitutionalRow,
    ] = {}

    for raw in payload:

        if not isinstance(
            raw,
            dict,
        ):
            continue

        trade_date = (
            parse_roc_compact_date(
                raw.get(
                    "Date"
                )
            )
        )

        if trade_date is None:

            raise RuntimeError(
                "TPEx OpenAPI "
                "invalid Date field"
            )

        response_dates.add(
            trade_date
        )

        stock_id = clean_text(
            raw.get(
                "SecuritiesCompanyCode"
            )
        )

        if not stock_id:
            continue

        if stock_id in result:

            raise RuntimeError(
                "TPEx OpenAPI duplicate "
                f"stock_id={stock_id}"
            )

        foreign_buy = (
            get_tpex_openapi_value(
                raw,
                group="foreign",
                field="buy",
            )
        )

        foreign_sell = (
            get_tpex_openapi_value(
                raw,
                group="foreign",
                field="sell",
            )
        )

        foreign_net = (
            get_tpex_openapi_value(
                raw,
                group="foreign",
                field="net",
            )
        )

        trust_buy = (
            get_tpex_openapi_value(
                raw,
                group="trust",
                field="buy",
            )
        )

        trust_sell = (
            get_tpex_openapi_value(
                raw,
                group="trust",
                field="sell",
            )
        )

        trust_net = (
            get_tpex_openapi_value(
                raw,
                group="trust",
                field="net",
            )
        )

        dealer_buy = (
            get_tpex_openapi_value(
                raw,
                group="dealer",
                field="buy",
            )
        )

        dealer_sell = (
            get_tpex_openapi_value(
                raw,
                group="dealer",
                field="sell",
            )
        )

        dealer_net = (
            get_tpex_openapi_value(
                raw,
                group="dealer",
                field="net",
            )
        )

        total = find_dict_value(
            raw,
            lambda key:
                key
                == "totaldifference",
        )

        result[
            stock_id
        ] = build_row(
            market="TPEX",
            stock_id=stock_id,
            trade_date=trade_date,
            source="TPEX_OPENAPI",

            foreign_buy=foreign_buy,
            foreign_sell=foreign_sell,
            foreign_net=foreign_net,

            trust_buy=trust_buy,
            trust_sell=trust_sell,
            trust_net=trust_net,

            dealer_buy=dealer_buy,
            dealer_sell=dealer_sell,
            dealer_net=dealer_net,

            official_total=total,
        )

    if len(
        response_dates
    ) != 1:

        raise RuntimeError(
            "TPEx OpenAPI contains "
            "multiple or zero dates: "
            f"{sorted(response_dates)}"
        )

    snapshot_date = next(
        iter(
            response_dates
        )
    )

    return FetchResult(
        market="TPEX",
        trade_date=snapshot_date,
        source_name="TPEX_OPENAPI",
        rows=result,
        raw_count=raw_count,
    )


# ============================================================
# TPEX HISTORICAL DAILY TRADE
# ============================================================


def fetch_tpex_history(
    trade_date: date,
) -> FetchResult:

    query = urllib.parse.urlencode(
        {
            "type":
                "Daily",

            "sect":
                "EW",

            "date":
                to_roc_date(
                    trade_date
                ),

            "id":
                "",

            "response":
                "json",
        }
    )

    url = (
        f"{TPEX_HISTORY_URL}"
        f"?{query}"
    )

    payload = decode_json(
        fetch_with_retry(
            url,

            headers={
                "Referer":
                    TPEX_REFERER,
            },

            prefer_curl=True,
        )
    )

    if not isinstance(
        payload,
        dict,
    ):

        raise RuntimeError(
            "TPEx historical response "
            "is not JSON object"
        )

    tables = payload.get(
        "tables"
    )

    if (
        not isinstance(
            tables,
            list,
        )
        or
        not tables
    ):

        raise RuntimeError(
            "TPEx historical "
            "has no tables for "
            f"{trade_date.isoformat()}"
        )

    table = tables[0]

    if not isinstance(
        table,
        dict,
    ):

        raise RuntimeError(
            "TPEx historical "
            "table invalid"
        )

    response_date = (
        parse_roc_slash_date(
            table.get(
                "date"
            )
            or
            payload.get(
                "date"
            )
        )
    )

    if (
        response_date is not None
        and
        response_date
        != trade_date
    ):

        raise RuntimeError(
            "TPEx historical "
            "wrong response date: "
            f"requested="
            f"{trade_date.isoformat()}, "
            f"returned="
            f"{response_date.isoformat()}"
        )

    raw_rows = table.get(
        "data"
    )

    if not isinstance(
        raw_rows,
        list,
    ):

        raise RuntimeError(
            "TPEx historical "
            "data invalid"
        )

    raw_count = len(
        raw_rows
    )

    if (
        raw_count
        <
        MIN_SOURCE_ROWS[
            "TPEX_HISTORY"
        ]
    ):

        raise RuntimeError(
            "TPEx historical source "
            "count too low on "
            f"{trade_date.isoformat()}: "
            f"{raw_count}"
        )

    result: dict[
        str,
        InstitutionalRow,
    ] = {}

    for raw in raw_rows:

        if (
            not isinstance(
                raw,
                list,
            )
            or
            len(raw) < 24
        ):

            raise RuntimeError(
                "TPEx historical "
                "unexpected row shape "
                f"on {trade_date.isoformat()}"
            )

        stock_id = (
            clean_text(
                raw[0]
            )
            .replace(
                "=",
                "",
            )
            .replace(
                '"',
                "",
            )
            .strip()
        )

        if not stock_id:
            continue

        if stock_id in result:

            raise RuntimeError(
                "TPEx historical duplicate "
                f"{stock_id} "
                f"on {trade_date.isoformat()}"
            )

        # ====================================================
        # TPEx Historical 24 columns
        #
        # 0  代號
        # 1  名稱
        #
        # 2~4
        # 外資及陸資
        # （不含外資自營商）
        #
        # 5~7
        # 外資自營商
        #
        # 8~10
        # 外資及陸資合計
        #
        # 11~13 投信
        #
        # 14~16 自營商自行買賣
        #
        # 17~19 自營商避險
        #
        # 20~22 自營商合計
        #
        # 23 三大法人買賣超合計
        #
        # StockWaveScanner V2 的 foreign
        # 固定採 2~4：
        #
        # 外資及陸資
        # （不含外資自營商）
        # ====================================================

        dealer_prop_buy = (
            parse_int(
                raw[14]
            )
        )

        dealer_prop_sell = (
            parse_int(
                raw[15]
            )
        )

        dealer_prop_net = (
            parse_int(
                raw[16]
            )
        )

        dealer_hedge_buy = (
            parse_int(
                raw[17]
            )
        )

        dealer_hedge_sell = (
            parse_int(
                raw[18]
            )
        )

        dealer_hedge_net = (
            parse_int(
                raw[19]
            )
        )

        dealer_total_buy = (
            parse_int(
                raw[20]
            )
        )

        dealer_total_sell = (
            parse_int(
                raw[21]
            )
        )

        dealer_total_net = (
            parse_int(
                raw[22]
            )
        )

        dealer_values = (
            dealer_prop_buy,
            dealer_prop_sell,
            dealer_prop_net,

            dealer_hedge_buy,
            dealer_hedge_sell,
            dealer_hedge_net,

            dealer_total_buy,
            dealer_total_sell,
            dealer_total_net,
        )

        if any(
            value is None
            for value
            in dealer_values
        ):

            raise RuntimeError(
                "TPEx historical "
                f"{stock_id} "
                "dealer component missing "
                f"on {trade_date.isoformat()}"
            )

        if (
            dealer_prop_buy
            + dealer_hedge_buy
            != dealer_total_buy
        ):

            raise RuntimeError(
                "TPEx historical "
                f"{stock_id} "
                "dealer buy mismatch "
                f"on {trade_date.isoformat()}"
            )

        if (
            dealer_prop_sell
            + dealer_hedge_sell
            != dealer_total_sell
        ):

            raise RuntimeError(
                "TPEx historical "
                f"{stock_id} "
                "dealer sell mismatch "
                f"on {trade_date.isoformat()}"
            )

        if (
            dealer_prop_net
            + dealer_hedge_net
            != dealer_total_net
        ):

            raise RuntimeError(
                "TPEx historical "
                f"{stock_id} "
                "dealer net mismatch "
                f"on {trade_date.isoformat()}"
            )

        result[
            stock_id
        ] = build_row(
            market="TPEX",
            stock_id=stock_id,
            trade_date=trade_date,
            source="TPEX_HISTORY",

            foreign_buy=raw[2],
            foreign_sell=raw[3],
            foreign_net=raw[4],

            trust_buy=raw[11],
            trust_sell=raw[12],
            trust_net=raw[13],

            dealer_buy=(
                dealer_total_buy
            ),

            dealer_sell=(
                dealer_total_sell
            ),

            dealer_net=(
                dealer_total_net
            ),

            official_total=raw[23],
        )

    return FetchResult(
        market="TPEX",
        trade_date=trade_date,
        source_name="TPEX_HISTORY",
        rows=result,
        raw_count=raw_count,
    )


# ============================================================
# TPEX SOURCE ROUTER
# ============================================================


def fetch_tpex_source(
    trade_date: date,
) -> FetchResult:

    # 最新幾天先嘗試官方 OpenAPI。
    #
    # OpenAPI 是正式 Daily Pipeline
    # 的 PRIMARY source。
    #
    # 若 OpenAPI 最新日期不是要求日期，
    # 再退回 Historical dailyTrade。
    days_ago = (
        taipei_today()
        - trade_date
    ).days

    if (
        0
        <= days_ago
        <= 5
    ):

        try:

            snapshot = (
                fetch_tpex_current_snapshot()
            )

            if (
                snapshot.trade_date
                == trade_date
            ):

                return snapshot

        except Exception as exc:

            print(
                "    [WARN] "
                "TPEx current OpenAPI "
                f"fallback: {exc}"
            )

    return fetch_tpex_history(
        trade_date
    )


def fetch_source(
    market: str,
    trade_date: date,
) -> FetchResult:

    if market == "TWSE":

        return fetch_twse_source(
            trade_date
        )

    if market == "TPEX":

        return fetch_tpex_source(
            trade_date
        )

    raise RuntimeError(
        f"Unsupported market: "
        f"{market}"
    )


# ============================================================
# TURSO READ HELPERS
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


def get_market_master_ids(
    conn,
    market: str,
) -> set[str]:

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
        clean_text(
            row[0]
        )

        for row in rows
    }


def get_traded_ids(
    conn,
    market: str,
    trade_date: str,
) -> set[str]:

    rows = (
        conn.execute(
            """
            SELECT p.stock_id

            FROM stock_price_daily p

            INNER JOIN stock_master s
                ON s.stock_id =
                   p.stock_id

            WHERE p.trade_date = ?
              AND s.market = ?
              AND s.security_type =
                  'COMMON_STOCK'
            """,
            (
                trade_date,
                market,
            ),
        )
        .fetchall()
    )

    return {
        clean_text(
            row[0]
        )

        for row in rows
    }


def get_latest_date(
    conn,
    market: str,
) -> str | None:

    value = scalar(
        conn,
        """
        SELECT MAX(
            i.trade_date
        )

        FROM institutional_daily i

        INNER JOIN stock_master s
            ON s.stock_id =
               i.stock_id

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


def get_pending_trade_dates(
    conn,
    market: str,
    cursor: str | None,
    through: date,
) -> list[str]:

    if cursor is None:

        # Daily Pipeline 不偷跑
        # Historical Backfill。
        #
        # 若整表為空，
        # 只從當月開始。
        start_date = (
            through.replace(
                day=1
            )
            .isoformat()
        )

        comparison = ">="

    else:

        start_date = cursor
        comparison = ">"

    rows = (
        conn.execute(
            f"""
            SELECT DISTINCT
                p.trade_date

            FROM stock_price_daily p

            INNER JOIN stock_master s
                ON s.stock_id =
                   p.stock_id

            WHERE s.market = ?
              AND s.security_type =
                  'COMMON_STOCK'

              AND p.trade_date
                  {comparison} ?

              AND p.trade_date <= ?

            ORDER BY
                p.trade_date
            """,
            (
                market,
                start_date,
                through.isoformat(),
            ),
        )
        .fetchall()
    )

    return [
        str(
            row[0]
        )

        for row in rows
    ]


# ============================================================
# PREPARE DAY
# ============================================================


def prepare_day_rows(
    conn,
    market: str,
    trade_date: date,
    fetched: FetchResult,
) -> tuple[
    list[InstitutionalRow],
    int,
    int,
    int,
    float,
]:

    master_ids = (
        get_market_master_ids(
            conn,
            market,
        )
    )

    traded_ids = (
        get_traded_ids(
            conn,
            market,
            trade_date.isoformat(),
        )
    )

    if not traded_ids:

        raise RuntimeError(
            f"{market} has no "
            "stock_price_daily universe "
            f"for {trade_date.isoformat()}"
        )

    source_rows = (
        fetched.rows
    )

    eligible_source = {
        stock_id: row

        for stock_id, row
        in source_rows.items()

        if (
            stock_id
            in master_ids

            and

            stock_id
            in traded_ids
        )
    }

    excluded = len(
        set(
            source_rows
        )
        - master_ids
    )

    source_not_traded = len(
        (
            set(
                source_rows
            )
            & master_ids
        )
        -
        traded_ids
    )

    stored_count = len(
        eligible_source
    )

    coverage = (
        stored_count
        /
        len(
            traded_ids
        )
    )

    rows: list[
        InstitutionalRow
    ] = []

    missing = 0

    for stock_id in sorted(
        traded_ids
    ):

        row = eligible_source.get(
            stock_id
        )

        if row is None:

            missing += 1

            # =================================================
            # 關鍵：
            #
            # Source 沒列
            # !=
            # 法人一定是 0
            #
            # 因此：
            #
            # NULL
            # +
            # INSUFFICIENT_DATA
            #
            # 不使用 ZERO_INFERRED。
            # =================================================

            row = build_missing_row(
                stock_id=stock_id,
                trade_date=trade_date,
                source=(
                    fetched.source_name
                ),
            )

        rows.append(
            row
        )

    return (
        rows,
        missing,
        excluded,
        source_not_traded,
        coverage,
    )


# ============================================================
# MULTI ROW UPSERT
# ============================================================


INSERT_PREFIX = """
INSERT INTO institutional_daily (
    stock_id,
    trade_date,

    foreign_buy,
    foreign_sell,
    foreign_net,

    trust_buy,
    trust_sell,
    trust_net,

    dealer_buy,
    dealer_sell,
    dealer_net,

    foreign_data_status,
    trust_data_status,
    dealer_data_status,

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
    ?, ?, ?,
    ?, ?, ?,

    ?, ?, ?,

    ?,

    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
"""


INSERT_SUFFIX = """
ON CONFLICT(
    stock_id,
    trade_date
)
DO UPDATE SET

    foreign_buy =
        excluded.foreign_buy,

    foreign_sell =
        excluded.foreign_sell,

    foreign_net =
        excluded.foreign_net,


    trust_buy =
        excluded.trust_buy,

    trust_sell =
        excluded.trust_sell,

    trust_net =
        excluded.trust_net,


    dealer_buy =
        excluded.dealer_buy,

    dealer_sell =
        excluded.dealer_sell,

    dealer_net =
        excluded.dealer_net,


    foreign_data_status =
        excluded.foreign_data_status,

    trust_data_status =
        excluded.trust_data_status,

    dealer_data_status =
        excluded.dealer_data_status,


    source =
        excluded.source,

    updated_at =
        CURRENT_TIMESTAMP
"""


def flatten_rows(
    rows: list[
        InstitutionalRow,
    ],
) -> tuple[
    Any,
    ...,
]:

    values: list[Any] = []

    for row in rows:

        values.extend(
            row.db_tuple()
        )

    return tuple(
        values
    )


def build_insert_sql(
    row_count: int,
) -> str:

    values_sql = (
        ",\n".join(
            INSERT_VALUE

            for _ in range(
                row_count
            )
        )
    )

    return (
        INSERT_PREFIX
        + values_sql
        + INSERT_SUFFIX
    )


# ============================================================
# SYNC STATE
# ============================================================


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
                    WHEN
                        excluded.status =
                        'SUCCESS'

                    THEN
                        CURRENT_TIMESTAMP

                    ELSE
                        sync_state.last_success_at
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


# ============================================================
# WRITE
# ============================================================


def write_day(
    conn,
    *,
    market: str,
    trade_date: str,
    rows: list[
        InstitutionalRow,
    ],
    cumulative_rows: int,
) -> int:

    conn.execute(
        "BEGIN"
    )

    try:

        for start in range(
            0,
            len(rows),
            SQL_ROWS_PER_STATEMENT,
        ):

            batch = rows[
                start:
                start
                + SQL_ROWS_PER_STATEMENT
            ]

            conn.execute(
                build_insert_sql(
                    len(batch)
                ),

                flatten_rows(
                    batch
                ),
            )

        new_total = (
            cumulative_rows
            + len(rows)
        )

        update_sync_state(
            conn,
            DATASETS[
                market
            ],
            trade_date,
            new_total,
            "RUNNING",
        )

        conn.commit()

        return new_total

    except BaseException:

        try:
            conn.rollback()

        except Exception:
            pass

        raise


def finish_market(
    conn,
    *,
    market: str,
    last_data_date: str | None,
    records_processed: int,
) -> None:

    conn.execute(
        "BEGIN"
    )

    try:

        update_sync_state(
            conn,
            DATASETS[
                market
            ],
            last_data_date,
            records_processed,
            "SUCCESS",
        )

        conn.commit()

    except BaseException:

        try:
            conn.rollback()

        except Exception:
            pass

        raise


def mark_failed(
    conn,
    *,
    market: str,
    last_data_date: str | None,
    records_processed: int,
    message: str,
) -> None:

    try:

        conn.execute(
            "BEGIN"
        )

        update_sync_state(
            conn,
            DATASETS[
                market
            ],
            last_data_date,
            records_processed,
            "FAILED",
            message[:1000],
        )

        conn.commit()

    except Exception:

        try:
            conn.rollback()

        except Exception:
            pass


# ============================================================
# DB RESULT CHECK
# ============================================================


def validate_db_rows(
    conn,
    market: str,
    trade_date: str,
) -> tuple[
    int,
    int,
    int,
]:

    row = (
        conn.execute(
            """
            SELECT
                COUNT(*),

                SUM(
                    CASE

                        WHEN
                            i.foreign_data_status =
                            'STORED'

                            AND

                            i.trust_data_status =
                            'STORED'

                            AND

                            i.dealer_data_status =
                            'STORED'

                        THEN 1

                        ELSE 0
                    END
                ),

                SUM(
                    CASE

                        WHEN
                            i.foreign_data_status =
                            'INSUFFICIENT_DATA'

                            OR

                            i.trust_data_status =
                            'INSUFFICIENT_DATA'

                            OR

                            i.dealer_data_status =
                            'INSUFFICIENT_DATA'

                        THEN 1

                        ELSE 0
                    END
                )

            FROM institutional_daily i

            INNER JOIN stock_master s
                ON s.stock_id =
                   i.stock_id

            WHERE s.market = ?
              AND s.security_type =
                  'COMMON_STOCK'

              AND i.trade_date = ?
            """,
            (
                market,
                trade_date,
            ),
        )
        .fetchone()
    )

    return (
        int(
            row[0] or 0
        ),

        int(
            row[1] or 0
        ),

        int(
            row[2] or 0
        ),
    )


# ============================================================
# READ ONLY VALIDATION
# ============================================================


def run_validation(
    conn,
    trade_date: date,
) -> None:

    if (
        trade_date.weekday()
        >= 5
    ):

        raise RuntimeError(
            "--validate-date must be "
            "a known trading weekday"
        )

    print()

    print(
        "=" * 76
    )

    print(
        "READ-ONLY "
        "INSTITUTIONAL VALIDATION"
    )

    print(
        "=" * 76
    )

    print(
        "Trade Date : "
        f"{trade_date.isoformat()}"
    )

    print(
        "Turso Write: DISABLED"
    )

    print()

    for index, market in enumerate(
        (
            "TWSE",
            "TPEX",
        )
    ):

        if index:

            time.sleep(
                REQUEST_INTERVAL
            )

        fetched = (
            fetch_source(
                market,
                trade_date,
            )
        )

        (
            rows,
            missing,
            excluded,
            source_not_traded,
            coverage,
        ) = prepare_day_rows(
            conn,
            market,
            trade_date,
            fetched,
        )

        stored = (
            len(rows)
            - missing
        )

        print(
            f"{market:<4} "
            f"| source="
            f"{fetched.source_name:<15} "

            f"| raw="
            f"{fetched.raw_count:,} "

            f"| traded="
            f"{len(rows):,} "

            f"| stored="
            f"{stored:,} "

            f"| missing="
            f"{missing:,} "

            f"| coverage="
            f"{coverage:.2%}"
        )

        print(
            "     "
            f"excluded_non_common="
            f"{excluded:,} "
            f"| source_not_traded="
            f"{source_not_traded:,}"
        )

    print()

    print(
        "[PASS] Official source fetch"
    )

    print(
        "[PASS] Source-size sanity validation"
    )

    print(
        "[PASS] Foreign / Trust / "
        "Dealer normalization"
    )

    print(
        "[PASS] Buy-Sell-Net "
        "arithmetic validation"
    )

    print(
        "[PASS] Official institutional "
        "total validation"
    )

    print(
        "[PASS] Missing rows preserved as "
        "INSUFFICIENT_DATA"
    )

    print(
        "[PASS] COMMON_STOCK / "
        "traded-universe filtering"
    )

    print(
        "[PASS] Turso DEV "
        "read connection"
    )

    print(
        "[PASS] No database rows "
        "were written"
    )


# ============================================================
# INCREMENTAL
# ============================================================


def run_incremental(
    conn,
    through: date,
) -> None:

    cursors = {

        market:
            get_latest_date(
                conn,
                market,
            )

        for market in (
            "TWSE",
            "TPEX",
        )
    }

    print()

    print(
        "=" * 76
    )

    print(
        "INSTITUTIONAL "
        "INCREMENTAL CURSOR"
    )

    print(
        "=" * 76
    )

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

    pending = {

        market:
            get_pending_trade_dates(
                conn,
                market,
                cursors[
                    market
                ],
                through,
            )

        for market in (
            "TWSE",
            "TPEX",
        )
    }

    print()

    for market in (
        "TWSE",
        "TPEX",
    ):

        dates = (
            pending[
                market
            ]
        )

        if dates:

            print(
                f"{market:<4} "
                "Pending Dates : "
                f"{len(dates):,} "
                f"| {dates[0]} "
                f".. {dates[-1]}"
            )

        else:

            print(
                f"{market:<4} "
                "Pending Dates : 0"
            )

    processed = {
        "TWSE": 0,
        "TPEX": 0,
    }

    last_success = dict(
        cursors
    )

    for market in (
        "TWSE",
        "TPEX",
    ):

        dates = (
            pending[
                market
            ]
        )

        try:

            for index, trade_date_text in enumerate(
                dates,
                start=1,
            ):

                trade_date = (
                    parse_iso_date(
                        trade_date_text
                    )
                )

                if index > 1:

                    time.sleep(
                        REQUEST_INTERVAL
                    )

                fetched = (
                    fetch_source(
                        market,
                        trade_date,
                    )
                )

                (
                    rows,
                    missing,
                    excluded,
                    source_not_traded,
                    coverage,
                ) = prepare_day_rows(
                    conn,
                    market,
                    trade_date,
                    fetched,
                )

                stored = (
                    len(rows)
                    - missing
                )

                print(
                    f"{market} "
                    f"{trade_date_text} "

                    f"| {index}/"
                    f"{len(dates)} "

                    f"| {fetched.source_name} "

                    f"| raw="
                    f"{fetched.raw_count:,} "

                    f"| stored="
                    f"{stored:,} "

                    f"| missing="
                    f"{missing:,} "

                    f"| coverage="
                    f"{coverage:.2%}"
                )

                processed[
                    market
                ] = write_day(
                    conn,
                    market=market,
                    trade_date=(
                        trade_date_text
                    ),
                    rows=rows,
                    cumulative_rows=(
                        processed[
                            market
                        ]
                    ),
                )

                last_success[
                    market
                ] = (
                    trade_date_text
                )

            finish_market(
                conn,
                market=market,
                last_data_date=(
                    last_success[
                        market
                    ]
                ),
                records_processed=(
                    processed[
                        market
                    ]
                ),
            )

        except Exception as exc:

            mark_failed(
                conn,
                market=market,
                last_data_date=(
                    last_success[
                        market
                    ]
                ),
                records_processed=(
                    processed[
                        market
                    ]
                ),
                message=str(
                    exc
                ),
            )

            raise

    print()

    print(
        "=" * 76
    )

    print(
        "INSTITUTIONAL "
        "INCREMENTAL RESULT"
    )

    print(
        "=" * 76
    )

    for market in (
        "TWSE",
        "TPEX",
    ):

        latest = (
            get_latest_date(
                conn,
                market,
            )
        )

        print(
            f"{market} "
            "Last Data Date : "
            f"{latest or 'EMPTY'}"
        )

        print(
            f"{market} "
            "Rows This Run  : "
            f"{processed[market]:,}"
        )

        if latest:

            (
                total,
                stored,
                insufficient,
            ) = validate_db_rows(
                conn,
                market,
                latest,
            )

            print(
                f"{market} "
                "Latest DB Rows  : "
                f"{total:,}"
            )

            print(
                f"{market} "
                "Latest STORED   : "
                f"{stored:,}"
            )

            print(
                f"{market} "
                "Latest INSUFF   : "
                f"{insufficient:,}"
            )

    print(
        "PROD Access         : "
        "DISABLED"
    )


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    args = (
        parse_args()
    )

    print(
        "=" * 76
    )

    print(
        "StockWaveScanner V2 - "
        "Institutional Incremental Pipeline"
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
                    "Turso DEV connection "
                    "validation failed"
                )

            schema_version = (
                get_schema_version(
                    conn
                )
            )

            if (
                schema_version
                is None
            ):

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

            if (
                args.validate_date
            ):

                run_validation(
                    conn,
                    parse_iso_date(
                        args.validate_date
                    ),
                )

            else:

                through = (
                    parse_iso_date(
                        args.through
                    )

                    if args.through

                    else taipei_today()
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

        print(
            "=" * 76
        )

        print(
            "INSTITUTIONAL "
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