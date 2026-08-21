from datetime import date, timedelta

from config import TEST_STOCKS
from crawler.tpex_institutional import download_day
from db.repository import crawl_success_exists


SOURCE = "TPEX_3INSTI_HISTORY"

BACKFILL_DAYS = 90


def get_target_stock_ids():
    return [
        stock["stock_id"]
        for stock in TEST_STOCKS
        if stock["market"] == "TPEx"
    ]


def main():

    stock_ids = get_target_stock_ids()

    print("================================")
    print("TPEx 外資歷史回補")
    print("================================")

    print(f"測試股票：{stock_ids}")
    print(f"回補範圍：最近 {BACKFILL_DAYS} 個日曆日")
    print()

    today = date.today()

    start_date = (
        today
        - timedelta(days=BACKFILL_DAYS)
    )

    current = start_date

    success_days = 0
    skipped_days = 0
    empty_days = 0
    error_days = 0

    while current <= today:

        # 星期六、日直接跳過，
        # 不向 TPEx 發 Request。
        if current.weekday() >= 5:

            current += timedelta(days=1)
            continue

        request_key = current.strftime(
            "%Y%m%d"
        )

        # 已經成功處理過的日期，
        # 不再重複 Request。
        #
        # SUCCESS 包含：
        # - 有資料
        # - 官方正常回傳但當日無資料
        #
        # 因此休市日也能避免重抓。
        if crawl_success_exists(
            source=SOURCE,
            request_key=request_key,
        ):

            print(
                f"[SKIP] {current} 已同步"
            )

            skipped_days += 1

            current += timedelta(days=1)
            continue

        try:

            inserted = download_day(
                trade_date=current,
                target_stock_ids=stock_ids,
            )

            if inserted > 0:
                success_days += 1
            else:
                empty_days += 1

        except Exception as ex:

            error_days += 1

            print(
                f"[ERROR] {current}: {ex}"
            )

        current += timedelta(days=1)

    print()
    print("================================")
    print("TPEx 歷史回補完成")
    print("================================")

    print(
        f"有資料日期：{success_days}"
    )

    print(
        f"已存在跳過：{skipped_days}"
    )

    print(
        f"無資料日期：{empty_days}"
    )

    print(
        f"錯誤日期：{error_days}"
    )


if __name__ == "__main__":
    main()