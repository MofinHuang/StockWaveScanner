from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys
import uuid

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

import libsql
import requests
import urllib3
from dotenv import load_dotenv


urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


YUANTA_ETFS = [
    "0050",
    "0056",
]


YUANTA_API_URL = (
    "https://etfapi.yuantaetfs.com/"
    "ectranslation/api/bridge"
)


CATHAY_00878_API_URL = (
    "https://cwapi.cathaysite.com.tw/"
    "api/ETF/GetIndexStockWeights"
)


CATHAY_00878_PAGE_URL = (
    "https://www.cathaysite.com.tw/"
    "ETF/purchase?code=CN"
)


CAPITAL_API_URL = (
    "https://www.capitalfund.com.tw/"
    "CFWeb/api/etf/buyback"
)


CAPITAL_PAGE_URL = (
    "https://www.capitalfund.com.tw/"
    "etf/product/detail/195/buyback"
)


FUHWA_00929_API_URL = (
    "https://www.fhtrust.com.tw/"
    "api/assets"
)


FUHWA_00929_PAGE_URL = (
    "https://www.fhtrust.com.tw/"
    "ETF/etf_list"
)


EZMONEY_00981A_PAGE_URL = (
    "https://www.ezmoney.com.tw/"
    "ETF/Fund/Info"
    "?fundCode=49YTW"
    "&tabName=asset"
)


KGI_009816_PAGE_URL = (
    "https://www.kgifund.com.tw/"
    "Fund/Detail?fundID=J023"
)


HEADERS = {
    "User-Agent":
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/154.0 Safari/537.36",

    "Accept":
        "application/json, text/plain, */*",

    "Accept-Language":
        "zh-TW,zh;q=0.9,en;q=0.8",
}

TAIPEI = ZoneInfo(
    "Asia/Taipei"
)

def configure_console():

    for stream in (
        sys.stdout,
        sys.stderr,
    ):

        fn = getattr(
            stream,
            "reconfigure",
            None,
        )

        if callable(fn):

            try:

                fn(
                    encoding="utf-8",
                    errors="replace",
                )

            except Exception:
                pass


def get_connection():

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

    if not url:
        raise RuntimeError(
            "TURSO_DEV_DATABASE_URL missing"
        )

    if not token:
        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN missing"
        )

    lower_url = url.lower()

    if "stockwave-dev" not in lower_url:
        raise RuntimeError(
            "SAFETY STOP: DEV database required"
        )

    if "stockwave-prod" in lower_url:
        raise RuntimeError(
            "SAFETY STOP: PROD database detected"
        )

    return libsql.connect(
        database=url,
        auth_token=token,
    )


def normalize_date(
    value,
):

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    if "T" in text:
        text = text.split(
            "T",
            1,
        )[0]

    text = (
        text
        .replace("上午", "")
        .replace("下午", "")
        .strip()
    )

    formats = [
        "%Y%m%d",
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                text,
                fmt,
            ).strftime(
                "%Y-%m-%d"
            )

        except ValueError:
            pass

    return None


def to_float(
    value,
):

    if value is None:
        return None

    if isinstance(
        value,
        (int, float),
    ):
        return float(value)

    text = (
        str(value)
        .replace(",", "")
        .replace("%", "")
        .replace("TWD$", "")
        .strip()
    )

    if not text:
        return None

    try:
        return float(text)

    except ValueError:
        return None


def clean_html_text(
    value: str,
):

    value = re.sub(
        r"<[^>]+>",
        "",
        value,
    )

    return html.unescape(
        value
    ).strip()


def deduplicate_rows(
    rows: list[dict],
):

    dedup = {}

    for row in rows:

        stock_id = (
            row.get(
                "stock_id"
            )
            or ""
        ).strip()

        if not stock_id:
            continue

        dedup[
            stock_id
        ] = row

    return list(
        dedup.values()
    )


# ============================================================
# Yuanta 0050 / 0056
# ============================================================

def page_url_for_yuanta(
    etf_id: str,
):

    return (
        "https://www.yuantaetfs.com/"
        f"tradeInfo/pcf/{etf_id}"
    )


def unwrap_yuanta_response(
    data,
):

    if not isinstance(
        data,
        dict,
    ):
        return data

    if (
        "PCF" in data
        or "FundWeights" in data
        or "InKind" in data
    ):
        return data

    for key in (
        "data",
        "Data",
        "result",
        "Result",
        "response",
        "Response",
    ):

        value = data.get(key)

        if isinstance(
            value,
            dict,
        ):

            result = (
                unwrap_yuanta_response(
                    value
                )
            )

            if isinstance(
                result,
                dict,
            ) and (
                "PCF" in result
                or "FundWeights" in result
                or "InKind" in result
            ):
                return result

    return data


def fetch_yuanta_pcf(
    etf_id: str,
):

    page_url = (
        page_url_for_yuanta(
            etf_id
        )
    )

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    page_response = session.get(
        page_url,
        timeout=30,
        verify=False,
    )

    page_response.raise_for_status()

    params = {
        "APIType": "ETFAPI",
        "CompanyName": "YUANTAFUNDS",
        "PageName":
            f"/tradeInfo/pcf/{etf_id}",
        "DeviceId":
            str(uuid.uuid4()),
        "FuncId": "PCF/Daily",
        "AppName": "ETF",
        "Device": "3",
        "Platform": "ETF",
        "ticker": etf_id,
        "ndate": "",
    }

    headers = {
        "Referer":
            page_url,

        "Origin":
            "https://www.yuantaetfs.com",
    }

    response = session.get(
        YUANTA_API_URL,
        params=params,
        headers=headers,
        timeout=30,
        verify=False,
    )

    response.raise_for_status()

    data = unwrap_yuanta_response(
        response.json()
    )

    if not isinstance(
        data,
        dict,
    ):
        raise RuntimeError(
            f"{etf_id}: invalid Yuanta response"
        )

    return data


def parse_yuanta_holdings(
    etf_id: str,
    data: dict,
):

    pcf = (
        data.get("PCF")
        or {}
    )

    trade_date = (
        normalize_date(
            pcf.get("trandate")
        )
        or normalize_date(
            pcf.get("anndate")
        )
    )

    if not trade_date:
        raise RuntimeError(
            f"{etf_id}: "
            "Yuanta reference date not found"
        )

    rows = []

    fund_weights = (
        data.get("FundWeights")
        or {}
    )

    stock_weights = (
        fund_weights.get(
            "StockWeights"
        )
        or []
    )

    for item in stock_weights:

        stock_id = str(
            item.get(
                "code",
                "",
            )
        ).strip()

        if not stock_id:
            continue

        rows.append(
            {
                "trade_date":
                    trade_date,

                "etf_id":
                    etf_id,

                "stock_id":
                    stock_id,

                "stock_name":
                    str(
                        item.get(
                            "name",
                            "",
                        )
                    ).strip(),

                "shares":
                    to_float(
                        item.get(
                            "qty"
                        )
                    ),

                "weight_pct":
                    to_float(
                        item.get(
                            "weights"
                        )
                    ),

                "market_value":
                    None,

                "source_url":
                    page_url_for_yuanta(
                        etf_id
                    ),
            }
        )

    if not rows:

        in_kind = (
            data.get("InKind")
            or {}
        )

        composition = (
            in_kind.get(
                "FundComposition"
            )
            or []
        )

        for item in composition:

            stock_id = str(
                item.get(
                    "stkcd",
                    "",
                )
            ).strip()

            if not stock_id:
                continue

            rows.append(
                {
                    "trade_date":
                        trade_date,

                    "etf_id":
                        etf_id,

                    "stock_id":
                        stock_id,

                    "stock_name":
                        str(
                            item.get(
                                "name",
                                "",
                            )
                        ).strip(),

                    "shares":
                        to_float(
                            item.get(
                                "qty"
                            )
                        ),

                    "weight_pct":
                        None,

                    "market_value":
                        None,

                    "source_url":
                        page_url_for_yuanta(
                            etf_id
                        ),
                }
            )

    return deduplicate_rows(
        rows
    )


# ============================================================
# Cathay 00878
# ============================================================

def fetch_cathay_00878():

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    session.get(
        CATHAY_00878_PAGE_URL,
        timeout=30,
        verify=False,
    ).raise_for_status()

    response = session.get(
        CATHAY_00878_API_URL,
        params={
            "FundCode": "CN",
            "status": "1",
        },
        headers={
            "Referer":
                CATHAY_00878_PAGE_URL,

            "Origin":
                "https://www.cathaysite.com.tw",
        },
        timeout=30,
        verify=False,
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(
        data,
        dict,
    ):
        raise RuntimeError(
            "00878: invalid Cathay response"
        )

    if data.get(
        "success"
    ) is not True:
        raise RuntimeError(
            "00878: Cathay API failed "
            f"returnCode={data.get('returnCode')} "
            f"message={data.get('returnMessage')}"
        )

    return data


def parse_cathay_00878(
    response: dict,
):

    result = (
        response.get(
            "result"
        )
        or {}
    )

    reference_date = normalize_date(
        result.get(
            "date"
        )
    )

    if not reference_date:
        raise RuntimeError(
            "00878: official reference date not found"
        )

    rows = []

    for item in (
        result.get(
            "stockWeights"
        )
        or []
    ):

        stock_id = str(
            item.get(
                "stockCode",
                "",
            )
        ).strip()

        if not stock_id:
            continue

        rows.append(
            {
                "trade_date":
                    reference_date,

                "etf_id":
                    "00878",

                "stock_id":
                    stock_id,

                "stock_name":
                    str(
                        item.get(
                            "stockName",
                            "",
                        )
                    ).strip(),

                "shares":
                    None,

                "weight_pct":
                    to_float(
                        item.get(
                            "weights"
                        )
                    ),

                "market_value":
                    None,

                "source_url":
                    CATHAY_00878_PAGE_URL,
            }
        )

    return deduplicate_rows(
        rows
    )


def get_curl_command():

    curl_path = (
        shutil.which("curl.exe")
        or shutil.which("curl")
    )

    if not curl_path:
        raise RuntimeError(
            "curl command not found"
        )

    return curl_path

# ============================================================
# Capital 00919
# ============================================================

def curl_get(
    url: str,
):

    result = subprocess.run(
        [
            get_curl_command(),
            "-L",
            "--http1.1",
            "--compressed",
            "-A",
            HEADERS[
                "User-Agent"
            ],
            "-H",
            (
                "Accept-Language: "
                "zh-TW,zh;q=0.9,en;q=0.8"
            ),
            "--connect-timeout",
            "15",
            "--max-time",
            "45",
            "-sS",
            url,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(
            "curl GET failed: "
            f"{result.stderr.strip()}"
        )

    return result.stdout


def curl_post_json(
    url: str,
    payload: dict,
    referer: str,
):

    body = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    result = subprocess.run(
        [
            get_curl_command(),
            "-L",
            "--http1.1",
            "--compressed",

            "-A",
            HEADERS[
                "User-Agent"
            ],

            "-H",
            (
                "Accept: "
                "application/json, "
                "text/plain, */*"
            ),

            "-H",
            (
                "Accept-Language: "
                "zh-TW,zh;q=0.9,en;q=0.8"
            ),

            "-H",
            "Content-Type: application/json",

            "-H",
            (
                "Origin: "
                "https://www.capitalfund.com.tw"
            ),

            "-H",
            f"Referer: {referer}",

            "--data-raw",
            body,

            "--connect-timeout",
            "15",

            "--max-time",
            "45",

            "-sS",

            url,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(
            "curl POST failed: "
            f"{result.stderr.strip()}"
        )

    text = result.stdout.strip()

    if not text:
        raise RuntimeError(
            "Capital API empty response"
        )

    try:
        return json.loads(text)

    except json.JSONDecodeError:

        raise RuntimeError(
            "Capital API did not return JSON: "
            + text[:500]
        )


def fetch_capital_00919():

    page_html = curl_get(
        CAPITAL_PAGE_URL
    )

    if not page_html.strip():
        raise RuntimeError(
            "00919: official page empty"
        )

    data = curl_post_json(
        CAPITAL_API_URL,
        {
            "fundId": "195",
            "date": None,
        },
        CAPITAL_PAGE_URL,
    )

    if not isinstance(
        data,
        dict,
    ):
        raise RuntimeError(
            "00919: invalid API response"
        )

    if data.get("code") != 200:
        raise RuntimeError(
            "00919: API code="
            f"{data.get('code')} "
            f"message={data.get('message')}"
        )

    return data


def parse_capital_00919(
    response: dict,
):

    data = (
        response.get("data")
        or {}
    )

    pcf = (
        data.get("pcf")
        or {}
    )

    reference_date = normalize_date(
        pcf.get("date1")
    )

    if not reference_date:
        raise RuntimeError(
            "00919: official reference date not found"
        )

    rows = []

    for item in (
        data.get("stocks")
        or []
    ):

        stock_id = str(
            item.get(
                "stocNo",
                "",
            )
        ).strip()

        if not stock_id:
            continue

        rows.append(
            {
                "trade_date":
                    reference_date,

                "etf_id":
                    "00919",

                "stock_id":
                    stock_id,

                "stock_name":
                    str(
                        item.get(
                            "stocName",
                            "",
                        )
                    ).strip(),

                "shares":
                    to_float(
                        item.get(
                            "share"
                        )
                    ),

                "weight_pct":
                    to_float(
                        item.get(
                            "weight"
                        )
                    ),

                "market_value":
                    None,

                "source_url":
                    CAPITAL_PAGE_URL,
            }
        )

    return deduplicate_rows(
        rows
    )


# ============================================================
# Fuh Hwa 00929
# ============================================================

def fetch_fuhwa_00929():

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    today = datetime.now(
        TAIPEI
    ).date()

    last_error = None

    for offset in range(
        0,
        11,
    ):

        query_date = (
            today
            - timedelta(
                days=offset
            )
        )

        q_date = query_date.strftime(
            "%Y/%m/%d"
        )

        try:

            response = session.get(
                FUHWA_00929_API_URL,
                params={
                    "fundID":
                        "ETF21",

                    "qDate":
                        q_date,
                },
                timeout=30,
                verify=False,
            )

            response.raise_for_status()

            data = response.json()

            if not isinstance(
                data,
                dict,
            ):
                continue

            if data.get(
                "status"
            ) != 0:
                continue

            result_list = (
                data.get(
                    "result"
                )
                or []
            )

            if not result_list:
                continue

            fund = result_list[0]

            if str(
                fund.get(
                    "etf002",
                    "",
                )
            ).strip() != "00929":
                continue

            official_date = (
                normalize_date(
                    fund.get(
                        "dDate"
                    )
                )
            )

            if not official_date:
                continue

            stock_rows = [
                item

                for item in (
                    fund.get(
                        "detail"
                    )
                    or []
                )

                if str(
                    item.get(
                        "ftype",
                        "",
                    )
                ).strip() == "股票"
            ]

            if len(
                stock_rows
            ) < 20:

                continue

            print(
                f"    official query date="
                f"{q_date} "
                f"snapshot="
                f"{official_date}"
            )

            return data

        except Exception as exc:

            last_error = exc

    raise RuntimeError(
        "00929: no valid official "
        "holding snapshot found "
        "within previous 10 days"
        +
        (
            f" ({last_error})"
            if last_error
            else ""
        )
    )


def parse_fuhwa_00929(
    response: dict,
):

    result_list = (
        response.get("result")
        or []
    )

    if not result_list:
        raise RuntimeError(
            "00929: result empty"
        )

    fund = result_list[0]

    if str(
        fund.get(
            "etf002",
            "",
        )
    ).strip() != "00929":
        raise RuntimeError(
            "00929: unexpected ETF id"
        )

    reference_date = normalize_date(
        fund.get("dDate")
    )

    if not reference_date:
        raise RuntimeError(
            "00929: official reference date not found"
        )

    rows = []

    for item in (
        fund.get("detail")
        or []
    ):

        if str(
            item.get(
                "ftype",
                "",
            )
        ).strip() != "股票":
            continue

        stock_id = str(
            item.get(
                "stockid",
                "",
            )
        ).strip()

        if not stock_id:
            continue

        rows.append(
            {
                "trade_date":
                    reference_date,

                "etf_id":
                    "00929",

                "stock_id":
                    stock_id,

                "stock_name":
                    str(
                        item.get(
                            "stockname",
                            "",
                        )
                    ).strip(),

                "shares":
                    to_float(
                        item.get(
                            "qshare"
                        )
                    ),

                "weight_pct":
                    to_float(
                        item.get(
                            "prate_addaccint"
                        )
                    ),

                "market_value":
                    to_float(
                        item.get(
                            "mvalue"
                        )
                    ),

                "source_url":
                    FUHWA_00929_PAGE_URL,
            }
        )

    return deduplicate_rows(
        rows
    )


# ============================================================
# Uni-President 00981A
# ============================================================

def fetch_unipresident_00981a():

    response = requests.get(
        EZMONEY_00981A_PAGE_URL,
        headers=HEADERS,
        timeout=30,
        verify=False,
    )

    response.raise_for_status()

    response.encoding = (
        response.apparent_encoding
        or "utf-8"
    )

    return response.text


def parse_unipresident_00981a(
    html_text: str,
):

    match = re.search(
        r'<div\s+id=["\']DataAsset["\']'
        r'[^>]*data-content=["\'](.*?)["\']'
        r'[^>]*>',
        html_text,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if not match:
        raise RuntimeError(
            "00981A: DataAsset not found"
        )

    encoded_json = (
        match.group(1)
    )

    decoded_json = html.unescape(
        encoded_json
    )

    try:
        assets = json.loads(
            decoded_json
        )

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "00981A: DataAsset JSON decode failed"
        ) from exc

    stock_asset = None

    for asset in assets:

        if str(
            asset.get(
                "AssetCode",
                "",
            )
        ).strip() == "ST":

            stock_asset = asset
            break

    if not stock_asset:
        raise RuntimeError(
            "00981A: stock asset ST not found"
        )

    details = (
        stock_asset.get(
            "Details"
        )
        or []
    )

    rows = []

    reference_date = None

    for item in details:

        if str(
            item.get(
                "AssetCode",
                "",
            )
        ).strip() != "ST":
            continue

        item_date = normalize_date(
            item.get(
                "TranDate"
            )
        )

        if not item_date:
            continue

        if reference_date is None:
            reference_date = item_date

        stock_id = str(
            item.get(
                "DetailCode",
                "",
            )
        ).strip()

        if not stock_id:
            continue

        rows.append(
            {
                "trade_date":
                    item_date,

                "etf_id":
                    "00981A",

                "stock_id":
                    stock_id,

                "stock_name":
                    str(
                        item.get(
                            "DetailName",
                            "",
                        )
                    ).strip(),

                "shares":
                    to_float(
                        item.get(
                            "Share"
                        )
                    ),

                "weight_pct":
                    to_float(
                        item.get(
                            "NavRate"
                        )
                    ),

                "market_value":
                    to_float(
                        item.get(
                            "Amount"
                        )
                    ),

                "source_url":
                    EZMONEY_00981A_PAGE_URL,
            }
        )

    if not reference_date:
        raise RuntimeError(
            "00981A: reference date not found"
        )

    return deduplicate_rows(
        rows
    )


# ============================================================
# KGI 009816
# ============================================================

def fetch_kgi_009816():

    response = requests.get(
        KGI_009816_PAGE_URL,
        headers=HEADERS,
        timeout=30,
        verify=False,
    )

    response.raise_for_status()

    response.encoding = (
        response.apparent_encoding
        or "utf-8"
    )

    return response.text


def parse_kgi_009816(
    html_text: str,
):

    date_match = re.search(
        r'class=["\']fund-asset__date["\']'
        r'[^>]*>\s*\((\d{4}/\d{2}/\d{2})\)',
        html_text,
        flags=re.IGNORECASE,
    )

    if not date_match:
        raise RuntimeError(
            "009816: holdings date not found"
        )

    reference_date = normalize_date(
        date_match.group(1)
    )

    table_match = re.search(
        r'<table[^>]*'
        r'class=["\'][^"\']*js-table-a-0'
        r'[^"\']*["\'][^>]*>'
        r'(.*?)'
        r'</table>',
        html_text,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if not table_match:
        raise RuntimeError(
            "009816: holdings table not found"
        )

    table_html = (
        table_match.group(1)
    )

    tr_matches = re.findall(
        r'<tr[^>]*name=["\']content["\'][^>]*>'
        r'(.*?)'
        r'</tr>',
        table_html,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    rows = []

    for tr_html in tr_matches:

        cells = re.findall(
            r'<td[^>]*>(.*?)</td>',
            tr_html,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        if len(cells) < 4:
            continue

        stock_id = clean_html_text(
            cells[0]
        )

        stock_name = clean_html_text(
            cells[1]
        )

        shares = to_float(
            clean_html_text(
                cells[2]
            )
        )

        weight_pct = to_float(
            clean_html_text(
                cells[3]
            )
        )

        if not stock_id:
            continue

        rows.append(
            {
                "trade_date":
                    reference_date,

                "etf_id":
                    "009816",

                "stock_id":
                    stock_id,

                "stock_name":
                    stock_name,

                "shares":
                    shares,

                "weight_pct":
                    weight_pct,

                "market_value":
                    None,

                "source_url":
                    KGI_009816_PAGE_URL,
            }
        )

    return deduplicate_rows(
        rows
    )


# ============================================================
# Validation / Save
# ============================================================

def validate_rows(
    etf_id: str,
    rows: list[dict],
):

    if not rows:
        raise RuntimeError(
            f"{etf_id}: no holdings"
        )

    if len(rows) < 20:
        raise RuntimeError(
            f"{etf_id}: holdings only "
            f"{len(rows)} rows, "
            "refuse to save incomplete data"
        )

    dates = {
        row[
            "trade_date"
        ]
        for row in rows
    }

    if len(dates) != 1:
        raise RuntimeError(
            f"{etf_id}: "
            f"multiple reference dates "
            f"{sorted(dates)}"
        )


def save_rows(
    conn,
    etf_id: str,
    rows: list[dict],
):

    trade_date = (
        rows[0][
            "trade_date"
        ]
    )

    conn.execute(
        """
        DELETE FROM etf_holding_daily
        WHERE etf_id = ?
          AND trade_date = ?
        """,
        (
            etf_id,
            trade_date,
        ),
    )

    for row in rows:

        conn.execute(
            """
            INSERT INTO etf_holding_daily (
                trade_date,
                etf_id,
                stock_id,
                stock_name,
                shares,
                weight_pct,
                market_value,
                source_url,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(
                trade_date,
                etf_id,
                stock_id
            )
            DO UPDATE SET
                stock_name =
                    excluded.stock_name,
                shares =
                    excluded.shares,
                weight_pct =
                    excluded.weight_pct,
                market_value =
                    excluded.market_value,
                source_url =
                    excluded.source_url
            """,
            (
                row[
                    "trade_date"
                ],
                row[
                    "etf_id"
                ],
                row[
                    "stock_id"
                ],
                row[
                    "stock_name"
                ],
                row[
                    "shares"
                ],
                row[
                    "weight_pct"
                ],
                row[
                    "market_value"
                ],
                row[
                    "source_url"
                ],
            ),
        )


def print_sample(
    rows: list[dict],
):

    for row in rows[:5]:

        print(
            f"    "
            f"{row['stock_id']} "
            f"{row['stock_name']} "
            f"| qty={row['shares']} "
            f"| weight={row['weight_pct']} "
            f"| value={row['market_value']}"
        )


def sync_one(
    conn,
    etf_id: str,
    rows: list[dict],
):

    validate_rows(
        etf_id,
        rows,
    )

    print_sample(
        rows
    )

    save_rows(
        conn,
        etf_id,
        rows,
    )

    conn.commit()

    print(
        f"[PASS] "
        f"date={rows[0]['trade_date']} "
        f"stocks={len(rows)}"
    )

    return len(rows)


# ============================================================
# Main
# ============================================================

def main():

    configure_console()

    print("=" * 70)

    print(
        "StockWaveScanner V3 - "
        "ETF Holdings Sync V6"
    )

    print("=" * 70)

    conn = get_connection()

    try:

        total = 0

        #
        # 0050 / 0056
        #
        for etf_id in YUANTA_ETFS:

            print()
            print(
                f"[SYNC] {etf_id}"
            )

            data = fetch_yuanta_pcf(
                etf_id
            )

            rows = parse_yuanta_holdings(
                etf_id,
                data,
            )

            total += sync_one(
                conn,
                etf_id,
                rows,
            )

        #
        # 00878
        #
        print()
        print("[SYNC] 00878")

        rows = parse_cathay_00878(
            fetch_cathay_00878()
        )

        total += sync_one(
            conn,
            "00878",
            rows,
        )

        #
        # 00919
        #
        print()
        print("[SYNC] 00919")

        rows = parse_capital_00919(
            fetch_capital_00919()
        )

        total += sync_one(
            conn,
            "00919",
            rows,
        )

        #
        # 00929
        #
        print()
        print("[SYNC] 00929")

        rows = parse_fuhwa_00929(
            fetch_fuhwa_00929()
        )

        total += sync_one(
            conn,
            "00929",
            rows,
        )

        #
        # 00981A
        #
        print()
        print("[SYNC] 00981A")

        rows = parse_unipresident_00981a(
            fetch_unipresident_00981a()
        )

        total += sync_one(
            conn,
            "00981A",
            rows,
        )

        #
        # 009816
        #
        print()
        print("[SYNC] 009816")

        rows = parse_kgi_009816(
            fetch_kgi_009816()
        )

        total += sync_one(
            conn,
            "009816",
            rows,
        )

        print()
        print("=" * 70)

        print(
            f"TOTAL HOLDINGS = {total}"
        )

        print(
            "ETF HOLDINGS SYNC OK"
        )

        print("=" * 70)

        return 0

    except Exception as exc:

        try:
            conn.rollback()
        except Exception:
            pass

        print()
        print("=" * 70)
        print("ERROR")
        print("=" * 70)

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return 1

    finally:

        conn.close()


if __name__ == "__main__":
    sys.exit(main())