TOTAL_MAX_SCORE = 100


def evaluate_stock(
    sleep_result: dict,
    chip_result: dict,
    breakout_result: dict,
):
    """
    三關總整合：

    Sleep      30
    Chip       40
    Breakout   30
    ----------------
    Total     100

    狀態規則：
    - 任一關 INSUFFICIENT_DATA
      -> INSUFFICIENT_DATA

    - 三關全部 PASS
      -> PASS

    - 其他
      -> FAIL

    注意：
    最終 PASS 不是只看總分，
    而是三關都必須通過。
    """

    sleep_status = sleep_result.get(
        "status",
        "INSUFFICIENT_DATA",
    )

    chip_status = chip_result.get(
        "status",
        "INSUFFICIENT_DATA",
    )

    breakout_status = breakout_result.get(
        "status",
        "INSUFFICIENT_DATA",
    )

    sleep_score = int(
        sleep_result.get(
            "score",
            0,
        )
    )

    chip_score = int(
        chip_result.get(
            "score",
            0,
        )
    )

    breakout_score = int(
        breakout_result.get(
            "score",
            0,
        )
    )

    total_score = (
        sleep_score
        + chip_score
        + breakout_score
    )

    result = {
        "status":
            "INSUFFICIENT_DATA",

        "passed":
            False,

        "score":
            total_score,

        "max_score":
            TOTAL_MAX_SCORE,

        "sleep_score":
            sleep_score,

        "chip_score":
            chip_score,

        "breakout_score":
            breakout_score,

        "sleep_status":
            sleep_status,

        "chip_status":
            chip_status,

        "breakout_status":
            breakout_status,

        "reason":
            "",
    }

    # =================================
    # 資料不足
    # =================================

    insufficient = []

    if (
        sleep_status
        == "INSUFFICIENT_DATA"
    ):
        insufficient.append(
            "Sleep 資料不足"
        )

    if (
        chip_status
        == "INSUFFICIENT_DATA"
    ):
        insufficient.append(
            "Chip 資料不足"
        )

    if (
        breakout_status
        == "INSUFFICIENT_DATA"
    ):
        insufficient.append(
            "Breakout 資料不足"
        )

    if insufficient:

        result["reason"] = (
            "；".join(
                insufficient
            )
        )

        return result

    # =================================
    # PASS / FAIL
    # =================================

    passed = (
        sleep_status == "PASS"
        and chip_status == "PASS"
        and breakout_status == "PASS"
    )

    result["passed"] = passed

    result["status"] = (
        "PASS"
        if passed
        else "FAIL"
    )

    if passed:

        result["reason"] = (
            "Sleep、Chip、Breakout "
            "三關全部通過"
        )

        return result

    failed = []

    if sleep_status != "PASS":
        failed.append(
            "Sleep 未通過"
        )

    if chip_status != "PASS":
        failed.append(
            "Chip 未通過"
        )

    if breakout_status != "PASS":
        failed.append(
            "Breakout 未通過"
        )

    result["reason"] = (
        "；".join(
            failed
        )
    )

    return result