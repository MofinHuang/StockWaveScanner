from __future__ import annotations

import bisect
import json
import math
import sys

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


# ============================================================
# CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = (
    ROOT
    / "docs"
    / "data"
    / "latest"
)

STOCKS_FILE = (
    DATA_DIR
    / "stocks.json"
)

TOP10_FILE = (
    DATA_DIR
    / "top10.json"
)

STATUS_FILE = (
    DATA_DIR
    / "status.json"
)

SCORE_MODEL_VERSION = "V2.1-DRAFT-2-SCORE-1"

TAIPEI = ZoneInfo(
    "Asia/Taipei"
)


# ============================================================
# HELPERS
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

        if callable(reconfigure):

            try:

                reconfigure(
                    encoding="utf-8",
                    errors="replace",
                )

            except Exception:
                pass


def now_iso() -> str:

    return (
        datetime
        .now(
            TAIPEI
        )
        .isoformat(
            timespec="seconds"
        )
    )


def load_json(
    path: Path,
) -> dict[str, Any]:

    if not path.exists():

        raise RuntimeError(
            f"File not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


def write_json(
    path: Path,
    payload: Any,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write(
            "\n"
        )

    print(
        f"[WRITE] {path}"
    )


def number(
    value: Any,
) -> float | None:

    if value is None:

        return None

    try:

        result = float(
            value
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


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def rounded(
    value: float | None,
    digits: int = 1,
) -> float | None:

    if value is None:

        return None

    return round(
        value,
        digits,
    )


def average(
    values: list[
        float | None
    ],
    minimum_count: int = 1,
) -> float | None:

    valid = [
        value

        for value
        in values

        if value is not None
    ]

    if len(
        valid
    ) < minimum_count:

        return None

    return (
        sum(
            valid
        )
        /
        len(
            valid
        )
    )


# ============================================================
# PERCENTILE
# ============================================================


def percentile_rank(
    sorted_values: list[float],
    value: float | None,
) -> float | None:

    if (
        value is None
        or
        not sorted_values
    ):

        return None

    if len(
        sorted_values
    ) == 1:

        return 50.0

    left = (
        bisect.bisect_left(
            sorted_values,
            value,
        )
    )

    right = (
        bisect.bisect_right(
            sorted_values,
            value,
        )
    )

    midpoint = (
        left
        +
        right
        -
        1
    ) / 2.0

    return clamp(
        midpoint
        /
        (
            len(
                sorted_values
            )
            -
            1
        )
        *
        100.0
    )


def get_metric(
    stock: dict[str, Any],
    metric: str,
) -> float | None:

    technical = (
        stock.get(
            "technical"
        )
        or {}
    )

    institutional = (
        stock.get(
            "institutional"
        )
        or {}
    )

    tdcc = (
        stock.get(
            "tdcc"
        )
        or {}
    )

    fundamental = (
        stock.get(
            "fundamental"
        )
        or {}
    )

    revenue = (
        fundamental.get(
            "revenue"
        )
        or {}
    )

    financial = (
        fundamental.get(
            "financial"
        )
        or {}
    )

    mapping = {
        "return_20d":
            technical.get(
                "return_20d_pct"
            ),

        "return_5d":
            technical.get(
                "return_5d_pct"
            ),

        "foreign_20d":
            institutional.get(
                "foreign_20d_net"
            ),

        "foreign_5d":
            institutional.get(
                "foreign_5d_net"
            ),

        "trust_5d":
            institutional.get(
                "trust_5d_net"
            ),

        "large_holder_pct":
            tdcc.get(
                "large_holder_pct"
            ),

        "large_holder_change":
            tdcc.get(
                "large_holder_change"
            ),

        "revenue_yoy":
            revenue.get(
                "revenue_yoy_pct"
            ),

        "cumulative_yoy":
            revenue.get(
                "cumulative_yoy_pct"
            ),

        "eps":
            financial.get(
                "eps"
            ),

        "operating_margin":
            financial.get(
                "operating_margin_pct"
            ),

        "net_margin":
            financial.get(
                "net_margin_pct"
            ),
    }

    return number(
        mapping.get(
            metric
        )
    )


def build_percentile_maps(
    stocks: list[
        dict[str, Any]
    ],
) -> dict[
    str,
    list[float],
]:

    metrics = (
        "return_20d",
        "return_5d",
        "foreign_20d",
        "foreign_5d",
        "trust_5d",
        "large_holder_pct",
        "large_holder_change",
        "revenue_yoy",
        "cumulative_yoy",
        "eps",
        "operating_margin",
        "net_margin",
    )

    result: dict[
        str,
        list[float],
    ] = {}

    for metric in metrics:

        values = []

        for stock in stocks:

            value = (
                get_metric(
                    stock,
                    metric,
                )
            )

            if value is not None:

                values.append(
                    value
                )

        values.sort()

        result[
            metric
        ] = values

    return result


def metric_percentile(
    stock: dict[str, Any],
    metric: str,
    maps: dict[
        str,
        list[float],
    ],
) -> float | None:

    return percentile_rank(
        maps.get(
            metric,
            [],
        ),
        get_metric(
            stock,
            metric,
        ),
    )


# ============================================================
# COMPONENT SCORES
# ============================================================


def trend_score(
    stock: dict[str, Any],
) -> float | None:

    latest = (
        stock.get(
            "latest"
        )
        or {}
    )

    technical = (
        stock.get(
            "technical"
        )
        or {}
    )

    close = number(
        latest.get(
            "close"
        )
    )

    ma20 = number(
        technical.get(
            "ma20"
        )
    )

    ma60 = number(
        technical.get(
            "ma60"
        )
    )

    return20 = number(
        technical.get(
            "return_20d_pct"
        )
    )

    if (
        close is None
        or
        ma20 is None
        or
        ma60 is None
        or
        return20 is None
    ):

        return None

    score = 0.0

    if close > ma20:

        score += 30.0

    elif close >= ma20 * 0.97:

        score += 18.0

    if ma20 > ma60:

        score += 35.0

    elif ma20 >= ma60 * 0.98:

        score += 18.0

    if close > ma60:

        score += 15.0

    momentum = clamp(
        50.0
        +
        return20
        *
        3.0
    )

    score += (
        momentum
        *
        0.20
    )

    return clamp(
        score
    )


def relative_strength_score(
    stock: dict[str, Any],
    maps: dict[
        str,
        list[float],
    ],
) -> float | None:

    return (
        metric_percentile(
            stock,
            "return_20d",
            maps,
        )
    )


def momentum_volume_score(
    stock: dict[str, Any],
    maps: dict[
        str,
        list[float],
    ],
) -> float | None:

    technical = (
        stock.get(
            "technical"
        )
        or {}
    )

    return_rank = (
        metric_percentile(
            stock,
            "return_5d",
            maps,
        )
    )

    volume_ratio = number(
        technical.get(
            "volume_ratio_20"
        )
    )

    volume_score = None

    if volume_ratio is not None:

        volume_score = clamp(
            volume_ratio
            /
            2.0
            *
            100.0
        )

    if (
        return_rank is None
        or
        volume_score is None
    ):

        return None

    return (
        return_rank
        *
        0.65
        +
        volume_score
        *
        0.35
    )


def chip_score(
    stock: dict[str, Any],
    maps: dict[
        str,
        list[float],
    ],
) -> float | None:

    parts = [
        metric_percentile(
            stock,
            "foreign_20d",
            maps,
        ),

        metric_percentile(
            stock,
            "trust_5d",
            maps,
        ),

        metric_percentile(
            stock,
            "large_holder_pct",
            maps,
        ),

        metric_percentile(
            stock,
            "large_holder_change",
            maps,
        ),
    ]

    return average(
        parts,
        minimum_count=2,
    )


def fundamental_score(
    stock: dict[str, Any],
    maps: dict[
        str,
        list[float],
    ],
) -> float | None:

    parts = [
        metric_percentile(
            stock,
            "revenue_yoy",
            maps,
        ),

        metric_percentile(
            stock,
            "cumulative_yoy",
            maps,
        ),

        metric_percentile(
            stock,
            "eps",
            maps,
        ),

        metric_percentile(
            stock,
            "operating_margin",
            maps,
        ),

        metric_percentile(
            stock,
            "net_margin",
            maps,
        ),
    ]

    return average(
        parts,
        minimum_count=3,
    )


# ============================================================
# TIMING
# ============================================================


def timing_score(
    stock: dict[str, Any],
    maps: dict[
        str,
        list[float],
    ],
) -> float | None:

    latest = (
        stock.get(
            "latest"
        )
        or {}
    )

    technical = (
        stock.get(
            "technical"
        )
        or {}
    )

    close = number(
        latest.get(
            "close"
        )
    )

    ma20 = number(
        technical.get(
            "ma20"
        )
    )

    return5 = number(
        technical.get(
            "return_5d_pct"
        )
    )

    volume_ratio = number(
        technical.get(
            "volume_ratio_20"
        )
    )

    foreign_rank = (
        metric_percentile(
            stock,
            "foreign_5d",
            maps,
        )
    )

    if (
        close is None
        or
        ma20 is None
        or
        ma20 == 0
        or
        return5 is None
        or
        volume_ratio is None
        or
        foreign_rank is None
    ):

        return None

    distance = (
        close
        /
        ma20
        -
        1
    ) * 100.0

    # 最佳位置約落在 MA20 附近至 MA20 +3%
    if (
        -1.5
        <= distance
        <= 3.0
    ):

        proximity = 100.0

    elif distance < -1.5:

        proximity = clamp(
            100.0
            -
            abs(
                distance
                +
                1.5
            )
            *
            8.0
        )

    else:

        proximity = clamp(
            100.0
            -
            (
                distance
                -
                3.0
            )
            *
            7.0
        )

    momentum = clamp(
        50.0
        +
        return5
        *
        5.0
    )

    # 過熱不再持續加分
    if return5 > 12.0:

        momentum = max(
            40.0,
            100.0
            -
            (
                return5
                -
                12.0
            )
            *
            5.0
        )

    volume = clamp(
        volume_ratio
        /
        2.0
        *
        100.0
    )

    return (
        proximity
        *
        0.35
        +
        momentum
        *
        0.25
        +
        volume
        *
        0.20
        +
        foreign_rank
        *
        0.20
    )


# ============================================================
# STAGE / TRADE PLAN
# ============================================================


def build_stage(
    stock: dict[str, Any],
    strength: float,
    timing: float,
) -> dict[str, str]:

    latest = (
        stock.get(
            "latest"
        )
        or {}
    )

    technical = (
        stock.get(
            "technical"
        )
        or {}
    )

    close = number(
        latest.get(
            "close"
        )
    )

    ma20 = number(
        technical.get(
            "ma20"
        )
    )

    atr = number(
        technical.get(
            "atr14"
        )
    )

    return5 = number(
        technical.get(
            "return_5d_pct"
        )
    )

    extended = False

    if (
        close is not None
        and
        ma20 is not None
        and
        atr is not None
        and
        close
        >
        ma20
        +
        atr
        *
        2.0
    ):

        extended = True

    if (
        return5 is not None
        and
        return5 > 12.0
    ):

        extended = True

    if extended:

        return {
            "code":
                "EXTENDED",

            "label":
                "漲幅延伸",
        }

    if strength < 55:

        return {
            "code":
                "AVOID",

            "label":
                "暫不關注",
        }

    if (
        strength >= 75
        and
        timing >= 70
    ):

        return {
            "code":
                "TRIGGER",

            "label":
                "進場訊號",
        }

    if strength >= 70:

        return {
            "code":
                "SETUP",

            "label":
                "型態準備",
        }

    return {
        "code":
            "WATCH",

        "label":
            "持續觀察",
    }


def build_action(
    stage_code: str,
) -> str:

    mapping = {
        "TRIGGER":
            "可列入今日優先觀察",

        "SETUP":
            "等待 Timing 改善",

        "WATCH":
            "持續追蹤，暫不追價",

        "EXTENDED":
            "股價偏離買點，等待拉回",

        "AVOID":
            "目前條件不足",
    }

    return mapping.get(
        stage_code,
        "等待資料補齊",
    )


def build_trade_plan(
    stock: dict[str, Any],
) -> dict[str, float | None]:

    latest = (
        stock.get(
            "latest"
        )
        or {}
    )

    technical = (
        stock.get(
            "technical"
        )
        or {}
    )

    close = number(
        latest.get(
            "close"
        )
    )

    ma20 = number(
        technical.get(
            "ma20"
        )
    )

    atr = number(
        technical.get(
            "atr14"
        )
    )

    if (
        close is None
        or
        ma20 is None
        or
        atr is None
        or
        atr <= 0
    ):

        return {
            "buy_zone_low":
                None,

            "buy_zone_high":
                None,

            "risk_price":
                None,

            "risk_pct":
                None,

            "target_low":
                None,

            "target_high":
                None,
        }

    buy_low = max(
        0.01,
        ma20
        -
        atr
        *
        0.25,
    )

    buy_high = (
        ma20
        +
        atr
        *
        0.50
    )

    risk_price = max(
        0.01,
        buy_low
        -
        atr
        *
        1.50,
    )

    target_low = (
        buy_high
        +
        atr
        *
        2.0
    )

    target_high = (
        buy_high
        +
        atr
        *
        3.0
    )

    risk_pct = (
        (
            risk_price
            /
            buy_high
            -
            1
        )
        *
        100.0
    )

    return {
        "buy_zone_low":
            rounded(
                buy_low,
                2,
            ),

        "buy_zone_high":
            rounded(
                buy_high,
                2,
            ),

        "risk_price":
            rounded(
                risk_price,
                2,
            ),

        "risk_pct":
            rounded(
                risk_pct,
                2,
            ),

        "target_low":
            rounded(
                target_low,
                2,
            ),

        "target_high":
            rounded(
                target_high,
                2,
            ),
    }


# ============================================================
# STOCK SCORING
# ============================================================


def score_stock(
    stock: dict[str, Any],
    maps: dict[
        str,
        list[float],
    ],
) -> bool:

    readiness = (
        stock.get(
            "readiness"
        )
        or {}
    )

    if (
        readiness.get(
            "overall"
        )
        != "READY"
    ):

        stock[
            "scores"
        ] = {
            "trend":
                None,

            "relative_strength":
                None,

            "momentum_volume":
                None,

            "chip":
                None,

            "fundamental":
                None,

            "strength":
                None,

            "timing":
                None,

            "buy_priority":
                None,

            "status":
                "WAITING_DATA",

            "model_version":
                SCORE_MODEL_VERSION,
        }

        stock[
            "stage"
        ] = {
            "code":
                "WAITING_DATA",

            "label":
                "資料補齊中",
        }

        stock[
            "action"
        ] = (
            "等待資料補齊"
        )

        return False

    trend = (
        trend_score(
            stock
        )
    )

    relative = (
        relative_strength_score(
            stock,
            maps,
        )
    )

    momentum = (
        momentum_volume_score(
            stock,
            maps,
        )
    )

    chip = (
        chip_score(
            stock,
            maps,
        )
    )

    fundamental = (
        fundamental_score(
            stock,
            maps,
        )
    )

    timing = (
        timing_score(
            stock,
            maps,
        )
    )

    components = (
        trend,
        relative,
        momentum,
        chip,
        fundamental,
        timing,
    )

    if any(
        value is None

        for value
        in components
    ):

        stock[
            "scores"
        ] = {
            "trend":
                rounded(
                    trend
                ),

            "relative_strength":
                rounded(
                    relative
                ),

            "momentum_volume":
                rounded(
                    momentum
                ),

            "chip":
                rounded(
                    chip
                ),

            "fundamental":
                rounded(
                    fundamental
                ),

            "strength":
                None,

            "timing":
                rounded(
                    timing
                ),

            "buy_priority":
                None,

            "status":
                "WAITING_DATA",

            "model_version":
                SCORE_MODEL_VERSION,
        }

        stock[
            "stage"
        ] = {
            "code":
                "WAITING_DATA",

            "label":
                "資料補齊中",
        }

        stock[
            "action"
        ] = (
            "部分評分欄位資料不足"
        )

        return False

    strength = (
        trend
        *
        0.30
        +
        relative
        *
        0.20
        +
        momentum
        *
        0.15
        +
        chip
        *
        0.20
        +
        fundamental
        *
        0.15
    )

    buy_priority = (
        strength
        *
        0.65
        +
        timing
        *
        0.35
    )

    stage = (
        build_stage(
            stock,
            strength,
            timing,
        )
    )

    stock[
        "scores"
    ] = {
        "trend":
            rounded(
                trend
            ),

        "relative_strength":
            rounded(
                relative
            ),

        "momentum_volume":
            rounded(
                momentum
            ),

        "chip":
            rounded(
                chip
            ),

        "fundamental":
            rounded(
                fundamental
            ),

        "strength":
            rounded(
                strength
            ),

        "timing":
            rounded(
                timing
            ),

        "buy_priority":
            rounded(
                buy_priority
            ),

        "status":
            "READY",

        "model_version":
            SCORE_MODEL_VERSION,
    }

    stock[
        "stage"
    ] = stage

    stock[
        "trade_plan"
    ] = (
        build_trade_plan(
            stock
        )
    )

    stock[
        "action"
    ] = (
        build_action(
            stage[
                "code"
            ]
        )
    )

    return True


# ============================================================
# TOP10
# ============================================================


def build_top10(
    stocks: list[
        dict[str, Any]
    ],
    data_date: str | None,
) -> dict[str, Any]:

    eligible = [
        stock

        for stock
        in stocks

        if (
            stock.get(
                "scores",
                {},
            )
            .get(
                "status"
            )
            ==
            "READY"
        )
    ]

    eligible.sort(
        key=lambda stock: (
            -(
                number(
                    stock[
                        "scores"
                    ].get(
                        "buy_priority"
                    )
                )
                or
                0
            ),

            -(
                number(
                    stock[
                        "scores"
                    ].get(
                        "strength"
                    )
                )
                or
                0
            ),

            stock.get(
                "stock_id",
                "",
            ),
        )
    )

    selected = (
        eligible[
            :10
        ]
    )

    rows = []

    for (
        index,
        stock,
    ) in enumerate(
        selected,
        start=1,
    ):

        rows.append(
            {
                "rank":
                    index,

                "stock_id":
                    stock.get(
                        "stock_id"
                    ),

                "short_name":
                    stock.get(
                        "short_name"
                    ),

                "market":
                    stock.get(
                        "market"
                    ),

                "industry_name":
                    stock.get(
                        "industry_name"
                    ),

                "close":
                    stock.get(
                        "latest",
                        {},
                    )
                    .get(
                        "close"
                    ),

                "change_pct":
                    stock.get(
                        "latest",
                        {},
                    )
                    .get(
                        "change_pct"
                    ),

                "strength":
                    stock[
                        "scores"
                    ].get(
                        "strength"
                    ),

                "timing":
                    stock[
                        "scores"
                    ].get(
                        "timing"
                    ),

                "buy_priority":
                    stock[
                        "scores"
                    ].get(
                        "buy_priority"
                    ),

                "stage":
                    stock.get(
                        "stage"
                    ),

                "action":
                    stock.get(
                        "action"
                    ),
            }
        )

    if len(
        eligible
    ) >= 10:

        status = "READY"

        message = (
            "TOP10 已依 Buy Priority 排序。"
        )

    elif eligible:

        status = "PARTIAL"

        message = (
            "目前可完整評分股票不足 10 檔，"
            "待歷史資料逐步補齊。"
        )

    else:

        status = "WAITING_DATA"

        message = (
            "尚無股票具備完整評分資料，"
            "歷史資料將由排程由近往遠補齊。"
        )

    return {
        "model_version":
            SCORE_MODEL_VERSION,

        "data_date":
            data_date,

        "generated_at":
            now_iso(),

        "status":
            status,

        "message":
            message,

        "eligible_count":
            len(
                eligible
            ),

        "rows":
            rows,
    }


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    configure_console()

    print(
        "=" * 80
    )

    print(
        "StockWaveScanner V2 - Score Engine"
    )

    print(
        "=" * 80
    )

    try:

        payload = (
            load_json(
                STOCKS_FILE
            )
        )

        stocks = (
            payload.get(
                "stocks"
            )
            or []
        )

        if not stocks:

            raise RuntimeError(
                "stocks.json contains no stocks"
            )

        print(
            f"Stocks      : "
            f"{len(stocks):,}"
        )

        maps = (
            build_percentile_maps(
                stocks
            )
        )

        scored_count = 0

        for stock in stocks:

            if score_stock(
                stock,
                maps,
            ):

                scored_count += 1

        payload[
            "score_model_version"
        ] = SCORE_MODEL_VERSION

        payload[
            "scored_at"
        ] = now_iso()

        payload[
            "scored_count"
        ] = scored_count

        write_json(
            STOCKS_FILE,
            payload,
        )

        top10 = (
            build_top10(
                stocks,
                payload.get(
                    "data_date"
                ),
            )
        )

        write_json(
            TOP10_FILE,
            top10,
        )

        status = (
            load_json(
                STATUS_FILE
            )
        )

        total = len(
            stocks
        )

        status[
            "score_model"
        ] = {
            "version":
                SCORE_MODEL_VERSION,

            "status":
                (
                    "READY"
                    if scored_count
                    else
                    "WAITING_DATA"
                ),

            "scored_stocks":
                scored_count,

            "total_stocks":
                total,

            "percent":
                round(
                    scored_count
                    /
                    total
                    *
                    100,
                    1,
                )
                if total
                else
                0,

            "updated_at":
                now_iso(),
        }

        write_json(
            STATUS_FILE,
            status,
        )

        print()

        print(
            "=" * 80
        )

        print(
            "SCORE RESULT"
        )

        print(
            "=" * 80
        )

        print(
            f"Total Stocks : "
            f"{total:,}"
        )

        print(
            f"Scored       : "
            f"{scored_count:,}"
        )

        print(
            f"Waiting      : "
            f"{total - scored_count:,}"
        )

        print(
            f"TOP10 Rows   : "
            f"{len(top10['rows'])}"
        )

        print()

        print(
            "[PASS] V2 score snapshot generated"
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