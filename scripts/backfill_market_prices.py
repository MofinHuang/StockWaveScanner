from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from crawler.twse import download_month as download_twse_month
from crawler.tpex import download_month as download_tpex_month

from db.database import get_connection

from db.repository import (
    crawl_success_exists,
    get_crawl_log,
)


TWSE_SOURCE = "TWSE_STOCK_DAY"
TPEX_SOURCE = "TPEX_TRADING_STOCK"


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "StockWaveScanner "
            "TWSE + TPEx historical price backfill"
        )
    )

    parser.add_argument(
        "--start",
        required=True,
        help=(
            "開始月份，格式 YYYY-MM，"
            "例如 2025-07"
        ),
    )

    parser.add_argument(
        "--end",
        required=True,
        help=(
            "結束月份，格式 YYYY-MM，"
            "例如 2026-06"
        ),
    )

    parser.add_argument(
        "--market",
        choices=[
            "ALL",
            "TWSE",
            "TPEx",
        ],
        default="ALL",
        help=(
            "市場。預設 ALL"
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "只測試前 N 檔股票。"
            "正式執行不指定。"
        ),
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=0.15,
        help=(
            "每個 request 間隔秒數。"
            "預設 0.15"
        ),
    )

    return parser.parse_args()


def parse_month(
    value: str,
) -> tuple[int, int]:

    parts = value.strip().split("-")

    if len(parts) != 2:
        raise ValueError(
            "月份格式必須是 YYYY-MM"
        )

    year = int(parts[0])
    month = int(parts[1])

    if month < 1 or month > 12:
        raise ValueError(
            "月份必須介於 01 到 12"
        )

    return year, month


def month_key(
    year: int,
    month: int,
) -> int:

    return (
        year * 12
        + month
    )


def build_months(
    start_value: str,
    end_value: str,
) -> list[tuple[int, int]]:

    start_year, start_month = (
        parse_month(
            start_value
        )
    )

    end_year, end_month = (
        parse_month(
            end_value
        )
    )

    if (
        month_key(
            start_year,
            start_month,
        )
        >
        month_key(
            end_year,
            end_month,
        )
    ):
        raise ValueError(
            "--start 不可晚於 --end"
        )

    result = []

    year = start_year
    month = start_month

    while True:

        result.append(
            (
                year,
                month,
            )
        )

        if (
            year == end_year
            and month == end_month
        ):
            break

        month += 1

        if month == 13:
            month = 1
            year += 1

    return result


def load_active_stocks(
    market: str,
):
    conn = get_connection()

    try:

        sql = """
            SELECT
                stock_id,
                stock_name,
                market

            FROM stocks

            WHERE
                is_active = 1
        """

        params = []

        if market != "ALL":

            sql += """
                AND market = ?
            """

            params.append(
                market
            )

        sql += """
            ORDER BY
                market,
                stock_id
        """

        rows = conn.execute(
            sql,
            params,
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        conn.close()


def get_source(
    market: str,
) -> str:

    if market == "TWSE":
        return TWSE_SOURCE

    if market == "TPEx":
        return TPEX_SOURCE

    raise ValueError(
        f"未知 market: {market}"
    )


def build_request_key(
    stock_id: str,
    year: int,
    month: int,
) -> str:

    return (
        f"{stock_id}_"
        f"{year}{month:02d}"
    )


def run_download(
    market: str,
    stock_id: str,
    year: int,
    month: int,
) -> int:

    if market == "TWSE":

        return int(
            download_twse_month(
                stock_id=stock_id,
                year=year,
                month=month,
            )
            or 0
        )

    if market == "TPEx":

        return int(
            download_tpex_month(
                stock_id=stock_id,
                year=year,
                month=month,
            )
            or 0
        )

    raise ValueError(
        f"未知 market: {market}"
    )


def main():
    args = parse_args()

    months = build_months(
        args.start,
        args.end,
    )

    stocks = load_active_stocks(
        args.market
    )

    if args.limit is not None:

        stocks = stocks[
            :max(
                0,
                int(args.limit),
            )
        ]

    total_units = (
        len(stocks)
        * len(months)
    )

    success_count = 0
    skip_count = 0
    no_data_count = 0
    error_count = 0

    print(
        "=" * 72
    )

    print(
        "StockWaveScanner "
        "Historical Price Backfill"
    )

    print(
        "=" * 72
    )

    print(
        "Market   :",
        args.market,
    )

    print(
        "Stocks   :",
        len(stocks),
    )

    print(
        "Months   :",
        len(months),
    )

    print(
        "Period   :",
        f"{args.start} ~ {args.end}",
    )

    print(
        "Units    :",
        total_units,
    )

    print()

    unit_index = 0

    try:

        for stock in stocks:

            stock_id = str(
                stock["stock_id"]
            )

            stock_name = str(
                stock["stock_name"]
                or ""
            )

            market = str(
                stock["market"]
            )

            source = get_source(
                market
            )

            for year, month in months:

                unit_index += 1

                request_key = (
                    build_request_key(
                        stock_id,
                        year,
                        month,
                    )
                )

                prefix = (
                    f"[{unit_index}/"
                    f"{total_units}] "
                    f"{market} "
                    f"{stock_id} "
                    f"{stock_name} "
                    f"{year}-{month:02d}"
                )

                #
                # 只以 crawl log SUCCESS
                # 判定該股票月份已完成。
                #
                # 不使用 has_price_month()，
                # 因為只要有 1 筆資料
                # 它就會回傳 True，
                # 不適合 historical backfill。
                #
                if crawl_success_exists(
                    source=source,
                    request_key=request_key,
                ):

                    skip_count += 1

                    print(
                        f"{prefix} "
                        "[SKIP SUCCESS]"
                    )

                    continue

                try:

                    inserted = (
                        run_download(
                            market=market,
                            stock_id=stock_id,
                            year=year,
                            month=month,
                        )
                    )

                    log = get_crawl_log(
                        source=source,
                        request_key=request_key,
                    )

                    status = (
                        log.get("status")
                        if log
                        else None
                    )

                    if (
                        status == "SUCCESS"
                        and inserted > 0
                    ):

                        success_count += 1

                    elif (
                        status == "SUCCESS"
                        and inserted == 0
                    ):

                        no_data_count += 1

                        print(
                            f"{prefix} "
                            "[NO_DATA]"
                        )

                    else:

                        #
                        # 某些舊 crawler 在
                        # EMPTY / 非 OK 回應時
                        # 可能留下 RUNNING。
                        #
                        # 不擅自標成 SUCCESS，
                        # 讓下次仍可安全 retry。
                        #
                        no_data_count += 1

                        print(
                            f"{prefix} "
                            "[NO_DATA/RETRYABLE] "
                            f"log_status={status}"
                        )

                except Exception as exc:

                    error_count += 1

                    print(
                        f"{prefix} "
                        f"[ERROR] {exc}"
                    )

                if args.sleep > 0:

                    time.sleep(
                        args.sleep
                    )

    except KeyboardInterrupt:

        print()
        print(
            "[STOP] 使用者中斷。"
        )

    finally:

        print()
        print(
            "=" * 72
        )

        print(
            "BACKFILL SUMMARY"
        )

        print(
            "=" * 72
        )

        print(
            "Units    :",
            total_units,
        )

        print(
            "Processed:",
            unit_index,
        )

        print(
            "SUCCESS  :",
            success_count,
        )

        print(
            "SKIP     :",
            skip_count,
        )

        print(
            "NO_DATA  :",
            no_data_count,
        )

        print(
            "ERROR    :",
            error_count,
        )


if __name__ == "__main__":
    main()