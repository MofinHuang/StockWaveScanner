from config import TEST_STOCKS

from db.repository import upsert_stock


def main():

    print("開始同步測試股票主檔...")

    for stock in TEST_STOCKS:

        stock_id = stock["stock_id"]
        stock_name = stock["stock_name"]
        market = stock["market"]

        upsert_stock(
            stock_id=stock_id,
            stock_name=stock_name,
            market=market,
        )

        print(
            f"[OK] "
            f"{stock_id} "
            f"{stock_name} "
            f"{market}"
        )

    print()
    print(
        f"完成，共同步 {len(TEST_STOCKS)} 檔股票。"
    )


if __name__ == "__main__":
    main()