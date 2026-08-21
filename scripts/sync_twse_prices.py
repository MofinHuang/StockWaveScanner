from datetime import datetime

from config import TEST_STOCKS
from crawler.twse import download_month

from db.repository import (
    has_price_month,
)

def get_months(
    count: int = 14,
):
    today = datetime.today()

    year = today.year
    month = today.month

    result = []

    for _ in range(count):

        result.append(
            (
                year,
                month,
            )
        )

        month -= 1

        if month == 0:
            month = 12
            year -= 1

    result.reverse()

    return result


def main():

    twse_stocks = [
        stock
        for stock in TEST_STOCKS
        if stock["market"] == "TWSE"
    ]

    months = get_months(
        count=14
    )

    print(
        "=============================="
    )

    print(
        "TWSE 歷史日K同步"
    )

    print(
        "=============================="
    )

    print(
        f"股票數：{len(twse_stocks)}"
    )

    print(
        f"月份數：{len(months)}"
    )

    print()

    for stock in twse_stocks:

        stock_id = stock["stock_id"]
        stock_name = stock["stock_name"]

        print()
        print(
            f"===== "
            f"{stock_id} "
            f"{stock_name} "
            f"====="
        )

        for year, month in months:

            today = datetime.today()

            is_current_month = (
                year == today.year
                and month == today.month
            )

            if (
                not is_current_month
                and has_price_month(
                    stock_id=stock_id,
                    market="TWSE",
                    year=year,
                    month=month,
                )
            ):
                print(
                    f"[SKIP] "
                    f"{stock_id} "
                    f"{year}-{month:02d} "
                    f"歷史資料已存在"
                )

                continue

            try:

                download_month(
                    stock_id=stock_id,
                    year=year,
                    month=month,
                )

            except Exception as ex:

                print(
                    f"[ERROR] "
                    f"{stock_id} "
                    f"{year}-{month:02d}: "
                    f"{ex}"
                )


if __name__ == "__main__":
    main()