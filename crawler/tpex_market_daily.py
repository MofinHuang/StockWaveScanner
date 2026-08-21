import json
from datetime import datetime

from crawler.http_client import (
    tpex_post,
)
from db.database import get_connection
from db.repository import (
    start_crawl_log,
    finish_crawl_success,
    finish_crawl_error,
)


BASE_URL = (
    "https://www.tpex.org.tw/"
    "www/zh-tw/afterTrading/dailyQuotes"
)

REFERER_URL = (
    "https://www.tpex.org.tw/"
    "zh-tw/mainboard/trading/info/pricing.html"
)

SOURCE = "TPEX_DAILY_QUOTES"


# =====================================
# Raw
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
# Number
# =====================================

def normalize_number(
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
        "-",
        "--",
        "---",
        "----",
    }:
        return None

    return text


# =====================================
# Parser
# =====================================

def parse_market_daily(
    raw_text: str,
    trade_date: str,
):
    """
    trade_date:
        YYYY-MM-DD

    只處理：
        Table title = 上櫃股票行情

    並只保留：
        4 碼純數字股票代號
    """

    payload = json.loads(
        raw_text
    )

    if payload.get(
        "stat"
    ) != "ok":

        return []

    tables = payload.get(
        "tables",
        []
    )

    target_table = None

    for table in tables:

        title = str(
            table.get(
                "title",
                "",
            )
        ).strip()

        if title == "上櫃股票行情":

            target_table = table
            break

    if target_table is None:

        raise ValueError(
            "TPEx 找不到上櫃股票行情表"
        )

    fields = target_table.get(
        "fields",
        []
    )

    required_fields = {
        "代號",
        "收盤",
        "開盤",
        "最高",
        "最低",
        "成交股數",
    }

    if not required_fields.issubset(
        set(fields)
    ):

        raise ValueError(
            "TPEx 上櫃股票行情欄位異常："
            f"{fields}"
        )

    parsed = []

    for values in target_table.get(
        "data",
        []
    ):

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
                "代號",
                "",
            )
        ).strip()

        # 排除 ETF / 權證 / 其他商品。
        if (
            len(stock_id) != 4
            or not stock_id.isdigit()
        ):
            continue

        open_text = normalize_number(
            row.get(
                "開盤"
            )
        )

        high_text = normalize_number(
            row.get(
                "最高"
            )
        )

        low_text = normalize_number(
            row.get(
                "最低"
            )
        )

        close_text = normalize_number(
            row.get(
                "收盤"
            )
        )

        volume_text = normalize_number(
            row.get(
                "成交股數"
            )
        )

        # 不捏造缺值。
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
                        "TPEx",

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

                    # 官方欄位就是成交股數，
                    # DB 同樣存 shares。
                    "volume":
                        int(
                            volume_text
                        ),
                }
            )

        except ValueError:

            continue

    return parsed


# =====================================
# DB
# =====================================

def upsert_daily_prices(
    rows: list[dict],
):
    if not rows:
        return 0

    conn = get_connection()
    cursor = conn.cursor()

    downloaded_at = (
        datetime.now()
        .isoformat()
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


# =====================================
# Download one market day
# =====================================

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

    request_date = (
        trade_date.strftime(
            "%Y/%m/%d"
        )
    )

    start_crawl_log(
        source=SOURCE,
        request_key=request_key,
    )

    try:

        response = tpex_post(
            BASE_URL,
            data={
                "date":
                    request_date,

                "response":
                    "json",
            },
            timeout=30,
            headers={
                "User-Agent":
                    "Mozilla/5.0 "
                    "StockWaveScanner/1.0",

                "Referer":
                    REFERER_URL,
            },
        )

        response.raise_for_status()

        raw_text = response.text

        save_raw_response(
            source=SOURCE,
            request_key=request_key,
            content=raw_text,
        )

        rows = parse_market_daily(
            raw_text=raw_text,
            trade_date=db_trade_date,
        )

        record_count = (
            upsert_daily_prices(
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