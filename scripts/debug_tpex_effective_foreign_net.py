from __future__ import annotations

import argparse

from db.database import get_connection
from strategy.foreign_data import (
    get_effective_foreign_net,
)


DEFAULT_DATE = "2026-08-14"


def inspect_stock(
    conn,
    stock_id: str,
    trade_date: str,
) -> None:
    rows = get_effective_foreign_net(
        conn=conn,
        stock_id=stock_id,
        market="TPEx",
        start_date=trade_date,
        end_date=trade_date,
    )

    print()
    print("=" * 72)

    print(
        "stock_id =",
        stock_id,
    )

    print(
        "trade_date =",
        trade_date,
    )

    if not rows:
        print(
            "RESULT = NO DAILY PRICE"
        )

        return

    for row in rows:
        print(
            "foreign_net =",
            row.foreign_net,
        )

        print(
            "status      =",
            row.status,
        )

        print(
            "source      =",
            row.source,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "驗證 TPEx effective foreign_net"
        )
    )

    parser.add_argument(
        "--date",
        default=DEFAULT_DATE,
    )

    args = parser.parse_args()

    conn = get_connection()

    try:
        print("=" * 72)
        print("TPEx Effective Foreign Net")
        print("=" * 72)

        #
        # 已確認 qfiiStat 有正式 row：
        #
        # 6488 環球晶
        # foreign_net = +1,132,000
        #
        inspect_stock(
            conn,
            stock_id="6488",
            trade_date=args.date,
        )

        #
        # 已確認 daily_price 有，
        # 但 qfiiStat normalized row 缺失：
        #
        # 1294 漢田生技
        #
        # 預期：
        # foreign_net = 0
        # ZERO_INFERRED
        #
        inspect_stock(
            conn,
            stock_id="1294",
            trade_date=args.date,
        )

        #
        # 已確認 qfiiStat 有負值：
        #
        # 6182 合晶
        # foreign_net = -11,752,000
        #
        inspect_stock(
            conn,
            stock_id="6182",
            trade_date=args.date,
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()