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


VOLATILITY_THRESHOLDS = [
    0.80,
    0.85,
    0.90,
    0.95,
    1.00,
    1.10,
]

OFFSETS = [
    1,
    3,
    5,
    10,
]

MA_DISTANCE_PCT = 0.05
VOLUME_RATIO_MAX = 0.80


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


def _snapshot_df(
    price_df: pd.DataFrame,
    offset: int,
) -> pd.DataFrame | None:
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

    return (
        price_df
        .iloc[
            : target_index + 1
        ]
        .copy()
    )


def _evaluate_sleep_with_threshold(
    price_df: pd.DataFrame,
    volatility_threshold: float,
) -> dict:
    return evaluate_sleep(
        price_df,
        ma_distance_pct=(
            MA_DISTANCE_PCT
        ),
        volatility_ratio_max=(
            volatility_threshold
        ),
        volume_ratio_max=(
            VOLUME_RATIO_MAX
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

        breakout_stocks = []

        total = len(
            stocks
        )

        # =====================================
        # 先找目前 Breakout PASS 股票
        # =====================================

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

            breakout_result = (
                evaluate_breakout(
                    price_df
                )
            )

            if (
                breakout_result.get(
                    "status"
                )
                == "PASS"
            ):
                breakout_stocks.append(
                    {
                        "stock_id":
                            stock_id,

                        "stock_name":
                            stock_name,

                        "market":
                            market,

                        "price_df":
                            price_df,

                        "breakout_date":
                            price_df.iloc[
                                -1
                            ][
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
                    }
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

    section(
        "BREAKOUT STOCKS"
    )

    print(
        "Breakout PASS stocks =",
        len(
            breakout_stocks
        ),
    )

    if not breakout_stocks:
        print(
            "[WARN] 沒有 Breakout PASS 股票"
        )
        return

    # =====================================
    # sensitivity matrix
    # =====================================

    results = []

    for stock in (
        breakout_stocks
    ):
        price_df = stock[
            "price_df"
        ]

        for offset in OFFSETS:
            snapshot = _snapshot_df(
                price_df,
                offset,
            )

            if snapshot is None:
                continue

            target_date = (
                snapshot.iloc[-1][
                    "trade_date"
                ]
            )

            for threshold in (
                VOLATILITY_THRESHOLDS
            ):
                sleep_result = (
                    _evaluate_sleep_with_threshold(
                        snapshot,
                        threshold,
                    )
                )

                metrics = (
                    sleep_result.get(
                        "metrics",
                        {},
                    )
                )

                conditions = {
                    str(item["name"]):
                        bool(
                            item["passed"]
                        )
                    for item
                    in sleep_result.get(
                        "conditions",
                        []
                    )
                }

                results.append(
                    {
                        "stock_id":
                            stock[
                                "stock_id"
                            ],

                        "stock_name":
                            stock[
                                "stock_name"
                            ],

                        "market":
                            stock[
                                "market"
                            ],

                        "breakout_date":
                            stock[
                                "breakout_date"
                            ],

                        "offset":
                            offset,

                        "snapshot_date":
                            target_date,

                        "volatility_threshold":
                            threshold,

                        "sleep_status":
                            sleep_result.get(
                                "status"
                            ),

                        "sleep_score":
                            sleep_result.get(
                                "score"
                            ),

                        "price_pass":
                            conditions.get(
                                "價格接近 MA20",
                                False,
                            ),

                        "volatility_pass":
                            conditions.get(
                                "波動收斂",
                                False,
                            ),

                        "volume_pass":
                            conditions.get(
                                "成交量沉澱",
                                False,
                            ),

                        "ma_distance":
                            metrics.get(
                                "ma_distance_pct"
                            ),

                        "volatility_ratio":
                            metrics.get(
                                "volatility_ratio"
                            ),

                        "volume_ratio":
                            metrics.get(
                                "volume_ratio"
                            ),

                        "breakout_pct":
                            stock[
                                "breakout_pct"
                            ],

                        "breakout_volume_ratio":
                            stock[
                                "breakout_volume_ratio"
                            ],
                    }
                )

    df = pd.DataFrame(
        results
    )

    # =====================================
    # PASS matrix
    # =====================================

    section(
        "SLEEP PASS MATRIX"
    )

    total_breakout = len(
        breakout_stocks
    )

    header = (
        "threshold"
        + "".join(
            f"   T-{offset:>2}"
            for offset in OFFSETS
        )
    )

    print(
        header
    )

    for threshold in (
        VOLATILITY_THRESHOLDS
    ):
        values = []

        for offset in OFFSETS:
            subset = df[
                (
                    df[
                        "volatility_threshold"
                    ]
                    == threshold
                )
                & (
                    df[
                        "offset"
                    ]
                    == offset
                )
            ]

            passed = int(
                (
                    subset[
                        "sleep_status"
                    ]
                    == "PASS"
                ).sum()
            )

            values.append(
                passed
            )

        print(
            f"{threshold:8.2f}"
            + "".join(
                f"   {value:2d}/{total_breakout:2d}"
                for value in values
            )
        )

    # =====================================
    # PASS percentage matrix
    # =====================================

    section(
        "SLEEP PASS PERCENTAGE MATRIX"
    )

    print(
        header
    )

    for threshold in (
        VOLATILITY_THRESHOLDS
    ):
        values = []

        for offset in OFFSETS:
            subset = df[
                (
                    df[
                        "volatility_threshold"
                    ]
                    == threshold
                )
                & (
                    df[
                        "offset"
                    ]
                    == offset
                )
            ]

            passed = int(
                (
                    subset[
                        "sleep_status"
                    ]
                    == "PASS"
                ).sum()
            )

            pct = (
                passed
                / total_breakout
                * 100
            )

            values.append(
                pct
            )

        print(
            f"{threshold:8.2f}"
            + "".join(
                f"   {value:5.1f}%"
                for value in values
            )
        )

    # =====================================
    # Score >= 20 sensitivity
    # =====================================

    section(
        "SLEEP SCORE >= 20 MATRIX"
    )

    print(
        header
    )

    for threshold in (
        VOLATILITY_THRESHOLDS
    ):
        values = []

        for offset in OFFSETS:
            subset = df[
                (
                    df[
                        "volatility_threshold"
                    ]
                    == threshold
                )
                & (
                    df[
                        "offset"
                    ]
                    == offset
                )
            ]

            count = int(
                (
                    subset[
                        "sleep_score"
                    ]
                    >= 20
                ).sum()
            )

            values.append(
                count
            )

        print(
            f"{threshold:8.2f}"
            + "".join(
                f"   {value:2d}/{total_breakout:2d}"
                for value in values
            )
        )

    # =====================================
    # Incremental gains vs 0.80
    # =====================================

    section(
        "INCREMENTAL PASS GAIN VS 0.80"
    )

    baseline_threshold = (
        VOLATILITY_THRESHOLDS[0]
    )

    for offset in OFFSETS:
        baseline_subset = df[
            (
                df[
                    "volatility_threshold"
                ]
                == baseline_threshold
            )
            & (
                df[
                    "offset"
                ]
                == offset
            )
        ]

        baseline_pass = int(
            (
                baseline_subset[
                    "sleep_status"
                ]
                == "PASS"
            ).sum()
        )

        print()
        print(
            f"T-{offset}"
        )

        for threshold in (
            VOLATILITY_THRESHOLDS
        ):
            subset = df[
                (
                    df[
                        "volatility_threshold"
                    ]
                    == threshold
                )
                & (
                    df[
                        "offset"
                    ]
                    == offset
                )
            ]

            passed = int(
                (
                    subset[
                        "sleep_status"
                    ]
                    == "PASS"
                ).sum()
            )

            print(
                f"  threshold "
                f"{threshold:.2f} "
                f"PASS={passed:2d} "
                f"gain={passed - baseline_pass:+d}"
            )

    # =====================================
    # T-1 detail by threshold
    # =====================================

    section(
        "T-1 PASS STOCKS BY THRESHOLD"
    )

    for threshold in (
        VOLATILITY_THRESHOLDS
    ):
        subset = df[
            (
                df[
                    "volatility_threshold"
                ]
                == threshold
            )
            & (
                df[
                    "offset"
                ]
                == 1
            )
            & (
                df[
                    "sleep_status"
                ]
                == "PASS"
            )
        ].copy()

        print()
        print(
            f"threshold = "
            f"{threshold:.2f}"
        )

        print(
            "PASS count =",
            len(subset),
        )

        if subset.empty:
            print(
                "(none)"
            )
            continue

        print(
            subset[
                [
                    "stock_id",
                    "stock_name",
                    "market",
                    "ma_distance",
                    "volatility_ratio",
                    "volume_ratio",
                    "breakout_pct",
                    "breakout_volume_ratio",
                ]
            ]
            .sort_values(
                by=[
                    "volatility_ratio",
                    "stock_id",
                ]
            )
            .to_string(
                index=False
            )
        )

    # =====================================
    # Newly admitted stocks
    # =====================================

    section(
        "NEWLY ADMITTED VS 0.80"
    )

    for offset in OFFSETS:
        base = df[
            (
                df[
                    "volatility_threshold"
                ]
                == 0.80
            )
            & (
                df[
                    "offset"
                ]
                == offset
            )
            & (
                df[
                    "sleep_status"
                ]
                == "PASS"
            )
        ]

        base_ids = set(
            base[
                "stock_id"
            ].tolist()
        )

        print()
        print(
            f"T-{offset}"
        )

        for threshold in (
            VOLATILITY_THRESHOLDS[1:]
        ):
            subset = df[
                (
                    df[
                        "volatility_threshold"
                    ]
                    == threshold
                )
                & (
                    df[
                        "offset"
                    ]
                    == offset
                )
                & (
                    df[
                        "sleep_status"
                    ]
                    == "PASS"
                )
            ]

            new_rows = subset[
                ~subset[
                    "stock_id"
                ].isin(
                    base_ids
                )
            ].copy()

            print(
                f"  threshold "
                f"{threshold:.2f} "
                f"new={len(new_rows)}"
            )

            if not new_rows.empty:
                names = [
                    (
                        f"{row.stock_id} "
                        f"{row.stock_name}"
                    )
                    for row
                    in new_rows.itertuples()
                ]

                print(
                    "   ",
                    ", ".join(
                        names
                    ),
                )

    # =====================================
    # Distribution of actual volatility
    # among Breakout PASS stocks
    # =====================================

    section(
        "ACTUAL VOLATILITY RATIO DISTRIBUTION"
    )

    for offset in OFFSETS:
        subset = (
            df[
                (
                    df[
                        "offset"
                    ]
                    == offset
                )
                & (
                    df[
                        "volatility_threshold"
                    ]
                    == 0.80
                )
            ]
            .copy()
        )

        values = pd.to_numeric(
            subset[
                "volatility_ratio"
            ],
            errors="coerce",
        ).dropna()

        print()
        print(
            f"T-{offset}"
        )

        if values.empty:
            print(
                "(none)"
            )
            continue

        print(
            "  min    =",
            round(
                float(
                    values.min()
                ),
                4,
            ),
        )

        print(
            "  p25    =",
            round(
                float(
                    values.quantile(
                        0.25
                    )
                ),
                4,
            ),
        )

        print(
            "  median =",
            round(
                float(
                    values.median()
                ),
                4,
            ),
        )

        print(
            "  p75    =",
            round(
                float(
                    values.quantile(
                        0.75
                    )
                ),
                4,
            ),
        )

        print(
            "  max    =",
            round(
                float(
                    values.max()
                ),
                4,
            ),
        )

    # =====================================
    # score distribution at each threshold
    # =====================================

    section(
        "T-1 SCORE DISTRIBUTION"
    )

    for threshold in (
        VOLATILITY_THRESHOLDS
    ):
        subset = df[
            (
                df[
                    "offset"
                ]
                == 1
            )
            & (
                df[
                    "volatility_threshold"
                ]
                == threshold
            )
        ]

        counts = Counter(
            subset[
                "sleep_score"
            ]
            .dropna()
            .astype(int)
            .tolist()
        )

        print(
            f"{threshold:.2f} =",
            dict(
                sorted(
                    counts.items()
                )
            ),
        )

    print()
    print("=" * 72)
    print("DONE")
    print("=" * 72)


if __name__ == "__main__":
    main()