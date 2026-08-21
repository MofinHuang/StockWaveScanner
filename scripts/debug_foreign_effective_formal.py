from __future__ import annotations

import argparse

from db.database import get_connection
from strategy.foreign_effective import (
    analyze_foreign_effective,
)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--stock-id",
        required=True,
    )

    parser.add_argument(
        "--market",
        required=True,
        choices=[
            "TWSE",
            "TPEx",
        ],
    )

    parser.add_argument(
        "--as-of-date",
        required=True,
    )

    args = parser.parse_args()

    conn = get_connection()

    try:
        result = (
            analyze_foreign_effective(
                conn=conn,
                stock_id=args.stock_id,
                market=args.market,
                as_of_date=(
                    args.as_of_date
                ),
            )
        )

        print("=" * 72)
        print("Foreign /20 Formal Effective")
        print("=" * 72)

        print(
            "stock_id   =",
            result.stock_id,
        )

        print(
            "market     =",
            result.market,
        )

        print(
            "as_of_date =",
            result.as_of_date,
        )

        for index, week in enumerate(
            result.weeks,
            start=1,
        ):
            print()
            print(
                f"Week {index}: "
                f"{week.week_start} "
                f"~ {week.week_end}"
            )

            print(
                "market days   =",
                len(
                    week.market_dates
                ),
            )

            print(
                "stored        =",
                week.stored_days,
            )

            print(
                "zero inferred =",
                week.zero_inferred_days,
            )

            print(
                "insufficient  =",
                week.insufficient_days,
            )

            print(
                "foreign_net   =",
                week.foreign_net,
            )

        print()
        print("=" * 72)

        print(
            "status =",
            result.status,
        )

        print(
            "score  =",
            result.score,
        )

        print(
            "A positive   =",
            result.condition_positive,
        )

        print(
            "B increasing =",
            result.condition_increasing,
        )

        print(
            "C no spike   =",
            result.condition_no_spike,
        )

        print(
            "reason =",
            result.reason,
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()