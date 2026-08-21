from __future__ import annotations

from collections import Counter

import pandas as pd

from db.database import get_connection
from strategy.ranking import build_ranking


def print_section(
    title: str,
) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def print_status_counts(
    ranking: pd.DataFrame,
    column: str,
) -> None:
    counts = Counter(
        ranking[column]
        .fillna("NULL")
        .astype(str)
        .tolist()
    )

    print(column)

    for status, count in sorted(
        counts.items()
    ):
        print(
            f"  {status:20s} = "
            f"{count}"
        )


def main() -> None:
    conn = get_connection()

    try:
        print_section(
            "BUILD FULL-MARKET RANKING"
        )

        ranking = build_ranking(
            conn
        )

    finally:
        conn.close()

    if ranking.empty:
        raise RuntimeError(
            "build_ranking() 回傳空 DataFrame"
        )

    # ======================================
    # Basic
    # ======================================

    print_section(
        "BASIC SUMMARY"
    )

    print(
        "ranking rows =",
        len(ranking),
    )

    market_counts = (
        ranking["market"]
        .value_counts()
    )

    print()
    print(
        "market counts:"
    )

    for market, count in (
        market_counts.items()
    ):
        print(
            f"  {market:4s} = "
            f"{count}"
        )

    # ======================================
    # Status
    # ======================================

    print_section(
        "STATUS DISTRIBUTION"
    )

    for column in [
        "sleep_status",
        "foreign_status",
        "tdcc_status",
        "chip_status",
        "breakout_status",
        "status",
    ]:
        print_status_counts(
            ranking,
            column,
        )

        print()

    # ======================================
    # Score range
    # ======================================

    print_section(
        "SCORE DISTRIBUTION"
    )

    score_columns = [
        "sleep_score",
        "foreign_score",
        "tdcc_score",
        "chip_score",
        "breakout_score",
        "total_score",
    ]

    for column in score_columns:
        series = pd.to_numeric(
            ranking[column],
            errors="coerce",
        )

        print()
        print(
            column
        )

        print(
            "  min    =",
            series.min(),
        )

        print(
            "  max    =",
            series.max(),
        )

        print(
            "  mean   =",
            round(
                float(
                    series.mean()
                ),
                2,
            ),
        )

        print(
            "  median =",
            series.median(),
        )

    # ======================================
    # Total score histogram
    # ======================================

    print_section(
        "TOTAL SCORE COUNTS"
    )

    total_counts = (
        ranking[
            "total_score"
        ]
        .value_counts()
        .sort_index(
            ascending=False
        )
    )

    for score, count in (
        total_counts.items()
    ):
        print(
            f"{int(score):3d} = "
            f"{count}"
        )

    # ======================================
    # Final PASS
    # ======================================

    print_section(
        "FINAL PASS"
    )

    passed = ranking[
        ranking["status"]
        == "PASS"
    ].copy()

    print(
        "PASS count =",
        len(passed),
    )

    if not passed.empty:
        print()
        print(
            passed[
                [
                    "rank",
                    "stock_id",
                    "stock_name",
                    "market",
                    "sleep_score",
                    "foreign_score",
                    "tdcc_score",
                    "chip_score",
                    "breakout_score",
                    "total_score",
                ]
            ]
            .head(30)
            .to_string(
                index=False
            )
        )

    # ======================================
    # Top 10
    # ======================================

    print_section(
        "TOP 10"
    )

    top10 = (
        ranking
        .head(10)
        .copy()
    )

    print(
        top10[
            [
                "rank",
                "stock_id",
                "stock_name",
                "market",
                "sleep_score",
                "foreign_score",
                "tdcc_score",
                "chip_score",
                "breakout_score",
                "total_score",
                "status",
            ]
        ]
        .to_string(
            index=False
        )
    )

    print()
    print(
        "Top10 market counts:"
    )

    for market, count in (
        top10[
            "market"
        ]
        .value_counts()
        .items()
    ):
        print(
            f"  {market:4s} = "
            f"{count}"
        )

    # ======================================
    # Highest TPEx
    # ======================================

    print_section(
        "TOP TPEx"
    )

    tpex = ranking[
        ranking["market"]
        == "TPEx"
    ].head(20)

    print(
        tpex[
            [
                "rank",
                "stock_id",
                "stock_name",
                "sleep_score",
                "foreign_score",
                "tdcc_score",
                "chip_score",
                "breakout_score",
                "total_score",
                "status",
            ]
        ]
        .to_string(
            index=False
        )
    )

    # ======================================
    # INSUFFICIENT_DATA
    # ======================================

    print_section(
        "INSUFFICIENT DATA AFTER PREFILTER"
    )

    insufficient = ranking[
        ranking["status"]
        == "INSUFFICIENT_DATA"
    ].copy()

    print(
        "count =",
        len(insufficient),
    )

    if not insufficient.empty:
        print()
        print(
            insufficient[
                [
                    "stock_id",
                    "stock_name",
                    "market",
                    "sleep_status",
                    "foreign_status",
                    "tdcc_status",
                    "chip_status",
                    "breakout_status",
                    "reason",
                ]
            ]
            .head(50)
            .to_string(
                index=False
            )
        )

    # ======================================
    # Suspicious conditions
    # ======================================

    print_section(
        "SANITY CHECK"
    )

    problems = []

    if len(ranking) < 1900:
        problems.append(
            "Ranking rows 明顯低於預期 coverage"
        )

    invalid_total = ranking[
        (
            ranking["total_score"]
            < 0
        )
        | (
            ranking["total_score"]
            > 100
        )
    ]

    if not invalid_total.empty:
        problems.append(
            "存在 total_score 超出 0~100"
        )

    invalid_chip = ranking[
        (
            ranking["chip_score"]
            < 0
        )
        | (
            ranking["chip_score"]
            > 40
        )
    ]

    if not invalid_chip.empty:
        problems.append(
            "存在 chip_score 超出 0~40"
        )

    invalid_sleep = ranking[
        (
            ranking["sleep_score"]
            < 0
        )
        | (
            ranking["sleep_score"]
            > 30
        )
    ]

    if not invalid_sleep.empty:
        problems.append(
            "存在 sleep_score 超出 0~30"
        )

    invalid_breakout = ranking[
        (
            ranking["breakout_score"]
            < 0
        )
        | (
            ranking["breakout_score"]
            > 30
        )
    ]

    if not invalid_breakout.empty:
        problems.append(
            "存在 breakout_score 超出 0~30"
        )

    if problems:
        for problem in problems:
            print(
                "[CHECK]",
                problem,
            )
    else:
        print(
            "[OK] 基本分數與 Ranking "
            "coverage sanity check 通過"
        )

    print()
    print("=" * 72)
    print("DONE")
    print("=" * 72)


if __name__ == "__main__":
    main()