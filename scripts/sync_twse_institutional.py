from datetime import date, timedelta

from config import TEST_STOCKS
from crawler.twse_institutional import (
    download_day,
    restore_day_from_raw,
)
from db.repository import crawl_success_exists


SOURCE = "TWSE_T86"

BACKFILL_DAYS = 90


def get_target_stock_ids():
    return [
        stock["stock_id"]
        for stock in TEST_STOCKS
        if stock["market"] == "TWSE"
    ]


def main():

    stock_ids = get_target_stock_ids()

    print("================================")
    print("TWSE 外資歷史回補")
    print("================================")

    print(
        f"測試股票：{stock_ids}"
    )

    print(
        f"回補範圍：最近 "
        f"{BACKFILL_DAYS} 個日曆日"
    )

    print()

    today = date.today()

    start_date = (
        today
        - timedelta(
            days=BACKFILL_DAYS
        )
    )

    current = start_date

    raw_restore_days = 0
    downloaded_days = 0
    empty_days = 0
    error_days = 0

    while current <= today:

        # 六、日不 Request
        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue

        request_key = current.strftime(
            "%Y%m%d"
        )

        # --------------------------------
        # 已成功抓過的市場資料
        #
        # 不重新 Request。
        # 改從 raw_responses 重新解析，
        # 這樣新增的測試股票（例如 6770）
        # 也能補進 institutional_trades。
        # --------------------------------

        if crawl_success_exists(
            source=SOURCE,
            request_key=request_key,
        ):

            try:
                inserted = (
                    restore_day_from_raw(
                        trade_date=current,
                        target_stock_ids=stock_ids,
                    )
                )

                if inserted is not None:

                    if inserted > 0:
                        print(
                            f"[RAW] {current} "
                            f"從既有 Raw 補寫 "
                            f"{inserted} 筆"
                        )

                        raw_restore_days += 1

                    else:
                        print(
                            f"[RAW EMPTY] "
                            f"{current}"
                        )

                        empty_days += 1

                    current += timedelta(
                        days=1
                    )

                    continue

                # crawl log 有 SUCCESS，
                # 但 Raw 不存在。
                #
                # 依專案原則 Raw 必須可追溯，
                # 所以重新抓一次官方資料。
                print(
                    f"[WARN] {current} "
                    "Crawl Log 已成功，"
                    "但找不到 Raw，重新下載"
                )

            except Exception as ex:
                print(
                    f"[ERROR] "
                    f"{current} "
                    f"Raw 重新解析失敗："
                    f"{ex}"
                )

                error_days += 1

                current += timedelta(
                    days=1
                )

                continue

        # --------------------------------
        # 尚未抓過，或 Raw 遺失
        # → 才真的發 Request
        # --------------------------------

        try:
            inserted = download_day(
                trade_date=current,
                target_stock_ids=stock_ids,
            )

            if inserted > 0:
                downloaded_days += 1
            else:
                empty_days += 1

        except Exception as ex:
            print(
                f"[ERROR] "
                f"{current}: {ex}"
            )

            error_days += 1

        current += timedelta(
            days=1
        )

    print()
    print("================================")
    print("TWSE 法人歷史回補完成")
    print("================================")

    print(
        f"Raw 重新解析日期："
        f"{raw_restore_days}"
    )

    print(
        f"實際重新下載日期："
        f"{downloaded_days}"
    )

    print(
        f"無資料日期："
        f"{empty_days}"
    )

    print(
        f"錯誤日期："
        f"{error_days}"
    )


if __name__ == "__main__":
    main()