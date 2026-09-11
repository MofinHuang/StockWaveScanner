from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from strategy.foreign_data import get_effective_foreign_net


BULLISH_V2_MAX_SCORE = 100

TREND_MAX_SCORE = 25
SETUP_MAX_SCORE = 20
MOMENTUM_MAX_SCORE = 20
FOREIGN_MAX_SCORE = 15
TDCC_MAX_SCORE = 20

MIN_PRICE_ROWS = 30
FOREIGN_LOOKBACK_DAYS = 10
TDCC_REQUIRED_DATES = 4


def _to_timestamp(value) -> Optional[pd.Timestamp]:
    if value is None:
        return None

    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None

    return pd.Timestamp(ts).normalize()


def _score_by_upper_bound(
    value: Optional[float],
    rules: list[tuple[float, int]],
    default: int = 0,
) -> int:
    if value is None or pd.isna(value):
        return default

    for upper_bound, score in rules:
        if value <= upper_bound:
            return score

    return default


def _prepare_price_df(
    price_df: pd.DataFrame,
    reference_date=None,
) -> tuple[pd.DataFrame, Optional[str]]:
    required_columns = {
        "trade_date",
        "high",
        "low",
        "close",
        "volume",
    }

    if (
        price_df is None
        or not isinstance(price_df, pd.DataFrame)
        or price_df.empty
    ):
        return pd.DataFrame(), "沒有日線資料"

    missing_columns = required_columns - set(price_df.columns)
    if missing_columns:
        return (
            pd.DataFrame(),
            "日線資料缺少必要欄位："
            + ", ".join(sorted(missing_columns)),
        )

    df = price_df.copy()
    df["trade_date"] = pd.to_datetime(
        df["trade_date"],
        errors="coerce",
    )

    for column in [
        "high",
        "low",
        "close",
        "volume",
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    ref = _to_timestamp(reference_date)
    if reference_date is not None and ref is None:
        return pd.DataFrame(), "reference_date 無法解析"

    if ref is not None:
        df = df[
            df["trade_date"] <= ref
        ]

    df = (
        df
        .dropna(
            subset=[
                "trade_date",
                "high",
                "low",
                "close",
                "volume",
            ]
        )
        .sort_values("trade_date")
        .drop_duplicates(
            subset=["trade_date"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    df = df[
        (df["close"] > 0)
        & (df["high"] >= df["low"])
        & (df["volume"] >= 0)
    ].reset_index(drop=True)

    if len(df) < MIN_PRICE_ROWS:
        return (
            df,
            f"日線資料不足：目前 {len(df)} 日，"
            f"至少需要 {MIN_PRICE_ROWS} 日",
        )

    return df, None


def evaluate_price_v2(
    price_df: pd.DataFrame,
    reference_date=None,
) -> dict[str, Any]:
    """
    Bullish v2 的價格模組：

    - Trend /25
    - Setup / Compression /20
    - Momentum / Breakout /20

    只負責價格與成交量，不讀 Foreign / TDCC。
    """
    result: dict[str, Any] = {
        "status": "INSUFFICIENT_DATA",
        "trend_score": 0,
        "setup_score": 0,
        "momentum_score": 0,
        "price_score": 0,
        "reason": "",
        "conditions": [],
        "metrics": {},
        "risk_flags": [],
    }

    df, error = _prepare_price_df(
        price_df,
        reference_date=reference_date,
    )
    if error is not None:
        result["reason"] = error
        return result

    df["ma5"] = (
        df["close"]
        .rolling(5)
        .mean()
    )
    df["ma10"] = (
        df["close"]
        .rolling(10)
        .mean()
    )
    df["ma20"] = (
        df["close"]
        .rolling(20)
        .mean()
    )
    df["range_pct"] = (
        (df["high"] - df["low"])
        / df["close"]
    )

    latest = df.iloc[-1]

    latest_close = float(latest["close"])
    latest_high = float(latest["high"])
    latest_low = float(latest["low"])
    latest_volume = float(latest["volume"])

    ma5 = float(latest["ma5"])
    ma10 = float(latest["ma10"])
    ma20 = float(latest["ma20"])

    # T-5 的 MA20。
    ma20_t5 = float(df.iloc[-6]["ma20"])

    if (
        pd.isna(ma5)
        or pd.isna(ma10)
        or pd.isna(ma20)
        or pd.isna(ma20_t5)
        or ma20 <= 0
        or ma20_t5 <= 0
    ):
        result["reason"] = "均線資料不足"
        return result

    history20 = df.iloc[-21:-1]
    history10 = df.iloc[-11:-1]

    previous_20d_high = float(
        history20["high"].max()
    )
    previous_20d_low = float(
        history20["low"].min()
    )
    previous_10d_high = float(
        history10["high"].max()
    )

    previous_20d_avg_volume = float(
        history20["volume"].mean()
    )

    close_t10 = float(
        df.iloc[-11]["close"]
    )
    return_10d = (
        latest_close / close_t10 - 1
        if close_t10 > 0
        else None
    )

    ma20_slope_5d = (
        ma20 / ma20_t5 - 1
    )

    if previous_20d_high > previous_20d_low:
        price_position_20d = (
            (latest_close - previous_20d_low)
            / (
                previous_20d_high
                - previous_20d_low
            )
        )
    else:
        price_position_20d = None

    ma_distance_abs = abs(
        latest_close / ma20 - 1
    )
    close_vs_ma20 = (
        latest_close / ma20 - 1
    )

    recent10 = df.tail(10)
    baseline20 = df.iloc[-30:-10]

    recent_volatility = float(
        recent10["range_pct"].mean()
    )
    baseline_volatility = float(
        baseline20["range_pct"].mean()
    )
    volatility_ratio = (
        recent_volatility
        / baseline_volatility
        if baseline_volatility > 0
        else None
    )

    recent_volume = float(
        recent10["volume"].mean()
    )
    baseline_volume = float(
        baseline20["volume"].mean()
    )
    setup_volume_ratio = (
        recent_volume
        / baseline_volume
        if baseline_volume > 0
        else None
    )

    breakout_volume_ratio = (
        latest_volume
        / previous_20d_avg_volume
        if previous_20d_avg_volume > 0
        else None
    )

    daily_range = (
        latest_high - latest_low
    )
    if daily_range > 0:
        close_from_high_ratio = (
            latest_high - latest_close
        ) / daily_range
    elif latest_close == latest_high:
        close_from_high_ratio = 0.0
    else:
        close_from_high_ratio = None

    # ==================================================
    # A. Trend /25
    # ==================================================

    if latest_close >= ma20:
        a1 = 7
    elif latest_close >= ma20 * 0.98:
        a1 = 4
    elif latest_close >= ma20 * 0.95:
        a1 = 2
    else:
        a1 = 0

    if ma20_slope_5d > 0.01:
        a2 = 6
    elif ma20_slope_5d >= 0:
        a2 = 4
    elif ma20_slope_5d > -0.01:
        a2 = 2
    else:
        a2 = 0

    a3 = 4 if ma5 > ma10 else 0

    if price_position_20d is None:
        a4 = 0
    elif price_position_20d >= 0.75:
        a4 = 4
    elif price_position_20d >= 0.50:
        a4 = 3
    elif price_position_20d >= 0.25:
        a4 = 1
    else:
        a4 = 0

    a5 = (
        4
        if (
            return_10d is not None
            and return_10d > 0
        )
        else 0
    )

    trend_score = (
        a1 + a2 + a3 + a4 + a5
    )

    # ==================================================
    # B. Setup / Compression /20
    # ==================================================

    b1 = _score_by_upper_bound(
        ma_distance_abs,
        [
            (0.03, 6),
            (0.05, 4),
            (0.08, 2),
        ],
    )

    b2 = _score_by_upper_bound(
        volatility_ratio,
        [
            (0.80, 7),
            (0.90, 5),
            (1.00, 3),
            (1.10, 1),
        ],
    )

    b3 = _score_by_upper_bound(
        setup_volume_ratio,
        [
            (0.80, 7),
            (0.90, 5),
            (1.00, 3),
            (1.10, 1),
        ],
    )

    setup_score = b1 + b2 + b3

    # ==================================================
    # C. Momentum / Breakout /20
    # ==================================================

    c1 = (
        3
        if latest_close
        > previous_10d_high
        else 0
    )

    c2 = (
        8
        if latest_close
        > previous_20d_high
        else 0
    )

    if breakout_volume_ratio is None:
        c3 = 0
    elif breakout_volume_ratio >= 1.50:
        c3 = 5
    elif breakout_volume_ratio >= 1.20:
        c3 = 3
    elif breakout_volume_ratio >= 1.00:
        c3 = 1
    else:
        c3 = 0

    if close_from_high_ratio is None:
        c4 = 0
    elif close_from_high_ratio <= 0.25:
        c4 = 4
    elif close_from_high_ratio <= 0.40:
        c4 = 2
    else:
        c4 = 0

    momentum_score = (
        c1 + c2 + c3 + c4
    )

    # ==================================================
    # Risk flags
    # ==================================================

    risk_flags: list[str] = []

    extended = (
        latest_close / ma20
        > 1.15
    )
    if extended:
        risk_flags.append(
            "EXTENDED"
        )

    if (
        close_from_high_ratio is not None
        and close_from_high_ratio > 0.50
    ):
        risk_flags.append(
            "UPPER_WICK_RISK"
        )

    structure_break = (
        latest_close < ma20 * 0.95
        and ma20_slope_5d < 0
    )
    if structure_break:
        risk_flags.append(
            "STRUCTURE_BREAK"
        )

    breakout_10d = (
        latest_close
        > previous_10d_high
    )
    breakout_20d = (
        latest_close
        > previous_20d_high
    )

    distance_to_20d_high = (
        latest_close
        / previous_20d_high
        - 1
        if previous_20d_high > 0
        else None
    )

    # ==================================================
    # Stage
    #
    # Score = 有多強
    # Stage = 現在走到哪
    # ==================================================

    if extended:
        stage = "EXTENDED"
    elif breakout_20d:
        stage = "BREAKOUT"
    elif (
        trend_score >= 14
        and latest_close
        >= previous_20d_high * 0.97
        and (
            setup_score >= 10
            or momentum_score >= 7
        )
    ):
        stage = "READY"
    elif (
        trend_score >= 14
        and setup_score >= 10
    ):
        stage = "SETUP"
    elif (
        trend_score >= 14
        and momentum_score >= 7
    ):
        stage = "MOMENTUM"
    elif setup_score >= 10:
        stage = "BASE"
    else:
        stage = "WEAK"

    result["status"] = "READY"
    result["trend_score"] = trend_score
    result["setup_score"] = setup_score
    result["momentum_score"] = (
        momentum_score
    )
    result["price_score"] = (
        trend_score
        + setup_score
        + momentum_score
    )
    result["stage"] = stage
    result["risk_flags"] = risk_flags

    result["metrics"] = {
        "trade_date": str(
            pd.Timestamp(
                latest["trade_date"]
            ).date()
        ),
        "latest_close": latest_close,
        "latest_high": latest_high,
        "latest_low": latest_low,
        "latest_volume": latest_volume,
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma20_t5": ma20_t5,
        "ma20_slope_5d":
            ma20_slope_5d,
        "close_vs_ma20":
            close_vs_ma20,
        "ma_distance_abs":
            ma_distance_abs,
        "return_10d": return_10d,
        "previous_10d_high":
            previous_10d_high,
        "previous_20d_high":
            previous_20d_high,
        "previous_20d_low":
            previous_20d_low,
        "price_position_20d":
            price_position_20d,
        "recent_volatility":
            recent_volatility,
        "baseline_volatility":
            baseline_volatility,
        "volatility_ratio":
            volatility_ratio,
        "recent_volume":
            recent_volume,
        "baseline_volume":
            baseline_volume,
        "setup_volume_ratio":
            setup_volume_ratio,
        "previous_20d_avg_volume":
            previous_20d_avg_volume,
        "breakout_volume_ratio":
            breakout_volume_ratio,
        "close_from_high_ratio":
            close_from_high_ratio,
        "distance_to_20d_high":
            distance_to_20d_high,
        "breakout_10d":
            breakout_10d,
        "breakout_20d":
            breakout_20d,
    }

    result["conditions"] = [
        {
            "code": "A1_CLOSE_VS_MA20",
            "name": "收盤相對 MA20",
            "score": a1,
            "max_score": 7,
        },
        {
            "code": "A2_MA20_SLOPE",
            "name": "MA20 方向",
            "score": a2,
            "max_score": 6,
        },
        {
            "code": "A3_MA5_GT_MA10",
            "name": "MA5 高於 MA10",
            "score": a3,
            "max_score": 4,
        },
        {
            "code": "A4_PRICE_POSITION",
            "name": "20 日價格位置",
            "score": a4,
            "max_score": 4,
        },
        {
            "code": "A5_RETURN_10D",
            "name": "10 日報酬方向",
            "score": a5,
            "max_score": 4,
        },
        {
            "code": "B1_NEAR_MA20",
            "name": "價格接近 MA20",
            "score": b1,
            "max_score": 6,
        },
        {
            "code": "B2_VOLATILITY",
            "name": "波動收斂",
            "score": b2,
            "max_score": 7,
        },
        {
            "code": "B3_VOLUME_CONTRACTION",
            "name": "成交量沉澱",
            "score": b3,
            "max_score": 7,
        },
        {
            "code": "C1_BREAK_10D_HIGH",
            "name": "突破前 10 日高點",
            "score": c1,
            "max_score": 3,
        },
        {
            "code": "C2_BREAK_20D_HIGH",
            "name": "突破前 20 日高點",
            "score": c2,
            "max_score": 8,
        },
        {
            "code": "C3_VOLUME_EXPANSION",
            "name": "突破量能",
            "score": c3,
            "max_score": 5,
        },
        {
            "code": "C4_CLOSE_NEAR_HIGH",
            "name": "收盤接近日高",
            "score": c4,
            "max_score": 4,
        },
    ]

    result["reason"] = (
        f"Trend {trend_score}/25, "
        f"Setup {setup_score}/20, "
        f"Momentum {momentum_score}/20, "
        f"Stage={stage}"
    )

    return result


def build_effective_foreign_daily_df(
    conn,
    stock_id: str,
    market: str,
    price_df: pd.DataFrame,
    reference_date=None,
    lookback_days: int = FOREIGN_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """
    從既有 effective Foreign semantic layer
    取得 Bullish v2 所需的每日 foreign_net。

    重要：
    - 使用該股票自己的 daily_prices 日期。
    - TPEx ZERO_INFERRED 只補 foreign_net=0。
    - 不建立假的 foreign_buy / foreign_sell。
    """
    columns = [
        "trade_date",
        "foreign_net",
        "status",
        "source",
    ]

    if (
        price_df is None
        or not isinstance(price_df, pd.DataFrame)
        or price_df.empty
        or "trade_date"
        not in price_df.columns
    ):
        return pd.DataFrame(
            columns=columns
        )

    dates = price_df[
        ["trade_date"]
    ].copy()

    dates["trade_date"] = (
        pd.to_datetime(
            dates["trade_date"],
            errors="coerce",
        )
    )

    ref = _to_timestamp(reference_date)
    if reference_date is not None and ref is None:
        return pd.DataFrame(
            columns=columns
        )

    if ref is not None:
        dates = dates[
            dates["trade_date"]
            <= ref
        ]

    dates = (
        dates
        .dropna()
        .drop_duplicates()
        .sort_values("trade_date")
        .tail(lookback_days)
        .reset_index(drop=True)
    )

    if dates.empty:
        return pd.DataFrame(
            columns=columns
        )

    start_date = str(
        dates.iloc[0][
            "trade_date"
        ].date()
    )
    end_date = str(
        dates.iloc[-1][
            "trade_date"
        ].date()
    )

    rows = get_effective_foreign_net(
        conn=conn,
        stock_id=stock_id,
        market=market,
        start_date=start_date,
        end_date=end_date,
        allow_twse_zero_inferred=True,
    )

    return pd.DataFrame(
        [
            {
                "trade_date":
                    item.trade_date,
                "foreign_net":
                    item.foreign_net,
                "status":
                    item.status,
                "source":
                    item.source,
            }
            for item in rows
        ],
        columns=columns,
    )


def evaluate_foreign_v2(
    foreign_daily_df: pd.DataFrame,
    price_df: pd.DataFrame,
    reference_date=None,
) -> dict[str, Any]:
    """
    Foreign /15

    D1. 近 5 交易日累計 foreign_net > 0      /4
    D2. 近 10 交易日累計 foreign_net > 0     /3
    D3. 近 5 日買超天數                     /3
    D4. 近 5 日外資參與率                   /3
    D5. 近 5 日淨額 > 前 5 日淨額           /2

    只使用 foreign_net。
    """
    result: dict[str, Any] = {
        "status": "INSUFFICIENT_DATA",
        "score": 0,
        "max_score":
            FOREIGN_MAX_SCORE,
        "reason": "",
        "conditions": [],
        "metrics": {},
    }

    price, price_error = (
        _prepare_price_df(
            price_df,
            reference_date=reference_date,
        )
    )
    if price_error is not None:
        result["reason"] = price_error
        return result

    if (
        foreign_daily_df is None
        or not isinstance(
            foreign_daily_df,
            pd.DataFrame,
        )
        or foreign_daily_df.empty
    ):
        result["reason"] = (
            "沒有 effective Foreign 每日資料"
        )
        return result

    required_columns = {
        "trade_date",
        "foreign_net",
    }
    missing_columns = (
        required_columns
        - set(
            foreign_daily_df.columns
        )
    )
    if missing_columns:
        result["reason"] = (
            "Foreign 資料缺少必要欄位："
            + ", ".join(
                sorted(missing_columns)
            )
        )
        return result

    foreign = (
        foreign_daily_df.copy()
    )
    foreign["trade_date"] = (
        pd.to_datetime(
            foreign["trade_date"],
            errors="coerce",
        )
    )
    foreign["foreign_net"] = (
        pd.to_numeric(
            foreign["foreign_net"],
            errors="coerce",
        )
    )

    ref = _to_timestamp(
        reference_date
    )
    if ref is not None:
        foreign = foreign[
            foreign["trade_date"]
            <= ref
        ]

    foreign = (
        foreign
        .dropna(
            subset=["trade_date"]
        )
        .sort_values("trade_date")
        .drop_duplicates(
            subset=["trade_date"],
            keep="last",
        )
    )

    needed = (
        price
        .tail(
            FOREIGN_LOOKBACK_DAYS
        )[
            [
                "trade_date",
                "volume",
            ]
        ]
        .copy()
        .reset_index(drop=True)
    )

    merged = needed.merge(
        foreign[
            [
                "trade_date",
                "foreign_net",
            ]
        ],
        on="trade_date",
        how="left",
    )

    if (
        len(merged)
        < FOREIGN_LOOKBACK_DAYS
    ):
        result["reason"] = (
            "近 10 個個股交易日不足"
        )
        return result

    missing_net = (
        merged["foreign_net"]
        .isna()
    )
    if missing_net.any():
        missing_dates = [
            str(
                pd.Timestamp(value)
                .date()
            )
            for value
            in merged.loc[
                missing_net,
                "trade_date",
            ].tolist()
        ]
        result["reason"] = (
            "近 10 個個股交易日 "
            "foreign_net 資料不足："
            + ", ".join(
                missing_dates
            )
        )
        return result

    merged["foreign_net"] = (
        merged["foreign_net"]
        .astype(float)
    )

    previous5 = merged.iloc[:5]
    latest5 = merged.iloc[5:]

    latest5_net = float(
        latest5[
            "foreign_net"
        ].sum()
    )
    previous5_net = float(
        previous5[
            "foreign_net"
        ].sum()
    )
    latest10_net = float(
        merged[
            "foreign_net"
        ].sum()
    )

    positive_days_5d = int(
        (
            latest5[
                "foreign_net"
            ]
            > 0
        ).sum()
    )

    volume_5d = float(
        latest5["volume"].sum()
    )
    foreign_participation_5d = (
        latest5_net / volume_5d
        if volume_5d > 0
        else None
    )

    d1 = (
        4
        if latest5_net > 0
        else 0
    )

    d2 = (
        3
        if latest10_net > 0
        else 0
    )

    if positive_days_5d >= 3:
        d3 = 3
    elif positive_days_5d == 2:
        d3 = 1
    else:
        d3 = 0

    if (
        foreign_participation_5d
        is None
    ):
        d4 = 0
    elif (
        foreign_participation_5d
        >= 0.01
    ):
        d4 = 3
    elif (
        foreign_participation_5d
        >= 0.005
    ):
        d4 = 2
    elif (
        foreign_participation_5d
        > 0
    ):
        d4 = 1
    else:
        d4 = 0

    d5 = (
        2
        if latest5_net
        > previous5_net
        else 0
    )

    score = d1 + d2 + d3 + d4 + d5

    result["status"] = "READY"
    result["score"] = score
    result["metrics"] = {
        "previous_5d_net":
            previous5_net,
        "latest_5d_net":
            latest5_net,
        "latest_10d_net":
            latest10_net,
        "positive_days_5d":
            positive_days_5d,
        "volume_5d":
            volume_5d,
        "foreign_participation_5d":
            foreign_participation_5d,
    }
    result["conditions"] = [
        {
            "code":
                "D1_FOREIGN_5D_NET",
            "name":
                "近 5 日外資累計偏買",
            "score": d1,
            "max_score": 4,
        },
        {
            "code":
                "D2_FOREIGN_10D_NET",
            "name":
                "近 10 日外資累計偏買",
            "score": d2,
            "max_score": 3,
        },
        {
            "code":
                "D3_FOREIGN_POSITIVE_DAYS",
            "name":
                "近 5 日外資買超天數",
            "score": d3,
            "max_score": 3,
        },
        {
            "code":
                "D4_FOREIGN_PARTICIPATION",
            "name":
                "近 5 日外資參與率",
            "score": d4,
            "max_score": 3,
        },
        {
            "code":
                "D5_FOREIGN_ACCELERATION",
            "name":
                "外資近 5 日改善",
            "score": d5,
            "max_score": 2,
        },
    ]
    result["reason"] = (
        f"Foreign {score}/15, "
        f"5D net={latest5_net:.0f}, "
        f"10D net={latest10_net:.0f}"
    )

    return result


def extract_tdcc_v2_features(
    tdcc_df: pd.DataFrame,
    reference_date=None,
) -> dict[str, Any]:
    """
    先抽出 TDCC 相對變化。

    之後全市場 debug script 會先收集每檔 feature，
    再建立 percentile context，
    最後才正式算 TDCC /20。
    """
    result: dict[str, Any] = {
        "status": "INSUFFICIENT_DATA",
        "reason": "",
        "latest_date": None,
        "large_latest": None,
        "retail_latest": None,
        "large_delta": None,
        "retail_delta": None,
        "large_4date_delta": None,
        "retail_4date_delta": None,
    }

    if (
        tdcc_df is None
        or not isinstance(
            tdcc_df,
            pd.DataFrame,
        )
        or tdcc_df.empty
    ):
        result["reason"] = (
            "沒有 TDCC 歷史資料"
        )
        return result

    required_columns = {
        "data_date",
        "large_holder_pct",
        "retail_holder_pct",
    }
    missing_columns = (
        required_columns
        - set(tdcc_df.columns)
    )
    if missing_columns:
        result["reason"] = (
            "TDCC 資料缺少必要欄位："
            + ", ".join(
                sorted(missing_columns)
            )
        )
        return result

    df = tdcc_df.copy()
    df["data_date"] = (
        pd.to_datetime(
            df["data_date"],
            errors="coerce",
        )
    )
    df["large_holder_pct"] = (
        pd.to_numeric(
            df["large_holder_pct"],
            errors="coerce",
        )
    )
    df["retail_holder_pct"] = (
        pd.to_numeric(
            df["retail_holder_pct"],
            errors="coerce",
        )
    )

    ref = _to_timestamp(
        reference_date
    )
    if reference_date is not None and ref is None:
        result["reason"] = (
            "reference_date 無法解析"
        )
        return result

    if ref is not None:
        df = df[
            df["data_date"] <= ref
        ]

    df = (
        df
        .dropna(
            subset=[
                "data_date",
                "large_holder_pct",
                "retail_holder_pct",
            ]
        )
        .sort_values("data_date")
        .drop_duplicates(
            subset=["data_date"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    recent = (
        df
        .tail(TDCC_REQUIRED_DATES)
        .reset_index(drop=True)
    )

    if len(recent) < TDCC_REQUIRED_DATES:
        result["reason"] = (
            f"TDCC 資料不足：目前 "
            f"{len(recent)} 期，"
            f"至少需要 "
            f"{TDCC_REQUIRED_DATES} 期"
        )
        return result

    latest = recent.iloc[-1]
    previous = recent.iloc[-2]
    oldest = recent.iloc[0]

    large_latest = float(
        latest[
            "large_holder_pct"
        ]
    )
    retail_latest = float(
        latest[
            "retail_holder_pct"
        ]
    )

    large_delta = (
        large_latest
        - float(
            previous[
                "large_holder_pct"
            ]
        )
    )
    retail_delta = (
        retail_latest
        - float(
            previous[
                "retail_holder_pct"
            ]
        )
    )

    large_4date_delta = (
        large_latest
        - float(
            oldest[
                "large_holder_pct"
            ]
        )
    )
    retail_4date_delta = (
        retail_latest
        - float(
            oldest[
                "retail_holder_pct"
            ]
        )
    )

    result.update(
        {
            "status": "READY",
            "reason": "TDCC feature ready",
            "latest_date": str(
                pd.Timestamp(
                    latest["data_date"]
                ).date()
            ),
            "large_latest":
                large_latest,
            "retail_latest":
                retail_latest,
            "large_delta":
                large_delta,
            "retail_delta":
                retail_delta,
            "large_4date_delta":
                large_4date_delta,
            "retail_4date_delta":
                retail_4date_delta,
        }
    )

    return result


def build_tdcc_market_context(
    tdcc_features_df: pd.DataFrame,
) -> dict[str, Any]:
    """
    使用全市場 ready stocks 的最新 TDCC delta，
    建立 v2 的 percentile threshold。

    必要欄位：
    - large_delta
    - retail_delta
    """
    required_columns = {
        "large_delta",
        "retail_delta",
    }

    if (
        tdcc_features_df is None
        or not isinstance(
            tdcc_features_df,
            pd.DataFrame,
        )
        or tdcc_features_df.empty
    ):
        raise ValueError(
            "沒有 TDCC feature 資料"
        )

    missing_columns = (
        required_columns
        - set(
            tdcc_features_df.columns
        )
    )
    if missing_columns:
        raise ValueError(
            "TDCC feature 缺少欄位："
            + ", ".join(
                sorted(missing_columns)
            )
        )

    df = tdcc_features_df.copy()

    for column in [
        "large_delta",
        "retail_delta",
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "large_delta",
            "retail_delta",
        ]
    )

    if df.empty:
        raise ValueError(
            "TDCC feature 沒有可用數值"
        )

    return {
        "sample_size": int(len(df)),
        "large_p50": float(
            df["large_delta"]
            .quantile(0.50)
        ),
        "large_p75": float(
            df["large_delta"]
            .quantile(0.75)
        ),
        "retail_p25": float(
            df["retail_delta"]
            .quantile(0.25)
        ),
        "retail_p50": float(
            df["retail_delta"]
            .quantile(0.50)
        ),
    }


def evaluate_tdcc_v2(
    tdcc_df: pd.DataFrame,
    market_context: Optional[
        dict[str, Any]
    ],
    reference_date=None,
) -> dict[str, Any]:
    """
    TDCC /20

    E1. 最新一期大戶變化 + 市場 percentile /6
    E2. 最新一期散戶變化 + 市場 percentile /5
    E3. 4 期大戶方向 /4
    E4. 4 期散戶方向 /3
    E5. 籌碼集中確認 /2

    E1 / E2 需要全市場 context。
    """
    result: dict[str, Any] = {
        "status": "INSUFFICIENT_DATA",
        "score": 0,
        "max_score": TDCC_MAX_SCORE,
        "reason": "",
        "conditions": [],
        "metrics": {},
    }

    feature = (
        extract_tdcc_v2_features(
            tdcc_df,
            reference_date=reference_date,
        )
    )

    if feature["status"] != "READY":
        result["reason"] = (
            feature["reason"]
        )
        return result

    required_context_keys = {
        "large_p50",
        "large_p75",
        "retail_p25",
        "retail_p50",
    }

    if (
        market_context is None
        or not required_context_keys
        .issubset(
            market_context.keys()
        )
    ):
        result["status"] = (
            "NEEDS_MARKET_CONTEXT"
        )
        result["reason"] = (
            "TDCC /20 需要全市場 percentile context"
        )
        result["metrics"] = feature
        return result

    large_delta = float(
        feature["large_delta"]
    )
    retail_delta = float(
        feature["retail_delta"]
    )
    large_4date_delta = float(
        feature[
            "large_4date_delta"
        ]
    )
    retail_4date_delta = float(
        feature[
            "retail_4date_delta"
        ]
    )

    large_p50 = float(
        market_context[
            "large_p50"
        ]
    )
    large_p75 = float(
        market_context[
            "large_p75"
        ]
    )
    retail_p25 = float(
        market_context[
            "retail_p25"
        ]
    )
    retail_p50 = float(
        market_context[
            "retail_p50"
        ]
    )

    # 大戶一定要增加才給分。
    if large_delta <= 0:
        e1 = 0
    elif large_delta >= large_p75:
        e1 = 6
    elif large_delta >= large_p50:
        e1 = 4
    else:
        e1 = 2

    # 散戶一定要下降才給分。
    if retail_delta >= 0:
        e2 = 0
    elif retail_delta <= retail_p25:
        e2 = 5
    elif retail_delta <= retail_p50:
        e2 = 3
    else:
        e2 = 1

    e3 = (
        4
        if large_4date_delta > 0
        else 0
    )
    e4 = (
        3
        if retail_4date_delta < 0
        else 0
    )
    e5 = (
        2
        if (
            large_4date_delta > 0
            and retail_4date_delta < 0
        )
        else 0
    )

    score = e1 + e2 + e3 + e4 + e5

    result["status"] = "READY"
    result["score"] = score
    result["metrics"] = {
        **feature,
        "market_sample_size":
            market_context.get(
                "sample_size"
            ),
        "large_p50": large_p50,
        "large_p75": large_p75,
        "retail_p25": retail_p25,
        "retail_p50": retail_p50,
    }
    result["conditions"] = [
        {
            "code":
                "E1_LARGE_DELTA",
            "name":
                "最新一期大戶增加",
            "score": e1,
            "max_score": 6,
        },
        {
            "code":
                "E2_RETAIL_DELTA",
            "name":
                "最新一期散戶下降",
            "score": e2,
            "max_score": 5,
        },
        {
            "code":
                "E3_LARGE_4DATE",
            "name":
                "4 期大戶方向",
            "score": e3,
            "max_score": 4,
        },
        {
            "code":
                "E4_RETAIL_4DATE",
            "name":
                "4 期散戶方向",
            "score": e4,
            "max_score": 3,
        },
        {
            "code":
                "E5_CONCENTRATION",
            "name":
                "籌碼集中確認",
            "score": e5,
            "max_score": 2,
        },
    ]
    result["reason"] = (
        f"TDCC {score}/20, "
        f"large Δ={large_delta:.4f}, "
        f"retail Δ={retail_delta:.4f}"
    )

    return result


def classify_bullish_state(
    total_score: int,
    trend_score: int,
    setup_score: int,
    momentum_score: int,
) -> str:
    """
    v2 research state。

    100 分不是 PASS 門檻。

    STRONG_BULLISH：
      total >= 75
      trend >= 17
      setup >= 12 OR momentum >= 12

    BULLISH：
      total >= 65
      trend >= 14
      setup >= 10 OR momentum >= 10
    """
    if (
        total_score >= 75
        and trend_score >= 17
        and (
            setup_score >= 12
            or momentum_score >= 12
        )
    ):
        return "STRONG_BULLISH"

    if (
        total_score >= 65
        and trend_score >= 14
        and (
            setup_score >= 10
            or momentum_score >= 10
        )
    ):
        return "BULLISH"

    if total_score >= 55:
        return "WATCH"

    if total_score >= 45:
        return "NEUTRAL"

    return "WEAK"


def evaluate_bullish_v2(
    price_df: pd.DataFrame,
    foreign_daily_df: pd.DataFrame,
    tdcc_df: pd.DataFrame,
    tdcc_market_context: Optional[
        dict[str, Any]
    ],
    reference_date=None,
) -> dict[str, Any]:
    """
    StockWaveScanner Bullish Opportunity Score v2 /100。

    這是 research model。
    不修改 Sleep / Chip / Breakout v1 production PASS。

    模組：
    - Trend /25
    - Setup /20
    - Momentum /20
    - Foreign /15
    - TDCC /20
    """
    price_result = (
        evaluate_price_v2(
            price_df,
            reference_date=reference_date,
        )
    )

    foreign_result = (
        evaluate_foreign_v2(
            foreign_daily_df,
            price_df,
            reference_date=reference_date,
        )
    )

    tdcc_result = (
        evaluate_tdcc_v2(
            tdcc_df,
            market_context=(
                tdcc_market_context
            ),
            reference_date=reference_date,
        )
    )

    trend_score = int(
        price_result.get(
            "trend_score",
            0,
        )
    )
    setup_score = int(
        price_result.get(
            "setup_score",
            0,
        )
    )
    momentum_score = int(
        price_result.get(
            "momentum_score",
            0,
        )
    )
    foreign_score = int(
        foreign_result.get(
            "score",
            0,
        )
    )
    tdcc_score = int(
        tdcc_result.get(
            "score",
            0,
        )
    )

    partial_score = (
        trend_score
        + setup_score
        + momentum_score
        + foreign_score
        + tdcc_score
    )

    module_status = {
        "price":
            price_result["status"],
        "foreign":
            foreign_result["status"],
        "tdcc":
            tdcc_result["status"],
    }

    all_ready = all(
        value == "READY"
        for value
        in module_status.values()
    )

    if all_ready:
        total_score: Optional[int] = (
            partial_score
        )
        state = classify_bullish_state(
            total_score=total_score,
            trend_score=trend_score,
            setup_score=setup_score,
            momentum_score=(
                momentum_score
            ),
        )
        data_status = "READY"
    else:
        total_score = None
        state = "UNRATED"

        if (
            tdcc_result["status"]
            == "NEEDS_MARKET_CONTEXT"
            and price_result["status"]
            == "READY"
            and foreign_result["status"]
            == "READY"
        ):
            data_status = (
                "NEEDS_MARKET_CONTEXT"
            )
        else:
            data_status = (
                "INSUFFICIENT_DATA"
            )

    return {
        "data_status":
            data_status,
        "score":
            total_score,
        "partial_score":
            partial_score,
        "max_score":
            BULLISH_V2_MAX_SCORE,
        "state":
            state,
        "stage":
            price_result.get(
                "stage",
                "UNRATED",
            ),
        "risk_flags":
            price_result.get(
                "risk_flags",
                [],
            ),
        "trend_score":
            trend_score,
        "setup_score":
            setup_score,
        "momentum_score":
            momentum_score,
        "foreign_score":
            foreign_score,
        "tdcc_score":
            tdcc_score,
        "module_status":
            module_status,
        "price":
            price_result,
        "foreign":
            foreign_result,
        "tdcc":
            tdcc_result,
    }
