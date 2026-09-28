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
    / "backtest_rows.csv"
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
    / "technical_v2_candidate_rows.csv"
)

OUTPUT_TECHNICAL_SUMMARY_FILE = (
    OUTPUT_DIR
    / "technical_v2_candidate_summary.csv"
)

OUTPUT_OVERALL_SUMMARY_FILE = (
    OUTPUT_DIR
    / "overall_v2_candidate_summary.csv"
)


BUCKET_ORDER = [
    "00-39",
    "40-49",
    "50-59",
    "60-69",
    "70-79",
    "80+",
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
# BASIC HELPERS
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


def clamp(
    value: float,
    low: float = 0.0,
    high: float = 100.0,
) -> float:

    return max(
        low,
        min(
            high,
            value,
        ),
    )


def weighted_average(
    items: list[
        tuple[
            float | None,
            float,
        ]
    ],
) -> float | None:

    total_weight = 0.0
    total_value = 0.0

    for (
        value,
        weight,
    ) in items:

        if value is None:

            continue

        total_value += (
            value
            *
            weight
        )

        total_weight += (
            weight
        )

    if total_weight <= 0:

        return None

    return (
        total_value
        /
        total_weight
    )


def score_bucket(
    value: float | None,
) -> str:

    if value is None:

        return "UNKNOWN"

    if value < 40:

        return "00-39"

    if value < 50:

        return "40-49"

    if value < 60:

        return "50-59"

    if value < 70:

        return "60-69"

    if value < 80:

        return "70-79"

    return "80+"


# ============================================================
# SCORE CURVES
# ============================================================


def score_ma20_ma60_distance(
    value: float | None,
) -> float | None:

    if value is None:

        return None

    if value < -10:

        return 55.0

    if value < -5:

        return 70.0

    if value < 0:

        return 80.0

    if value < 5:

        return 85.0

    if value < 10:

        return 60.0

    return 25.0


def score_close_ma20_distance(
    value: float | None,
) -> float | None:

    if value is None:

        return None

    if value < -10:

        return 60.0

    if value < -5:

        return 75.0

    if value < 0:

        return 90.0

    if value < 5:

        return 85.0

    if value < 10:

        return 60.0

    if value < 20:

        return 35.0

    return 10.0


def score_atr_position(
    value: float | None,
) -> float | None:

    if value is None:

        return None

    if value < -3:

        return 55.0

    if value < -2:

        return 70.0

    if value < -1:

        return 85.0

    if value <= 1:

        return 90.0

    if value <= 2:

        return 75.0

    if value <= 3:

        return 55.0

    if value <= 4:

        return 35.0

    return 15.0


def score_return_20d(
    value: float | None,
) -> float | None:

    if value is None:

        return None

    if value < -10:

        return 55.0

    if value < -5:

        return 75.0

    if value < 0:

        return 85.0

    if value < 5:

        return 80.0

    if value < 10:

        return 60.0

    if value < 20:

        return 40.0

    return 15.0


def score_return_5d(
    value: float | None,
) -> float | None:

    if value is None:

        return None

    if value < -5:

        return 60.0

    if value < 0:

        return 85.0

    if value < 3:

        return 80.0

    if value < 6:

        return 60.0

    if value < 10:

        return 40.0

    return 20.0


def score_volume_ratio(
    value: float | None,
) -> float | None:

    if value is None:

        return None

    if value < 0.5:

        return 55.0

    if value < 0.8:

        return 80.0

    if value < 1.2:

        return 85.0

    if value < 1.5:

        return 70.0

    if value < 2.0:

        return 55.0

    return 35.0


# ============================================================
# TECHNICAL V2 CANDIDATE
# ============================================================


def calculate_technical_v2(
    row: dict[str, Any],
) -> dict[str, float | None]:

    close = safe_float(
        row.get(
            "close"
        )
    )

    ma20 = safe_float(
        row.get(
            "ma20"
        )
    )

    ma60 = safe_float(
        row.get(
            "ma60"
        )
    )

    atr14 = safe_float(
        row.get(
            "atr14"
        )
    )

    return_5d = safe_float(
        row.get(
            "return_5d_pct"
        )
    )

    return_20d = safe_float(
        row.get(
            "return_20d_pct"
        )
    )

    volume_ratio = safe_float(
        row.get(
            "volume_ratio_20"
        )
    )

    ma20_ma60_pct = None

    if (
        ma20 is not None
        and
        ma60 is not None
        and
        ma60 != 0
    ):

        ma20_ma60_pct = (
            ma20
            /
            ma60
            -
            1.0
        ) * 100.0

    close_ma20_pct = None

    if (
        close is not None
        and
        ma20 is not None
        and
        ma20 != 0
    ):

        close_ma20_pct = (
            close
            /
            ma20
            -
            1.0
        ) * 100.0

    close_ma20_atr = None

    if (
        close is not None
        and
        ma20 is not None
        and
        atr14 is not None
        and
        atr14 > 0
    ):

        close_ma20_atr = (
            close
            -
            ma20
        ) / atr14

    trend_structure = (
        weighted_average(
            [
                (
                    score_ma20_ma60_distance(
                        ma20_ma60_pct
                    ),
                    0.60,
                ),
                (
                    score_close_ma20_distance(
                        close_ma20_pct
                    ),
                    0.40,
                ),
            ]
        )
    )

    price_position = (
        weighted_average(
            [
                (
                    score_close_ma20_distance(
                        close_ma20_pct
                    ),
                    0.70,
                ),
                (
                    score_atr_position(
                        close_ma20_atr
                    ),
                    0.30,
                ),
            ]
        )
    )

    momentum_quality = (
        weighted_average(
            [
                (
                    score_return_20d(
                        return_20d
                    ),
                    0.45,
                ),
                (
                    score_return_5d(
                        return_5d
                    ),
                    0.30,
                ),
                (
                    score_volume_ratio(
                        volume_ratio
                    ),
                    0.25,
                ),
            ]
        )
    )

    technical_v2 = (
        weighted_average(
            [
                (
                    trend_structure,
                    0.35,
                ),
                (
                    price_position,
                    0.40,
                ),
                (
                    momentum_quality,
                    0.25,
                ),
            ]
        )
    )

    return {
        "ma20_ma60_pct":
            round_or_none(
                ma20_ma60_pct,
                4,
            ),

        "close_ma20_pct":
            round_or_none(
                close_ma20_pct,
                4,
            ),

        "close_ma20_atr":
            round_or_none(
                close_ma20_atr,
                4,
            ),

        "trend_structure_v2":
            round_or_none(
                trend_structure,
                2,
            ),

        "price_position_v2":
            round_or_none(
                price_position,
                2,
            ),

        "momentum_quality_v2":
            round_or_none(
                momentum_quality,
                2,
            ),

        "technical_v2":
            round_or_none(
                technical_v2,
                2,
            ),
    }


# ============================================================
# SUMMARY
# ============================================================


def summarize_rows(
    rows: list[
        dict[str, Any]
    ],
    score_field: str,
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

        score = safe_float(
            row.get(
                score_field
            )
        )

        future_20d = safe_float(
            row.get(
                "future_return_20d"
            )
        )

        if (
            score is None
            or
            future_20d is None
        ):

            continue

        bucket = (
            score_bucket(
                score
            )
        )

        groups[
            bucket
        ].append(
            row
        )

    result = []

    for bucket in BUCKET_ORDER:

        bucket_rows = (
            groups.get(
                bucket,
                [],
            )
        )

        values_5d = []
        values_10d = []
        values_20d = []
        gains_20d = []
        drawdowns_20d = []

        for row in bucket_rows:

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

        avg_5d = (
            statistics.fmean(
                values_5d
            )
            if values_5d
            else None
        )

        avg_10d = (
            statistics.fmean(
                values_10d
            )
            if values_10d
            else None
        )

        avg_20d = (
            statistics.fmean(
                values_20d
            )
            if values_20d
            else None
        )

        median_20d = (
            statistics.median(
                values_20d
            )
            if values_20d
            else None
        )

        win_rate = (
            (
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
            if values_20d
            else None
        )

        avg_gain = (
            statistics.fmean(
                gains_20d
            )
            if gains_20d
            else None
        )

        avg_drawdown = (
            statistics.fmean(
                drawdowns_20d
            )
            if drawdowns_20d
            else None
        )

        result.append(
            {
                "bucket":
                    bucket,

                "count":
                    len(
                        bucket_rows
                    ),

                "avg_5d_pct":
                    round_or_none(
                        avg_5d,
                        3,
                    ),

                "avg_10d_pct":
                    round_or_none(
                        avg_10d,
                        3,
                    ),

                "avg_20d_pct":
                    round_or_none(
                        avg_20d,
                        3,
                    ),

                "median_20d_pct":
                    round_or_none(
                        median_20d,
                        3,
                    ),

                "win_rate_20d_pct":
                    round_or_none(
                        win_rate,
                        2,
                    ),

                "avg_max_gain_20d_pct":
                    round_or_none(
                        avg_gain,
                        3,
                    ),

                "avg_max_drawdown_20d_pct":
                    round_or_none(
                        avg_drawdown,
                        3,
                    ),
            }
        )

    return result


# ============================================================
# CSV
# ============================================================


def load_rows() -> list[
    dict[str, Any]
]:

    if not INPUT_FILE.exists():

        raise RuntimeError(
            f"Input file not found: {INPUT_FILE}"
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
            "backtest_rows.csv is empty"
        )

    required_columns = {
        "signal_date",
        "stock_id",
        "close",
        "ma20",
        "ma60",
        "atr14",
        "return_5d_pct",
        "return_20d_pct",
        "volume_ratio_20",
        "fundamental",
        "chip",
        "technical",
        "overall",
        "future_return_5d",
        "future_return_10d",
        "future_return_20d",
        "max_gain_20d",
        "max_drawdown_20d",
    }

    columns = set(
        rows[0].keys()
    )

    missing = (
        required_columns
        -
        columns
    )

    if missing:

        raise RuntimeError(
            "Missing columns in "
            "backtest_rows.csv: "
            +
            ", ".join(
                sorted(
                    missing
                )
            )
        )

    return rows


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
        "ma20",
        "ma60",
        "atr14",

        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
        "volume_ratio_20",

        "ma20_ma60_pct",
        "close_ma20_pct",
        "close_ma20_atr",

        "trend_structure_v2",
        "price_position_v2",
        "momentum_quality_v2",

        "technical_v1",
        "technical_v2",

        "fundamental",
        "chip",

        "overall_v1",
        "overall_v2",

        "stage",

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
    path: Path,
    rows: list[
        dict[str, Any]
    ],
) -> None:

    fieldnames = [
        "bucket",
        "count",
        "avg_5d_pct",
        "avg_10d_pct",
        "avg_20d_pct",
        "median_20d_pct",
        "win_rate_20d_pct",
        "avg_max_gain_20d_pct",
        "avg_max_drawdown_20d_pct",
    ]

    with path.open(
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
        f"[WRITE] {path}"
    )


# ============================================================
# CONSOLE SUMMARY
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
        "bucket      count  "
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
            f"{row['bucket']:10} "
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
        "- Technical V2 Candidate Backtest"
    )

    print(
        "=" * 80
    )

    try:

        source_rows = (
            load_rows()
        )

        output_rows = []

        for source in source_rows:

            candidate = (
                calculate_technical_v2(
                    source
                )
            )

            fundamental = (
                safe_float(
                    source.get(
                        "fundamental"
                    )
                )
            )

            chip = (
                safe_float(
                    source.get(
                        "chip"
                    )
                )
            )

            technical_v1 = (
                safe_float(
                    source.get(
                        "technical"
                    )
                )
            )

            overall_v1 = (
                safe_float(
                    source.get(
                        "overall"
                    )
                )
            )

            technical_v2 = (
                candidate.get(
                    "technical_v2"
                )
            )

            overall_v2 = (
                weighted_average(
                    [
                        (
                            fundamental,
                            0.30,
                        ),
                        (
                            chip,
                            0.30,
                        ),
                        (
                            technical_v2,
                            0.40,
                        ),
                    ]
                )
            )

            output_rows.append(
                {
                    "signal_date":
                        source.get(
                            "signal_date"
                        ),

                    "stock_id":
                        source.get(
                            "stock_id"
                        ),

                    "short_name":
                        source.get(
                            "short_name"
                        ),

                    "market":
                        source.get(
                            "market"
                        ),

                    "industry_name":
                        source.get(
                            "industry_name"
                        ),

                    "close":
                        source.get(
                            "close"
                        ),

                    "ma20":
                        source.get(
                            "ma20"
                        ),

                    "ma60":
                        source.get(
                            "ma60"
                        ),

                    "atr14":
                        source.get(
                            "atr14"
                        ),

                    "return_5d_pct":
                        source.get(
                            "return_5d_pct"
                        ),

                    "return_10d_pct":
                        source.get(
                            "return_10d_pct"
                        ),

                    "return_20d_pct":
                        source.get(
                            "return_20d_pct"
                        ),

                    "volume_ratio_20":
                        source.get(
                            "volume_ratio_20"
                        ),

                    "ma20_ma60_pct":
                        candidate.get(
                            "ma20_ma60_pct"
                        ),

                    "close_ma20_pct":
                        candidate.get(
                            "close_ma20_pct"
                        ),

                    "close_ma20_atr":
                        candidate.get(
                            "close_ma20_atr"
                        ),

                    "trend_structure_v2":
                        candidate.get(
                            "trend_structure_v2"
                        ),

                    "price_position_v2":
                        candidate.get(
                            "price_position_v2"
                        ),

                    "momentum_quality_v2":
                        candidate.get(
                            "momentum_quality_v2"
                        ),

                    "technical_v1":
                        round_or_none(
                            technical_v1,
                            2,
                        ),

                    "technical_v2":
                        round_or_none(
                            technical_v2,
                            2,
                        ),

                    "fundamental":
                        round_or_none(
                            fundamental,
                            2,
                        ),

                    "chip":
                        round_or_none(
                            chip,
                            2,
                        ),

                    "overall_v1":
                        round_or_none(
                            overall_v1,
                            2,
                        ),

                    "overall_v2":
                        round_or_none(
                            overall_v2,
                            2,
                        ),

                    "stage":
                        source.get(
                            "stage"
                        ),

                    "future_return_5d":
                        source.get(
                            "future_return_5d"
                        ),

                    "future_return_10d":
                        source.get(
                            "future_return_10d"
                        ),

                    "future_return_20d":
                        source.get(
                            "future_return_20d"
                        ),

                    "max_gain_20d":
                        source.get(
                            "max_gain_20d"
                        ),

                    "max_drawdown_20d":
                        source.get(
                            "max_drawdown_20d"
                        ),
                }
            )

        technical_v1_summary = (
            summarize_rows(
                output_rows,
                "technical_v1",
            )
        )

        technical_v2_summary = (
            summarize_rows(
                output_rows,
                "technical_v2",
            )
        )

        overall_v1_summary = (
            summarize_rows(
                output_rows,
                "overall_v1",
            )
        )

        overall_v2_summary = (
            summarize_rows(
                output_rows,
                "overall_v2",
            )
        )

        write_rows_csv(
            output_rows
        )

        write_summary_csv(
            OUTPUT_TECHNICAL_SUMMARY_FILE,
            technical_v2_summary,
        )

        write_summary_csv(
            OUTPUT_OVERALL_SUMMARY_FILE,
            overall_v2_summary,
        )

        print_summary(
            "TECHNICAL V1",
            technical_v1_summary,
        )

        print_summary(
            "TECHNICAL V2 CANDIDATE",
            technical_v2_summary,
        )

        print_summary(
            "OVERALL V1",
            overall_v1_summary,
        )

        print_summary(
            "OVERALL V2 CANDIDATE",
            overall_v2_summary,
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
            f"Rows : {len(output_rows):,}"
        )

        print()

        print(
            "[PASS] Technical V2 "
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