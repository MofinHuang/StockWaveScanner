import json
from datetime import datetime

from crawler.http_client import tpex_get
from db.database import get_connection
from db.repository import (
    start_crawl_log,
    finish_crawl_success,
    finish_crawl_error,
)


BASE_URL = (
    "https://www.tpex.org.tw/openapi/v1/"
    "tpex_3insti_daily_trading"
)

HISTORY_URL = (
    "https://www.tpex.org.tw/web/stock/3insti/"
    "daily_trade/3itrade_hedge_result.php"
)


def parse_int(value) -> int:

    if value is None:
        return 0

    text = (
        str(value)
        .replace(",", "")
        .replace("+", "")
        .strip()
    )

    if text in ("", "--", "---", "None"):
        return 0

    try:
        return int(float(text))
    except ValueError:
        return 0


def parse_roc_date(value: str) -> str:
    """
    1150814 -> 2026-08-14
    """

    value = str(value).strip()

    if len(value) != 7:
        raise ValueError(
            f"無法解析 TPEx 日期：{value}"
        )

    roc_year = int(value[:3])
    year = roc_year + 1911

    month = int(value[3:5])
    day = int(value[5:7])

    return (
        f"{year:04d}-"
        f"{month:02d}-"
        f"{day:02d}"
    )


def format_roc_query_date(
    trade_date,
) -> str:
    """
    2026-08-14 -> 115/08/14
    """

    roc_year = (
        trade_date.year
        - 1911
    )

    return (
        f"{roc_year:03d}/"
        f"{trade_date.month:02d}/"
        f"{trade_date.day:02d}"
    )


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


def upsert_institutional_trade(
    stock_id: str,
    trade_date: str,
    foreign_buy: int,
    foreign_sell: int,
    foreign_net: int,
    source: str = "TPEX_3INSTI_DAILY",
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
            "TPEx",
            trade_date,
            foreign_buy,
            foreign_sell,
            foreign_net,
            source,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


def normalize_key(value: str) -> str:

    return (
        value
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
        .lower()
    )


def find_value(
    row: dict,
    candidates: list[str],
):

    normalized = {
        normalize_key(key): value
        for key, value in row.items()
    }

    for candidate in candidates:

        key = normalize_key(
            candidate
        )

        if key in normalized:
            return normalized[key]

    return None


def download_today(
    target_stock_ids=None,
):

    source = "TPEX_3INSTI_DAILY"

    request_key = (
        datetime.now()
        .strftime("%Y%m%d")
    )

    start_crawl_log(
        source=source,
        request_key=request_key,
    )

    print(
        "下載 TPEx 今日三大法人資料..."
    )

    try:

        response = tpex_get(
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
            source=source,
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
                "TPEx 法人 API "
                "回傳格式不是 List"
            )

        if len(rows) == 0:

            finish_crawl_success(
                source=source,
                request_key=request_key,
                record_count=0,
            )

            print(
                "[EMPTY] TPEx 今日法人資料為空"
            )

            return 0

        print()
        print(
            "TPEx API 欄位："
        )

        for key in rows[0].keys():
            print(
                f"  - {key}"
            )

        print()

        inserted = 0

        for row in rows:

            stock_id = find_value(
                row,
                [
                    "SecuritiesCompanyCode",
                    "SecuritiesCode",
                    "Code",
                ],
            )

            if stock_id is None:
                continue

            stock_id = str(
                stock_id
            ).strip()

            if (
                target_stock_ids is not None
                and stock_id not in target_stock_ids
            ):
                continue

            raw_date = find_value(
                row,
                [
                    "Date",
                    "TradeDate",
                ],
            )

            if raw_date is None:
                continue

            trade_date = parse_roc_date(
                str(raw_date)
            )

            foreign_buy = parse_int(
                find_value(
                    row,
                    [
                        (
                            "ForeignInvestorsInclude"
                            "MainlandAreaInvestors"
                            "-TotalBuy"
                        ),
                        (
                            "ForeignInvestors"
                            "IncludeMainlandAreaInvestors"
                            "TotalBuy"
                        ),
                    ],
                )
            )

            foreign_sell = parse_int(
                find_value(
                    row,
                    [
                        (
                            "ForeignInvestorsInclude"
                            "MainlandAreaInvestors"
                            "-TotalSell"
                        ),
                        (
                            "ForeignInvestors"
                            "IncludeMainlandAreaInvestors"
                            "TotalSell"
                        ),
                    ],
                )
            )

            foreign_net_value = find_value(
                row,
                [
                    (
                        "ForeignInvestorsInclude"
                        "MainlandAreaInvestors"
                        "-Difference"
                    ),
                    (
                        "ForeignInvestors"
                        "IncludeMainlandAreaInvestors"
                        "Difference"
                    ),
                ],
            )

            foreign_net = parse_int(
                foreign_net_value
            )

            if foreign_net_value is None:
                foreign_net = (
                    foreign_buy
                    - foreign_sell
                )

            upsert_institutional_trade(
                stock_id=stock_id,
                trade_date=trade_date,
                foreign_buy=foreign_buy,
                foreign_sell=foreign_sell,
                foreign_net=foreign_net,
                source=source,
            )

            inserted += 1

        finish_crawl_success(
            source=source,
            request_key=request_key,
            record_count=inserted,
        )

        print(
            f"[OK] TPEx 法人資料 "
            f"寫入 {inserted} 筆"
        )

        return inserted

    except Exception as ex:

        finish_crawl_error(
            source=source,
            request_key=request_key,
            error_message=str(ex),
        )

        raise


def download_day(
    trade_date,
    target_stock_ids=None,
):
    """
    下載指定日期 TPEx 三大法人歷史資料。

    trade_date:
        datetime.date

    target_stock_ids:
        ["6488"]
        None 表示全部存
    """

    source = "TPEX_3INSTI_HISTORY"

    request_key = (
        trade_date.strftime(
            "%Y%m%d"
        )
    )

    roc_date = format_roc_query_date(
        trade_date
    )

    start_crawl_log(
        source=source,
        request_key=request_key,
    )

    params = {
        "l": "zh-tw",
        "o": "json",
        "se": "EW",
        "t": "D",
        "d": roc_date,
        "s": "0,asc",
    }

    print(
        f"下載 TPEx 法人歷史資料 "
        f"{trade_date} ..."
    )

    try:

        response = tpex_get(
            HISTORY_URL,
            params=params,
            timeout=30,
            headers={
                "User-Agent":
                    "Mozilla/5.0 "
                    "StockWaveScanner/1.0"
            },
        )

        response.raise_for_status()

        raw_text = response.text

        # 先保存官方 Raw Response
        save_raw_response(
            source=source,
            request_key=request_key,
            content=raw_text,
        )

        data = json.loads(
            raw_text
        )

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "TPEx 歷史法人資料"
                "最外層不是 dict"
            )

        # TPEx 歷史 JSON 實際結構：
        #
        # {
        #     "columnNum": 25,
        #     "tables": [
        #         {
        #             "title": "...",
        #             "date": "115/08/14",
        #             "fields": [...],
        #             "data": [...]
        #         }
        #     ]
        # }

        tables = data.get(
            "tables",
            [],
        )

        if not tables:

            finish_crawl_success(
                source=source,
                request_key=request_key,
                record_count=0,
            )

            print(
                f"[EMPTY] {trade_date} "
                "沒有 tables"
            )

            return 0

        table = tables[0]

        if not isinstance(
            table,
            dict,
        ):
            raise ValueError(
                "TPEx 歷史法人資料 "
                "tables[0] 不是 dict"
            )

        raw_table_date = str(
            table.get(
                "date",
                "",
            )
        ).strip()

        # 防止官方端點忽略指定日期，
        # 回傳其他日期資料。
        if (
            raw_table_date
            and raw_table_date != roc_date
        ):
            raise ValueError(
                "TPEx 回傳日期與要求日期不同："
                f"要求 {roc_date}，"
                f"實際 {raw_table_date}"
            )

        rows = table.get(
            "data",
            [],
        )

        if not isinstance(
            rows,
            list,
        ):
            raise ValueError(
                "TPEx 歷史法人資料 "
                "data 不是 list"
            )

        if len(rows) == 0:

            finish_crawl_success(
                source=source,
                request_key=request_key,
                record_count=0,
            )

            print(
                f"[EMPTY] {trade_date}"
            )

            return 0

        formatted_date = (
            trade_date.strftime(
                "%Y-%m-%d"
            )
        )

        inserted = 0

        for row in rows:

            # TPEx 官方資料目前每列共 25 欄。
            #
            # row[0]
            #   股票代號
            #
            # row[1]
            #   股票名稱
            #
            # row[2:5]
            #   外資及陸資
            #   （不含外資自營商）
            #   買進 / 賣出 / 買賣超
            #
            # 後續欄位是：
            #   外資自營商
            #   外資及陸資
            #   投信
            #   自營商自行買賣
            #   自營商避險
            #   自營商
            #   三大法人合計

            if (
                not isinstance(row, list)
                or len(row) < 5
            ):
                continue

            stock_id = str(
                row[0]
            ).strip()

            if (
                target_stock_ids
                is not None
                and stock_id
                not in target_stock_ids
            ):
                continue

            foreign_buy = parse_int(
                row[2]
            )

            foreign_sell = parse_int(
                row[3]
            )

            foreign_net = parse_int(
                row[4]
            )

            upsert_institutional_trade(
                stock_id=stock_id,
                trade_date=formatted_date,
                foreign_buy=foreign_buy,
                foreign_sell=foreign_sell,
                foreign_net=foreign_net,
                source=source,
            )

            inserted += 1

        finish_crawl_success(
            source=source,
            request_key=request_key,
            record_count=inserted,
        )

        print(
            f"[OK] {formatted_date} "
            f"寫入 {inserted} 筆"
        )

        return inserted

    except Exception as ex:

        finish_crawl_error(
            source=source,
            request_key=request_key,
            error_message=str(ex),
        )

        raise