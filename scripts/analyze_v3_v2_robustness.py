from __future__ import annotations

import csv
import math
import statistics
import sys

from collections import defaultdict
from pathlib import Path
from typing import Any


# ============================================================
# CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT
    / "docs"
    / "data"
    / "backtest"
    / "v3"
    / "stage_v2_candidate_rows.csv"
)


# ============================================================
# CONSOLE
# ============================================================


def configure_console() -> None:

    for stream in (
        sys.stdout,
        sys.stderr,
    ):

        reconfigure = getattr(
            stream,
            "reconfigure",
            None,
        )

        if callable(
            reconfigure
        ):

            try:

                reconfigure(
                    encoding="utf-8",
                    errors="replace",
                )

            except Exception:

                pass


# ============================================================
# HELPERS
# ============================================================


def safe_float(
    value: Any,
) -> float | None:

    if value is None:

        return None

    text = str(
        value
    ).strip()

    if not text:

        return None

    try:

        result = float(
            text
        )

    except (
        TypeError,
        ValueError,
    ):

        return None

    if not math.isfinite(
        result
    ):

        return None

    return result


def mean_or_none(
    values: list[float],
) -> float | None:

    if not values:

        return None

    return statistics.fmean(
        values
    )


def median_or_none(
    values: list[float],
) -> float | None:

    if not values:

        return None

    return statistics.median(
        values
    )


def win_rate(
    values: list[float],
) -> float | None:

    if not values:

        return None

    return (
        sum(
            value > 0
            for value in values
        )
        /
        len(
            values
        )
        *
        100.0
    )


def fmt(
    value: float | None,
    width: int = 8,
) -> str:

    if value is None:

        return (
            f"{'-':>{width}}"
        )

    return (
        f"{value:>{width}.2f}"
    )


# ============================================================
# LOAD
# ============================================================


def load_rows() -> list[
    dict[str, Any]
]:

    if not INPUT_FILE.exists():

        raise RuntimeError(
            f"File not found: {INPUT_FILE}"
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(
            file
        )

        rows = list(
            reader
        )

    if not rows:

        raise RuntimeError(
            "stage_v2_candidate_rows.csv is empty"
        )

    return rows


# ============================================================
# METRIC
# ============================================================


def future20_values(
    rows: list[
        dict[str, Any]
    ],
) -> list[float]:

    result = []

    for row in rows:

        value = safe_float(
            row.get(
                "future_return_20d"
            )
        )

        if value is not None:

            result.append(
                value
            )

    return result


def summarize(
    rows: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:

    values = (
        future20_values(
            rows
        )
    )

    return {
        "count":
            len(
                rows
            ),

        "avg20":
            mean_or_none(
                values
            ),

        "median20":
            median_or_none(
                values
            ),

        "win20":
            win_rate(
                values
            ),
    }


# ============================================================
# FILTERS
# ============================================================


def filter_overall(
    rows: list[
        dict[str, Any]
    ],
    field: str,
    minimum: float,
) -> list[
    dict[str, Any]
]:

    result = []

    for row in rows:

        value = safe_float(
            row.get(
                field
            )
        )

        if (
            value is not None
            and
            value >= minimum
        ):

            result.append(
                row
            )

    return result


def filter_stage(
    rows: list[
        dict[str, Any]
    ],
    field: str,
    stages: set[str],
) -> list[
    dict[str, Any]
]:

    return [
        row
        for row in rows
        if str(
            row.get(
                field
            )
            or
            ""
        )
        in stages
    ]


# ============================================================
# PER DATE
# ============================================================


def analyze_by_date(
    rows: list[
        dict[str, Any]
    ],
) -> None:

    grouped: dict[
        str,
        list[
            dict[str, Any]
        ],
    ] = defaultdict(
        list
    )

    for row in rows:

        signal_date = str(
            row.get(
                "signal_date"
            )
        )

        grouped[
            signal_date
        ].append(
            row
        )

    print()

    print(
        "=" * 130
    )

    print(
        "PER SIGNAL DATE - OVERALL >= 70"
    )

    print(
        "=" * 130
    )

    print(
        "date         "
        "V1_count V1_avg20 V1_win%   "
        "V2_count V2_avg20 V2_win%   "
        "V2-V1"
    )

    overall_v2_better = 0
    overall_dates = 0

    for signal_date in sorted(
        grouped
    ):

        date_rows = (
            grouped[
                signal_date
            ]
        )

        v1_rows = (
            filter_overall(
                date_rows,
                "overall_v1",
                70.0,
            )
        )

        v2_rows = (
            filter_overall(
                date_rows,
                "overall_v2",
                70.0,
            )
        )

        v1 = summarize(
            v1_rows
        )

        v2 = summarize(
            v2_rows
        )

        difference = None

        if (
            v1["avg20"] is not None
            and
            v2["avg20"] is not None
        ):

            difference = (
                v2["avg20"]
                -
                v1["avg20"]
            )

            overall_dates += 1

            if difference > 0:

                overall_v2_better += 1

        print(
            f"{signal_date:12} "
            f"{v1['count']:8} "
            f"{fmt(v1['avg20'])} "
            f"{fmt(v1['win20'], 7)}   "
            f"{v2['count']:8} "
            f"{fmt(v2['avg20'])} "
            f"{fmt(v2['win20'], 7)}   "
            f"{fmt(difference)}"
        )

    print()

    print(
        f"Overall V2 better dates : "
        f"{overall_v2_better} / "
        f"{overall_dates}"
    )

    # --------------------------------------------------------

    action_stages = {
        "READY",
        "BREAKOUT",
    }

    print()

    print(
        "=" * 130
    )

    print(
        "PER SIGNAL DATE - READY + BREAKOUT"
    )

    print(
        "=" * 130
    )

    print(
        "date         "
        "V1_count V1_avg20 V1_win%   "
        "V2_count V2_avg20 V2_win%   "
        "V2-V1"
    )

    stage_v2_better = 0
    stage_dates = 0

    for signal_date in sorted(
        grouped
    ):

        date_rows = (
            grouped[
                signal_date
            ]
        )

        v1_rows = (
            filter_stage(
                date_rows,
                "stage_v1",
                action_stages,
            )
        )

        v2_rows = (
            filter_stage(
                date_rows,
                "stage_v2",
                action_stages,
            )
        )

        v1 = summarize(
            v1_rows
        )

        v2 = summarize(
            v2_rows
        )

        difference = None

        if (
            v1["avg20"] is not None
            and
            v2["avg20"] is not None
        ):

            difference = (
                v2["avg20"]
                -
                v1["avg20"]
            )

            stage_dates += 1

            if difference > 0:

                stage_v2_better += 1

        print(
            f"{signal_date:12} "
            f"{v1['count']:8} "
            f"{fmt(v1['avg20'])} "
            f"{fmt(v1['win20'], 7)}   "
            f"{v2['count']:8} "
            f"{fmt(v2['avg20'])} "
            f"{fmt(v2['win20'], 7)}   "
            f"{fmt(difference)}"
        )

    print()

    print(
        f"Stage V2 better dates   : "
        f"{stage_v2_better} / "
        f"{stage_dates}"
    )


# ============================================================
# GLOBAL
# ============================================================


def print_global(
    rows: list[
        dict[str, Any]
    ],
) -> None:

    print()

    print(
        "=" * 100
    )

    print(
        "GLOBAL ROBUSTNESS SUMMARY"
    )

    print(
        "=" * 100
    )

    overall_v1 = summarize(
        filter_overall(
            rows,
            "overall_v1",
            70.0,
        )
    )

    overall_v2 = summarize(
        filter_overall(
            rows,
            "overall_v2",
            70.0,
        )
    )

    ready_breakout_v1 = summarize(
        filter_stage(
            rows,
            "stage_v1",
            {
                "READY",
                "BREAKOUT",
            },
        )
    )

    ready_breakout_v2 = summarize(
        filter_stage(
            rows,
            "stage_v2",
            {
                "READY",
                "BREAKOUT",
            },
        )
    )

    extended_v1 = summarize(
        filter_stage(
            rows,
            "stage_v1",
            {
                "EXTENDED",
            },
        )
    )

    extended_v2 = summarize(
        filter_stage(
            rows,
            "stage_v2",
            {
                "EXTENDED",
            },
        )
    )

    print(
        "Group                    "
        "Count    Avg20   Median20   Win20%"
    )

    print(
        f"{'Overall V1 >=70':24} "
        f"{overall_v1['count']:6} "
        f"{fmt(overall_v1['avg20'])} "
        f"{fmt(overall_v1['median20'], 10)} "
        f"{fmt(overall_v1['win20'], 8)}"
    )

    print(
        f"{'Overall V2 >=70':24} "
        f"{overall_v2['count']:6} "
        f"{fmt(overall_v2['avg20'])} "
        f"{fmt(overall_v2['median20'], 10)} "
        f"{fmt(overall_v2['win20'], 8)}"
    )

    print()

    print(
        f"{'V1 READY+BREAKOUT':24} "
        f"{ready_breakout_v1['count']:6} "
        f"{fmt(ready_breakout_v1['avg20'])} "
        f"{fmt(ready_breakout_v1['median20'], 10)} "
        f"{fmt(ready_breakout_v1['win20'], 8)}"
    )

    print(
        f"{'V2 READY+BREAKOUT':24} "
        f"{ready_breakout_v2['count']:6} "
        f"{fmt(ready_breakout_v2['avg20'])} "
        f"{fmt(ready_breakout_v2['median20'], 10)} "
        f"{fmt(ready_breakout_v2['win20'], 8)}"
    )

    print()

    print(
        f"{'V1 EXTENDED':24} "
        f"{extended_v1['count']:6} "
        f"{fmt(extended_v1['avg20'])} "
        f"{fmt(extended_v1['median20'], 10)} "
        f"{fmt(extended_v1['win20'], 8)}"
    )

    print(
        f"{'V2 EXTENDED':24} "
        f"{extended_v2['count']:6} "
        f"{fmt(extended_v2['avg20'])} "
        f"{fmt(extended_v2['median20'], 10)} "
        f"{fmt(extended_v2['win20'], 8)}"
    )


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    configure_console()

    print(
        "=" * 80
    )

    print(
        "StockWaveScanner V3 "
        "- V2 Robustness Analysis"
    )

    print(
        "=" * 80
    )

    try:

        rows = load_rows()

        print(
            f"Rows : {len(rows):,}"
        )

        signal_dates = sorted(
            {
                str(
                    row.get(
                        "signal_date"
                    )
                )
                for row in rows
            }
        )

        print(
            f"Signal Dates : "
            f"{len(signal_dates)}"
        )

        print_global(
            rows
        )

        analyze_by_date(
            rows
        )

        print()

        print(
            "=" * 80
        )

        print(
            "[PASS] V2 robustness analysis completed"
        )

        return 0

    except Exception as exc:

        print()

        print(
            "=" * 80
        )

        print(
            "ERROR"
        )

        print(
            "=" * 80
        )

        print(
            str(
                exc
            )
        )

        return 1


if __name__ == "__main__":

    sys.exit(
        main()
    )