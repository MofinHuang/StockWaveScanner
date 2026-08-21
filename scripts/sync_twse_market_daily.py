from datetime import (
    date,
    timedelta,
)

from crawler.twse_market_daily import (
    download_day,
)

from db.repository import (
    crawl_success_exists,
)


BACKFILL_DAYS = 60
SOURCE = "TWSE_MI_INDEX"


def main():

    print(
        "================================"
    )

    print(
        "TWSE 全市場日 K 同步"
    )

    print(
        "================================"
    )

    today = date.today()

    start_date = (
        today
        - timedelta(
            days=BACKFILL_DAYS
        )
    )

    current = start_date

    total_rows = 0
    success_days = 0
    skipped_days = 0

    while current <= today:

        # 週六、週日不請求。
        if current.weekday() >= 5:

            current += timedelta(
                days=1
            )

            continue

        request_key = (
            current.strftime(
                "%Y%m%d"
            )
        )

        # 已成功處理過就跳過，
        # 避免重複打官方 API。
        if crawl_success_exists(
            source=SOURCE,
            request_key=request_key,
        ):

            print(
                f"[SKIP] "
                f"{current} "
                "已有 SUCCESS"
            )

            skipped_days += 1

            current += timedelta(
                days=1
            )

            continue

        try:

            count = download_day(
                current
            )

            if count == 0:

                # 假日 / 無交易日
                print(
                    f"[EMPTY] "
                    f"{current}"
                )

            else:

                print(
                    f"[OK] "
                    f"{current} "
                    f"{count:,} 檔"
                )

                success_days += 1
                total_rows += count

        except Exception as ex:

            print(
                f"[ERROR] "
                f"{current}: "
                f"{ex}"
            )

        current += timedelta(
            days=1
        )

    print()

    print(
        "================================"
    )

    print(
        "TWSE 全市場日 K 同步完成"
    )

    print(
        "================================"
    )

    print(
        f"有效交易日："
        f"{success_days}"
    )

    print(
        f"跳過既有 SUCCESS："
        f"{skipped_days}"
    )

    print(
        f"寫入 / 更新："
        f"{total_rows:,} 筆"
    )


if __name__ == "__main__":
    main()