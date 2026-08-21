from config import TEST_STOCKS

from crawler.tdcc import (
    download_latest_raw,
    parse_tdcc_rows,
    build_tdcc_holding_summary,
    get_history_dates,
    download_history_stock_day,
)

from db.repository import (
    upsert_tdcc_holding,
)


HISTORY_WEEKS = 4


def format_data_date(
    data_date: str,
) -> str:

    if (
        len(data_date) != 8
        or not data_date.isdigit()
    ):
        raise ValueError(
            "TDCC 資料日期格式異常："
            f"{data_date}"
        )

    return (
        f"{data_date[0:4]}-"
        f"{data_date[4:6]}-"
        f"{data_date[6:8]}"
    )


def save_summary(
    row: dict,
):
    formatted_date = format_data_date(
        row["data_date"]
    )

    upsert_tdcc_holding(
        stock_id=row[
            "stock_id"
        ],
        data_date=formatted_date,
        large_holder_pct=row[
            "large_holder_pct"
        ],
        retail_holder_pct=row[
            "retail_holder_pct"
        ],
    )

    print(
        f"[OK] "
        f"{row['stock_id']} "
        f"{formatted_date} "
        f"大戶 "
        f"{row['large_holder_pct']:.2f}% "
        f"散戶 "
        f"{row['retail_holder_pct']:.2f}%"
    )


def main():

    stock_ids = [
        stock["stock_id"]
        for stock in TEST_STOCKS
    ]

    print(
        "================================"
    )

    print(
        "TDCC 最近 4 週同步"
    )

    print(
        "================================"
    )

    print(
        f"測試股票：{stock_ids}"
    )

    print()

    # =================================
    # 1. 最新一期：
    #    使用市場級 OpenAPI
    # =================================

    raw_text = download_latest_raw()

    parsed_latest = parse_tdcc_rows(
        raw_text=raw_text,
        target_stock_ids=stock_ids,
    )

    latest_summaries = (
        build_tdcc_holding_summary(
            parsed_latest
        )
    )

    if not latest_summaries:

        raise ValueError(
            "TDCC 最新 OpenAPI "
            "找不到測試股票資料"
        )

    latest_dates = {
        row["data_date"]
        for row in latest_summaries
    }

    if len(latest_dates) != 1:

        raise ValueError(
            "TDCC 最新資料出現"
            "多個資料日期："
            f"{sorted(latest_dates)}"
        )

    latest_date = next(
        iter(latest_dates)
    )

    print(
        f"最新一期：{latest_date}"
    )

    for row in latest_summaries:
        save_summary(
            row
        )

    # =================================
    # 2. 官方歷史頁日期
    # =================================

    available_dates = (
        get_history_dates()
    )

    older_dates = [
        value
        for value in available_dates
        if value < latest_date
    ]

    # 最新一期已經由 OpenAPI 完成，
    # 所以只補前三個較舊週。
    history_dates = (
        older_dates[
            :HISTORY_WEEKS - 1
        ]
    )

    if (
        len(history_dates)
        < HISTORY_WEEKS - 1
    ):
        raise ValueError(
            "TDCC 官方歷史日期不足，"
            "無法取得最近 4 週"
        )

    target_dates = [
        latest_date,
        *history_dates,
    ]

    print()

    print(
        "本次 4 週："
    )

    for value in target_dates:
        print(
            f"  {value}"
        )

    print()

    # =================================
    # 3. 前三期歷史資料
    # =================================

    for data_date in history_dates:

        print(
            "--------------------------------"
        )

        print(
            f"回補 TDCC {data_date}"
        )

        print(
            "--------------------------------"
        )

        for stock_id in stock_ids:

            try:

                parsed_history = (
                    download_history_stock_day(
                        stock_id=stock_id,
                        data_date=data_date,
                    )
                )

                if not parsed_history:

                    print(
                        f"[EMPTY] "
                        f"{stock_id} "
                        f"{data_date}"
                    )

                    continue

                summaries = (
                    build_tdcc_holding_summary(
                        parsed_history
                    )
                )

                for row in summaries:
                    save_summary(
                        row
                    )

            except Exception as ex:

                print(
                    f"[ERROR] "
                    f"{stock_id} "
                    f"{data_date}: "
                    f"{ex}"
                )

    print()

    print(
        "================================"
    )

    print(
        "TDCC 最近 4 週同步完成"
    )

    print(
        "================================"
    )


if __name__ == "__main__":
    main()