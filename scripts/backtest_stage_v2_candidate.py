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

BACKTEST_ROWS_FILE = (
    ROOT
    / "docs"
    / "data"
    / "backtest"
    / "v3"
    / "backtest_rows.csv"
)

TECHNICAL_V2_FILE = (
    ROOT
    / "docs"
    / "data"
    / "backtest"
    / "v3"
    / "technical_v2_candidate_rows.csv"
)

OUTPUT_DIR = (
    ROOT
    / "docs"
    / "data"
    / "backtest"
    / "v3"
)

OUTPUT_ROWS_FILE = (
    OUTPUT_DIR
    / "stage_v2_candidate_rows.csv"
)

OUTPUT_SUMMARY_FILE = (
    OUTPUT_DIR
    / "stage_v2_candidate_summary.csv"
)


STAGE_ORDER = [
    "AVOID",
    "WATCH",
    "SETUP",
    "READY",
    "BREAKOUT",
    "EXTENDED",
]


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


def round_or_none(
    value: float | None,
    digits: int = 2,
) -> float | None:

    if value is None:

        return None

    return round(
        value,
        digits,
    )


def mean_or_none(
    values: list[
        float
    ],
) -> float | None:

    if not values:

        return None

    return statistics.fmean(
        values
    )


def median_or_none(
    values: list[
        float
    ],
) -> float | None:

    if not values:

        return None

    return statistics.median(
        values
    )


# ============================================================
# LOAD CSV
# ============================================================


def load_csv(
    path: Path,
) -> list[
    dict[str, Any]
]:

    if not path.exists():

        raise RuntimeError(
            f"File not found: {path}"
        )

    with path.open(
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
            f"CSV is empty: {path}"
        )

    return rows


# ============================================================
# STAGE V2 CANDIDATE
# ============================================================


def build_stage_v2(
    overall: float | None,
    buy_zone_distance_pct: float | None,
    breakout_distance_pct: float | None,
    current_risk_pct: float | None,
) -> str:

    if overall is None:

        return "WATCH"

    # --------------------------------------------------------
    # 1. Weak quality
    # --------------------------------------------------------

    if overall < 40:

        return "AVOID"

    # --------------------------------------------------------
    # 2. Extended
    # --------------------------------------------------------

    extended = False

    if (
        breakout_distance_pct is not None
        and
        breakout_distance_pct > 8
    ):

        extended = True

    if (
        buy_zone_distance_pct is not None
        and
        buy_zone_distance_pct > 12
    ):

        extended = True

    if (
        current_risk_pct is not None
        and
        current_risk_pct > 25
    ):

        extended = True

    if extended:

        return "EXTENDED"

    # --------------------------------------------------------
    # 3. Action stages require Overall >= 70
    # --------------------------------------------------------

    if overall < 70:

        return "WATCH"

    # --------------------------------------------------------
    # 4. Breakout
    # --------------------------------------------------------

    if (
        breakout_distance_pct is not None
        and
        current_risk_pct is not None
        and
        breakout_distance_pct >= 0
        and
        breakout_distance_pct <= 5
        and
        current_risk_pct <= 22
    ):

        return "BREAKOUT"

    # --------------------------------------------------------
    # 5. Ready
    # --------------------------------------------------------

    ready_price = False

    if (
        buy_zone_distance_pct is not None
        and
        buy_zone_distance_pct >= -3
        and
        buy_zone_distance_pct <= 3
    ):

        ready_price = True

    if (
        breakout_distance_pct is not None
        and
        breakout_distance_pct >= -3
        and
        breakout_distance_pct < 0
    ):

        ready_price = True

    if (
        ready_price
        and
        current_risk_pct is not None
        and
        current_risk_pct <= 18
    ):

        return "READY"

    # --------------------------------------------------------
    # 6. Setup
    # --------------------------------------------------------

    setup_price = False

    if (
        buy_zone_distance_pct is not None
        and
        buy_zone_distance_pct >= -5
        and
        buy_zone_distance_pct <= 8
    ):

        setup_price = True

    if (
        breakout_distance_pct is not None
        and
        breakout_distance_pct >= -10
        and
        breakout_distance_pct < 0
    ):

        setup_price = True

    if (
        setup_price
        and
        current_risk_pct is not None
        and
        current_risk_pct <= 22
    ):

        return "SETUP"

    return "WATCH"


# ============================================================
# SUMMARY
# ============================================================


def summarize_group(
    rows: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:

    values_5d = []
    values_10d = []
    values_20d = []

    gains_20d = []
    drawdowns_20d = []

    for row in rows:

        value = safe_float(
            row.get(
                "future_return_5d"
            )
        )

        if value is not None:

            values_5d.append(
                value
            )

        value = safe_float(
            row.get(
                "future_return_10d"
            )
        )

        if value is not None:

            values_10d.append(
                value
            )

        value = safe_float(
            row.get(
                "future_return_20d"
            )
        )

        if value is not None:

            values_20d.append(
                value
            )

        value = safe_float(
            row.get(
                "max_gain_20d"
            )
        )

        if value is not None:

            gains_20d.append(
                value
            )

        value = safe_float(
            row.get(
                "max_drawdown_20d"
            )
        )

        if value is not None:

            drawdowns_20d.append(
                value
            )

    win_rate_20d = None

    if values_20d:

        win_rate_20d = (
            sum(
                value > 0
                for value in values_20d
            )
            /
            len(
                values_20d
            )
            *
            100.0
        )

    return {
        "count":
            len(
                rows
            ),

        "avg_5d_pct":
            round_or_none(
                mean_or_none(
                    values_5d
                ),
                3,
            ),

        "avg_10d_pct":
            round_or_none(
                mean_or_none(
                    values_10d
                ),
                3,
            ),

        "avg_20d_pct":
            round_or_none(
                mean_or_none(
                    values_20d
                ),
                3,
            ),

        "median_20d_pct":
            round_or_none(
                median_or_none(
                    values_20d
                ),
                3,
            ),

        "win_rate_20d_pct":
            round_or_none(
                win_rate_20d,
                2,
            ),

        "avg_max_gain_20d_pct":
            round_or_none(
                mean_or_none(
                    gains_20d
                ),
                3,
            ),

        "avg_max_drawdown_20d_pct":
            round_or_none(
                mean_or_none(
                    drawdowns_20d
                ),
                3,
            ),
    }


def build_stage_summary(
    rows: list[
        dict[str, Any]
    ],
    stage_field: str,
) -> list[
    dict[str, Any]
]:

    groups: dict[
        str,
        list[
            dict[str, Any]
        ],
    ] = defaultdict(
        list
    )

    for row in rows:

        stage = str(
            row.get(
                stage_field
            )
            or
            "UNKNOWN"
        )

        groups[
            stage
        ].append(
            row
        )

    result = []

    for stage in STAGE_ORDER:

        result.append(
            {
                "stage":
                    stage,

                **summarize_group(
                    groups.get(
                        stage,
                        [],
                    )
                ),
            }
        )

    return result


# ============================================================
# BUILD
# ============================================================


def build_rows() -> list[
    dict[str, Any]
]:

    original_rows = (
        load_csv(
            BACKTEST_ROWS_FILE
        )
    )

    candidate_rows = (
        load_csv(
            TECHNICAL_V2_FILE
        )
    )

    candidate_map = {}

    for row in candidate_rows:

        key = (
            str(
                row.get(
                    "signal_date"
                )
            ),
            str(
                row.get(
                    "stock_id"
                )
            ),
        )

        candidate_map[
            key
        ] = row

    result = []

    missing_candidate = 0

    for original in original_rows:

        key = (
            str(
                original.get(
                    "signal_date"
                )
            ),
            str(
                original.get(
                    "stock_id"
                )
            ),
        )

        candidate = (
            candidate_map.get(
                key
            )
        )

        if candidate is None:

            missing_candidate += 1

            continue

        overall_v2 = safe_float(
            candidate.get(
                "overall_v2"
            )
        )

        technical_v2 = safe_float(
            candidate.get(
                "technical_v2"
            )
        )

        buy_zone_distance = safe_float(
            original.get(
                "buy_zone_distance_pct"
            )
        )

        breakout_distance = safe_float(
            original.get(
                "breakout_distance_pct"
            )
        )

        current_risk = safe_float(
            original.get(
                "current_risk_pct"
            )
        )

        stage_v1 = str(
            original.get(
                "stage"
            )
            or
            "WATCH"
        )

        stage_v2 = (
            build_stage_v2(
                overall=overall_v2,
                buy_zone_distance_pct=
                    buy_zone_distance,
                breakout_distance_pct=
                    breakout_distance,
                current_risk_pct=
                    current_risk,
            )
        )

        result.append(
            {
                "signal_date":
                    original.get(
                        "signal_date"
                    ),

                "stock_id":
                    original.get(
                        "stock_id"
                    ),

                "short_name":
                    original.get(
                        "short_name"
                    ),

                "market":
                    original.get(
                        "market"
                    ),

                "industry_name":
                    original.get(
                        "industry_name"
                    ),

                "close":
                    original.get(
                        "close"
                    ),

                "fundamental":
                    candidate.get(
                        "fundamental"
                    ),

                "chip":
                    candidate.get(
                        "chip"
                    ),

                "technical_v1":
                    candidate.get(
                        "technical_v1"
                    ),

                "technical_v2":
                    candidate.get(
                        "technical_v2"
                    ),

                "overall_v1":
                    candidate.get(
                        "overall_v1"
                    ),

                "overall_v2":
                    candidate.get(
                        "overall_v2"
                    ),

                "buy_zone_distance_pct":
                    original.get(
                        "buy_zone_distance_pct"
                    ),

                "breakout_distance_pct":
                    original.get(
                        "breakout_distance_pct"
                    ),

                "current_risk_pct":
                    original.get(
                        "current_risk_pct"
                    ),

                "stage_v1":
                    stage_v1,

                "stage_v2":
                    stage_v2,

                "future_return_5d":
                    original.get(
                        "future_return_5d"
                    ),

                "future_return_10d":
                    original.get(
                        "future_return_10d"
                    ),

                "future_return_20d":
                    original.get(
                        "future_return_20d"
                    ),

                "max_gain_20d":
                    original.get(
                        "max_gain_20d"
                    ),

                "max_drawdown_20d":
                    original.get(
                        "max_drawdown_20d"
                    ),
            }
        )

    if missing_candidate:

        print(
            f"[WARN] Missing candidate rows: "
            f"{missing_candidate:,}"
        )

    return result


# ============================================================
# OUTPUT
# ============================================================


def write_rows_csv(
    rows: list[
        dict[str, Any]
    ],
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "signal_date",
        "stock_id",
        "short_name",
        "market",
        "industry_name",
        "close",

        "fundamental",
        "chip",

        "technical_v1",
        "technical_v2",

        "overall_v1",
        "overall_v2",

        "buy_zone_distance_pct",
        "breakout_distance_pct",
        "current_risk_pct",

        "stage_v1",
        "stage_v2",

        "future_return_5d",
        "future_return_10d",
        "future_return_20d",

        "max_gain_20d",
        "max_drawdown_20d",
    ]

    with OUTPUT_ROWS_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            rows
        )

    print(
        f"[WRITE] {OUTPUT_ROWS_FILE}"
    )


def write_summary_csv(
    rows: list[
        dict[str, Any]
    ],
) -> None:

    fieldnames = [
        "stage",
        "count",
        "avg_5d_pct",
        "avg_10d_pct",
        "avg_20d_pct",
        "median_20d_pct",
        "win_rate_20d_pct",
        "avg_max_gain_20d_pct",
        "avg_max_drawdown_20d_pct",
    ]

    with OUTPUT_SUMMARY_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            rows
        )

    print(
        f"[WRITE] {OUTPUT_SUMMARY_FILE}"
    )


# ============================================================
# PRINT
# ============================================================


def print_summary(
    title: str,
    rows: list[
        dict[str, Any]
    ],
) -> None:

    print()

    print(
        "=" * 100
    )

    print(
        title
    )

    print(
        "=" * 100
    )

    print(
        "stage       count  "
        "avg5D   avg10D  avg20D  "
        "median20  win20%  "
        "maxGain20  maxDD20"
    )

    for row in rows:

        def fmt(
            key: str,
            width: int = 7,
        ) -> str:

            value = row.get(
                key
            )

            if value is None:

                return (
                    f"{'-':>{width}}"
                )

            return (
                f"{float(value):>{width}.2f}"
            )

        print(
            f"{row['stage']:10} "
            f"{row['count']:6} "
            f"{fmt('avg_5d_pct')} "
            f"{fmt('avg_10d_pct')} "
            f"{fmt('avg_20d_pct')} "
            f"{fmt('median_20d_pct', 8)} "
            f"{fmt('win_rate_20d_pct', 7)} "
            f"{fmt('avg_max_gain_20d_pct', 9)} "
            f"{fmt('avg_max_drawdown_20d_pct', 8)}"
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
        "- Stage V2 Candidate Backtest"
    )

    print(
        "=" * 80
    )

    try:

        rows = (
            build_rows()
        )

        if not rows:

            raise RuntimeError(
                "No rows generated"
            )

        stage_v1_summary = (
            build_stage_summary(
                rows,
                "stage_v1",
            )
        )

        stage_v2_summary = (
            build_stage_summary(
                rows,
                "stage_v2",
            )
        )

        write_rows_csv(
            rows
        )

        write_summary_csv(
            stage_v2_summary
        )

        print_summary(
            "STAGE V1",
            stage_v1_summary,
        )

        print_summary(
            "STAGE V2 CANDIDATE",
            stage_v2_summary,
        )

        print()

        print(
            "=" * 80
        )

        print(
            "RESULT"
        )

        print(
            "=" * 80
        )

        print(
            f"Rows : {len(rows):,}"
        )

        print()

        print(
            "[PASS] Stage V2 "
            "Candidate backtest completed"
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