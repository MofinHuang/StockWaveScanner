from __future__ import annotations

from collections import Counter

import pandas as pd

from db.database import get_connection
from strategy.sleep import (
    evaluate_sleep,
)
from strategy.breakout import (
    evaluate_breakout,
)


def section(
    title: str,
) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _condition_map(
    result: dict,
) -> dict[str, bool]:
    return {
        str(item["name"]):
            bool(item["passed"])
        for item
        in result.get(
            "conditions",
            []
        )
    }


def _load_price(
    conn,
    stock_id: str,
    market: str,
) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT
            trade_date,
            open,
            high,
            low,
            close,
            volume
        FROM daily_prices
        WHERE stock_id = ?
          AND market = ?
        ORDER BY trade_date ASC
        """,
        conn,
        params=(
            stock_id,
            market,
        ),
    )


def main() -> None:
    conn = get_connection()

    try:
        stocks = pd.read_sql_query(
            """
            SELECT
                s.stock_id,
                s.stock_name,
                s.market
            FROM stocks s
            WHERE s.is_active = 1
              AND s.market IN (
                  'TWSE',
                  'TPEx'
              )
              AND (
                  SELECT COUNT(*)
                  FROM daily_prices p
                  WHERE p.stock_id =
                        s.stock_id
                    AND p.market =
                        s.market
              ) >= 30
            ORDER BY
                s.market,
                s.stock_id
            """,
            conn,
        )

        rows = []

        total = len(
            stocks
        )

        for index, stock in (
            stocks.iterrows()
        ):
            stock_id = str(
                stock["stock_id"]
            )

            stock_name = str(
                stock["stock_name"]
            )

            market = str(
                stock["market"]
            )

            price_df = (
                _load_price(
                    conn,
                    stock_id,
                    market,
                )
            )

            sleep = evaluate_sleep(
                price_df
            )

            breakout = (
                evaluate_breakout(
                    price_df
                )
            )

            sleep_conditions = (
                _condition_map(
                    sleep
                )
            )

            breakout_conditions = (
                _condition_map(
                    breakout
                )
            )

            rows.append(
                {
                    "stock_id":
                        stock_id,

                    "stock_name":
                        stock_name,

                    "market":
                        market,

                    "sleep_status":
                        sleep["status"],

                    "sleep_score":
                        sleep["score"],

                    "sleep_price":
                        sleep_conditions.get(
                            "價格接近 MA20",
                            False,
                        ),

                    "sleep_volatility":
                        sleep_conditions.get(
                            "波動收斂",
                            False,
                        ),

                    "sleep_volume":
                        sleep_conditions.get(
                            "成交量沉澱",
                            False,
                        ),

                    "sleep_ma_distance":
                        sleep.get(
                            "metrics",
                            {},
                        ).get(
                            "ma_distance_pct"
                        ),

                    "sleep_vol_ratio":
                        sleep.get(
                            "metrics",
                            {},
                        ).get(
                            "volatility_ratio"
                        ),

                    "sleep_volume_ratio":
                        sleep.get(
                            "metrics",
                            {},
                        ).get(
                            "volume_ratio"
                        ),

                    "breakout_status":
                        breakout["status"],

                    "breakout_score":
                        breakout["score"],

                    "breakout_price":
                        breakout_conditions.get(
                            "收盤突破前 20 日高點",
                            False,
                        ),

                    "breakout_volume":
                        breakout_conditions.get(
                            "成交量放大",
                            False,
                        ),

                    "breakout_close":
                        breakout_conditions.get(
                            "收盤位置強勢",
                            False,
                        ),

                    "breakout_pct":
                        breakout.get(
                            "metrics",
                            {},
                        ).get(
                            "breakout_pct"
                        ),

                    "breakout_volume_ratio":
                        breakout.get(
                            "metrics",
                            {},
                        ).get(
                            "volume_ratio"
                        ),

                    "close_from_high":
                        breakout.get(
                            "metrics",
                            {},
                        ).get(
                            "close_from_high_ratio"
                        ),
                }
            )

            if (
                (index + 1) % 200
                == 0
            ):
                print(
                    f"[INFO] "
                    f"{index + 1}/"
                    f"{total}"
                )

    finally:
        conn.close()

    df = pd.DataFrame(
        rows
    )

    section(
        "BASIC"
    )

    print(
        "stocks =",
        len(df),
    )

    sleep_pass = df[
        df["sleep_status"]
        == "PASS"
    ]

    breakout_pass = df[
        df["breakout_status"]
        == "PASS"
    ]

    both_pass = df[
        (
            df["sleep_status"]
            == "PASS"
        )
        & (
            df["breakout_status"]
            == "PASS"
        )
    ]

    print(
        "Sleep PASS    =",
        len(sleep_pass),
    )

    print(
        "Breakout PASS =",
        len(breakout_pass),
    )

    print(
        "Both PASS     =",
        len(both_pass),
    )

    # =====================================
    # Breakout PASS 股票的 Sleep 條件
    # =====================================

    section(
        "BREAKOUT PASS -> SLEEP CONDITIONS"
    )

    print(
        "Breakout PASS stocks =",
        len(breakout_pass),
    )

    for column, label in [
        (
            "sleep_price",
            "Sleep 價格接近 MA20",
        ),
        (
            "sleep_volatility",
            "Sleep 波動收斂",
        ),
        (
            "sleep_volume",
            "Sleep 成交量沉澱",
        ),
    ]:
        count = int(
            breakout_pass[
                column
            ].sum()
        )

        print(
            f"{label:22s} = "
            f"{count} / "
            f"{len(breakout_pass)}"
        )

    print()
    print(
        "Sleep score distribution "
        "among Breakout PASS:"
    )

    for score, count in sorted(
        Counter(
            breakout_pass[
                "sleep_score"
            ].tolist()
        ).items()
    ):
        print(
            f"  {score:2d} = "
            f"{count}"
        )

    # =====================================
    # Sleep PASS 股票的 Breakout 條件
    # =====================================

    section(
        "SLEEP PASS -> BREAKOUT CONDITIONS"
    )

    print(
        "Sleep PASS stocks =",
        len(sleep_pass),
    )

    for column, label in [
        (
            "breakout_price",
            "Breakout 突破前高",
        ),
        (
            "breakout_volume",
            "Breakout 成交量放大",
        ),
        (
            "breakout_close",
            "Breakout 收盤強勢",
        ),
    ]:
        count = int(
            sleep_pass[
                column
            ].sum()
        )

        print(
            f"{label:22s} = "
            f"{count} / "
            f"{len(sleep_pass)}"
        )

    print()
    print(
        "Breakout score distribution "
        "among Sleep PASS:"
    )

    for score, count in sorted(
        Counter(
            sleep_pass[
                "breakout_score"
            ].tolist()
        ).items()
    ):
        print(
            f"  {score:2d} = "
            f"{count}"
        )

    # =====================================
    # Breakout PASS 全部明細
    # =====================================

    section(
        "ALL BREAKOUT PASS STOCKS"
    )

    columns = [
        "stock_id",
        "stock_name",
        "market",
        "sleep_score",
        "sleep_price",
        "sleep_volatility",
        "sleep_volume",
        "sleep_ma_distance",
        "sleep_vol_ratio",
        "sleep_volume_ratio",
        "breakout_score",
        "breakout_pct",
        "breakout_volume_ratio",
        "close_from_high",
    ]

    if breakout_pass.empty:
        print(
            "(none)"
        )
    else:
        print(
            breakout_pass[
                columns
            ]
            .sort_values(
                by=[
                    "sleep_score",
                    "stock_id",
                ],
                ascending=[
                    False,
                    True,
                ],
            )
            .to_string(
                index=False
            )
        )

    # =====================================
    # Sleep PASS 中最接近 Breakout 的
    # =====================================

    section(
        "SLEEP PASS - HIGHEST BREAKOUT SCORE"
    )

    candidates = (
        sleep_pass
        .sort_values(
            by=[
                "breakout_score",
                "breakout_volume_ratio",
                "stock_id",
            ],
            ascending=[
                False,
                False,
                True,
            ],
        )
        .head(50)
    )

    candidate_columns = [
        "stock_id",
        "stock_name",
        "market",
        "sleep_score",
        "breakout_score",
        "breakout_price",
        "breakout_volume",
        "breakout_close",
        "breakout_pct",
        "breakout_volume_ratio",
        "close_from_high",
    ]

    print(
        candidates[
            candidate_columns
        ].to_string(
            index=False
        )
    )

    # =====================================
    # Direct volume conflict
    # =====================================

    section(
        "VOLUME CONDITION CROSS-CHECK"
    )

    sleep_volume_pass = df[
        df["sleep_volume"]
    ]

    breakout_volume_pass = df[
        df["breakout_volume"]
    ]

    both_volume = df[
        df["sleep_volume"]
        & df["breakout_volume"]
    ]

    print(
        "Sleep volume condition PASS    =",
        len(sleep_volume_pass),
    )

    print(
        "Breakout volume condition PASS =",
        len(breakout_volume_pass),
    )

    print(
        "Both volume conditions PASS    =",
        len(both_volume),
    )

    if not both_volume.empty:
        print()
        print(
            both_volume[
                [
                    "stock_id",
                    "stock_name",
                    "market",
                    "sleep_volume_ratio",
                    "breakout_volume_ratio",
                    "sleep_status",
                    "breakout_status",
                ]
            ]
            .head(50)
            .to_string(
                index=False
            )
        )

    print()
    print("=" * 72)
    print("DONE")
    print("=" * 72)


if __name__ == "__main__":
    main()