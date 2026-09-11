from __future__ import annotations

import argparse
import math
import sys
import warnings
from collections import Counter
from pathlib import Path
from typing import Any, Optional

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from db.database import get_connection

from strategy.bullish_v2 import (
    build_effective_foreign_daily_df,
    build_tdcc_market_context,
    evaluate_bullish_v2,
    extract_tdcc_v2_features,
)

from strategy.trade_plan_v2 import (
    evaluate_trade_plan_v2,
    round_to_tick,
)


# 目前 bullish_v2.py 某些舊 TDCC 日期格式
# 會觸發 pandas format warning。
# 已知不影響結果，這支大量回測先避免洗版。
warnings.filterwarnings(
    "ignore",
    message="Could not infer format.*",
    category=UserWarning,
)


HORIZONS = (
    5,
    10,
    20,
)

R_MULTIPLES = (
    1.5,
    2.0,
    2.5,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "StockWaveScanner "
            "Trade Plan v2 Historical Backtest"
        )
    )

    parser.add_argument(
        "--start",
        default=None,
        help=(
            "最早 signal date，"
            "例如 2026-01-01"
        ),
    )

    parser.add_argument(
        "--end",
        default=None,
        help=(
            "最晚 signal date，"
            "例如 2026-07-01"
        ),
    )

    parser.add_argument(
        "--dates",
        type=int,
        default=20,
        help=(
            "最多測試幾個 reference dates，"
            "預設 20"
        ),
    )

    parser.add_argument(
        "--step",
        type=int,
        default=5,
        help=(
            "每隔幾個市場交易日取一個 snapshot，"
            "預設 5"
        ),
    )

    parser.add_argument(
        "--entry-days",
        type=int,
        default=1,
        help=(
            "signal 後允許幾個個股交易日"
            "等待買進區被碰到。"
            "預設 1 = 只測明天"
        ),
    )

    parser.add_argument(
        "--min-score",
        type=int,
        default=65,
        help=(
            "candidate 最低 Bullish score，"
            "預設 65"
        ),
    )

    parser.add_argument(
        "--show",
        type=int,
        default=20,
        help=(
            "最後顯示幾筆實際成交 sample，"
            "預設 20"
        ),
    )

    parser.add_argument(
        "--save-csv",
        default=None,
        help=(
            "若指定路徑，將交易明細輸出 CSV。"
            "例如 outputs/backtest_v2.csv"
        ),
    )

    return parser.parse_args()


def safe_float(
    value: Any,
) -> Optional[float]:

    if value is None:
        return None

    try:
        result = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(result):
        return None

    return result


def prepare_price_df(
    df: pd.DataFrame,
) -> pd.DataFrame:

    result = df.copy()

    if result.empty:
        return result

    result[
        "trade_date"
    ] = (
        result[
            "trade_date"
        ]
        .astype(str)
    )

    for col in [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]:

        if col in result.columns:

            result[col] = (
                pd.to_numeric(
                    result[col],
                    errors="coerce",
                )
            )

    result = (
        result
        .dropna(
            subset=[
                "high",
                "low",
                "close",
            ]
        )
        .sort_values(
            "trade_date"
        )
        .drop_duplicates(
            subset=[
                "trade_date"
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    return result


def prepare_tdcc_df(
    df: pd.DataFrame,
) -> pd.DataFrame:

    result = df.copy()

    if result.empty:
        return result

    result[
        "data_date"
    ] = (
        result[
            "data_date"
        ]
        .astype(str)
    )

    for col in [
        "large_holder_pct",
        "retail_holder_pct",
    ]:

        result[col] = (
            pd.to_numeric(
                result[col],
                errors="coerce",
            )
        )

    return (
        result
        .sort_values(
            "data_date"
        )
        .drop_duplicates(
            subset=[
                "data_date"
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )


def load_active_stocks(
    conn,
):
    return pd.read_sql_query(
        """
        SELECT
            stock_id,
            stock_name,
            market

        FROM stocks

        WHERE
            is_active = 1

        ORDER BY
            market,
            stock_id
        """,
        conn,
    )


def load_all_market_dates(
    conn,
) -> list[str]:

    rows = conn.execute(
        """
        SELECT DISTINCT
            trade_date

        FROM daily_prices

        ORDER BY trade_date ASC
        """
    ).fetchall()

    return [
        str(
            row["trade_date"]
        )
        for row in rows
    ]


def load_price_full(
    conn,
    stock_id,
    market,
):
    return prepare_price_df(
        pd.read_sql_query(
            """
            SELECT
                trade_date,
                open,
                high,
                low,
                close,
                volume

            FROM daily_prices

            WHERE
                stock_id = ?
                AND market = ?

            ORDER BY
                trade_date ASC
            """,
            conn,
            params=(
                stock_id,
                market,
            ),
        )
    )


def load_tdcc_full(
    conn,
    stock_id,
):
    return prepare_tdcc_df(
        pd.read_sql_query(
            """
            SELECT
                data_date,
                large_holder_pct,
                retail_holder_pct

            FROM tdcc_holdings

            WHERE
                stock_id = ?

            ORDER BY
                data_date ASC
            """,
            conn,
            params=(
                stock_id,
            ),
        )
    )


def get_stock_history(
    conn,
    cache,
    stock_id,
    market,
):

    key = (
        stock_id,
        market,
    )

    if key not in cache:

        cache[key] = {
            "price":
                load_price_full(
                    conn,
                    stock_id,
                    market,
                ),

            "tdcc":
                load_tdcc_full(
                    conn,
                    stock_id,
                ),
        }

    return cache[key]


def select_reference_dates(
    market_dates: list[str],
    start_date: Optional[str],
    end_date: Optional[str],
    max_dates: int,
    step: int,
    forward_days: int,
) -> list[str]:

    if len(
        market_dates
    ) <= forward_days:

        raise RuntimeError(
            "市場歷史資料不足，"
            "無法建立 forward backtest。"
        )

    #
    # reference date 必須保留
    # 至少 forward_days 個未來市場交易日。
    #
    eligible = market_dates[
        :-forward_days
    ]

    if start_date:

        eligible = [
            x
            for x in eligible
            if x >= start_date
        ]

    if end_date:

        eligible = [
            x
            for x in eligible
            if x <= end_date
        ]

    if not eligible:

        raise RuntimeError(
            "找不到符合條件的 "
            "reference dates"
        )

    step = max(
        1,
        int(step),
    )

    max_dates = max(
        1,
        int(max_dates),
    )

    #
    # 從較新的歷史往回取，
    # 再排序回時間正序。
    #
    selected = (
        list(
            reversed(
                eligible
            )
        )[::step]
    )[
        :max_dates
    ]

    return sorted(
        selected
    )


def filter_price_as_of(
    price_df,
    reference_date,
):
    return (
        price_df[
            price_df[
                "trade_date"
            ]
            <= reference_date
        ]
        .copy()
        .reset_index(
            drop=True
        )
    )


def filter_tdcc_as_of(
    tdcc_df,
    reference_date,
):
    return (
        tdcc_df[
            tdcc_df[
                "data_date"
            ]
            <= reference_date
        ]
        .copy()
        .reset_index(
            drop=True
        )
    )


def is_candidate_as_of(
    price_df,
    tdcc_df,
    reference_date,
):

    price_as_of = (
        filter_price_as_of(
            price_df,
            reference_date,
        )
    )

    tdcc_as_of = (
        filter_tdcc_as_of(
            tdcc_df,
            reference_date,
        )
    )

    return (
        len(price_as_of) >= 30
        and
        tdcc_as_of[
            "data_date"
        ].nunique() >= 4
    )


def build_tdcc_context_for_date(
    conn,
    stocks,
    history_cache,
    reference_date,
):

    feature_rows = []

    candidates = []

    for _, stock in stocks.iterrows():

        stock_id = str(
            stock["stock_id"]
        )

        market = str(
            stock["market"]
        )

        history = (
            get_stock_history(
                conn,
                history_cache,
                stock_id,
                market,
            )
        )

        price_df = history[
            "price"
        ]

        tdcc_df = history[
            "tdcc"
        ]

        if not is_candidate_as_of(
            price_df,
            tdcc_df,
            reference_date,
        ):
            continue

        candidates.append(
            {
                "stock_id":
                    stock_id,

                "stock_name":
                    str(
                        stock[
                            "stock_name"
                        ]
                        or ""
                    ),

                "market":
                    market,
            }
        )

        tdcc_as_of = (
            filter_tdcc_as_of(
                tdcc_df,
                reference_date,
            )
        )

        feature = (
            extract_tdcc_v2_features(
                tdcc_as_of,
                reference_date=(
                    reference_date
                ),
            )
        )

        if (
            feature.get(
                "status"
            )
            == "READY"
        ):

            feature_rows.append(
                {
                    "stock_id":
                        stock_id,

                    "market":
                        market,

                    "large_delta":
                        feature.get(
                            "large_delta"
                        ),

                    "retail_delta":
                        feature.get(
                            "retail_delta"
                        ),
                }
            )

    if not feature_rows:

        return (
            candidates,
            None,
        )

    feature_df = pd.DataFrame(
        feature_rows
    )

    context = (
        build_tdcc_market_context(
            feature_df
        )
    )

    return (
        candidates,
        context,
    )


def ranges_intersect(
    day_low,
    day_high,
    zone_low,
    zone_high,
):
    return (
        day_high >= zone_low
        and
        day_low <= zone_high
    )


def calculate_fill_price(
    day_open,
    zone_low,
    zone_high,
):

    if day_open < zone_low:
        return zone_low

    if day_open > zone_high:
        return zone_high

    return day_open


def find_future_entry(
    full_price_df,
    signal_date,
    buy_zone_low,
    buy_zone_high,
    risk_price,
    entry_days,
):
    """
    T 日收盤得到 signal。

    從 T+1 開始最多等待 entry_days
    個「該股票自己的交易日」。

    買進區有被碰到才算成交。

    Daily OHLC 無法知道盤中先後順序。

    若買進當日同時也碰到 risk_price，
    為避免美化回測，
    標記 AMBIGUOUS_ENTRY_RISK，
    不算有效成交。
    """

    future = (
        full_price_df[
            full_price_df[
                "trade_date"
            ]
            > signal_date
        ]
        .head(
            max(
                1,
                entry_days,
            )
        )
        .copy()
    )

    if future.empty:

        return {
            "status":
                "NO_FUTURE_DATA",
        }

    for idx, row in future.iterrows():

        day_open = safe_float(
            row.get(
                "open"
            )
        )

        day_high = safe_float(
            row.get(
                "high"
            )
        )

        day_low = safe_float(
            row.get(
                "low"
            )
        )

        if (
            day_high is None
            or day_low is None
        ):
            continue

        if not ranges_intersect(
            day_low,
            day_high,
            buy_zone_low,
            buy_zone_high,
        ):
            continue

        trade_date = str(
            row[
                "trade_date"
            ]
        )

        #
        # 如果直接跳空到 risk 以下，
        # 原本交易結構已失效。
        #
        if (
            day_open is not None
            and day_open
            <= risk_price
        ):

            return {
                "status":
                    "GAP_BELOW_RISK",

                "entry_date":
                    trade_date,
            }

        #
        # Daily OHLC 不知道是
        # 先進買進區還是先碰 risk。
        #
        if day_low <= risk_price:

            return {
                "status":
                    "AMBIGUOUS_ENTRY_RISK",

                "entry_date":
                    trade_date,
            }

        if day_open is None:

            fill_price = (
                buy_zone_low
                + buy_zone_high
            ) / 2.0

        else:

            fill_price = (
                calculate_fill_price(
                    day_open,
                    buy_zone_low,
                    buy_zone_high,
                )
            )

        return {
            "status":
                "FILLED",

            "entry_date":
                trade_date,

            "fill_price":
                float(
                    fill_price
                ),
        }

    return {
        "status":
            "NO_FILL",
    }


def get_future_after_entry(
    full_price_df,
    entry_date,
):
    return (
        full_price_df[
            full_price_df[
                "trade_date"
            ]
            > entry_date
        ]
        .copy()
        .reset_index(
            drop=True
        )
    )


def forward_return(
    future_df,
    fill_price,
    horizon,
):

    if len(
        future_df
    ) < horizon:

        return None

    close_value = safe_float(
        future_df.iloc[
            horizon - 1
        ][
            "close"
        ]
    )

    if (
        close_value is None
        or fill_price <= 0
    ):
        return None

    return (
        close_value
        / fill_price
        - 1.0
    )


def calculate_mfe_mae(
    future_df,
    fill_price,
    horizon=20,
):

    temp = future_df.head(
        horizon
    )

    if temp.empty:
        return (
            None,
            None,
        )

    max_high = safe_float(
        temp[
            "high"
        ].max()
    )

    min_low = safe_float(
        temp[
            "low"
        ].min()
    )

    mfe = None
    mae = None

    if (
        max_high is not None
        and fill_price > 0
    ):

        mfe = (
            max_high
            / fill_price
            - 1.0
        )

    if (
        min_low is not None
        and fill_price > 0
    ):

        mae = (
            min_low
            / fill_price
            - 1.0
        )

    return (
        mfe,
        mae,
    )


def first_hit_outcome(
    future_df,
    risk_price,
    target_price,
    horizon=20,
):
    """
    從「進場日之後」開始判斷。

    不使用進場日的 high/low，
    因為 Daily OHLC 無法知道：
    先成交、先停損、還是先碰目標。

    若某個未來交易日同時碰 risk
    與 target，標記 AMBIGUOUS。
    """

    temp = future_df.head(
        horizon
    )

    for _, row in temp.iterrows():

        low = safe_float(
            row["low"]
        )

        high = safe_float(
            row["high"]
        )

        if (
            low is None
            or high is None
        ):
            continue

        risk_hit = (
            low
            <= risk_price
        )

        target_hit = (
            high
            >= target_price
        )

        if (
            risk_hit
            and target_hit
        ):

            return (
                "AMBIGUOUS"
            )

        if risk_hit:

            return (
                "RISK_FIRST"
            )

        if target_hit:

            return (
                "TARGET_FIRST"
            )

    return "NONE"


def score_band(
    score,
):

    if score >= 85:
        return "85+"

    if score >= 75:
        return "75-84"

    if score >= 65:
        return "65-74"

    return "<65"


def percent_text(
    value,
):
    if value is None:
        return "-"

    try:
        if pd.isna(value):
            return "-"
    except Exception:
        pass

    return (
        f"{float(value) * 100:.2f}%"
    )


def summarize_filled(
    df,
    title,
):

    print()
    print("=" * 88)
    print(title)
    print("=" * 88)

    if df.empty:

        print(
            "沒有有效成交樣本。"
        )

        return

    print(
        f"filled samples     : "
        f"{len(df)}"
    )

    for horizon in HORIZONS:

        col = (
            f"return_{horizon}d"
        )

        valid = (
            pd.to_numeric(
                df[col],
                errors="coerce",
            )
            .dropna()
        )

        if valid.empty:

            print(
                f"{horizon:>2}D return          : "
                "-"
            )

            continue

        win_rate = (
            valid.gt(0)
            .mean()
        )

        avg_return = (
            valid.mean()
        )

        median_return = (
            valid.median()
        )

        print(
            f"{horizon:>2}D win rate        : "
            f"{win_rate * 100:6.2f}%"
        )

        print(
            f"{horizon:>2}D avg return      : "
            f"{avg_return * 100:6.2f}%"
        )

        print(
            f"{horizon:>2}D median return   : "
            f"{median_return * 100:6.2f}%"
        )

    mfe = (
        pd.to_numeric(
            df[
                "mfe_20d"
            ],
            errors="coerce",
        )
        .dropna()
    )

    mae = (
        pd.to_numeric(
            df[
                "mae_20d"
            ],
            errors="coerce",
        )
        .dropna()
    )

    if not mfe.empty:

        print(
            "20D avg MFE         : "
            f"{mfe.mean() * 100:6.2f}%"
        )

        print(
            "20D median MFE      : "
            f"{mfe.median() * 100:6.2f}%"
        )

    if not mae.empty:

        print(
            "20D avg MAE         : "
            f"{mae.mean() * 100:6.2f}%"
        )

        print(
            "20D median MAE      : "
            f"{mae.median() * 100:6.2f}%"
        )

    for r_value in R_MULTIPLES:

        label = str(
            r_value
        ).replace(
            ".",
            "_",
        )

        col = (
            f"outcome_{label}r"
        )

        counts = (
            df[col]
            .fillna(
                "UNKNOWN"
            )
            .value_counts()
        )

        total = len(df)

        target_count = int(
            counts.get(
                "TARGET_FIRST",
                0,
            )
        )

        risk_count = int(
            counts.get(
                "RISK_FIRST",
                0,
            )
        )

        ambiguous_count = int(
            counts.get(
                "AMBIGUOUS",
                0,
            )
        )

        none_count = int(
            counts.get(
                "NONE",
                0,
            )
        )

        print()

        print(
            f"{r_value:.1f}R TARGET_FIRST     : "
            f"{target_count:5d} "
            f"({target_count / total * 100:6.2f}%)"
        )

        print(
            f"{r_value:.1f}R RISK_FIRST       : "
            f"{risk_count:5d} "
            f"({risk_count / total * 100:6.2f}%)"
        )

        print(
            f"{r_value:.1f}R AMBIGUOUS        : "
            f"{ambiguous_count:5d} "
            f"({ambiguous_count / total * 100:6.2f}%)"
        )

        print(
            f"{r_value:.1f}R NONE             : "
            f"{none_count:5d} "
            f"({none_count / total * 100:6.2f}%)"
        )


def print_signal_summary(
    signals_df,
):

    print()
    print("=" * 88)
    print("SIGNAL / ENTRY SUMMARY")
    print("=" * 88)

    if signals_df.empty:

        print(
            "沒有 candidate signals。"
        )

        return

    print(
        "candidate signals      :",
        len(signals_df),
    )

    counts = Counter(
        signals_df[
            "entry_result"
        ].fillna(
            "UNKNOWN"
        )
    )

    for key, value in (
        counts.most_common()
    ):

        print(
            f"{key:<24}"
            f"{int(value):>6}"
        )

    filled_count = int(
        (
            signals_df[
                "entry_result"
            ]
            == "FILLED"
        ).sum()
    )

    print()

    print(
        "fill rate              : "
        f"{filled_count / len(signals_df) * 100:.2f}%"
    )


def print_group_summary(
    filled_df,
    group_col,
    title,
):

    print()
    print("=" * 88)
    print(title)
    print("=" * 88)

    if filled_df.empty:
        print(
            "沒有有效成交資料。"
        )
        return

    groups = (
        filled_df[
            group_col
        ]
        .dropna()
        .unique()
        .tolist()
    )

    if group_col == "score_band":

        preferred = [
            "85+",
            "75-84",
            "65-74",
            "<65",
        ]

    elif group_col == "stage":

        preferred = [
            "SETUP",
            "READY",
            "BREAKOUT",
            "MOMENTUM",
        ]

    else:

        preferred = groups

    for group in preferred:

        subset = (
            filled_df[
                filled_df[
                    group_col
                ]
                == group
            ]
        )

        if subset.empty:
            continue

        r10 = (
            pd.to_numeric(
                subset[
                    "return_10d"
                ],
                errors="coerce",
            )
            .dropna()
        )

        r20 = (
            pd.to_numeric(
                subset[
                    "return_20d"
                ],
                errors="coerce",
            )
            .dropna()
        )

        outcome = (
            subset[
                "outcome_2_0r"
            ]
        )

        target_2r = int(
            (
                outcome
                == "TARGET_FIRST"
            ).sum()
        )

        risk_2r = int(
            (
                outcome
                == "RISK_FIRST"
            ).sum()
        )

        print()

        print(
            f"{group}"
        )

        print(
            f"  samples       : "
            f"{len(subset)}"
        )

        if not r10.empty:

            print(
                f"  10D win       : "
                f"{r10.gt(0).mean() * 100:.2f}%"
            )

            print(
                f"  10D avg       : "
                f"{r10.mean() * 100:.2f}%"
            )

        if not r20.empty:

            print(
                f"  20D win       : "
                f"{r20.gt(0).mean() * 100:.2f}%"
            )

            print(
                f"  20D avg       : "
                f"{r20.mean() * 100:.2f}%"
            )

        print(
            f"  2R first      : "
            f"{target_2r / len(subset) * 100:.2f}%"
        )

        print(
            f"  Risk first    : "
            f"{risk_2r / len(subset) * 100:.2f}%"
        )


def forward_from_signal_close(
    full_price_df,
    signal_date,
    signal_close,
    horizon,
):

    future = (
        full_price_df[
            full_price_df[
                "trade_date"
            ]
            > signal_date
        ]
        .head(
            horizon
        )
    )

    if len(
        future
    ) < horizon:

        return None

    future_close = safe_float(
        future.iloc[
            horizon - 1
        ]["close"]
    )

    if (
        future_close is None
        or signal_close <= 0
    ):
        return None

    return (
        future_close
        / signal_close
        - 1.0
    )


def main():
    args = parse_args()

    conn = get_connection()

    try:

        stocks = load_active_stocks(
            conn
        )

        market_dates = (
            load_all_market_dates(
                conn
            )
        )

        reference_dates = (
            select_reference_dates(
                market_dates=market_dates,
                start_date=args.start,
                end_date=args.end,
                max_dates=args.dates,
                step=args.step,
                forward_days=20,
            )
        )

        print("=" * 88)
        print(
            "StockWaveScanner "
            "Trade Plan v2 Backtest"
        )
        print("=" * 88)

        print(
            "active stocks       :",
            len(stocks),
        )

        print(
            "DB first date       :",
            market_dates[0],
        )

        print(
            "DB latest date      :",
            market_dates[-1],
        )

        print(
            "reference dates     :",
            len(reference_dates),
        )

        print(
            "first reference     :",
            reference_dates[0],
        )

        print(
            "last reference      :",
            reference_dates[-1],
        )

        print(
            "snapshot step       :",
            args.step,
        )

        print(
            "entry wait days     :",
            args.entry_days,
        )

        print(
            "minimum score       :",
            args.min_score,
        )

        print()

        print(
            "回測語意："
            "T 日收盤產生訊號，"
            "最快 T+1 才能成交。"
        )

        history_cache = {}

        signal_rows = []

        extended_rows = []

        errors = []

        for date_index, reference_date in enumerate(
            reference_dates,
            start=1,
        ):

            print()
            print(
                "-" * 88
            )

            print(
                f"[{date_index}/"
                f"{len(reference_dates)}] "
                f"{reference_date}"
            )

            (
                candidates,
                tdcc_context,
            ) = (
                build_tdcc_context_for_date(
                    conn=conn,
                    stocks=stocks,
                    history_cache=(
                        history_cache
                    ),
                    reference_date=(
                        reference_date
                    ),
                )
            )

            print(
                "  candidates      :",
                len(candidates),
            )

            if (
                not candidates
                or tdcc_context is None
            ):

                print(
                    "  skip: TDCC context "
                    "not ready"
                )

                continue

            date_signals = 0
            date_fills = 0
            date_extended = 0

            for candidate in candidates:

                stock_id = (
                    candidate[
                        "stock_id"
                    ]
                )

                stock_name = (
                    candidate[
                        "stock_name"
                    ]
                )

                market = (
                    candidate[
                        "market"
                    ]
                )

                try:

                    history = (
                        get_stock_history(
                            conn,
                            history_cache,
                            stock_id,
                            market,
                        )
                    )

                    full_price_df = (
                        history[
                            "price"
                        ]
                    )

                    full_tdcc_df = (
                        history[
                            "tdcc"
                        ]
                    )

                    price_as_of = (
                        filter_price_as_of(
                            full_price_df,
                            reference_date,
                        )
                    )

                    tdcc_as_of = (
                        filter_tdcc_as_of(
                            full_tdcc_df,
                            reference_date,
                        )
                    )

                    foreign_df = (
                        build_effective_foreign_daily_df(
                            conn=conn,
                            stock_id=stock_id,
                            market=market,
                            price_df=(
                                price_as_of
                            ),
                            reference_date=(
                                reference_date
                            ),
                        )
                    )

                    bullish = (
                        evaluate_bullish_v2(
                            price_df=(
                                price_as_of
                            ),
                            foreign_daily_df=(
                                foreign_df
                            ),
                            tdcc_df=(
                                tdcc_as_of
                            ),
                            tdcc_market_context=(
                                tdcc_context
                            ),
                            reference_date=(
                                reference_date
                            ),
                        )
                    )

                    if (
                        bullish.get(
                            "data_status"
                        )
                        != "READY"
                    ):
                        continue

                    score = int(
                        bullish.get(
                            "score",
                            0,
                        )
                    )

                    stage = str(
                        bullish.get(
                            "stage",
                            ""
                        )
                    )

                    state = str(
                        bullish.get(
                            "state",
                            ""
                        )
                    )

                    signal_close = (
                        safe_float(
                            price_as_of[
                                "close"
                            ].iloc[-1]
                        )
                    )

                    #
                    # 額外保存：
                    # 高分 EXTENDED 若直接追價，
                    # 後續報酬如何。
                    #
                    if (
                        stage
                        == "EXTENDED"
                        and score >= 75
                        and signal_close
                        is not None
                    ):

                        extended_rows.append(
                            {
                                "reference_date":
                                    reference_date,

                                "stock_id":
                                    stock_id,

                                "stock_name":
                                    stock_name,

                                "market":
                                    market,

                                "score":
                                    score,

                                "signal_close":
                                    signal_close,

                                "return_5d":
                                    forward_from_signal_close(
                                        full_price_df,
                                        reference_date,
                                        signal_close,
                                        5,
                                    ),

                                "return_10d":
                                    forward_from_signal_close(
                                        full_price_df,
                                        reference_date,
                                        signal_close,
                                        10,
                                    ),

                                "return_20d":
                                    forward_from_signal_close(
                                        full_price_df,
                                        reference_date,
                                        signal_close,
                                        20,
                                    ),
                            }
                        )

                        date_extended += 1

                    trade_plan = (
                        evaluate_trade_plan_v2(
                            price_df=(
                                price_as_of
                            ),
                            bullish_result=(
                                bullish
                            ),
                            reference_date=(
                                reference_date
                            ),
                        )
                    )

                    if (
                        trade_plan.get(
                            "status"
                        )
                        != "READY"
                    ):
                        continue

                    if (
                        score
                        < args.min_score
                    ):
                        continue

                    if not bool(
                        trade_plan.get(
                            "candidate_eligible",
                            False,
                        )
                    ):
                        continue

                    date_signals += 1

                    buy_zone_low = (
                        safe_float(
                            trade_plan.get(
                                "buy_zone_low"
                            )
                        )
                    )

                    buy_zone_high = (
                        safe_float(
                            trade_plan.get(
                                "buy_zone_high"
                            )
                        )
                    )

                    risk_price = (
                        safe_float(
                            trade_plan.get(
                                "risk_price"
                            )
                        )
                    )

                    if (
                        buy_zone_low
                        is None
                        or buy_zone_high
                        is None
                        or risk_price
                        is None
                    ):
                        continue

                    entry = (
                        find_future_entry(
                            full_price_df=(
                                full_price_df
                            ),
                            signal_date=(
                                reference_date
                            ),
                            buy_zone_low=(
                                buy_zone_low
                            ),
                            buy_zone_high=(
                                buy_zone_high
                            ),
                            risk_price=(
                                risk_price
                            ),
                            entry_days=(
                                args.entry_days
                            ),
                        )
                    )

                    row = {
                        "reference_date":
                            reference_date,

                        "stock_id":
                            stock_id,

                        "stock_name":
                            stock_name,

                        "market":
                            market,

                        "score":
                            score,

                        "score_band":
                            score_band(
                                score
                            ),

                        "state":
                            state,

                        "stage":
                            stage,

                        "signal_close":
                            signal_close,

                        "buy_zone_low":
                            buy_zone_low,

                        "buy_zone_high":
                            buy_zone_high,

                        "risk_price":
                            risk_price,

                        "plan_risk_pct":
                            trade_plan.get(
                                "risk_pct"
                            ),

                        "entry_result":
                            entry.get(
                                "status"
                            ),

                        "entry_date":
                            entry.get(
                                "entry_date"
                            ),

                        "fill_price":
                            entry.get(
                                "fill_price"
                            ),

                        "target_1_5r":
                            None,

                        "target_2_0r":
                            None,

                        "target_2_5r":
                            None,

                        "return_5d":
                            None,

                        "return_10d":
                            None,

                        "return_20d":
                            None,

                        "mfe_20d":
                            None,

                        "mae_20d":
                            None,

                        "outcome_1_5r":
                            None,

                        "outcome_2_0r":
                            None,

                        "outcome_2_5r":
                            None,
                    }

                    if (
                        entry.get(
                            "status"
                        )
                        != "FILLED"
                    ):

                        signal_rows.append(
                            row
                        )

                        continue

                    fill_price = float(
                        entry[
                            "fill_price"
                        ]
                    )

                    entry_date = str(
                        entry[
                            "entry_date"
                        ]
                    )

                    #
                    # 如果實際成交價
                    # 已低於風險價，
                    # 不視為正常交易。
                    #
                    if (
                        fill_price
                        <= risk_price
                    ):

                        row[
                            "entry_result"
                        ] = (
                            "INVALID_FILL_RISK"
                        )

                        signal_rows.append(
                            row
                        )

                        continue

                    date_fills += 1

                    actual_risk = (
                        fill_price
                        - risk_price
                    )

                    target_prices = {}

                    for r_value in (
                        R_MULTIPLES
                    ):

                        target = (
                            fill_price
                            + actual_risk
                            * r_value
                        )

                        target = (
                            round_to_tick(
                                target,
                                "up",
                            )
                        )

                        target_prices[
                            r_value
                        ] = target

                    row[
                        "target_1_5r"
                    ] = target_prices[
                        1.5
                    ]

                    row[
                        "target_2_0r"
                    ] = target_prices[
                        2.0
                    ]

                    row[
                        "target_2_5r"
                    ] = target_prices[
                        2.5
                    ]

                    future_df = (
                        get_future_after_entry(
                            full_price_df,
                            entry_date,
                        )
                    )

                    for horizon in (
                        HORIZONS
                    ):

                        row[
                            f"return_{horizon}d"
                        ] = (
                            forward_return(
                                future_df,
                                fill_price,
                                horizon,
                            )
                        )

                    (
                        mfe,
                        mae,
                    ) = (
                        calculate_mfe_mae(
                            future_df,
                            fill_price,
                            horizon=20,
                        )
                    )

                    row[
                        "mfe_20d"
                    ] = mfe

                    row[
                        "mae_20d"
                    ] = mae

                    for r_value in (
                        R_MULTIPLES
                    ):

                        label = str(
                            r_value
                        ).replace(
                            ".",
                            "_",
                        )

                        row[
                            f"outcome_{label}r"
                        ] = (
                            first_hit_outcome(
                                future_df=(
                                    future_df
                                ),
                                risk_price=(
                                    risk_price
                                ),
                                target_price=(
                                    target_prices[
                                        r_value
                                    ]
                                ),
                                horizon=20,
                            )
                        )

                    signal_rows.append(
                        row
                    )

                except Exception as exc:

                    errors.append(
                        {
                            "reference_date":
                                reference_date,

                            "stock_id":
                                stock_id,

                            "stock_name":
                                stock_name,

                            "market":
                                market,

                            "error":
                                repr(
                                    exc
                                ),
                        }
                    )

            print(
                "  eligible signals:",
                date_signals,
            )

            print(
                "  next-entry fills:",
                date_fills,
            )

            print(
                "  score>=75 EXTENDED:",
                date_extended,
            )

        signals_df = (
            pd.DataFrame(
                signal_rows
            )
        )

        extended_df = (
            pd.DataFrame(
                extended_rows
            )
        )

        print()
        print("=" * 88)
        print("BACKTEST SUMMARY")
        print("=" * 88)

        print(
            "reference dates       :",
            len(reference_dates),
        )

        print(
            "candidate signal rows :",
            len(signals_df),
        )

        print(
            "errors                :",
            len(errors),
        )

        if signals_df.empty:

            print(
                "沒有符合條件的 candidate signals。"
            )

            return

        print_signal_summary(
            signals_df
        )

        filled_df = (
            signals_df[
                signals_df[
                    "entry_result"
                ]
                == "FILLED"
            ]
            .copy()
        )

        summarize_filled(
            filled_df,
            (
                "ALL VALID FILLED TRADES "
                f"(score >= {args.min_score})"
            ),
        )

        print_group_summary(
            filled_df,
            "score_band",
            "RESULT BY BULLISH SCORE",
        )

        print_group_summary(
            filled_df,
            "stage",
            "RESULT BY STAGE",
        )

        #
        # Score >= 75
        #
        strong = (
            filled_df[
                filled_df[
                    "score"
                ]
                >= 75
            ]
            .copy()
        )

        summarize_filled(
            strong,
            (
                "STRONG SAMPLE "
                "(Bullish Score >= 75)"
            ),
        )

        #
        # READY >=75
        #
        ready_strong = (
            filled_df[
                (
                    filled_df[
                        "score"
                    ]
                    >= 75
                )
                &
                (
                    filled_df[
                        "stage"
                    ]
                    == "READY"
                )
            ]
            .copy()
        )

        summarize_filled(
            ready_strong,
            (
                "READY + Score >= 75"
            ),
        )

        #
        # BREAKOUT >=75
        #
        breakout_strong = (
            filled_df[
                (
                    filled_df[
                        "score"
                    ]
                    >= 75
                )
                &
                (
                    filled_df[
                        "stage"
                    ]
                    == "BREAKOUT"
                )
            ]
            .copy()
        )

        summarize_filled(
            breakout_strong,
            (
                "BREAKOUT + Score >= 75"
            ),
        )

        #
        # EXTENDED：假設直接追 signal close，
        # 只比較未來報酬。
        #
        print()
        print("=" * 88)
        print(
            "EXTENDED >=75 "
            "- IF CHASED AT SIGNAL CLOSE"
        )
        print("=" * 88)

        if extended_df.empty:

            print(
                "沒有 EXTENDED >=75 樣本。"
            )

        else:

            print(
                "samples:",
                len(
                    extended_df
                ),
            )

            for horizon in HORIZONS:

                col = (
                    f"return_{horizon}d"
                )

                valid = (
                    pd.to_numeric(
                        extended_df[
                            col
                        ],
                        errors="coerce",
                    )
                    .dropna()
                )

                if valid.empty:
                    continue

                print(
                    f"{horizon:>2}D win rate      : "
                    f"{valid.gt(0).mean() * 100:.2f}%"
                )

                print(
                    f"{horizon:>2}D avg return    : "
                    f"{valid.mean() * 100:.2f}%"
                )

                print(
                    f"{horizon:>2}D median return : "
                    f"{valid.median() * 100:.2f}%"
                )

        #
        # 顯示實際成交 sample
        #
        if not filled_df.empty:

            show_n = max(
                1,
                int(
                    args.show
                ),
            )

            sample = (
                filled_df
                .sort_values(
                    by=[
                        "score",
                        "reference_date",
                        "stock_id",
                    ],
                    ascending=[
                        False,
                        False,
                        True,
                    ],
                )
                .head(
                    show_n
                )
                .copy()
            )

            print()
            print("=" * 88)
            print(
                f"TOP {show_n} FILLED SAMPLE"
            )
            print("=" * 88)

            display_cols = [
                "reference_date",
                "stock_id",
                "stock_name",
                "market",
                "score",
                "stage",
                "signal_close",
                "buy_zone_low",
                "buy_zone_high",
                "entry_date",
                "fill_price",
                "risk_price",
                "target_1_5r",
                "target_2_0r",
                "target_2_5r",
                "return_5d",
                "return_10d",
                "return_20d",
                "mfe_20d",
                "mae_20d",
                "outcome_2_0r",
            ]

            print(
                sample[
                    display_cols
                ].to_string(
                    index=False,
                    justify="left",
                )
            )

        #
        # Optional CSV
        #
        if args.save_csv:

            output_path = Path(
                args.save_csv
            )

            if not output_path.is_absolute():

                output_path = (
                    ROOT
                    / output_path
                )

            output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            signals_df.to_csv(
                output_path,
                index=False,
                encoding="utf-8-sig",
            )

            print()
            print(
                "CSV saved:",
                output_path,
            )

        if errors:

            print()
            print("=" * 88)
            print("FIRST ERRORS")
            print("=" * 88)

            for item in errors[:20]:

                print(
                    f"{item['reference_date']} "
                    f"{item['stock_id']} "
                    f"{item['stock_name']} "
                    f"{item['market']} "
                    f"-> "
                    f"{item['error']}"
                )

        print()
        print("=" * 88)
        print("INTERPRETATION NOTES")
        print("=" * 88)

        print(
            "1. Signal 使用 T 日收盤資料。"
        )

        print(
            "2. 最快 T+1 才允許成交，"
            "避免 look-ahead bias。"
        )

        print(
            "3. 預設只等待下一個個股交易日，"
            "符合『今晚選、明天買』情境。"
        )

        print(
            "4. 買進日若同時碰到 risk，"
            "Daily OHLC 無法判斷先後，"
            "保守標記為 AMBIGUOUS_ENTRY_RISK。"
        )

        print(
            "5. Risk / Target first-hit "
            "從進場後下一交易日開始計算。"
        )

        print(
            "6. 1.5R / 2R / 2.5R "
            "使用實際模擬成交價重新計算。"
        )

        print(
            "7. EXTENDED 區塊是在研究："
            "若當時直接追 signal close，"
            "後續表現如何。"
        )

        print(
            "8. 本程式不修改 production，"
            "不寫入 DB。"
        )

        print()
        print("完成。")

    finally:

        conn.close()


if __name__ == "__main__":
    main()