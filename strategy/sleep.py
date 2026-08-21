import pandas as pd


SLEEP_MAX_SCORE = 30


def evaluate_sleep(
    price_df: pd.DataFrame,
    ma_days: int = 20,
    recent_days: int = 10,
    baseline_days: int = 20,
    ma_distance_pct: float = 0.05,
    volatility_ratio_max: float = 0.80,
    volume_ratio_max: float = 0.80,
):
    """
    第一關：Sleep Analyzer v1

    分數：
        A. 價格位置     10
        B. 波動收斂     10
        C. 成交量沉澱   10

    PASS：
        三項全部成立 = 30 / 30
    """

    result = {
        "status": "INSUFFICIENT_DATA",
        "passed": False,
        "score": 0,
        "max_score": SLEEP_MAX_SCORE,
        "reason": "",
        "conditions": [],
        "metrics": {},
    }

    if (
        price_df is None
        or not isinstance(price_df, pd.DataFrame)
        or price_df.empty
    ):
        result["reason"] = "沒有日線資料"
        return result

    required_columns = {
        "trade_date",
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
            "日線資料缺少必要欄位："
            + ", ".join(sorted(missing_columns))
        )
        return result

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
        .reset_index(drop=True)
    )

    minimum_rows = max(
        ma_days,
        recent_days + baseline_days,
    )

    if len(df) < minimum_rows:
        result["reason"] = (
            f"日線資料不足：目前 {len(df)} 日，"
            f"至少需要 {minimum_rows} 日"
        )
        return result

    # =================================
    # 指標
    # =================================

    df["ma"] = (
        df["close"]
        .rolling(ma_days)
        .mean()
    )

    # 每日振幅：
    # (high - low) / close
    df["range_pct"] = (
        (df["high"] - df["low"])
        / df["close"]
    )

    latest = df.iloc[-1]

    latest_close = float(
        latest["close"]
    )

    latest_ma = float(
        latest["ma"]
    )

    if pd.isna(latest_ma):
        result["reason"] = (
            "均線資料不足"
        )
        return result

    ma_distance = abs(
        latest_close - latest_ma
    ) / latest_ma

    recent = df.tail(
        recent_days
    )

    baseline = df.iloc[
        -(
            recent_days
            + baseline_days
        ):
        -recent_days
    ]

    if (
        len(recent) < recent_days
        or len(baseline) < baseline_days
    ):
        result["reason"] = (
            "Sleep 比較區間資料不足"
        )
        return result

    recent_volatility = float(
        recent["range_pct"].mean()
    )

    baseline_volatility = float(
        baseline["range_pct"].mean()
    )

    recent_volume = float(
        recent["volume"].mean()
    )

    baseline_volume = float(
        baseline["volume"].mean()
    )

    if baseline_volatility <= 0:
        volatility_ratio = None
    else:
        volatility_ratio = (
            recent_volatility
            / baseline_volatility
        )

    if baseline_volume <= 0:
        volume_ratio = None
    else:
        volume_ratio = (
            recent_volume
            / baseline_volume
        )

    # =================================
    # A. 價格位置 /10
    # =================================

    price_position_pass = (
        ma_distance
        <= ma_distance_pct
    )

    # =================================
    # B. 波動收斂 /10
    # =================================

    volatility_pass = (
        volatility_ratio is not None
        and volatility_ratio
        <= volatility_ratio_max
    )

    # =================================
    # C. 成交量沉澱 /10
    # =================================

    volume_pass = (
        volume_ratio is not None
        and volume_ratio
        <= volume_ratio_max
    )

    score = 0

    if price_position_pass:
        score += 10

    if volatility_pass:
        score += 10

    if volume_pass:
        score += 10

    passed = (
        price_position_pass
        and volatility_pass
        and volume_pass
    )

    result["status"] = (
        "PASS"
        if passed
        else "FAIL"
    )

    result["passed"] = passed
    result["score"] = score

    result["metrics"] = {
        "latest_close":
            latest_close,

        "ma":
            latest_ma,

        "ma_distance_pct":
            ma_distance,

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

        "volume_ratio":
            volume_ratio,
    }

    result["conditions"] = [
        {
            "name":
                "價格接近 MA20",

            "passed":
                price_position_pass,

            "score":
                10 if price_position_pass else 0,

            "max_score":
                10,
        },
        {
            "name":
                "波動收斂",

            "passed":
                volatility_pass,

            "score":
                10 if volatility_pass else 0,

            "max_score":
                10,
        },
        {
            "name":
                "成交量沉澱",

            "passed":
                volume_pass,

            "score":
                10 if volume_pass else 0,

            "max_score":
                10,
        },
    ]

    failed = [
        item["name"]
        for item in result["conditions"]
        if not item["passed"]
    ]

    if passed:
        result["reason"] = (
            "價格靠近 MA20、波動收斂、"
            "成交量沉澱三項皆成立"
        )
    else:
        result["reason"] = (
            "未通過："
            + "、".join(failed)
        )

    return result