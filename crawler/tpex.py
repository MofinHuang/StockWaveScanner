import json
from datetime import datetime

import requests

from db.database import get_connection

from db.repository import (
    start_crawl_log,
    finish_crawl_success,
    finish_crawl_error,
)

BASE_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"


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

    return int(float(value))


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
            "TPEx",
            trade_date,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
            "TPEX_TRADING_STOCK",
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
    source = "TPEX_TRADING_STOCK"

    request_key = (
        f"{stock_id}_{year}{month:02d}"
    )

    params = {
        "date": f"{year}/{month:02d}/01",
        "code": stock_id,
        "response": "json",
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
        
        response = requests.get(
            BASE_URL,
            params=params,
            timeout=30,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "StockWaveScanner/1.0"
                )
            },
        )

        response.raise_for_status()

        raw_text = response.text

        save_raw_response(
            source=source,
            request_key=request_key,
            content=raw_text,
        )

        data = json.loads(raw_text)

        if data.get("stat", "").lower() != "ok":
            print(
                f"[SKIP] {stock_id} "
                f"{year}-{month:02d} "
                f"stat={data.get('stat')}"
            )
            return 0

        tables = data.get("tables", [])

        if not tables:
            print(
                f"[SKIP] {stock_id} "
                f"{year}-{month:02d} "
                "沒有 tables"
            )
            return 0

        rows = tables[0].get(
            "data",
            [],
        )

        inserted = 0

        for row in rows:

            try:
                # TPEx tradingStock:
                #
                # 0 日期
                # 1 成交張數
                # 2 成交仟元
                # 3 開盤
                # 4 最高
                # 5 最低
                # 6 收盤
                # 7 漲跌
                # 8 筆數

                trade_date = parse_roc_date(
                    row[0]
                )

                # TPEx 是「成交張數」
                # 我們 DB 的 volume 統一存「股」
                volume_lots = parse_int(
                    row[1]
                )

                volume = (
                    volume_lots * 1000
                )

                open_price = parse_float(
                    row[3]
                )

                high_price = parse_float(
                    row[4]
                )

                low_price = parse_float(
                    row[5]
                )

                close_price = parse_float(
                    row[6]
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
            f"[OK] {stock_id} "
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