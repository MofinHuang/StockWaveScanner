import json
from datetime import datetime

import requests

from db.database import get_connection
from db.repository import (
    start_crawl_log,
    finish_crawl_success,
    finish_crawl_error,
)


BASE_URL = (
    "https://www.twse.com.tw/"
    "rwd/zh/afterTrading/MI_INDEX"
)

SOURCE = "TWSE_MI_INDEX"


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


def _normalize_number(
    value,
):
    if value is None:
        return None

    text = (
        str(value)
        .replace(",", "")
        .strip()
    )

    if text in {
        "",
        "--",
        "---",
        "----",
        "除權",
        "除息",
    }:
        return None

    return text


def parse_market_daily(
    raw_text: str,
    trade_date: str,
):
    """
    trade_date:
        YYYY-MM-DD
    """

    payload = json.loads(
        raw_text
    )

    if payload.get("stat") != "OK":
        return []

    tables = payload.get(
        "tables",
        []
    )

    target_table = None

    for table in tables:

        fields = table.get(
            "fields",
            []
        )

        required = {
            "證券代號",
            "成交股數",
            "開盤價",
            "最高價",
            "最低價",
            "收盤價",
        }

        if required.issubset(
            set(fields)
        ):
            target_table = table
            break

    if target_table is None:
        raise ValueError(
            "TWSE MI_INDEX 找不到個股行情表"
        )

    fields = target_table[
        "fields"
    ]

    parsed = []

    for values in target_table.get(
        "data",
        []
    ):

        row = dict(
            zip(
                fields,
                values,
            )
        )

        stock_id = str(
            row.get(
                "證券代號",
                "",
            )
        ).strip()

        # 全市場主檔目前只收 4 碼股票。
        if (
            len(stock_id) != 4
            or not stock_id.isdigit()
        ):
            continue

        open_text = _normalize_number(
            row.get("開盤價")
        )

        high_text = _normalize_number(
            row.get("最高價")
        )

        low_text = _normalize_number(
            row.get("最低價")
        )

        close_text = _normalize_number(
            row.get("收盤價")
        )

        volume_text = _normalize_number(
            row.get("成交股數")
        )

        # 沒有完整 OHLC 時不自行補值。
        if any(
            value is None
            for value in [
                open_text,
                high_text,
                low_text,
                close_text,
                volume_text,
            ]
        ):
            continue

        try:

            parsed.append(
                {
                    "stock_id":
                        stock_id,

                    "market":
                        "TWSE",

                    "trade_date":
                        trade_date,

                    "open":
                        float(
                            open_text
                        ),

                    "high":
                        float(
                            high_text
                        ),

                    "low":
                        float(
                            low_text
                        ),

                    "close":
                        float(
                            close_text
                        ),

                    # TWSE 回傳成交股數，
                    # DB 也固定存 shares。
                    "volume":
                        int(
                            volume_text
                        ),
                }
            )

        except ValueError:
            continue

    return parsed


def upsert_daily_prices(
    rows: list[dict],
):
    if not rows:
        return 0

    conn = get_connection()
    cursor = conn.cursor()

    downloaded_at = (
        datetime.now().isoformat()
    )

    cursor.executemany(
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
        [
            (
                row["stock_id"],
                row["market"],
                row["trade_date"],
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
                SOURCE,
                downloaded_at,
            )
            for row in rows
        ],
    )

    conn.commit()
    conn.close()

    return len(rows)


def download_day(
    trade_date,
):
    """
    trade_date:
        datetime.date
    """

    request_key = (
        trade_date.strftime(
            "%Y%m%d"
        )
    )

    db_trade_date = (
        trade_date.strftime(
            "%Y-%m-%d"
        )
    )

    print(
        f"[DEBUG] {db_trade_date} "
        "step 1: start_crawl_log"
    )

    start_crawl_log(
        source=SOURCE,
        request_key=request_key,
    )

    print(
        f"[DEBUG] {db_trade_date} "
        "step 1 OK"
    )

    try:

        print(
            f"[DEBUG] {db_trade_date} "
            "step 2: HTTP GET"
        )

        response = requests.get(
            BASE_URL,
            params={
                "date":
                    request_key,

                "type":
                    "ALLBUT0999",

                "response":
                    "json",
            },
            timeout=30,
            headers={
                "User-Agent":
                    "Mozilla/5.0 "
                    "StockWaveScanner/1.0"
            },
        )

        response.raise_for_status()

        raw_text = response.text

        print(
            f"[DEBUG] {db_trade_date} "
            "step 2 OK"
        )

        # =================================
        # Raw
        # =================================

        print(
            f"[DEBUG] {db_trade_date} "
            "step 3: save_raw_response"
        )

        save_raw_response(
            source=SOURCE,
            request_key=request_key,
            content=raw_text,
        )

        print(
            f"[DEBUG] {db_trade_date} "
            "step 3 OK"
        )

        # =================================
        # Parse
        # =================================

        print(
            f"[DEBUG] {db_trade_date} "
            "step 4: parse_market_daily"
        )

        rows = parse_market_daily(
            raw_text=raw_text,
            trade_date=db_trade_date,
        )

        print(
            f"[DEBUG] {db_trade_date} "
            f"step 4 OK rows={len(rows):,}"
        )

        # =================================
        # daily_prices
        # =================================

        print(
            f"[DEBUG] {db_trade_date} "
            "step 5: upsert_daily_prices"
        )

        record_count = (
            upsert_daily_prices(
                rows
            )
        )

        print(
            f"[DEBUG] {db_trade_date} "
            f"step 5 OK rows={record_count:,}"
        )

        # =================================
        # crawl log SUCCESS
        # =================================

        print(
            f"[DEBUG] {db_trade_date} "
            "step 6: finish_crawl_success"
        )

        finish_crawl_success(
            source=SOURCE,
            request_key=request_key,
            record_count=record_count,
        )

        print(
            f"[DEBUG] {db_trade_date} "
            "step 6 OK"
        )

        return record_count

    except Exception as ex:

        print(
            f"[DEBUG] {db_trade_date} "
            f"exception: {type(ex).__name__}: {ex}"
        )

        try:

            print(
                f"[DEBUG] {db_trade_date} "
                "step ERROR: finish_crawl_error"
            )

            finish_crawl_error(
                source=SOURCE,
                request_key=request_key,
                error_message=str(ex),
            )

            print(
                f"[DEBUG] {db_trade_date} "
                "step ERROR OK"
            )

        except Exception as log_ex:

            print(
                f"[DEBUG] {db_trade_date} "
                "finish_crawl_error 也失敗："
                f"{type(log_ex).__name__}: {log_ex}"
            )

        raise