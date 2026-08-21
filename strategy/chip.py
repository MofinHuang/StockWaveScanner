def evaluate_chip(
    foreign_result: dict,
    tdcc_result: dict,
):
    """
    第二關：籌碼面 Chip Analyzer

    外資：
        20 分

    TDCC：
        20 分

    合計：
        40 分

    規則：
    - 任一子策略資料不足
      → INSUFFICIENT_DATA
    - 外資、TDCC 都 PASS
      → PASS
    - 其他
      → FAIL
    """

    foreign_status = foreign_result.get(
        "status",
        "INSUFFICIENT_DATA",
    )

    tdcc_status = tdcc_result.get(
        "status",
        "INSUFFICIENT_DATA",
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

    total_score = (
        foreign_score
        + tdcc_score
    )

    result = {
        "status":
            "INSUFFICIENT_DATA",

        "passed":
            False,

        "score":
            total_score,

        "max_score":
            40,

        "foreign_score":
            foreign_score,

        "tdcc_score":
            tdcc_score,

        "foreign_status":
            foreign_status,

        "tdcc_status":
            tdcc_status,

        "reason":
            "",
    }

    # =================================
    # 資料不足
    # =================================

    insufficient = []

    if (
        foreign_status
        == "INSUFFICIENT_DATA"
    ):
        insufficient.append(
            "外資資料不足"
        )

    if (
        tdcc_status
        == "INSUFFICIENT_DATA"
    ):
        insufficient.append(
            "TDCC 資料不足"
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
        foreign_status == "PASS"
        and tdcc_status == "PASS"
    )

    result["passed"] = passed

    result["status"] = (
        "PASS"
        if passed
        else "FAIL"
    )

    if passed:

        result["reason"] = (
            "外資與 TDCC "
            "兩項籌碼條件皆通過"
        )

    else:

        failed = []

        if foreign_status != "PASS":
            failed.append(
                "外資未通過"
            )

        if tdcc_status != "PASS":
            failed.append(
                "TDCC 未通過"
            )

        result["reason"] = (
            "；".join(
                failed
            )
        )

    return result