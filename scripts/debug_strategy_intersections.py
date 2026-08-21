from __future__ import annotations

import pandas as pd

from db.database import get_connection
from strategy.ranking import build_ranking


def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def show_rows(
    df: pd.DataFrame,
    limit: int = 30,
) -> None:
    if df.empty:
        print("(none)")
        return

    columns = [
        "rank",
        "stock_id",
        "stock_name",
        "market",
        "sleep_score",
        "sleep_status",
        "foreign_score",
        "foreign_status",
        "tdcc_score",
        "tdcc_status",
        "chip_score",
        "chip_status",
        "breakout_score",
        "breakout_status",
        "total_score",
        "status",
    ]

    print(
        df[
            columns
        ]
        .head(limit)
        .to_string(
            index=False
        )
    )


def main() -> None:
    conn = get_connection()

    try:
        ranking = build_ranking(
            conn
        )
    finally:
        conn.close()

    if ranking.empty:
        raise RuntimeError(
            "Ranking 為空"
        )

    section(
        "STRATEGY INTERSECTION ANALYSIS"
    )

    print(
        "ranking rows =",
        len(ranking),
    )

    # =====================================
    # Individual PASS
    # =====================================

    sleep_pass = ranking[
        ranking["sleep_status"]
        == "PASS"
    ]

    foreign_pass = ranking[
        ranking["foreign_status"]
        == "PASS"
    ]

    tdcc_pass = ranking[
        ranking["tdcc_status"]
        == "PASS"
    ]

    chip_pass = ranking[
        ranking["chip_status"]
        == "PASS"
    ]

    breakout_pass = ranking[
        ranking["breakout_status"]
        == "PASS"
    ]

    section(
        "INDIVIDUAL PASS COUNTS"
    )

    print(
        "Sleep PASS    =",
        len(sleep_pass),
    )

    print(
        "Foreign PASS  =",
        len(foreign_pass),
    )

    print(
        "TDCC PASS     =",
        len(tdcc_pass),
    )

    print(
        "Chip PASS     =",
        len(chip_pass),
    )

    print(
        "Breakout PASS =",
        len(breakout_pass),
    )

    # =====================================
    # Foreign ∩ TDCC
    # =====================================

    section(
        "CHIP PASS STOCKS"
    )

    show_rows(
        chip_pass
    )

    # =====================================
    # Sleep + Chip
    # =====================================

    sleep_chip = ranking[
        (
            ranking["sleep_status"]
            == "PASS"
        )
        & (
            ranking["chip_status"]
            == "PASS"
        )
    ]

    section(
        "SLEEP PASS ∩ CHIP PASS"
    )

    print(
        "count =",
        len(sleep_chip),
    )

    show_rows(
        sleep_chip
    )

    # =====================================
    # Chip + Breakout
    # =====================================

    chip_breakout = ranking[
        (
            ranking["chip_status"]
            == "PASS"
        )
        & (
            ranking["breakout_status"]
            == "PASS"
        )
    ]

    section(
        "CHIP PASS ∩ BREAKOUT PASS"
    )

    print(
        "count =",
        len(chip_breakout),
    )

    show_rows(
        chip_breakout
    )

    # =====================================
    # Sleep + Breakout
    # =====================================

    sleep_breakout = ranking[
        (
            ranking["sleep_status"]
            == "PASS"
        )
        & (
            ranking["breakout_status"]
            == "PASS"
        )
    ]

    section(
        "SLEEP PASS ∩ BREAKOUT PASS"
    )

    print(
        "count =",
        len(sleep_breakout),
    )

    show_rows(
        sleep_breakout
    )

    # =====================================
    # All 3
    # =====================================

    all_pass = ranking[
        (
            ranking["sleep_status"]
            == "PASS"
        )
        & (
            ranking["chip_status"]
            == "PASS"
        )
        & (
            ranking["breakout_status"]
            == "PASS"
        )
    ]

    section(
        "FINAL THREE-WAY PASS"
    )

    print(
        "count =",
        len(all_pass),
    )

    show_rows(
        all_pass
    )

    # =====================================
    # Near miss:
    # 2 of 3 main gates pass
    # =====================================

    work = ranking.copy()

    work["main_pass_count"] = (
        (
            work["sleep_status"]
            == "PASS"
        ).astype(int)
        +
        (
            work["chip_status"]
            == "PASS"
        ).astype(int)
        +
        (
            work["breakout_status"]
            == "PASS"
        ).astype(int)
    )

    near_miss = (
        work[
            work["main_pass_count"]
            == 2
        ]
        .sort_values(
            by=[
                "total_score",
                "chip_score",
                "sleep_score",
                "breakout_score",
            ],
            ascending=False,
        )
    )

    section(
        "NEAR MISS: 2 OF 3 MAIN GATES PASS"
    )

    print(
        "count =",
        len(near_miss),
    )

    show_rows(
        near_miss,
        limit=50,
    )

    # =====================================
    # Exactly which gate blocks them
    # =====================================

    section(
        "NEAR-MISS BLOCKER"
    )

    if near_miss.empty:
        print("(none)")
    else:
        blocker_counts = {
            "Sleep": 0,
            "Chip": 0,
            "Breakout": 0,
        }

        for _, row in (
            near_miss.iterrows()
        ):
            if (
                row["sleep_status"]
                != "PASS"
            ):
                blocker_counts[
                    "Sleep"
                ] += 1

            if (
                row["chip_status"]
                != "PASS"
            ):
                blocker_counts[
                    "Chip"
                ] += 1

            if (
                row[
                    "breakout_status"
                ]
                != "PASS"
            ):
                blocker_counts[
                    "Breakout"
                ] += 1

        for key, value in (
            blocker_counts.items()
        ):
            print(
                f"{key:10s} =",
                value,
            )

    # =====================================
    # Foreign PASS detail
    # =====================================

    section(
        "FOREIGN PASS STOCKS"
    )

    show_rows(
        foreign_pass,
        limit=50,
    )

    # =====================================
    # TDCC PASS detail
    # =====================================

    section(
        "TDCC PASS STOCKS"
    )

    show_rows(
        tdcc_pass,
        limit=50,
    )

    print()
    print("=" * 72)
    print("DONE")
    print("=" * 72)


if __name__ == "__main__":
    main()