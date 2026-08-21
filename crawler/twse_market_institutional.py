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
    "rwd/zh/fund/T86"
)

SOURCE = "TWSE_T86_MARKET"


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


def normalize_integer(
    value,
):
    if value is None:
        return None

    text = (
        str(value)
        .replace(",", "")
        .replace("+", "")
        .strip()
    )

    if text in {
        "",
        "-",
        "--",
        "---",
    }:
        return None

    return int(text)


def find_field(
    fields: list[str],
    candidates: list[str],
):
    for candidate in candidates:

        if candidate in fields:
            return candidate

    raise ValueError(
        "TWSE T86 缺少必要欄位："
        f"{candidates}"
    )


def parse_market_institutional(
    raw_text: str,
    trade_date: str,
):
    payload = json.loads(
        raw_text
    )

    stat = str(
        payload.get(
            "stat",
            "",
        )
    ).strip()

    if stat.upper() != "OK":

        return []

    fields = payload.get(
        "fields",
        []
    )

    data = payload.get(
        "data",
        []
    )

    if not fields:
        return []

    stock_field = find_field(
        fields,
        [
            "證券代號",
        ],
    )

    foreign_buy_field = find_field(
        fields,
        [
            (
                "外陸資買進股數"
                "(不含外資自營商)"
            ),
            (
                "外資及陸資買進股數"
                "(不含外資自營商)"
            ),
        ],
    )

    foreign_sell_field = find_field(
        fields,
        [
            (
                "外陸資賣出股數"
                "(不含外資自營商)"
            ),
            (
                "外資及陸資賣出股數"
                "(不含外資自營商)"
            ),
        ],
    )

    foreign_net_field = find_field(
        fields,
        [
            (
                "外陸資買賣超股數"
                "(不含外資自營商)"
            ),
            (
                "外資及陸資買賣超股數"
                "(不含外資自營商)"
            ),
        ],
    )

    result = []

    for values in data:

        if len(values) != len(fields):
            continue

        row = dict(
            zip(
                fields,
                values,
            )
        )

        stock_id = str(
            row.get(
                stock_field,
                "",
            )
        ).strip()

        # StockWaveScanner 股票主檔目前
        # 使用 4 碼純數字普通股票。
        if (
            len(stock_id) != 4
            or not stock_id.isdigit()
        ):
            continue

        try:

            foreign_buy = normalize_integer(
                row.get(
                    foreign_buy_field
                )
            )

            foreign_sell = normalize_integer(
                row.get(
                    foreign_sell_field
                )
            )

            foreign_net = normalize_integer(
                row.get(
                    foreign_net_field
                )
            )

        except ValueError:
            continue

        if (
            foreign_buy is None
            or foreign_sell is None
            or foreign_net is None
        ):
            continue

        result.append(
            {
                "stock_id":
                    stock_id,

                "market":
                    "TWSE",

                "trade_date":
                    trade_date,

                "foreign_buy":
                    foreign_buy,

                "foreign_sell":
                    foreign_sell,

                "foreign_net":
                    foreign_net,
            }
        )

    return result


def upsert_institutional_trades(
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
        [
            (
                row["stock_id"],
                row["market"],
                row["trade_date"],
                row["foreign_buy"],
                row["foreign_sell"],
                row["foreign_net"],
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

    start_crawl_log(
        source=SOURCE,
        request_key=request_key,
    )

    try:

        response = requests.get(
            BASE_URL,
            params={
                "date":
                    request_key,

                "selectType":
                    "ALLBUT0999",

                "response":
                    "json",
            },
            timeout=30,
            headers={
                "User-Agent":
                    "Mozilla/5.0 "
                    "StockWaveScanner/1.0",

                "Referer":
                    (
                        "https://www.twse.com.tw/"
                        "zh/trading/foreign/"
                        "t86.html"
                    ),
            },
        )

        response.raise_for_status()

        raw_text = response.text

        save_raw_response(
            source=SOURCE,
            request_key=request_key,
            content=raw_text,
        )

        rows = parse_market_institutional(
            raw_text=raw_text,
            trade_date=db_trade_date,
        )

        record_count = (
            upsert_institutional_trades(
                rows
            )
        )

        finish_crawl_success(
            source=SOURCE,
            request_key=request_key,
            record_count=record_count,
        )

        return record_count

    except Exception as ex:

        finish_crawl_error(
            source=SOURCE,
            request_key=request_key,
            error_message=str(ex),
        )

        raise