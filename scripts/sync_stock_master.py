from crawler.stock_master import (
    download_twse_stock_master,
    download_tpex_stock_master,
)

from db.repository import (
    upsert_stock,
    deactivate_market_stocks,
)


def save_market(
    market: str,
    rows: list[dict],
):
    if not rows:

        raise ValueError(
            f"{market} 股票主檔為空，"
            "停止更新 stocks"
        )

    # =================================
    # 先停用舊清單
    # =================================

    deactivate_market_stocks(
        market
    )

    # =================================
    # 官方目前存在股票重新 active
    # =================================

    count = 0

    for row in rows:

        upsert_stock(
            stock_id=row[
                "stock_id"
            ],
            market=row[
                "market"
            ],
            stock_name=row[
                "stock_name"
            ],
            is_active=1,
        )

        count += 1

    print(
        f"[OK] {market} "
        f"寫入 / 更新 {count:,} 檔"
    )

    return count


def main():

    print(
        "================================"
    )

    print(
        "TWSE + TPEx 全市場股票主檔同步"
    )

    print(
        "================================"
    )

    # =================================
    # 1. 先下載
    #
    # 兩邊都成功，
    # 才開始改 stocks。
    # =================================

    twse_rows = (
        download_twse_stock_master()
    )

    tpex_rows = (
        download_tpex_stock_master()
    )

    if not twse_rows:
        raise ValueError(
            "TWSE 官方股票主檔為空"
        )

    if not tpex_rows:
        raise ValueError(
            "TPEx 官方股票主檔為空"
        )

    print()

    # =================================
    # 2. DB
    # =================================

    twse_count = save_market(
        market="TWSE",
        rows=twse_rows,
    )

    tpex_count = save_market(
        market="TPEx",
        rows=tpex_rows,
    )

    total = (
        twse_count
        + tpex_count
    )

    print()

    print(
        "================================"
    )

    print(
        "股票主檔同步完成"
    )

    print(
        "================================"
    )

    print(
        f"TWSE：{twse_count:,} 檔"
    )

    print(
        f"TPEx：{tpex_count:,} 檔"
    )

    print(
        f"合計：{total:,} 檔"
    )


if __name__ == "__main__":
    main()