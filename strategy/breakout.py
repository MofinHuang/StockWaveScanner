import pandas as pd


BREAKOUT_MAX_SCORE = 30


def evaluate_breakout(
    price_df: pd.DataFrame,
    breakout_days: int = 20,
    volume_ratio_min: float = 1.50,
    close_position_max: float = 0.25,
):
    """
    第三關：Breakout Analyzer v1

    分數：
        A. 收盤突破前高    10
        B. 成交量放大      10
        C. 收盤位置強勢    10

    PASS：
        三項全部成立 = 30 / 30
    """

    result = {
        "status": "INSUFFICIENT_DATA",
        "passed": False,
        "score": 0,
        "max_score": BREAKOUT_MAX_SCORE,
        "reason": "",
        "conditions": [],
        "metrics": {},
    }

    # =================================
    # 輸入驗證
    # =================================

    if (
        price_df is None
        or not isinstance(
            price_df,
            pd.DataFrame,
        )
        or price_df.empty
    ):
        result["reason"] = (
            "沒有日線資料"
        )
        return result

    required_columns = {
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing_columns = (
        required_columns
        - set(price_df.columns)
    )

    if missing_columns:
        result["reason"] = (
            "Breakout 日線資料缺少必要欄位："
            + ", ".join(
                sorted(missing_columns)
            )
        )
        return result

    # =================================
    # 清理資料
    # =================================

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

    # 最新一日
    # +
    # 前 breakout_days 日
    minimum_rows = (
        breakout_days
        + 1
    )

    if len(df) < minimum_rows:

        result["reason"] = (
            f"日線資料不足：目前 {len(df)} 日，"
            f"至少需要 {minimum_rows} 日"
        )

        return result

    latest = df.iloc[-1]

    history = df.iloc[
        -(breakout_days + 1):
        -1
    ]

    if len(history) < breakout_days:

        result["reason"] = (
            "Breakout 前期比較資料不足"
        )

        return result

    latest_open = float(
        latest["open"]
    )

    latest_high = float(
        latest["high"]
    )

    latest_low = float(
        latest["low"]
    )

    latest_close = float(
        latest["close"]
    )

    latest_volume = float(
        latest["volume"]
    )

    previous_high = float(
        history["high"].max()
    )

    average_volume = float(
        history["volume"].mean()
    )

    # =================================
    # 指標
    # =================================

    if previous_high > 0:

        breakout_pct = (
            latest_close
            / previous_high
            - 1
        )

    else:

        breakout_pct = None

    if average_volume > 0:

        volume_ratio = (
            latest_volume
            / average_volume
        )

    else:

        volume_ratio = None

    daily_range = (
        latest_high
        - latest_low
    )

    if daily_range > 0:

        close_from_high_ratio = (
            latest_high
            - latest_close
        ) / daily_range

    else:

        # 一字線：
        # high == low == close
        #
        # 收盤就在最高點。
        if (
            latest_close
            == latest_high
        ):
            close_from_high_ratio = 0.0

        else:
            close_from_high_ratio = None

    # =================================
    # A. 收盤突破前高 /10
    # =================================

    breakout_pass = (
        latest_close
        > previous_high
    )

    # =================================
    # B. 成交量放大 /10
    # =================================

    volume_pass = (
        volume_ratio is not None
        and volume_ratio
        >= volume_ratio_min
    )

    # =================================
    # C. 收盤位置強勢 /10
    # =================================

    close_position_pass = (
        close_from_high_ratio is not None
        and close_from_high_ratio
        <= close_position_max
    )

    # =================================
    # Score
    # =================================

    score = 0

    if breakout_pass:
        score += 10

    if volume_pass:
        score += 10

    if close_position_pass:
        score += 10

    passed = (
        breakout_pass
        and volume_pass
        and close_position_pass
    )

    result["status"] = (
        "PASS"
        if passed
        else "FAIL"
    )

    result["passed"] = passed
    result["score"] = score

    # =================================
    # Metrics
    # =================================

    result["metrics"] = {
        "trade_date":
            latest[
                "trade_date"
            ],

        "latest_open":
            latest_open,

        "latest_high":
            latest_high,

        "latest_low":
            latest_low,

        "latest_close":
            latest_close,

        "previous_high":
            previous_high,

        "breakout_pct":
            breakout_pct,

        "latest_volume":
            latest_volume,

        "average_volume":
            average_volume,

        "volume_ratio":
            volume_ratio,

        "close_from_high_ratio":
            close_from_high_ratio,
    }

    # =================================
    # Conditions
    # =================================

    result["conditions"] = [
        {
            "name":
                "收盤突破前 20 日高點",

            "passed":
                breakout_pass,

            "score":
                10 if breakout_pass else 0,

            "max_score":
                10,
        },
        {
            "name":
                "成交量放大",

            "passed":
                volume_pass,

            "score":
                10 if volume_pass else 0,

            "max_score":
                10,
        },
        {
            "name":
                "收盤位置強勢",

            "passed":
                close_position_pass,

            "score":
                10 if close_position_pass else 0,

            "max_score":
                10,
        },
    ]

    # =================================
    # Reason
    # =================================

    failed = [
        item["name"]
        for item in result[
            "conditions"
        ]
        if not item["passed"]
    ]

    if passed:

        result["reason"] = (
            "收盤突破前高、成交量放大、"
            "收盤位置強勢三項皆成立"
        )

    else:

        result["reason"] = (
            "未通過："
            + "、".join(
                failed
            )
        )

    return result