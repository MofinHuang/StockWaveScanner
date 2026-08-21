from datetime import date

import pandas as pd

from strategy.foreign_data import (
    get_effective_foreign_net,
)


def empty_weekly_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "week_start",
            "week_end",
            "foreign_buy",
            "foreign_sell",
            "foreign_net",
            "trading_days",
        ]
    )


def build_weekly_foreign(
    institutional_df: pd.DataFrame,
    reference_date=None,
) -> pd.DataFrame:
    """
    將每日法人資料聚合成完整週資料。

    這是既有資料路徑，保留給：
    - TWSE
    - 已有完整 institutional row 的資料
    - 既有呼叫端

    完整週定義：
    - 每週一為 week_start
    - 每週日為 week_end
    - reference_date 所在的本週一律排除
    - 過去已結束的週視為完整週
    - 不強制 trading_days == 5，
      因為台股可能遇到國定假日或休市

    reference_date:
        預設今天。
        測試時可傳入指定日期。
    """

    if institutional_df.empty:
        return empty_weekly_dataframe()

    if reference_date is None:
        reference_date = date.today()

    reference_date = pd.Timestamp(
        reference_date
    ).normalize()

    df = institutional_df.copy()

    required_columns = {
        "trade_date",
        "foreign_buy",
        "foreign_sell",
        "foreign_net",
    }

    missing_columns = (
        required_columns
        - set(df.columns)
    )

    if missing_columns:
        raise ValueError(
            "institutional_df 缺少必要欄位："
            + ", ".join(
                sorted(missing_columns)
            )
        )

    df["trade_date"] = pd.to_datetime(
        df["trade_date"],
        errors="coerce",
    )

    df = df.dropna(
        subset=["trade_date"]
    )

    if df.empty:
        return empty_weekly_dataframe()

    numeric_columns = [
        "foreign_buy",
        "foreign_sell",
        "foreign_net",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=numeric_columns
    )

    if df.empty:
        return empty_weekly_dataframe()

    df = df.sort_values(
        "trade_date"
    )

    # 每週一
    df["week_start"] = (
        df["trade_date"]
        - pd.to_timedelta(
            df["trade_date"].dt.weekday,
            unit="D",
        )
    ).dt.normalize()

    # 每週日
    df["week_end"] = (
        df["week_start"]
        + pd.Timedelta(days=6)
    )

    current_week_start = (
        reference_date
        - pd.Timedelta(
            days=reference_date.weekday()
        )
    )

    # 排除目前尚未完成的本週
    df = df[
        df["week_start"]
        < current_week_start
    ].copy()

    if df.empty:
        return empty_weekly_dataframe()

    weekly = (
        df
        .groupby(
            [
                "week_start",
                "week_end",
            ],
            as_index=False,
        )
        .agg(
            foreign_buy=(
                "foreign_buy",
                "sum",
            ),
            foreign_sell=(
                "foreign_sell",
                "sum",
            ),
            foreign_net=(
                "foreign_net",
                "sum",
            ),
            trading_days=(
                "trade_date",
                "nunique",
            ),
        )
        .sort_values(
            "week_start"
        )
        .reset_index(
            drop=True
        )
    )

    return weekly


def build_weekly_foreign_effective(
    conn,
    stock_id: str,
    market: str,
    reference_date=None,
) -> pd.DataFrame:
    """
    使用 effective foreign_net 建立週資料。

    重要語意：

    - 使用「該股票自己的 daily_prices 日期」
      作為需要 Foreign coverage 的交易日集合。

    - 不使用市場全體交易日強迫每檔股票
      每天都必須有資料。

    原因：
    個股可能有：
    - 停牌
    - 暫停交易
    - 個別無行情日

    原策略本身也不要求 trading_days == 5。

    TPEx：
    - STORED:
        使用官方 institutional row
    - ZERO_INFERRED:
        該股票當日有 daily_price
        + qfiiStat crawl SUCCESS
        + institutional row 缺失
        => foreign_net = 0
    - INSUFFICIENT_DATA:
        該股票有 daily_price，
        但沒有足夠 Foreign 證據

    reference_date 所在週仍一律排除。
    """

    if reference_date is None:
        reference_date = date.today()

    reference_date = pd.Timestamp(
        reference_date
    ).normalize()

    current_week_start = (
        reference_date
        - pd.Timedelta(
            days=reference_date.weekday()
        )
    )

    # =====================================
    # 關鍵修正：
    #
    # 使用「這檔股票自己的交易日期」
    # 而不是整個市場所有交易日期。
    # =====================================

    price_rows = conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM daily_prices
        WHERE stock_id = ?
          AND market = ?
          AND trade_date < ?
        ORDER BY trade_date ASC
        """,
        (
            stock_id,
            market,
            current_week_start.strftime(
                "%Y-%m-%d"
            ),
        ),
    ).fetchall()

    if not price_rows:
        return empty_weekly_dataframe()

    stock_dates = [
        str(row["trade_date"])
        for row in price_rows
    ]

    start_date = stock_dates[0]
    end_date = stock_dates[-1]

    effective_rows = (
        get_effective_foreign_net(
            conn=conn,
            stock_id=stock_id,
            market=market,
            start_date=start_date,
            end_date=end_date,
        )
    )

    effective_by_date = {
        row.trade_date: row
        for row in effective_rows
    }

    # =====================================
    # 真正 STORED row
    #
    # 只有 STORED 時 buy / sell 才已知。
    # ZERO_INFERRED 只能知道 net=0。
    # =====================================

    institutional_rows = conn.execute(
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
          AND trade_date >= ?
          AND trade_date <= ?
        ORDER BY trade_date ASC
        """,
        (
            stock_id,
            market,
            start_date,
            end_date,
        ),
    ).fetchall()

    institutional_by_date = {
        str(row["trade_date"]): row
        for row in institutional_rows
    }

    # =====================================
    # 個股自己的交易 calendar
    # =====================================

    calendar_df = pd.DataFrame(
        {
            "trade_date":
                pd.to_datetime(
                    stock_dates,
                    errors="coerce",
                )
        }
    )

    calendar_df = calendar_df.dropna(
        subset=[
            "trade_date",
        ]
    )

    if calendar_df.empty:
        return empty_weekly_dataframe()

    calendar_df[
        "week_start"
    ] = (
        calendar_df[
            "trade_date"
        ]
        - pd.to_timedelta(
            calendar_df[
                "trade_date"
            ].dt.weekday,
            unit="D",
        )
    ).dt.normalize()

    calendar_df[
        "week_end"
    ] = (
        calendar_df[
            "week_start"
        ]
        + pd.Timedelta(
            days=6
        )
    )

    weekly_rows = []

    for (
        week_start,
        week_end,
    ), week_df in calendar_df.groupby(
        [
            "week_start",
            "week_end",
        ],
        sort=True,
    ):

        week_dates = [
            value.strftime(
                "%Y-%m-%d"
            )
            for value
            in week_df[
                "trade_date"
            ].tolist()
        ]

        foreign_net_values = []

        foreign_buy_values = []
        foreign_sell_values = []

        has_zero_inferred = False
        has_insufficient = False

        stored_days = 0
        zero_inferred_days = 0

        for trade_date_text in week_dates:

            effective = (
                effective_by_date.get(
                    trade_date_text
                )
            )

            # =================================
            # 該股票明明有 daily_price，
            # 卻連 effective row 都不存在，
            # 才是真正異常 / insufficient。
            # =================================

            if effective is None:
                has_insufficient = True
                continue

            if (
                effective.status
                == "INSUFFICIENT_DATA"
                or effective.foreign_net
                is None
            ):
                has_insufficient = True
                continue

            foreign_net_values.append(
                int(
                    effective.foreign_net
                )
            )

            # =================================
            # ZERO_INFERRED
            # =================================

            if (
                effective.status
                == "ZERO_INFERRED"
            ):
                has_zero_inferred = True
                zero_inferred_days += 1
                continue

            # =================================
            # STORED
            # =================================

            if (
                effective.status
                != "STORED"
            ):
                raise RuntimeError(
                    "未知 effective foreign "
                    "status："
                    f"{effective.status!r}"
                )

            stored_days += 1

            institutional = (
                institutional_by_date.get(
                    trade_date_text
                )
            )

            if institutional is None:
                has_insufficient = True
                continue

            foreign_buy_values.append(
                int(
                    institutional[
                        "foreign_buy"
                    ]
                )
            )

            foreign_sell_values.append(
                int(
                    institutional[
                        "foreign_sell"
                    ]
                )
            )

        trading_days = len(
            week_dates
        )

        # =====================================
        # foreign_net
        # =====================================

        if (
            has_insufficient
            or len(
                foreign_net_values
            )
            != trading_days
        ):
            weekly_foreign_net = pd.NA

        else:
            weekly_foreign_net = sum(
                foreign_net_values
            )

        # =====================================
        # foreign_buy / sell
        #
        # 只要含 ZERO_INFERRED，
        # 真正 buy/sell 就未知。
        # =====================================

        if (
            has_insufficient
            or has_zero_inferred
            or len(
                foreign_buy_values
            )
            != trading_days
            or len(
                foreign_sell_values
            )
            != trading_days
        ):
            weekly_foreign_buy = pd.NA
            weekly_foreign_sell = pd.NA

        else:
            weekly_foreign_buy = sum(
                foreign_buy_values
            )

            weekly_foreign_sell = sum(
                foreign_sell_values
            )

        weekly_rows.append(
            {
                "week_start":
                    week_start,

                "week_end":
                    week_end,

                "foreign_buy":
                    weekly_foreign_buy,

                "foreign_sell":
                    weekly_foreign_sell,

                "foreign_net":
                    weekly_foreign_net,

                "trading_days":
                    trading_days,
            }
        )

    if not weekly_rows:
        return empty_weekly_dataframe()

    return (
        pd.DataFrame(
            weekly_rows
        )
        .sort_values(
            "week_start"
        )
        .reset_index(
            drop=True
        )
    )


def _optional_int(
    value,
):
    """
    foreign_buy / foreign_sell 在
    TPEx ZERO_INFERRED 週可能未知。

    UI / result 必須保留 None，
    不可自行補 0。
    """
    if pd.isna(value):
        return None

    return int(value)


def evaluate_foreign(
    weekly_df: pd.DataFrame,
    required_weeks: int = 3,
    max_jump_ratio: float = 2.5,
):
    """
    外資布局策略。

    規則：
    1. 最近 required_weeks 個完整週
       每週 foreign_net > 0
    2. foreign_net 逐週增加
    3. 相鄰週增加倍率不可 > max_jump_ratio

    評分：
    - 連續買超：10 分
    - 逐週增加：5 分
    - 沒有突然暴增：5 分

    總分：
        20 分

    注意：
    TPEx effective data 中，
    foreign_buy / foreign_sell
    可能因 ZERO_INFERRED 而為 NA。

    Foreign /20 評分只依 foreign_net，
    因此不影響評分。

    foreign_net 若為 NA，
    才是真正 INSUFFICIENT_DATA。
    """

    result = {
        "status": "INSUFFICIENT_DATA",
        "passed": False,
        "score": 0,
        "reason": "",
        "required_weeks": required_weeks,
        "max_jump_ratio": max_jump_ratio,
        "all_positive": False,
        "growing": False,
        "stable": False,
        "weeks": [],
    }

    if weekly_df.empty:
        result["reason"] = (
            "沒有完整週外資資料"
        )

        return result

    recent = (
        weekly_df
        .tail(required_weeks)
        .copy()
        .reset_index(drop=True)
    )

    if len(recent) < required_weeks:
        result["reason"] = (
            f"外資完整週資料不足："
            f"目前 {len(recent)} 週，"
            f"需要 {required_weeks} 週"
        )

        return result

    #
    # effective data 的真正缺資料，
    # 會以 foreign_net = NA 表示。
    #
    missing_net = (
        recent["foreign_net"]
        .isna()
    )

    if missing_net.any():
        missing_count = int(
            missing_net.sum()
        )

        result["reason"] = (
            f"最近 {required_weeks} 個完整週"
            f"有 {missing_count} 週 "
            "foreign_net 資料不足"
        )

        return result

    values = [
        int(value)
        for value
        in recent[
            "foreign_net"
        ].tolist()
    ]

    all_positive = all(
        value > 0
        for value in values
    )

    #
    # 這裡刻意保留現有策略行為。
    #
    # 原程式只有 current < previous
    # 才判定 growing=False，
    # 因此相等目前仍視為 growing。
    #
    # 本階段不偷偷改評分規則。
    #
    growing = True
    stable = True

    week_details = []

    for i, row in recent.iterrows():
        current_value = int(
            row["foreign_net"]
        )

        ratio = None

        if i > 0:
            previous_value = int(
                recent.iloc[i - 1][
                    "foreign_net"
                ]
            )

            if (
                current_value
                < previous_value
            ):
                growing = False

            if previous_value > 0:
                ratio = (
                    current_value
                    / previous_value
                )

                if (
                    ratio
                    > max_jump_ratio
                ):
                    stable = False

            else:
                # 若前一週不是正買超，
                # 本身已無法符合穩定布局邏輯。
                stable = False

        week_details.append(
            {
                "week_start":
                    row["week_start"],

                "week_end":
                    row["week_end"],

                "foreign_buy":
                    _optional_int(
                        row[
                            "foreign_buy"
                        ]
                    ),

                "foreign_sell":
                    _optional_int(
                        row[
                            "foreign_sell"
                        ]
                    ),

                "foreign_net":
                    current_value,

                "trading_days":
                    int(
                        row[
                            "trading_days"
                        ]
                    ),

                "ratio_to_previous":
                    ratio,
            }
        )

    score = 0

    if all_positive:
        score += 10

    if growing:
        score += 5

    if stable:
        score += 5

    passed = (
        all_positive
        and growing
        and stable
    )

    result["status"] = (
        "PASS"
        if passed
        else "FAIL"
    )

    result["passed"] = passed
    result["score"] = score

    result["all_positive"] = (
        all_positive
    )

    result["growing"] = (
        growing
    )

    result["stable"] = (
        stable
    )

    result["weeks"] = (
        week_details
    )

    if passed:
        result["reason"] = (
            f"最近 {required_weeks} 個完整週"
            "皆為外資買超，"
            "買超逐週增加，"
            f"且單週增加倍率未超過 "
            f"{max_jump_ratio:.1f} 倍"
        )

    else:
        reasons = []

        if not all_positive:
            reasons.append(
                f"最近 {required_weeks} 週"
                "未全部買超"
            )

        if not growing:
            reasons.append(
                "外資買超未逐週增加"
            )

        if not stable:
            reasons.append(
                f"單週增加倍率超過 "
                f"{max_jump_ratio:.1f} 倍"
            )

        result["reason"] = (
            "；".join(reasons)
        )

    return result