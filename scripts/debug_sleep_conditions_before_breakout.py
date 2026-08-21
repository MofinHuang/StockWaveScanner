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


OFFSETS = [
    1,
    3,
    5,
    10,
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


def _evaluate_sleep_at_offset(
    price_df: pd.DataFrame,
    offset: int,
) -> dict | None:
    """
    offset=1
        表示突破日前 1 個交易日。

    offset=3
        表示突破日前 3 個交易日。

    回傳該 snapshot 的 Sleep result。
    """
    latest_index = (
        len(price_df)
        - 1
    )

    target_index = (
        latest_index
        - offset
    )

    if target_index < 0:
        return None

    historical_df = (
        price_df
        .iloc[
            : target_index + 1
        ]
        .copy()
    )

    result = evaluate_sleep(
        historical_df
    )

    result = result.copy()

    result[
        "_target_index"
    ] = target_index

    result[
        "_target_date"
    ] = price_df.iloc[
        target_index
    ]["trade_date"]

    return result


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

            price_df = (
                _load_price(
                    conn,
                    stock_id,
                    market,
                )
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

            latest = (
                price_df.iloc[-1]
            )

            row = {
                "stock_id":
                    stock_id,

                "stock_name":
                    stock_name,

                "market":
                    market,

                "breakout_date":
                    latest[
                        "trade_date"
                    ],

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

            for offset in OFFSETS:
                sleep_result = (
                    _evaluate_sleep_at_offset(
                        price_df,
                        offset,
                    )
                )

                prefix = (
                    f"t_minus_{offset}"
                )

                if sleep_result is None:
                    row[
                        f"{prefix}_available"
                    ] = False

                    row[
                        f"{prefix}_status"
                    ] = None

                    row[
                        f"{prefix}_score"
                    ] = None

                    row[
                        f"{prefix}_date"
                    ] = None

                    row[
                        f"{prefix}_price"
                    ] = None

                    row[
                        f"{prefix}_volatility"
                    ] = None

                    row[
                        f"{prefix}_volume"
                    ] = None

                    row[
                        f"{prefix}_ma_distance"
                    ] = None

                    row[
                        f"{prefix}_volatility_ratio"
                    ] = None

                    row[
                        f"{prefix}_volume_ratio"
                    ] = None

                    continue

                conditions = (
                    _condition_map(
                        sleep_result
                    )
                )

                metrics = (
                    sleep_result.get(
                        "metrics",
                        {},
                    )
                )

                row[
                    f"{prefix}_available"
                ] = True

                row[
                    f"{prefix}_status"
                ] = sleep_result.get(
                    "status"
                )

                row[
                    f"{prefix}_score"
                ] = sleep_result.get(
                    "score"
                )

                row[
                    f"{prefix}_date"
                ] = sleep_result.get(
                    "_target_date"
                )

                row[
                    f"{prefix}_price"
                ] = conditions.get(
                    "價格接近 MA20",
                    False,
                )

                row[
                    f"{prefix}_volatility"
                ] = conditions.get(
                    "波動收斂",
                    False,
                )

                row[
                    f"{prefix}_volume"
                ] = conditions.get(
                    "成交量沉澱",
                    False,
                )

                row[
                    f"{prefix}_ma_distance"
                ] = metrics.get(
                    "ma_distance_pct"
                )

                row[
                    f"{prefix}_volatility_ratio"
                ] = metrics.get(
                    "volatility_ratio"
                )

                row[
                    f"{prefix}_volume_ratio"
                ] = metrics.get(
                    "volume_ratio"
                )

            breakout_rows.append(
                row
            )

            print(
                "[BREAKOUT PASS] "
                f"{market} "
                f"{stock_id} "
                f"{stock_name}"
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

    df = pd.DataFrame(
        breakout_rows
    )

    section(
        "BREAKOUT -> SLEEP CONDITION SNAPSHOTS"
    )

    print(
        "Breakout PASS stocks =",
        len(df),
    )

    if df.empty:
        print(
            "[WARN] 沒有 Breakout PASS 股票"
        )
        return

    # =====================================
    # Aggregate condition counts by offset
    # =====================================

    section(
        "CONDITION PASS COUNTS BY OFFSET"
    )

    for offset in OFFSETS:
        prefix = (
            f"t_minus_{offset}"
        )

        available = df[
            df[
                f"{prefix}_available"
            ]
        ].copy()

        total_available = len(
            available
        )

        print()
        print(
            f"T-{offset}"
        )

        print(
            "  available snapshots =",
            total_available,
        )

        if total_available == 0:
            continue

        price_count = int(
            available[
                f"{prefix}_price"
            ].sum()
        )

        volatility_count = int(
            available[
                f"{prefix}_volatility"
            ].sum()
        )

        volume_count = int(
            available[
                f"{prefix}_volume"
            ].sum()
        )

        full_pass_count = int(
            (
                available[
                    f"{prefix}_status"
                ]
                == "PASS"
            ).sum()
        )

        print(
            "  價格接近 MA20 =",
            f"{price_count} / "
            f"{total_available}",
        )

        print(
            "  波動收斂      =",
            f"{volatility_count} / "
            f"{total_available}",
        )

        print(
            "  成交量沉澱    =",
            f"{volume_count} / "
            f"{total_available}",
        )

        print(
            "  Sleep PASS    =",
            f"{full_pass_count} / "
            f"{total_available}",
        )

    # =====================================
    # Sleep score distribution
    # =====================================

    section(
        "SLEEP SCORE DISTRIBUTION BY OFFSET"
    )

    for offset in OFFSETS:
        prefix = (
            f"t_minus_{offset}"
        )

        series = df[
            f"{prefix}_score"
        ].dropna()

        print()
        print(
            f"T-{offset}"
        )

        if series.empty:
            print(
                "  (none)"
            )
            continue

        for score, count in sorted(
            Counter(
                series.astype(
                    int
                ).tolist()
            ).items()
        ):
            print(
                f"  score "
                f"{score:2d} = "
                f"{count}"
            )

    # =====================================
    # Which single condition blocks score 20
    # =====================================

    section(
        "SCORE 20 BLOCKER ANALYSIS"
    )

    for offset in OFFSETS:
        prefix = (
            f"t_minus_{offset}"
        )

        score_20 = df[
            df[
                f"{prefix}_score"
            ]
            == 20
        ].copy()

        print()
        print(
            f"T-{offset} "
            f"score=20 stocks = "
            f"{len(score_20)}"
        )

        blockers = Counter()

        for _, row in (
            score_20.iterrows()
        ):
            if not bool(
                row[
                    f"{prefix}_price"
                ]
            ):
                blockers[
                    "價格接近 MA20"
                ] += 1

            if not bool(
                row[
                    f"{prefix}_volatility"
                ]
            ):
                blockers[
                    "波動收斂"
                ] += 1

            if not bool(
                row[
                    f"{prefix}_volume"
                ]
            ):
                blockers[
                    "成交量沉澱"
                ] += 1

        if not blockers:
            print(
                "  (none)"
            )
        else:
            for name, count in (
                blockers.items()
            ):
                print(
                    f"  {name:12s} = "
                    f"{count}"
                )

    # =====================================
    # Never Sleep PASS:
    # how close were they?
    # =====================================

    section(
        "NEVER-SLEEP STOCKS CONDITION PROFILE"
    )

    never_sleep_mask = pd.Series(
        True,
        index=df.index,
    )

    for offset in OFFSETS:
        prefix = (
            f"t_minus_{offset}"
        )

        never_sleep_mask &= (
            df[
                f"{prefix}_status"
            ]
            != "PASS"
        )

    never_sleep = df[
        never_sleep_mask
    ].copy()

    print(
        "Never Sleep PASS across "
        "T-1/T-3/T-5/T-10 =",
        len(never_sleep),
    )

    for offset in OFFSETS:
        prefix = (
            f"t_minus_{offset}"
        )

        available = never_sleep[
            never_sleep[
                f"{prefix}_available"
            ]
        ]

        print()
        print(
            f"T-{offset}"
        )

        if available.empty:
            print(
                "  (none)"
            )
            continue

        print(
            "  price pass      =",
            int(
                available[
                    f"{prefix}_price"
                ].sum()
            ),
            "/",
            len(available),
        )

        print(
            "  volatility pass =",
            int(
                available[
                    f"{prefix}_volatility"
                ].sum()
            ),
            "/",
            len(available),
        )

        print(
            "  volume pass     =",
            int(
                available[
                    f"{prefix}_volume"
                ].sum()
            ),
            "/",
            len(available),
        )

        score_counts = Counter(
            available[
                f"{prefix}_score"
            ]
            .dropna()
            .astype(int)
            .tolist()
        )

        print(
            "  score counts    =",
            dict(
                sorted(
                    score_counts.items()
                )
            ),
        )

    # =====================================
    # All breakout stocks detailed view
    # =====================================

    section(
        "ALL BREAKOUT PASS STOCK DETAILS"
    )

    display_columns = [
        "stock_id",
        "stock_name",
        "market",
        "breakout_date",
    ]

    for offset in OFFSETS:
        prefix = (
            f"t_minus_{offset}"
        )

        display_columns.extend(
            [
                f"{prefix}_date",
                f"{prefix}_score",
                f"{prefix}_price",
                f"{prefix}_volatility",
                f"{prefix}_volume",
                f"{prefix}_ma_distance",
                f"{prefix}_volatility_ratio",
                f"{prefix}_volume_ratio",
            ]
        )

    print(
        df[
            display_columns
        ]
        .to_string(
            index=False
        )
    )

    # =====================================
    # T-1 detail
    # =====================================

    section(
        "T-1 DETAIL"
    )

    t1_columns = [
        "stock_id",
        "stock_name",
        "market",
        "t_minus_1_date",
        "t_minus_1_score",
        "t_minus_1_price",
        "t_minus_1_volatility",
        "t_minus_1_volume",
        "t_minus_1_ma_distance",
        "t_minus_1_volatility_ratio",
        "t_minus_1_volume_ratio",
        "breakout_pct",
        "breakout_volume_ratio",
    ]

    print(
        df[
            t1_columns
        ]
        .sort_values(
            by=[
                "t_minus_1_score",
                "t_minus_1_ma_distance",
                "stock_id",
            ],
            ascending=[
                False,
                True,
                True,
            ],
        )
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