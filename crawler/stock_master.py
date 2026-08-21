import json
from datetime import datetime

import requests

from crawler.http_client import (
    tpex_get,
)
from db.database import get_connection


TWSE_URL = (
    "https://openapi.twse.com.tw/"
    "v1/opendata/t187ap03_L"
)

TPEX_URL = (
    "https://www.tpex.org.tw/"
    "openapi/v1/mopsfin_t187ap03_O"
)

TWSE_SOURCE = "TWSE_STOCK_MASTER"
TPEX_SOURCE = "TPEX_STOCK_MASTER"


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
# 共用工具
# =====================================

def normalize_row_keys(
    row: dict,
):
    """
    正規化官方 JSON 欄位名稱。

    處理：
    - UTF-8 BOM
    - 前後空白
    """

    return {
        str(key)
        .replace("\ufeff", "")
        .strip():
        value

        for key, value
        in row.items()
    }


def is_valid_stock_id(
    stock_id: str,
):
    """
    現階段股票主檔只保留：

    - 4 碼
    - 純數字

    排除 ETF、權證等其他證券商品。
    """

    return (
        len(stock_id) == 4
        and stock_id.isdigit()
    )


# =====================================
# TWSE Parser
# =====================================

def parse_twse_company_rows(
    raw_text: str,
):
    rows = json.loads(
        raw_text
    )

    if not isinstance(
        rows,
        list,
    ):
        raise ValueError(
            "TWSE 股票主檔不是 list"
        )

    parsed = []

    for raw_row in rows:

        if not isinstance(
            raw_row,
            dict,
        ):
            continue

        row = normalize_row_keys(
            raw_row
        )

        stock_id = str(
            row.get(
                "公司代號",
                "",
            )
        ).strip()

        stock_name = str(
            row.get(
                "公司簡稱",
                "",
            )
        ).strip()

        if not is_valid_stock_id(
            stock_id
        ):
            continue

        if not stock_name:
            continue

        parsed.append(
            {
                "stock_id":
                    stock_id,

                "market":
                    "TWSE",

                "stock_name":
                    stock_name,

                "is_active":
                    1,
            }
        )

    parsed.sort(
        key=lambda row: (
            row["stock_id"]
        )
    )

    return parsed


# =====================================
# TPEx Parser
# =====================================

def parse_tpex_company_rows(
    raw_text: str,
):
    """
    TPEx 官方 OpenAPI 實際欄位：

    SecuritiesCompanyCode
        股票代號

    CompanyAbbreviation
        公司簡稱
    """

    rows = json.loads(
        raw_text
    )

    if not isinstance(
        rows,
        list,
    ):
        raise ValueError(
            "TPEx 股票主檔不是 list"
        )

    parsed = []

    for raw_row in rows:

        if not isinstance(
            raw_row,
            dict,
        ):
            continue

        row = normalize_row_keys(
            raw_row
        )

        stock_id = str(
            row.get(
                "SecuritiesCompanyCode",
                "",
            )
        ).strip()

        stock_name = str(
            row.get(
                "CompanyAbbreviation",
                "",
            )
        ).strip()

        if not is_valid_stock_id(
            stock_id
        ):
            continue

        if not stock_name:
            continue

        parsed.append(
            {
                "stock_id":
                    stock_id,

                "market":
                    "TPEx",

                "stock_name":
                    stock_name,

                "is_active":
                    1,
            }
        )

    parsed.sort(
        key=lambda row: (
            row["stock_id"]
        )
    )

    return parsed


# =====================================
# TWSE
# =====================================

def download_twse_stock_master():

    print(
        "下載 TWSE 上市公司基本資料..."
    )

    response = requests.get(
        TWSE_URL,
        timeout=30,
        headers={
            "User-Agent":
                "Mozilla/5.0 "
                "StockWaveScanner/1.0"
        },
    )

    response.raise_for_status()

    raw_text = response.text

    request_key = (
        datetime.now()
        .strftime("%Y%m%d")
    )

    save_raw_response(
        source=TWSE_SOURCE,
        request_key=request_key,
        content=raw_text,
    )

    rows = parse_twse_company_rows(
        raw_text
    )

    print(
        f"[OK] TWSE 股票主檔："
        f"{len(rows):,} 檔"
    )

    return rows


# =====================================
# TPEx
# =====================================

def download_tpex_stock_master():

    print(
        "下載 TPEx 上櫃公司基本資料..."
    )

    response = tpex_get(
        TPEX_URL,
        timeout=30,
        headers={
            "User-Agent":
                "Mozilla/5.0 "
                "StockWaveScanner/1.0"
        },
    )

    response.raise_for_status()

    raw_text = response.text

    request_key = (
        datetime.now()
        .strftime("%Y%m%d")
    )

    save_raw_response(
        source=TPEX_SOURCE,
        request_key=request_key,
        content=raw_text,
    )

    rows = parse_tpex_company_rows(
        raw_text
    )

    print(
        f"[OK] TPEx 股票主檔："
        f"{len(rows):,} 檔"
    )

    return rows