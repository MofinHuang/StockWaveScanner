import json
import time
from datetime import datetime
from pathlib import Path

import requests

from db.database import get_connection

from db.repository import (
    start_crawl_log,
    finish_crawl_success,
    finish_crawl_error,
)

BASE_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

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


def parse_roc_date(value: str) -> str:
    """
    115/08/14
    ->
    2026-08-14
    """

    year, month, day = value.split("/")

    western_year = int(year) + 1911

    return (
        f"{western_year:04d}-"
        f"{int(month):02d}-"
        f"{int(day):02d}"
    )


def parse_int(value: str) -> int:
    value = (
        value
        .replace(",", "")
        .replace("+", "")
        .strip()
    )

    if value in ("", "--", "---"):
        return 0

    return int(value)


def parse_float(value: str) -> float:
    value = (
        value
        .replace(",", "")
        .replace("+", "")
        .strip()
    )

    if value in ("", "--", "---"):
        return 0.0

    return float(value)


def upsert_daily_price(
    stock_id: str,
    trade_date: str,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    volume: int,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO daily_prices
        (
            stock_id,
            market,
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            source,
            downloaded_at
        )
        VALUES
        (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )

        ON CONFLICT(
            stock_id,
            market,
            trade_date
        )
        DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume,
            source = excluded.source,
            downloaded_at = excluded.downloaded_at
        """,
        (
            stock_id,
            "TWSE",
            trade_date,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
            "TWSE_STOCK_DAY",
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()

def download_month(
    stock_id: str,
    year: int,
    month: int,
):
    source = "TWSE_STOCK_DAY"

    request_key = (
        f"{stock_id}_{year}{month:02d}"
    )

    date_value = (
        f"{year}{month:02d}01"
    )

    params = {
        "response": "json",
        "date": date_value,
        "stockNo": stock_id,
    }

    print(
        f"下載 {stock_id} "
        f"{year}-{month:02d} ..."
    )

    start_crawl_log(
        source=source,
        request_key=request_key,
    )

    try:

#         response = requests.get(
#             BASE_URL,
#             params=params,
#             timeout=30,
#             headers={
#                 "User-Agent":
#                     "Mozilla/5.0 StockWaveScanner/1.0"
#             },
#         )

#         response.raise_for_status()

        retry_waits = [5, 15, 30]

        for attempt in range(
            len(retry_waits) + 1
        ):
            response = requests.get(
                BASE_URL,
                params=params,
                timeout=30,
                headers=HEADERS,
            )

            if response.status_code != 428:
                break

            if attempt >= len(retry_waits):
                break

            wait_seconds = retry_waits[
                attempt
            ]

            print(
                f"[428 RETRY] "
                f"{stock_id} "
                f"{year}-{month:02d} "
                f"等待 {wait_seconds} 秒後重試"
            )

            time.sleep(
                wait_seconds
            )

        response.raise_for_status()

        raw_text = response.text

        save_raw_response(
            source=source,
            request_key=request_key,
            content=raw_text,
        )

        data = json.loads(
            raw_text
        )

        if data.get("stat") != "OK":

            finish_crawl_success(
                source=source,
                request_key=request_key,
                record_count=0,
            )

            print(
                f"[EMPTY] "
                f"{stock_id} "
                f"{year}-{month:02d}"
            )

            return 0

        rows = data.get(
            "data",
            [],
        )

        inserted = 0

        for row in rows:

            try:

                trade_date = (
                    parse_roc_date(
                        row[0]
                    )
                )

                volume = (
                    parse_int(
                        row[1]
                    )
                )

                open_price = (
                    parse_float(
                        row[3]
                    )
                )

                high_price = (
                    parse_float(
                        row[4]
                    )
                )

                low_price = (
                    parse_float(
                        row[5]
                    )
                )

                close_price = (
                    parse_float(
                        row[6]
                    )
                )

                if (
                    open_price <= 0
                    or high_price <= 0
                    or low_price <= 0
                    or close_price <= 0
                ):
                    continue

                upsert_daily_price(
                    stock_id=stock_id,
                    trade_date=trade_date,
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=close_price,
                    volume=volume,
                )

                inserted += 1

            except Exception as ex:

                print(
                    f"[ROW ERROR] "
                    f"{stock_id}: {ex}"
                )

        finish_crawl_success(
            source=source,
            request_key=request_key,
            record_count=inserted,
        )

        print(
            f"[OK] "
            f"{stock_id} "
            f"{year}-{month:02d} "
            f"{inserted} 筆"
        )

        return inserted

    except Exception as ex:

        finish_crawl_error(
            source=source,
            request_key=request_key,
            error_message=str(ex),
        )

        raise