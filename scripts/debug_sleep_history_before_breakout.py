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


LOOKBACK_WINDOWS = [
    10,
    20,
    30,
    40,
]


def section(
    title: str,
) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


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


def _normalize_price_df(
    price_df: pd.DataFrame,
) -> pd.DataFrame:
    df = price_df.copy()

    df["trade_date"] = pd.to_datetime(
        df["trade_date"],
        errors="coerce",
    )

    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = (
        df
        .dropna(
            subset=[
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        )
        .sort_values(
            "trade_date"
        )
        .reset_index(
            drop=True
        )
    )

    return df


def _find_historical_sleep_passes(
    price_df: pd.DataFrame,
) -> list[dict]:
    """
    對最新 Breakout 日之前的每一個交易日，
    都以當日為 snapshot 終點重新執行
    evaluate_sleep()。

    不包含最新 Breakout 日本身。

    回傳：
        [
            {
                "index": ...,
                "trade_date": ...,
                "score": 30,
            },
            ...
        ]
    """
    passes = []

    #
    # 最新一列是目前 Breakout 日，
    # 所以只跑到 len(df) - 2。
    #
    for end_index in range(
        len(price_df) - 1
    ):
        historical_df = (
            price_df
            .iloc[
                : end_index + 1
            ]
            .copy()
        )

        result = evaluate_sleep(
            historical_df
        )

        if (
            result.get("status")
            != "PASS"
        ):
            continue

        passes.append(
            {
                "index":
                    end_index,

                "trade_date":
                    price_df.iloc[
                        end_index
                    ]["trade_date"],

                "score":
                    result.get(
                        "score",
                        0,
                    ),
            }
        )

    return passes


def _days_ago(
    latest_index: int,
    sleep_index: int,
) -> int:
    """
    使用交易日距離，不是 calendar days。

    例如：
        breakout index = 39
        sleep index = 38

        => 1 trading day ago
    """
    return (
        latest_index
        - sleep_index
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

        breakout_rows = []

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

            price_df = _load_price(
                conn,
                stock_id,
                market,
            )

            price_df = (
                _normalize_price_df(
                    price_df
                )
            )

            if price_df.empty:
                continue

            breakout_result = (
                evaluate_breakout(
                    price_df
                )
            )

            if (
                breakout_result.get(
                    "status"
                )
                != "PASS"
            ):
                if (
                    (index + 1)
                    % 200
                    == 0
                ):
                    print(
                        f"[INFO] "
                        f"{index + 1}/"
                        f"{total}"
                    )

                continue

            historical_passes = (
                _find_historical_sleep_passes(
                    price_df
                )
            )

            latest_index = (
                len(price_df)
                - 1
            )

            breakout_date = (
                price_df.iloc[
                    latest_index
                ]["trade_date"]
            )

            if historical_passes:
                last_sleep = (
                    historical_passes[-1]
                )

                last_sleep_date = (
                    last_sleep[
                        "trade_date"
                    ]
                )

                sleep_days_ago = (
                    _days_ago(
                        latest_index,
                        int(
                            last_sleep[
                                "index"
                            ]
                        ),
                    )
                )

            else:
                last_sleep_date = None
                sleep_days_ago = None

            row = {
                "stock_id":
                    stock_id,

                "stock_name":
                    stock_name,

                "market":
                    market,

                "breakout_date":
                    breakout_date,

                "last_sleep_date":
                    last_sleep_date,

                "sleep_days_ago":
                    sleep_days_ago,

                "historical_sleep_pass_count":
                    len(
                        historical_passes
                    ),

                "breakout_score":
                    breakout_result.get(
                        "score",
                        0,
                    ),

                "breakout_pct":
                    breakout_result.get(
                        "metrics",
                        {},
                    ).get(
                        "breakout_pct"
                    ),

                "breakout_volume_ratio":
                    breakout_result.get(
                        "metrics",
                        {},
                    ).get(
                        "volume_ratio"
                    ),

                "close_from_high":
                    breakout_result.get(
                        "metrics",
                        {},
                    ).get(
                        "close_from_high_ratio"
                    ),
            }

            for window in (
                LOOKBACK_WINDOWS
            ):
                row[
                    f"sleep_within_{window}"
                ] = (
                    sleep_days_ago
                    is not None
                    and sleep_days_ago
                    <= window
                )

            breakout_rows.append(
                row
            )

            print(
                "[BREAKOUT PASS] "
                f"{market} "
                f"{stock_id} "
                f"{stock_name} "
                f"last_sleep="
                f"{last_sleep_date} "
                f"days_ago="
                f"{sleep_days_ago}"
            )

            if (
                (index + 1)
                % 200
                == 0
            ):
                print(
                    f"[INFO] "
                    f"{index + 1}/"
                    f"{total}"
                )

    finally:
        conn.close()

    result_df = pd.DataFrame(
        breakout_rows
    )

    section(
        "BREAKOUT -> HISTORICAL SLEEP"
    )

    print(
        "Breakout PASS stocks =",
        len(result_df),
    )

    if result_df.empty:
        print(
            "[WARN] 沒有 Breakout PASS 股票"
        )
        return

    print()

    for window in LOOKBACK_WINDOWS:
        column = (
            f"sleep_within_{window}"
        )

        count = int(
            result_df[
                column
            ].sum()
        )

        print(
            f"Sleep PASS within previous "
            f"{window:2d} trading days = "
            f"{count} / "
            f"{len(result_df)}"
        )

    # =====================================
    # Last Sleep distance distribution
    # =====================================

    section(
        "LAST SLEEP DISTANCE DISTRIBUTION"
    )

    with_sleep = result_df[
        result_df[
            "sleep_days_ago"
        ].notna()
    ].copy()

    never_sleep = result_df[
        result_df[
            "sleep_days_ago"
        ].isna()
    ].copy()

    print(
        "Ever Sleep PASS before breakout =",
        len(with_sleep),
    )

    print(
        "Never Sleep PASS before breakout=",
        len(never_sleep),
    )

    if not with_sleep.empty:
        distances = (
            with_sleep[
                "sleep_days_ago"
            ]
            .astype(int)
        )

        print()
        print(
            "min trading days ago    =",
            distances.min(),
        )

        print(
            "median trading days ago =",
            distances.median(),
        )

        print(
            "mean trading days ago   =",
            round(
                float(
                    distances.mean()
                ),
                2,
            ),
        )

        print(
            "max trading days ago    =",
            distances.max(),
        )

        print()
        print(
            "distance counts:"
        )

        for distance, count in sorted(
            Counter(
                distances.tolist()
            ).items()
        ):
            print(
                f"  {distance:3d} days = "
                f"{count}"
            )

    # =====================================
    # All Breakout PASS stocks
    # =====================================

    section(
        "ALL BREAKOUT PASS STOCKS"
    )

    display_columns = [
        "stock_id",
        "stock_name",
        "market",
        "breakout_date",
        "last_sleep_date",
        "sleep_days_ago",
        "historical_sleep_pass_count",
        "sleep_within_10",
        "sleep_within_20",
        "sleep_within_30",
        "sleep_within_40",
        "breakout_pct",
        "breakout_volume_ratio",
        "close_from_high",
    ]

    print(
        result_df[
            display_columns
        ]
        .sort_values(
            by=[
                "sleep_days_ago",
                "stock_id",
            ],
            na_position="last",
        )
        .to_string(
            index=False
        )
    )

    # =====================================
    # Never Sleep
    # =====================================

    section(
        "NEVER SLEEP PASS BEFORE BREAKOUT"
    )

    print(
        "count =",
        len(never_sleep),
    )

    if never_sleep.empty:
        print(
            "(none)"
        )

    else:
        print(
            never_sleep[
                [
                    "stock_id",
                    "stock_name",
                    "market",
                    "breakout_date",
                    "breakout_pct",
                    "breakout_volume_ratio",
                    "close_from_high",
                ]
            ]
            .to_string(
                index=False
            )
        )

    # =====================================
    # Within 30 days
    # =====================================

    section(
        "SLEEP PASS WITHIN PREVIOUS 30 DAYS"
    )

    within_30 = result_df[
        result_df[
            "sleep_within_30"
        ]
    ].copy()

    print(
        "count =",
        len(within_30),
    )

    if within_30.empty:
        print(
            "(none)"
        )

    else:
        print(
            within_30[
                [
                    "stock_id",
                    "stock_name",
                    "market",
                    "breakout_date",
                    "last_sleep_date",
                    "sleep_days_ago",
                    "historical_sleep_pass_count",
                    "breakout_pct",
                    "breakout_volume_ratio",
                ]
            ]
            .sort_values(
                by=[
                    "sleep_days_ago",
                    "stock_id",
                ]
            )
            .to_string(
                index=False
            )
        )

    # =====================================
    # Suggested window diagnostics
    # =====================================

    section(
        "LOOKBACK WINDOW COVERAGE"
    )

    for window in (
        LOOKBACK_WINDOWS
    ):
        column = (
            f"sleep_within_{window}"
        )

        count = int(
            result_df[
                column
            ].sum()
        )

        pct = (
            count
            / len(result_df)
            * 100
        )

        print(
            f"{window:2d} trading days "
            f"-> "
            f"{count:2d} / "
            f"{len(result_df)} "
            f"({pct:.1f}%)"
        )

    print()
    print("=" * 72)
    print("DONE")
    print("=" * 72)


if __name__ == "__main__":
    main()