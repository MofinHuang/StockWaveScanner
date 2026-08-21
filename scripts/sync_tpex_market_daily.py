from datetime import (
    date,
    timedelta,
)

from crawler.tpex_market_daily import (
    download_day,
)

from db.repository import (
    crawl_success_exists,
)


BACKFILL_DAYS = 60

SOURCE = "TPEX_DAILY_QUOTES"


def main():

    print(
        "================================"
    )

    print(
        "TPEx 全市場日 K 同步"
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
    empty_days = 0
    skipped_days = 0
    error_days = 0

    while current <= today:

        # =================================
        # Weekend
        # =================================

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

        # =================================
        # Crawl log
        # =================================

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

        # =================================
        # Download
        # =================================

        try:

            count = download_day(
                current
            )

            if count == 0:

                print(
                    f"[EMPTY] "
                    f"{current}"
                )

                empty_days += 1

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

            error_days += 1

        current += timedelta(
            days=1
        )

    # =================================
    # Summary
    # =================================

    print()

    print(
        "================================"
    )

    print(
        "TPEx 全市場日 K 同步完成"
    )

    print(
        "================================"
    )

    print(
        f"有效交易日："
        f"{success_days}"
    )

    print(
        f"無資料日："
        f"{empty_days}"
    )

    print(
        f"跳過既有 SUCCESS："
        f"{skipped_days}"
    )

    print(
        f"錯誤日："
        f"{error_days}"
    )

    print(
        f"寫入 / 更新："
        f"{total_rows:,} 筆"
    )


if __name__ == "__main__":
    main()