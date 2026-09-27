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

DATA_DIR = ROOT / "docs" / "data" / "latest"

STOCKS_FILE = DATA_DIR / "stocks.json"
TOP10_FILE = DATA_DIR / "top10.json"
ACTION_PRIORITY_FILE = DATA_DIR / "action_priority.json"
STATUS_FILE = DATA_DIR / "status.json"

SCORE_MODEL_VERSION = "V3-STEP4E-RESEARCH-1"

TAIPEI = ZoneInfo("Asia/Taipei")


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
        .now(TAIPEI)
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

        return json.load(file)


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

        file.write("\n")

    print(
        f"[WRITE] {path}"
    )


def number(
    value: Any,
) -> float | None:

    if value is None:

        return None

    try:

        result = float(value)

    except (
        TypeError,
        ValueError,
    ):

        return None

    if not math.isfinite(result):

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
        for value in values
        if value is not None
    ]

    if len(valid) < minimum_count:

        return None

    return (
        sum(valid)
        /
        len(valid)
    )


def weighted_average(
    items: list[
        tuple[
            float | None,
            float,
        ]
    ],
) -> float | None:

    total_value = 0.0
    total_weight = 0.0

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

        total_weight += weight

    if total_weight <= 0:

        return None

    return (
        total_value
        /
        total_weight
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

    if len(sorted_values) == 1:

        return 50.0

    left = bisect.bisect_left(
        sorted_values,
        value,
    )

    right = bisect.bisect_right(
        sorted_values,
        value,
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
            len(sorted_values)
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
        stock.get("technical")
        or {}
    )

    institutional = (
        stock.get("institutional")
        or {}
    )

    tdcc = (
        stock.get("tdcc")
        or {}
    )

    fundamental = (
        stock.get("fundamental")
        or {}
    )

    revenue = (
        fundamental.get("revenue")
        or {}
    )

    financial = (
        fundamental.get("financial")
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
            financial.get("eps"),

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
        mapping.get(metric)
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

            value = get_metric(
                stock,
                metric,
            )

            if value is not None:

                values.append(value)

        values.sort()

        result[metric] = values

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
# LEGACY TECHNICAL COMPONENTS
#
# 目前只保留給：
# - Legacy Strength
# - Timing
# - Buy Priority
#
# 不再作為正式 Technical / Overall 主模型。
# ============================================================


def trend_score(
    stock: dict[str, Any],
) -> float | None:

    latest = (
        stock.get("latest")
        or {}
    )

    technical = (
        stock.get("technical")
        or {}
    )

    close = number(
        latest.get("close")
    )

    ma20 = number(
        technical.get("ma20")
    )

    ma60 = number(
        technical.get("ma60")
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

    return clamp(score)


def relative_strength_score(
    stock: dict[str, Any],
    maps: dict[
        str,
        list[float],
    ],
) -> float | None:

    return metric_percentile(
        stock,
        "return_20d",
        maps,
    )


def momentum_volume_score(
    stock: dict[str, Any],
    maps: dict[
        str,
        list[float],
    ],
) -> float | None:

    technical = (
        stock.get("technical")
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


# ============================================================
# CHIP
# ============================================================


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


# ============================================================
# FUNDAMENTAL
# ============================================================


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
# TECHNICAL V2 SCORE CURVES
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
# TECHNICAL V2
# ============================================================


def technical_v2_components(
    stock: dict[str, Any],
) -> dict[
    str,
    float | None,
]:

    latest = (
        stock.get("latest")
        or {}
    )

    technical = (
        stock.get("technical")
        or {}
    )

    close = number(
        latest.get("close")
    )

    ma20 = number(
        technical.get("ma20")
    )

    ma60 = number(
        technical.get("ma60")
    )

    atr14 = number(
        technical.get("atr14")
    )

    return_5d = number(
        technical.get(
            "return_5d_pct"
        )
    )

    return_20d = number(
        technical.get(
            "return_20d_pct"
        )
    )

    volume_ratio = number(
        technical.get(
            "volume_ratio_20"
        )
    )

    # --------------------------------------------------------
    # MA20 / MA60
    # --------------------------------------------------------

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
            1
        ) * 100.0

    # --------------------------------------------------------
    # CLOSE / MA20
    # --------------------------------------------------------

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
            1
        ) * 100.0

    # --------------------------------------------------------
    # ATR position
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Trend Structure
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Price Position
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Momentum Quality
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Technical
    # --------------------------------------------------------

    technical_score = (
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
            rounded(
                ma20_ma60_pct,
                2,
            ),

        "close_ma20_pct":
            rounded(
                close_ma20_pct,
                2,
            ),

        "close_ma20_atr":
            rounded(
                close_ma20_atr,
                2,
            ),

        "trend_structure":
            rounded(
                trend_structure,
                1,
            ),

        "price_position":
            rounded(
                price_position,
                1,
            ),

        "momentum_quality":
            rounded(
                momentum_quality,
                1,
            ),

        "technical":
            rounded(
                technical_score,
                1,
            ),
    }


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
        stock.get("latest")
        or {}
    )

    technical = (
        stock.get("technical")
        or {}
    )

    close = number(
        latest.get("close")
    )

    ma20 = number(
        technical.get("ma20")
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
# TRADE PLAN
# ============================================================


def build_trade_plan(
    stock: dict[str, Any],
) -> dict[
    str,
    float | None,
]:

    latest = (
        stock.get("latest")
        or {}
    )

    technical = (
        stock.get("technical")
        or {}
    )

    close = number(
        latest.get("close")
    )

    ma20 = number(
        technical.get("ma20")
    )

    atr = number(
        technical.get("atr14")
    )

    breakout_price = number(
        technical.get(
            "breakout_price_candidate"
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

            "distance_to_buy_zone_pct":
                None,

            "breakout_price":
                rounded(
                    breakout_price,
                    2,
                ),

            "breakout_distance_pct":
                None,

            "risk_price":
                None,

            "risk_pct":
                None,

            "current_risk_pct":
                None,

            "target_low":
                None,

            "target_high":
                None,

            "reward_risk_ratio":
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

    # --------------------------------------------------------
    # Buy Zone Distance
    # --------------------------------------------------------

    if close < buy_low:

        distance_to_buy_zone_pct = (
            (
                close
                -
                buy_low
            )
            /
            buy_low
            *
            100.0
        )

    elif close > buy_high:

        distance_to_buy_zone_pct = (
            (
                close
                -
                buy_high
            )
            /
            buy_high
            *
            100.0
        )

    else:

        distance_to_buy_zone_pct = 0.0

    # --------------------------------------------------------
    # Breakout Distance
    # --------------------------------------------------------

    breakout_distance_pct = None

    if (
        breakout_price is not None
        and
        breakout_price > 0
    ):

        breakout_distance_pct = (
            (
                close
                -
                breakout_price
            )
            /
            breakout_price
            *
            100.0
        )

    # --------------------------------------------------------
    # Current Risk
    # --------------------------------------------------------

    current_risk_pct = None

    if close > 0:

        current_risk_pct = (
            (
                close
                -
                risk_price
            )
            /
            close
            *
            100.0
        )

    # --------------------------------------------------------
    # Reward / Risk
    # --------------------------------------------------------

    reward_risk_ratio = None

    current_risk_amount = (
        close
        -
        risk_price
    )

    potential_reward = (
        target_low
        -
        close
    )

    if (
        current_risk_amount > 0
        and
        potential_reward > 0
    ):

        reward_risk_ratio = (
            potential_reward
            /
            current_risk_amount
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

        "distance_to_buy_zone_pct":
            rounded(
                distance_to_buy_zone_pct,
                2,
            ),

        "breakout_price":
            rounded(
                breakout_price,
                2,
            ),

        "breakout_distance_pct":
            rounded(
                breakout_distance_pct,
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

        "current_risk_pct":
            rounded(
                current_risk_pct,
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

        "reward_risk_ratio":
            rounded(
                reward_risk_ratio,
                2,
            ),
    }


# ============================================================
# STAGE V2
# ============================================================


def build_stage(
    stock: dict[str, Any],
    overall: float,
    trade_plan: dict[
        str,
        float | None,
    ],
) -> dict[str, str]:

    buy_distance = number(
        trade_plan.get(
            "distance_to_buy_zone_pct"
        )
    )

    breakout_distance = number(
        trade_plan.get(
            "breakout_distance_pct"
        )
    )

    current_risk = number(
        trade_plan.get(
            "current_risk_pct"
        )
    )

    # --------------------------------------------------------
    # AVOID
    # --------------------------------------------------------

    if overall < 40.0:

        return {
            "code": "AVOID",
            "label": "暫不關注",
        }

    # --------------------------------------------------------
    # Missing price structure
    # --------------------------------------------------------

    if (
        buy_distance is None
        or
        breakout_distance is None
        or
        current_risk is None
    ):

        return {
            "code": "WATCH",
            "label": "持續觀察",
        }

    # --------------------------------------------------------
    # EXTENDED
    # --------------------------------------------------------

    if (
        breakout_distance > 8.0
        or
        buy_distance > 12.0
        or
        current_risk > 25.0
    ):

        return {
            "code": "EXTENDED",
            "label": "漲幅延伸",
        }

    # --------------------------------------------------------
    # Actionable quality gate
    # --------------------------------------------------------

    if overall < 70.0:

        return {
            "code": "WATCH",
            "label": "持續觀察",
        }

    # --------------------------------------------------------
    # BREAKOUT
    # --------------------------------------------------------

    if (
        0.0
        <= breakout_distance
        <= 5.0
        and
        current_risk <= 22.0
    ):

        return {
            "code": "BREAKOUT",
            "label": "突破確認",
        }

    # --------------------------------------------------------
    # READY
    # --------------------------------------------------------

    ready_price = False

    if (
        -3.0
        <= buy_distance
        <= 3.0
    ):

        ready_price = True

    if (
        -3.0
        <= breakout_distance
        < 0.0
    ):

        ready_price = True

    if (
        ready_price
        and
        current_risk <= 18.0
    ):

        return {
            "code": "READY",
            "label": "接近買點",
        }

    # --------------------------------------------------------
    # SETUP
    # --------------------------------------------------------

    setup_price = False

    if (
        -5.0
        <= buy_distance
        <= 8.0
    ):

        setup_price = True

    if (
        -10.0
        <= breakout_distance
        < 0.0
    ):

        setup_price = True

    if (
        setup_price
        and
        current_risk <= 22.0
    ):

        return {
            "code": "SETUP",
            "label": "型態準備",
        }

    return {
        "code": "WATCH",
        "label": "持續觀察",
    }


# ============================================================
# ACTION
# ============================================================


def build_action(
    stage_code: str,
) -> str:

    mapping = {

        "BREAKOUT":
            "突破前高，觀察量價與是否站穩",

        "READY":
            "價格接近買點，可列入今日優先觀察",

        "SETUP":
            "條件接近，等待價格結構確認",

        "WATCH":
            "股票品質可追蹤，價格位置尚未成熟",

        "EXTENDED":
            "股價偏離合理買點，等待拉回",

        "AVOID":
            "整體條件不足",
    }

    return mapping.get(
        stage_code,
        "等待資料補齊",
    )


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
        stock.get("readiness")
        or {}
    )

    if (
        readiness.get("overall")
        !=
        "READY"
    ):

        stock["scores"] = {

            "trend":
                None,

            "relative_strength":
                None,

            "momentum_volume":
                None,

            "trend_structure":
                None,

            "price_position":
                None,

            "momentum_quality":
                None,

            "chip":
                None,

            "fundamental":
                None,

            "technical":
                None,

            "overall":
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

        stock["stage"] = {
            "code":
                "WAITING_DATA",

            "label":
                "資料補齊中",
        }

        stock["action"] = (
            "等待資料補齊"
        )

        return False

    # --------------------------------------------------------
    # Legacy
    # --------------------------------------------------------

    legacy_trend = (
        trend_score(stock)
    )

    legacy_relative = (
        relative_strength_score(
            stock,
            maps,
        )
    )

    legacy_momentum = (
        momentum_volume_score(
            stock,
            maps,
        )
    )

    # --------------------------------------------------------
    # Fundamental / Chip
    # --------------------------------------------------------

    fundamental = (
        fundamental_score(
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

    # --------------------------------------------------------
    # Technical V2
    # --------------------------------------------------------

    technical_v2 = (
        technical_v2_components(
            stock
        )
    )

    technical = number(
        technical_v2.get(
            "technical"
        )
    )

    trend_structure = number(
        technical_v2.get(
            "trend_structure"
        )
    )

    price_position = number(
        technical_v2.get(
            "price_position"
        )
    )

    momentum_quality = number(
        technical_v2.get(
            "momentum_quality"
        )
    )

    # --------------------------------------------------------
    # Timing
    # --------------------------------------------------------

    timing = (
        timing_score(
            stock,
            maps,
        )
    )

    # --------------------------------------------------------
    # Core V3 readiness
    # --------------------------------------------------------

    if (
        fundamental is None
        or
        chip is None
        or
        technical is None
    ):

        stock["scores"] = {

            "trend":
                rounded(
                    legacy_trend
                ),

            "relative_strength":
                rounded(
                    legacy_relative
                ),

            "momentum_volume":
                rounded(
                    legacy_momentum
                ),

            "trend_structure":
                rounded(
                    trend_structure
                ),

            "price_position":
                rounded(
                    price_position
                ),

            "momentum_quality":
                rounded(
                    momentum_quality
                ),

            "fundamental":
                rounded(
                    fundamental
                ),

            "chip":
                rounded(
                    chip
                ),

            "technical":
                rounded(
                    technical
                ),

            "overall":
                None,

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

        stock["stage"] = {
            "code":
                "WAITING_DATA",

            "label":
                "資料補齊中",
        }

        stock["action"] = (
            "部分評分欄位資料不足"
        )

        return False

    # --------------------------------------------------------
    # OVERALL V2
    # --------------------------------------------------------

    overall = (
        fundamental
        *
        0.30
        +
        chip
        *
        0.30
        +
        technical
        *
        0.40
    )

    # --------------------------------------------------------
    # Legacy Strength
    # --------------------------------------------------------

    legacy_strength = None

    if (
        legacy_trend is not None
        and
        legacy_relative is not None
        and
        legacy_momentum is not None
    ):

        legacy_strength = (
            legacy_trend
            *
            0.30
            +
            legacy_relative
            *
            0.20
            +
            legacy_momentum
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

    # --------------------------------------------------------
    # Legacy Buy Priority
    # --------------------------------------------------------

    buy_priority = None

    if (
        legacy_strength is not None
        and
        timing is not None
    ):

        buy_priority = (
            legacy_strength
            *
            0.65
            +
            timing
            *
            0.35
        )

    # --------------------------------------------------------
    # Trade Plan / Stage
    # --------------------------------------------------------

    trade_plan = (
        build_trade_plan(stock)
    )

    stage = (
        build_stage(
            stock,
            overall,
            trade_plan,
        )
    )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    stock["scores"] = {

        # Legacy
        "trend":
            rounded(
                legacy_trend
            ),

        "relative_strength":
            rounded(
                legacy_relative
            ),

        "momentum_volume":
            rounded(
                legacy_momentum
            ),

        # Technical V2
        "trend_structure":
            rounded(
                trend_structure
            ),

        "price_position":
            rounded(
                price_position
            ),

        "momentum_quality":
            rounded(
                momentum_quality
            ),

        # V3
        "fundamental":
            rounded(
                fundamental
            ),

        "chip":
            rounded(
                chip
            ),

        "technical":
            rounded(
                technical
            ),

        "overall":
            rounded(
                overall
            ),

        # Legacy compatibility
        "strength":
            rounded(
                legacy_strength
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

    stock["technical_v2"] = {

        "ma20_ma60_pct":
            technical_v2.get(
                "ma20_ma60_pct"
            ),

        "close_ma20_pct":
            technical_v2.get(
                "close_ma20_pct"
            ),

        "close_ma20_atr":
            technical_v2.get(
                "close_ma20_atr"
            ),

        "trend_structure":
            technical_v2.get(
                "trend_structure"
            ),

        "price_position":
            technical_v2.get(
                "price_position"
            ),

        "momentum_quality":
            technical_v2.get(
                "momentum_quality"
            ),
    }

    stock["stage"] = stage

    stock["trade_plan"] = (
        trade_plan
    )

    stock["action"] = (
        build_action(
            stage["code"]
        )
    )

    return True


# ============================================================
# COMMON RANKING ROW
# ============================================================


def build_ranking_row(
    stock: dict[str, Any],
    rank: int,
) -> dict[str, Any]:

    scores = (
        stock.get("scores")
        or {}
    )

    return {

        "rank":
            rank,

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
            ).get(
                "close"
            ),

        "change_pct":
            stock.get(
                "latest",
                {},
            ).get(
                "change_pct"
            ),

        "fundamental":
            scores.get(
                "fundamental"
            ),

        "chip":
            scores.get(
                "chip"
            ),

        "technical":
            scores.get(
                "technical"
            ),

        "overall":
            scores.get(
                "overall"
            ),

        # Legacy fields temporarily retained
        "strength":
            scores.get(
                "strength"
            ),

        "timing":
            scores.get(
                "timing"
            ),

        "buy_priority":
            scores.get(
                "buy_priority"
            ),

        "stage":
            stock.get(
                "stage"
            ),

        "trade_plan":
            stock.get(
                "trade_plan"
            ),

        "action":
            stock.get(
                "action"
            ),
    }


# ============================================================
# TOP10
#
# V3 definition:
# "哪些股票值得優先研究？"
#
# Only Overall controls ranking.
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
            ).get(
                "status"
            )
            ==
            "READY"
        )
        and
        number(
            stock.get(
                "scores",
                {},
            ).get(
                "overall"
            )
        )
        is not None
    ]

    eligible.sort(
        key=lambda stock: (

            -(
                number(
                    stock.get(
                        "scores",
                        {},
                    ).get(
                        "overall"
                    )
                )
                or
                0.0
            ),

            stock.get(
                "stock_id",
                "",
            ),
        )
    )

    selected = (
        eligible[:10]
    )

    rows = [

        build_ranking_row(
            stock,
            rank,
        )

        for (
            rank,
            stock,
        )
        in enumerate(
            selected,
            start=1,
        )
    ]

    if len(eligible) >= 10:

        status = "READY"

        message = (
            "TOP10 已依 V3 Overall Score 排序。"
        )

    elif eligible:

        status = "PARTIAL"

        message = (
            "目前可完整評分股票不足 10 檔。"
        )

    else:

        status = "WAITING_DATA"

        message = (
            "目前尚無股票具備完整 Overall Score。"
        )

    return {

        "model_version":
            SCORE_MODEL_VERSION,

        "ranking_method":
            "OVERALL_DESC",

        "purpose":
            "RESEARCH_PRIORITY",

        "data_date":
            data_date,

        "generated_at":
            now_iso(),

        "status":
            status,

        "message":
            message,

        "eligible_count":
            len(eligible),

        "rows":
            rows,
    }


# ============================================================
# ACTION PRIORITY
#
# V3 definition:
# "目前哪些股票最接近可行動位置？"
#
# Stage priority:
# BREAKOUT > READY > SETUP
#
# Within same Stage:
# Overall DESC
# ============================================================


def build_action_priority(
    stocks: list[
        dict[str, Any]
    ],
    data_date: str | None,
) -> dict[str, Any]:

    allowed_stages = {
        "BREAKOUT",
        "READY",
        "SETUP",
    }

    stage_priority = {
        "BREAKOUT": 1,
        "READY": 2,
        "SETUP": 3,
    }

    eligible = []

    for stock in stocks:

        scores = (
            stock.get("scores")
            or {}
        )

        stage = (
            stock.get("stage")
            or {}
        )

        stage_code = (
            stage.get("code")
        )

        overall = number(
            scores.get("overall")
        )

        if (
            scores.get("status")
            !=
            "READY"
        ):

            continue

        if (
            stage_code
            not in
            allowed_stages
        ):

            continue

        if overall is None:

            continue

        eligible.append(stock)

    eligible.sort(
        key=lambda stock: (

            stage_priority.get(
                (
                    stock.get("stage")
                    or {}
                ).get(
                    "code"
                ),
                99,
            ),

            -(
                number(
                    (
                        stock.get("scores")
                        or {}
                    ).get(
                        "overall"
                    )
                )
                or
                0.0
            ),

            stock.get(
                "stock_id",
                "",
            ),
        )
    )

    rows = [

        build_ranking_row(
            stock,
            rank,
        )

        for (
            rank,
            stock,
        )
        in enumerate(
            eligible,
            start=1,
        )
    ]

    if rows:

        status = "READY"

        message = (
            "今日優先觀察已依 "
            "BREAKOUT → READY → SETUP，"
            "同 Stage 內依 Overall 排序。"
        )

    else:

        status = "EMPTY"

        message = (
            "目前沒有 BREAKOUT、READY "
            "或 SETUP 股票。"
        )

    stage_counts = {
        "BREAKOUT": 0,
        "READY": 0,
        "SETUP": 0,
    }

    for stock in eligible:

        stage_code = (
            stock.get(
                "stage",
                {},
            ).get(
                "code"
            )
        )

        if stage_code in stage_counts:

            stage_counts[
                stage_code
            ] += 1

    return {

        "model_version":
            SCORE_MODEL_VERSION,

        "ranking_method":
            "STAGE_THEN_OVERALL_DESC",

        "purpose":
            "ACTION_PRIORITY",

        "data_date":
            data_date,

        "generated_at":
            now_iso(),

        "status":
            status,

        "message":
            message,

        "eligible_count":
            len(eligible),

        "stage_counts":
            stage_counts,

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
        "StockWaveScanner V3 "
        "- Score Engine"
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
            payload.get("stocks")
            or []
        )

        if not stocks:

            raise RuntimeError(
                "stocks.json contains no stocks"
            )

        print(
            f"Model       : "
            f"{SCORE_MODEL_VERSION}"
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

        # ----------------------------------------------------
        # STOCKS.JSON
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # TOP10 = RESEARCH PRIORITY
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # ACTION PRIORITY
        # ----------------------------------------------------

        action_priority = (
            build_action_priority(
                stocks,
                payload.get(
                    "data_date"
                ),
            )
        )

        write_json(
            ACTION_PRIORITY_FILE,
            action_priority,
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        status = (
            load_json(
                STATUS_FILE
            )
        )

        total = len(stocks)

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
                (
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
                    0
                ),

            "updated_at":
                now_iso(),
        }

        status[
            "ranking"
        ] = {

            "top10": {

                "status":
                    top10.get(
                        "status"
                    ),

                "method":
                    top10.get(
                        "ranking_method"
                    ),

                "rows":
                    len(
                        top10.get(
                            "rows",
                            [],
                        )
                    ),
            },

            "action_priority": {

                "status":
                    action_priority.get(
                        "status"
                    ),

                "method":
                    action_priority.get(
                        "ranking_method"
                    ),

                "rows":
                    len(
                        action_priority.get(
                            "rows",
                            [],
                        )
                    ),

                "stage_counts":
                    action_priority.get(
                        "stage_counts"
                    ),
            },

            "updated_at":
                now_iso(),
        }

        write_json(
            STATUS_FILE,
            status,
        )

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

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
            f"Total Stocks    : "
            f"{total:,}"
        )

        print(
            f"Scored          : "
            f"{scored_count:,}"
        )

        print(
            f"Waiting         : "
            f"{total - scored_count:,}"
        )

        print(
            f"TOP10 Rows      : "
            f"{len(top10['rows'])}"
        )

        print(
            f"Action Priority : "
            f"{len(action_priority['rows'])}"
        )

        print()

        print(
            "Action Stage Counts"
        )

        print(
            "--------------------"
        )

        print(
            "BREAKOUT : "
            f"{action_priority['stage_counts']['BREAKOUT']}"
        )

        print(
            "READY    : "
            f"{action_priority['stage_counts']['READY']}"
        )

        print(
            "SETUP    : "
            f"{action_priority['stage_counts']['SETUP']}"
        )

        print()

        print(
            "[PASS] V3 Step4E ranking snapshot generated"
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
            str(exc)
        )

        return 1


if __name__ == "__main__":

    sys.exit(
        main()
    )