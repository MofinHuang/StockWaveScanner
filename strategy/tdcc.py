import pandas as pd


def evaluate_tdcc(
    holdings_df: pd.DataFrame,
    required_weeks: int = 4,
):
    """
    TDCC 籌碼策略。

    條件：
    1. 最近 required_weeks 週資料完整
    2. 大戶持股比例逐週嚴格增加
    3. 散戶持股比例逐週嚴格下降

    評分：
    - 大戶連續增加：10 分
    - 散戶連續下降：10 分

    總分：
        20 分
    """

    result = {
        "status": "INSUFFICIENT_DATA",
        "passed": False,
        "score": 0,
        "reason": "",
        "required_weeks": required_weeks,
        "large_holder_growing": False,
        "retail_holder_falling": False,
        "weeks": [],
    }

    if holdings_df.empty:

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
        - set(holdings_df.columns)
    )

    if missing_columns:

        result["reason"] = (
            "TDCC 資料缺少必要欄位："
            + ", ".join(
                sorted(missing_columns)
            )
        )

        return result

    df = holdings_df.copy()

    df["data_date"] = pd.to_datetime(
        df["data_date"],
        format="%Y-%m-%d",
        errors="coerce",
    )

    df["large_holder_pct"] = pd.to_numeric(
        df["large_holder_pct"],
        errors="coerce",
    )

    df["retail_holder_pct"] = pd.to_numeric(
        df["retail_holder_pct"],
        errors="coerce",
    )

    df = df.dropna(
        subset=[
            "data_date",
            "large_holder_pct",
            "retail_holder_pct",
        ]
    )

    df = (
        df
        .sort_values(
            "data_date"
        )
        .drop_duplicates(
            subset=["data_date"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    recent = (
        df
        .tail(required_weeks)
        .copy()
        .reset_index(drop=True)
    )

    if len(recent) < required_weeks:

        result["reason"] = (
            f"TDCC 歷史資料不足："
            f"目前 {len(recent)} 週，"
            f"需要 {required_weeks} 週"
        )

        return result

    large_values = (
        recent[
            "large_holder_pct"
        ]
        .tolist()
    )

    retail_values = (
        recent[
            "retail_holder_pct"
        ]
        .tolist()
    )

    large_holder_growing = all(
        large_values[i]
        > large_values[i - 1]
        for i in range(
            1,
            len(large_values),
        )
    )

    retail_holder_falling = all(
        retail_values[i]
        < retail_values[i - 1]
        for i in range(
            1,
            len(retail_values),
        )
    )

    week_details = []

    for i, row in recent.iterrows():

        large_change = None
        retail_change = None

        if i > 0:

            large_change = (
                row["large_holder_pct"]
                - recent.iloc[i - 1][
                    "large_holder_pct"
                ]
            )

            retail_change = (
                row["retail_holder_pct"]
                - recent.iloc[i - 1][
                    "retail_holder_pct"
                ]
            )

        week_details.append(
            {
                "data_date":
                    row["data_date"],

                "large_holder_pct":
                    float(
                        row[
                            "large_holder_pct"
                        ]
                    ),

                "large_change":
                    (
                        None
                        if large_change is None
                        else float(
                            large_change
                        )
                    ),

                "retail_holder_pct":
                    float(
                        row[
                            "retail_holder_pct"
                        ]
                    ),

                "retail_change":
                    (
                        None
                        if retail_change is None
                        else float(
                            retail_change
                        )
                    ),
            }
        )

    score = 0

    if large_holder_growing:
        score += 10

    if retail_holder_falling:
        score += 10

    passed = (
        large_holder_growing
        and retail_holder_falling
    )

    result["status"] = (
        "PASS"
        if passed
        else "FAIL"
    )

    result["passed"] = passed
    result["score"] = score

    result[
        "large_holder_growing"
    ] = large_holder_growing

    result[
        "retail_holder_falling"
    ] = retail_holder_falling

    result["weeks"] = (
        week_details
    )

    if passed:

        result["reason"] = (
            f"最近 {required_weeks} 週"
            "大戶持股比例連續增加，"
            "且散戶持股比例連續下降"
        )

    else:

        reasons = []

        if not large_holder_growing:

            reasons.append(
                "大戶持股比例未連續增加"
            )

        if not retail_holder_falling:

            reasons.append(
                "散戶持股比例未連續下降"
            )

        result["reason"] = (
            "；".join(reasons)
        )

    return result