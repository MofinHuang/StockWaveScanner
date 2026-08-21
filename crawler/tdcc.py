import html
import json
import re
from datetime import datetime

import requests

from crawler.http_client import (
    tdcc_session_get,
    tdcc_session_post,
)
from db.database import get_connection
from db.repository import (
    start_crawl_log,
    finish_crawl_success,
    finish_crawl_error,
)


BASE_URL = (
    "https://openapi.tdcc.com.tw/"
    "v1/opendata/1-5"
)

HISTORY_URL = (
    "https://www.tdcc.com.tw/"
    "portal/zh/smWeb/qryStock"
)

SOURCE = "TDCC_SHAREHOLDING"

HISTORY_SOURCE = (
    "TDCC_SHAREHOLDING_HISTORY"
)


# =====================================
# TDCC 持股分級
# =====================================

TDCC_LEVEL_LABELS = {
    1: "1-999",
    2: "1,000-5,000",
    3: "5,001-10,000",
    4: "10,001-15,000",
    5: "15,001-20,000",
    6: "20,001-30,000",
    7: "30,001-40,000",
    8: "40,001-50,000",
    9: "50,001-100,000",
    10: "100,001-200,000",
    11: "200,001-400,000",
    12: "400,001-600,000",
    13: "600,001-800,000",
    14: "800,001-1,000,000",
    15: "1,000,001以上",
}


RETAIL_LEVELS = {
    1,
    2,
}


LARGE_HOLDER_LEVELS = {
    15,
}


# =====================================
# Raw Response
# =====================================

def save_raw_response(
    source: str,
    request_key: str,
    content: str,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO raw_responses
        (
            source,
            request_key,
            content,
            downloaded_at
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(source, request_key)
        DO UPDATE SET
            content = excluded.content,
            downloaded_at = excluded.downloaded_at
        """,
        (
            source,
            request_key,
            content,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


# =====================================
# OpenAPI Raw Parser
# =====================================

def get_tdcc_value(
    row: dict,
    field_name: str,
    default="",
):
    normalized = {
        str(key)
        .replace("\ufeff", "")
        .strip():
        value

        for key, value
        in row.items()
    }

    return normalized.get(
        field_name,
        default,
    )


def parse_tdcc_rows(
    raw_text: str,
    target_stock_ids=None,
):
    rows = json.loads(
        raw_text
    )

    if not isinstance(
        rows,
        list,
    ):
        raise ValueError(
            "TDCC Raw Response 不是 list"
        )

    if target_stock_ids is not None:

        target_stock_ids = {
            str(stock_id).strip()
            for stock_id
            in target_stock_ids
        }

    parsed = []

    for row in rows:

        if not isinstance(
            row,
            dict,
        ):
            continue

        stock_id = str(
            get_tdcc_value(
                row,
                "證券代號",
                "",
            )
        ).strip()

        if not stock_id:
            continue

        if (
            target_stock_ids is not None
            and stock_id
            not in target_stock_ids
        ):
            continue

        data_date = str(
            get_tdcc_value(
                row,
                "資料日期",
                "",
            )
        ).strip()

        normalized_date = (
            data_date
            .replace("/", "")
            .replace("-", "")
        )

        if (
            len(normalized_date) != 8
            or not normalized_date.isdigit()
        ):
            continue

        holding_level_text = str(
            get_tdcc_value(
                row,
                "持股分級",
                "",
            )
        ).strip()

        if not holding_level_text:
            continue

        holders_text = str(
            get_tdcc_value(
                row,
                "人數",
                "0",
            )
        ).replace(
            ",",
            "",
        ).strip()

        shares_text = str(
            get_tdcc_value(
                row,
                "股數",
                "0",
            )
        ).replace(
            ",",
            "",
        ).strip()

        percentage_text = str(
            get_tdcc_value(
                row,
                "占集保庫存數比例%",
                "0",
            )
        ).replace(
            ",",
            "",
        ).replace(
            "%",
            "",
        ).strip()

        try:

            holding_level = int(
                holding_level_text
            )

            holders = int(
                holders_text or 0
            )

            shares = int(
                shares_text or 0
            )

            percentage = float(
                percentage_text or 0
            )

        except ValueError as ex:

            raise ValueError(
                "TDCC 欄位格式異常："
                f"{row}"
            ) from ex

        parsed.append(
            {
                "stock_id":
                    stock_id,

                "data_date":
                    normalized_date,

                "holding_level":
                    holding_level,

                "holders":
                    holders,

                "shares":
                    shares,

                "percentage":
                    percentage,
            }
        )

    return parsed


# =====================================
# 策略摘要
# =====================================

def build_tdcc_holding_summary(
    parsed_rows: list[dict],
):
    if not parsed_rows:
        return []

    grouped = {}

    for row in parsed_rows:

        stock_id = row[
            "stock_id"
        ]

        data_date = row[
            "data_date"
        ]

        key = (
            stock_id,
            data_date,
        )

        if key not in grouped:

            grouped[key] = {
                "stock_id":
                    stock_id,

                "data_date":
                    data_date,

                "large_holder_pct":
                    0.0,

                "retail_holder_pct":
                    0.0,
            }

        level = row[
            "holding_level"
        ]

        percentage = row[
            "percentage"
        ]

        if level in LARGE_HOLDER_LEVELS:

            grouped[key][
                "large_holder_pct"
            ] += percentage

        if level in RETAIL_LEVELS:

            grouped[key][
                "retail_holder_pct"
            ] += percentage

    summaries = list(
        grouped.values()
    )

    summaries.sort(
        key=lambda row: (
            row["stock_id"],
            row["data_date"],
        )
    )

    return summaries


# =====================================
# 最新 OpenAPI
# =====================================

def download_latest_raw():
    request_key = (
        datetime.now()
        .strftime("%Y%m%d")
    )

    start_crawl_log(
        source=SOURCE,
        request_key=request_key,
    )

    print(
        "下載 TDCC 集保戶股權分散表..."
    )

    try:

        response = requests.get(
            BASE_URL,
            timeout=30,
            headers={
                "User-Agent":
                    "Mozilla/5.0 "
                    "StockWaveScanner/1.0"
            },
        )

        response.raise_for_status()

        raw_text = response.text

        save_raw_response(
            source=SOURCE,
            request_key=request_key,
            content=raw_text,
        )

        rows = json.loads(
            raw_text
        )

        if not isinstance(
            rows,
            list,
        ):
            raise ValueError(
                "TDCC API 回傳格式不是 list"
            )

        record_count = len(
            rows
        )

        finish_crawl_success(
            source=SOURCE,
            request_key=request_key,
            record_count=record_count,
        )

        print(
            "[OK] TDCC Raw Response 已保存，"
            f"共 {record_count:,} 筆分級資料"
        )

        return raw_text

    except Exception as ex:

        finish_crawl_error(
            source=SOURCE,
            request_key=request_key,
            error_message=str(ex),
        )

        raise


# =====================================
# 歷史頁工具
# =====================================

def _extract_hidden_value(
    html_text: str,
    name: str,
):
    input_match = re.search(
        (
            r'<input[^>]+'
            rf'name=["\']{re.escape(name)}["\']'
            r'[^>]*>'
        ),
        html_text,
        flags=re.IGNORECASE,
    )

    if input_match is None:
        return None

    value_match = re.search(
        r'value=["\']([^"\']*)["\']',
        input_match.group(0),
        flags=re.IGNORECASE,
    )

    if value_match is None:
        return None

    return value_match.group(1)


def get_history_dates():
    """
    讀取 TDCC 官方歷史頁可查詢日期。
    """

    session = requests.Session()

    response = tdcc_session_get(
        session=session,
        url=HISTORY_URL,
        timeout=30,
        headers={
            "User-Agent":
                "Mozilla/5.0 "
                "StockWaveScanner/1.0"
        },
    )

    response.raise_for_status()

    dates = re.findall(
        (
            r'<option[^>]+'
            r'value=["\']'
            r'(20\d{6})'
            r'["\']'
        ),
        response.text,
        flags=re.IGNORECASE,
    )

    dates = list(
        dict.fromkeys(
            dates
        )
    )

    dates.sort(
        reverse=True
    )

    return dates


def _clean_html_cell(
    value: str,
) -> str:
    value = re.sub(
        r"<[^>]+>",
        "",
        value,
    )

    value = html.unescape(
        value
    )

    value = (
        value
        .replace("\u3000", " ")
        .replace("\xa0", " ")
        .strip()
    )

    return value


def parse_history_html(
    html_text: str,
    stock_id: str,
    data_date: str,
):
    """
    解析 TDCC 歷史查詢頁。

    歷史頁目前：
        LV1～15 = 實際持股級距
        LV16 = 合計

    策略只使用：
        LV1 + LV2
        LV15
    """

    if "查無此資料" in html_text:
        return []

    table_rows = re.findall(
        r"<tr[^>]*>(.*?)</tr>",
        html_text,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    parsed = []

    for table_row in table_rows:

        cells = re.findall(
            r"<td[^>]*>(.*?)</td>",
            table_row,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        if len(cells) != 5:
            continue

        values = [
            _clean_html_cell(
                cell
            )
            for cell in cells
        ]

        if not values[0].isdigit():
            continue

        level = int(
            values[0]
        )

        try:

            holders = int(
                values[2]
                .replace(",", "")
            )

            shares = int(
                values[3]
                .replace(",", "")
            )

            percentage = float(
                values[4]
                .replace(",", "")
                .replace("%", "")
            )

        except ValueError:
            continue

        parsed.append(
            {
                "stock_id":
                    stock_id,

                "data_date":
                    data_date,

                "holding_level":
                    level,

                "holders":
                    holders,

                "shares":
                    shares,

                "percentage":
                    percentage,
            }
        )

    levels = {
        row["holding_level"]
        for row in parsed
    }

    required_levels = set(
        range(1, 16)
    )

    if not required_levels.issubset(
        levels
    ):
        raise ValueError(
            f"TDCC 歷史資料分級不完整："
            f"{stock_id} {data_date} "
            f"levels={sorted(levels)}"
        )

    return parsed


# =====================================
# 指定股票 / 指定歷史週
# =====================================

def download_history_stock_day(
    stock_id: str,
    data_date: str,
):
    """
    data_date:
        YYYYMMDD

    每次查詢先 GET：
        token + cookie

    再 POST：
        指定股票 + 指定日期
    """

    request_key = (
        f"{data_date}_{stock_id}"
    )

    start_crawl_log(
        source=HISTORY_SOURCE,
        request_key=request_key,
    )

    try:

        session = requests.Session()

        headers = {
            "User-Agent":
                "Mozilla/5.0 "
                "StockWaveScanner/1.0"
        }

        page = tdcc_session_get(
            session=session,
            url=HISTORY_URL,
            timeout=30,
            headers=headers,
        )

        page.raise_for_status()

        page_html = page.text

        token = _extract_hidden_value(
            page_html,
            "SYNCHRONIZER_TOKEN",
        )

        synchronizer_uri = (
            _extract_hidden_value(
                page_html,
                "SYNCHRONIZER_URI",
            )
        )

        fir_date = _extract_hidden_value(
            page_html,
            "firDate",
        )

        if not token:
            raise ValueError(
                "TDCC 找不到 "
                "SYNCHRONIZER_TOKEN"
            )

        form_data = {
            "SYNCHRONIZER_TOKEN":
                token,

            "SYNCHRONIZER_URI":
                synchronizer_uri
                or "/portal/zh/smWeb/qryStock",

            "method":
                "submit",

            "firDate":
                fir_date or data_date,

            "scaDate":
                data_date,

            "sqlMethod":
                "StockNo",

            "stockNo":
                stock_id,

            "stockName":
                "",
        }

        response = tdcc_session_post(
            session=session,
            url=HISTORY_URL,
            data=form_data,
            timeout=30,
            headers={
                **headers,
                "Referer":
                    HISTORY_URL,
            },
        )

        response.raise_for_status()

        raw_html = response.text

        save_raw_response(
            source=HISTORY_SOURCE,
            request_key=request_key,
            content=raw_html,
        )

        parsed = parse_history_html(
            html_text=raw_html,
            stock_id=stock_id,
            data_date=data_date,
        )

        finish_crawl_success(
            source=HISTORY_SOURCE,
            request_key=request_key,
            record_count=len(parsed),
        )

        if not parsed:

            print(
                f"[EMPTY] TDCC 歷史 "
                f"{stock_id} {data_date}"
            )

        return parsed

    except Exception as ex:

        finish_crawl_error(
            source=HISTORY_SOURCE,
            request_key=request_key,
            error_message=str(ex),
        )

        raise