import json
from datetime import datetime

import requests

from db.database import get_connection
from db.repository import (
    start_crawl_log,
    finish_crawl_success,
    finish_crawl_error,
)


BASE_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"

SOURCE = "TWSE_T86"


def parse_int(value: str) -> int:
    if value is None:
        return 0

    value = (
        str(value)
        .replace(",", "")
        .replace("+", "")
        .strip()
    )

    if value in ("", "--", "---"):
        return 0

    return int(value)


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


def get_saved_raw_response(
    source: str,
    request_key: str,
):
    """
    讀取已保存的官方 Raw Response。

    找不到時回傳 None。
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT content
        FROM raw_responses
        WHERE source = ?
          AND request_key = ?
        """,
        (
            source,
            request_key,
        ),
    )

    row = cursor.fetchone()

    conn.close()

    if row is None:
        return None

    return row["content"]


def upsert_institutional_trade(
    stock_id: str,
    trade_date: str,
    foreign_buy: int,
    foreign_sell: int,
    foreign_net: int,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO institutional_trades
        (
            stock_id,
            market,
            trade_date,

            foreign_buy,
            foreign_sell,
            foreign_net,

            source,
            downloaded_at
        )
        VALUES
        (
            ?, ?, ?, ?, ?, ?, ?, ?
        )

        ON CONFLICT(
            stock_id,
            market,
            trade_date
        )
        DO UPDATE SET

            foreign_buy =
                excluded.foreign_buy,

            foreign_sell =
                excluded.foreign_sell,

            foreign_net =
                excluded.foreign_net,

            source =
                excluded.source,

            downloaded_at =
                excluded.downloaded_at
        """,
        (
            stock_id,
            "TWSE",
            trade_date,

            foreign_buy,
            foreign_sell,
            foreign_net,

            SOURCE,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


def parse_and_store(
    raw_text: str,
    target_stock_ids=None,
):
    """
    解析 TWSE T86 Raw Response，
    將指定股票寫入 institutional_trades。

    target_stock_ids:
        ["2330", "2317", "2454", "6770"]

        None 表示全部存。
    """

    data = json.loads(
        raw_text
    )

    if data.get("stat") != "OK":
        return 0

    fields = data.get(
        "fields",
        [],
    )

    rows = data.get(
        "data",
        [],
    )

    if not fields:
        return 0

    if not rows:
        return 0

    # 不硬寫欄位位置，
    # 依官方欄位名稱找 index。

    stock_id_index = fields.index(
        "證券代號"
    )

    foreign_buy_index = fields.index(
        "外陸資買進股數(不含外資自營商)"
    )

    foreign_sell_index = fields.index(
        "外陸資賣出股數(不含外資自營商)"
    )

    foreign_net_index = fields.index(
        "外陸資買賣超股數(不含外資自營商)"
    )

    actual_date = data.get(
        "date",
        "",
    )

    if len(actual_date) != 8:
        raise ValueError(
            f"TWSE T86 日期格式異常：{actual_date}"
        )

    formatted_date = (
        f"{actual_date[0:4]}-"
        f"{actual_date[4:6]}-"
        f"{actual_date[6:8]}"
    )

    inserted = 0

    for row in rows:
        stock_id = (
            str(
                row[stock_id_index]
            )
            .strip()
        )

        if (
            target_stock_ids is not None
            and stock_id not in target_stock_ids
        ):
            continue

        foreign_buy = parse_int(
            row[foreign_buy_index]
        )

        foreign_sell = parse_int(
            row[foreign_sell_index]
        )

        foreign_net = parse_int(
            row[foreign_net_index]
        )

        upsert_institutional_trade(
            stock_id=stock_id,
            trade_date=formatted_date,
            foreign_buy=foreign_buy,
            foreign_sell=foreign_sell,
            foreign_net=foreign_net,
        )

        inserted += 1

    return inserted


def restore_day_from_raw(
    trade_date,
    target_stock_ids=None,
):
    """
    不發 Request。

    直接使用 raw_responses 已保存的
    TWSE T86 官方資料重新解析。

    用途：
    後來新增測試股票時，
    可以直接從既有 Raw 補入資料。
    """

    request_key = trade_date.strftime(
        "%Y%m%d"
    )

    raw_text = get_saved_raw_response(
        source=SOURCE,
        request_key=request_key,
    )

    if raw_text is None:
        return None

    inserted = parse_and_store(
        raw_text=raw_text,
        target_stock_ids=target_stock_ids,
    )

    return inserted


def download_day(
    trade_date,
    target_stock_ids=None,
):
    """
    trade_date:
        datetime.date

    target_stock_ids:
        ["2330", "2317", "2454", "6770"]

        None 表示全部存。
    """

    date_text = trade_date.strftime(
        "%Y%m%d"
    )

    request_key = date_text

    start_crawl_log(
        source=SOURCE,
        request_key=request_key,
    )

    params = {
        "date": date_text,
        "selectType": "ALL",
        "response": "json",
    }

    print(
        f"下載 TWSE 法人資料 {date_text} ..."
    )

    try:
        response = requests.get(
            BASE_URL,
            params=params,
            timeout=30,
            headers={
                "User-Agent":
                    "Mozilla/5.0 StockWaveScanner/1.0"
            },
        )

        response.raise_for_status()

        raw_text = response.text

        # 官方 Raw Response 必須先保存
        save_raw_response(
            source=SOURCE,
            request_key=request_key,
            content=raw_text,
        )

        inserted = parse_and_store(
            raw_text=raw_text,
            target_stock_ids=target_stock_ids,
        )

        finish_crawl_success(
            source=SOURCE,
            request_key=request_key,
            record_count=inserted,
        )

        if inserted == 0:
            print(
                f"[EMPTY] {date_text}"
            )
        else:
            print(
                f"[OK] {date_text} "
                f"寫入 {inserted} 筆"
            )

        return inserted

    except Exception as ex:
        finish_crawl_error(
            source=SOURCE,
            request_key=request_key,
            error_message=str(ex),
        )

        raise