from __future__ import annotations

import argparse

from db.database import get_connection
from strategy.foreign import (
    build_weekly_foreign_effective,
    evaluate_foreign,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "驗證正式 strategy.foreign "
            "effective data integration"
        )
    )

    parser.add_argument(
        "--stock-id",
        default="1294",
    )

    parser.add_argument(
        "--market",
        default="TPEx",
        choices=[
            "TWSE",
            "TPEx",
        ],
    )

    parser.add_argument(
        "--reference-date",
        default="2026-08-14",
    )

    args = parser.parse_args()

    conn = get_connection()

    try:
        weekly = (
            build_weekly_foreign_effective(
                conn=conn,
                stock_id=args.stock_id,
                market=args.market,
                reference_date=(
                    args.reference_date
                ),
            )
        )

        print("=" * 72)
        print(
            "Foreign Effective Integration"
        )
        print("=" * 72)

        print(
            "stock_id       =",
            args.stock_id,
        )

        print(
            "market         =",
            args.market,
        )

        print(
            "reference_date =",
            args.reference_date,
        )

        print()
        print(
            "Recent 5 weeks:"
        )

        print(
            weekly.tail(5).to_string(
                index=False
            )
        )

        result = evaluate_foreign(
            weekly
        )

        print()
        print("=" * 72)
        print("FOREIGN /20")
        print("=" * 72)

        print(
            "status       =",
            result["status"],
        )

        print(
            "passed       =",
            result["passed"],
        )

        print(
            "score        =",
            result["score"],
        )

        print(
            "all_positive =",
            result["all_positive"],
        )

        print(
            "growing      =",
            result["growing"],
        )

        print(
            "stable       =",
            result["stable"],
        )

        print(
            "reason       =",
            result["reason"],
        )

        print()
        print(
            "Scored weeks:"
        )

        for week in result["weeks"]:
            print()
            print(
                "week_start =",
                week["week_start"],
            )

            print(
                "week_end   =",
                week["week_end"],
            )

            print(
                "buy        =",
                week["foreign_buy"],
            )

            print(
                "sell       =",
                week["foreign_sell"],
            )

            print(
                "net        =",
                week["foreign_net"],
            )

            print(
                "days       =",
                week["trading_days"],
            )

            print(
                "ratio      =",
                week[
                    "ratio_to_previous"
                ],
            )

    finally:
        conn.close()


if __name__ == "__main__":
    main()