from datetime import date

import pandas as pd

from db.database import get_connection
from strategy.foreign import (
    build_weekly_foreign,
    evaluate_foreign,
)


STOCK_ID = "3646"
MARKET = "TPEx"
REFERENCE_DATE = date(2026, 8, 14)


def section(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def main():
    conn = get_connection()

    try:
        df = pd.read_sql_query(
            """
            SELECT
                trade_date,
                foreign_buy,
                foreign_sell,
                foreign_net,
                source
            FROM institutional_trades
            WHERE stock_id = ?
              AND market = ?
            ORDER BY trade_date ASC
            """,
            conn,
            params=(
                STOCK_ID,
                MARKET,
            ),
        )
    finally:
        conn.close()

    section("FOREIGN INSUFFICIENT DEBUG")

    print("stock_id       =", STOCK_ID)
    print("market         =", MARKET)
    print("reference_date =", REFERENCE_DATE)
    print("DB rows        =", len(df))

    if df.empty:
        print("[FAIL] institutional_trades 無資料")
        return

    df["trade_date"] = pd.to_datetime(
        df["trade_date"],
        errors="coerce",
    )

    section("DATE RANGE")

    print(
        "min trade_date =",
        df["trade_date"].min(),
    )
    print(
        "max trade_date =",
        df["trade_date"].max(),
    )
    print(
        "unique dates   =",
        df["trade_date"].nunique(),
    )

    section("DAILY DATA")

    print(
        df.tail(40).to_string(
            index=False
        )
    )

    section("WEEK DISTRIBUTION")

    inspect = df.copy()

    inspect["week_start"] = (
        inspect["trade_date"]
        - pd.to_timedelta(
            inspect["trade_date"].dt.weekday,
            unit="D",
        )
    ).dt.normalize()

    week_summary = (
        inspect
        .groupby(
            "week_start",
            as_index=False,
        )
        .agg(
            first_date=(
                "trade_date",
                "min",
            ),
            last_date=(
                "trade_date",
                "max",
            ),
            rows=(
                "trade_date",
                "nunique",
            ),
            foreign_net=(
                "foreign_net",
                "sum",
            ),
        )
    )

    print(
        week_summary
        .tail(10)
        .to_string(
            index=False
        )
    )

    section("BUILD WEEKLY FOREIGN")

    weekly = build_weekly_foreign(
        df,
        reference_date=REFERENCE_DATE,
    )

    print(
        "weekly rows =",
        len(weekly),
    )

    if not weekly.empty:
        print()
        print(
            weekly.tail(10).to_string(
                index=False
            )
        )

    section("EVALUATE FOREIGN")

    result = evaluate_foreign(
        weekly
    )

    for key, value in result.items():
        print(
            f"{key:16s} = {value}"
        )

    section("KEY CHECK")

    print(
        "Need >= 3 completed weeks."
    )

    print(
        "Actual completed weeks =",
        len(weekly),
    )

    if len(weekly) < 3:
        print()
        print(
            "[CONFIRMED] INSUFFICIENT_DATA "
            "來自 build_weekly_foreign "
            "只有不足 3 個完整週。"
        )

        print()
        print(
            "下一步檢查：為什麼 DB 雖有 "
            f"{len(df)} rows，卻跨不到 3 個完整週。"
        )
    else:
        print()
        print(
            "[UNEXPECTED] 已有 >= 3 個完整週，"
            "evaluate_foreign 理論上不應回傳 "
            "INSUFFICIENT_DATA。"
        )


if __name__ == "__main__":
    main()