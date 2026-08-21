from datetime import (
    date,
    timedelta,
)

from crawler.twse_market_institutional import (
    download_day,
    SOURCE,
)

from db.repository import (
    crawl_success_exists,
)


BACKFILL_DAYS = 90


def main():

    print(
        "================================"
    )

    print(
        "TWSE 全市場外資同步"
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

    success_days = 0
    empty_days = 0
    skipped_days = 0
    error_days = 0
    total_rows = 0

    while current <= today:

        # 六、日不查。
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
                f"{type(ex).__name__}: "
                f"{ex}"
            )

            error_days += 1

        current += timedelta(
            days=1
        )

    print()

    print(
        "================================"
    )

    print(
        "TWSE 全市場外資同步完成"
    )

    print(
        "================================"
    )

    print(
        f"成功交易日："
        f"{success_days}"
    )

    print(
        f"無資料日："
        f"{empty_days}"
    )

    print(
        f"跳過 SUCCESS："
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