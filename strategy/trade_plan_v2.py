from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Optional

import pandas as pd


@dataclass(frozen=True)
class TradePlanV2Config:
    """StockWaveScanner v2 交易位置研究參數。"""

    atr_period: int = 14
    recent_low_window: int = 10

    setup_zone_atr: float = 0.35
    ready_zone_atr_low: float = 0.40
    ready_zone_atr_high: float = 0.25
    breakout_zone_atr_low: float = 0.50
    breakout_zone_atr_high: float = 0.25
    momentum_zone_atr: float = 0.50
    extended_zone_atr: float = 0.50

    risk_atr_buffer: float = 0.35
    min_risk_pct: float = 0.015
    max_candidate_risk_pct: float = 0.10

    target_r_low: float = 1.50
    target_r_high: float = 2.50


DEFAULT_CONFIG = TradePlanV2Config()


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(result):
        return None

    return result


def _normalize_risk_flags(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        return [
            x.strip()
            for x in value.split(",")
            if x.strip()
        ]

    if isinstance(value, (list, tuple, set)):
        return [
            str(x).strip()
            for x in value
            if str(x).strip()
        ]

    return [str(value).strip()]


def _prepare_price_df(
    price_df: pd.DataFrame,
    reference_date: Optional[str],
) -> pd.DataFrame:
    required = {
        "trade_date",
        "high",
        "low",
        "close",
    }

    missing = required - set(price_df.columns)

    if missing:
        raise ValueError(
            "price_df 缺少欄位: "
            + ", ".join(sorted(missing))
        )

    df = price_df.copy()

    df["trade_date"] = (
        df["trade_date"]
        .astype(str)
    )

    if reference_date is not None:
        df = df[
            df["trade_date"]
            <= str(reference_date)
        ].copy()

    for col in [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )

    df = (
        df.sort_values("trade_date")
        .drop_duplicates(
            subset=["trade_date"],
            keep="last",
        )
        .dropna(
            subset=[
                "high",
                "low",
                "close",
            ]
        )
        .reset_index(drop=True)
    )

    return df


def _atr(
    df: pd.DataFrame,
    period: int,
) -> Optional[float]:
    if len(df) < period + 1:
        return None

    prev_close = df["close"].shift(1)

    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (
                df["high"]
                - prev_close
            ).abs(),
            (
                df["low"]
                - prev_close
            ).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return _safe_float(
        true_range
        .rolling(period)
        .mean()
        .iloc[-1]
    )


def _tick_size(
    price: float,
) -> float:
    """
    台股普通股票升降單位。

    < 10      : 0.01
    10~<50    : 0.05
    50~<100   : 0.10
    100~<500  : 0.50
    500~<1000 : 1.00
    >=1000    : 5.00
    """

    if price < 10:
        return 0.01

    if price < 50:
        return 0.05

    if price < 100:
        return 0.10

    if price < 500:
        return 0.50

    if price < 1000:
        return 1.00

    return 5.00


def _tick_decimals(
    tick: float,
) -> int:
    if tick >= 1:
        return 0

    if tick >= 0.1:
        return 1

    return 2


def round_to_tick(
    price: Optional[float],
    mode: str = "nearest",
) -> Optional[float]:
    """
    將模型價格對齊台股股票升降單位。

    mode:
      nearest
      down
      up
    """

    value = _safe_float(price)

    if value is None or value <= 0:
        return None

    tick = _tick_size(value)

    units = value / tick

    if mode == "down":

        rounded_units = math.floor(
            units + 1e-12
        )

    elif mode == "up":

        rounded_units = math.ceil(
            units - 1e-12
        )

    elif mode == "nearest":

        rounded_units = math.floor(
            units + 0.5
        )

    else:

        raise ValueError(
            "mode 必須是 "
            "nearest / down / up"
        )

    result = (
        rounded_units
        * tick
    )

    return round(
        result,
        _tick_decimals(tick),
    )


def _calculate_price_metrics(
    df: pd.DataFrame,
    config: TradePlanV2Config,
) -> dict[str, Optional[float]]:

    close = float(
        df["close"].iloc[-1]
    )

    ma5 = _safe_float(
        df["close"]
        .rolling(5)
        .mean()
        .iloc[-1]
    )

    ma10 = _safe_float(
        df["close"]
        .rolling(10)
        .mean()
        .iloc[-1]
    )

    ma20 = _safe_float(
        df["close"]
        .rolling(20)
        .mean()
        .iloc[-1]
    )

    previous_20d = (
        df.iloc[:-1]
        .tail(20)
    )

    previous_20d_high = (
        _safe_float(
            previous_20d[
                "high"
            ].max()
        )
        if not previous_20d.empty
        else None
    )

    previous_20d_low = (
        _safe_float(
            previous_20d[
                "low"
            ].min()
        )
        if not previous_20d.empty
        else None
    )

    recent_low = _safe_float(
        df.tail(
            config.recent_low_window
        )["low"].min()
    )

    atr14 = _atr(
        df,
        config.atr_period,
    )

    if (
        atr14 is None
        or atr14 <= 0
    ):
        atr14 = (
            close
            * 0.02
        )

    distance_ma20_pct = None

    if (
        ma20 is not None
        and ma20 > 0
    ):
        distance_ma20_pct = (
            close / ma20
            - 1.0
        )

    return {
        "latest_close":
            close,

        "ma5":
            ma5,

        "ma10":
            ma10,

        "ma20":
            ma20,

        "atr14":
            atr14,

        "previous_20d_high":
            previous_20d_high,

        "previous_20d_low":
            previous_20d_low,

        "recent_low":
            recent_low,

        "distance_ma20_pct":
            distance_ma20_pct,
    }


def _build_buy_zone(
    stage: str,
    metrics: dict[
        str,
        Optional[float],
    ],
    config: TradePlanV2Config,
) -> tuple[
    Optional[float],
    Optional[float],
    Optional[float],
]:

    close = metrics[
        "latest_close"
    ]

    ma10 = metrics[
        "ma10"
    ]

    ma20 = metrics[
        "ma20"
    ]

    atr = metrics[
        "atr14"
    ]

    previous_20d_high = (
        metrics[
            "previous_20d_high"
        ]
    )

    if (
        close is None
        or ma10 is None
        or ma20 is None
        or atr is None
    ):
        return (
            None,
            None,
            None,
        )

    stage = stage.upper()

    #
    # BASE / SETUP
    #
    if stage in {
        "BASE",
        "SETUP",
    }:

        anchor = max(
            ma20,
            min(
                ma10,
                close,
            ),
        )

        low = (
            anchor
            - config.setup_zone_atr
            * atr
        )

        high = (
            anchor
            + config.setup_zone_atr
            * atr
        )

        if (
            stage == "SETUP"
            and previous_20d_high
            is not None
            and previous_20d_high
            > low
        ):
            high = min(
                high,
                previous_20d_high,
            )

    #
    # READY
    #
    elif stage == "READY":

        if previous_20d_high is None:

            anchor = max(
                ma10,
                ma20,
            )

        else:

            anchor = max(
                ma10,
                min(
                    close,
                    previous_20d_high,
                ),
            )

        low = (
            anchor
            - config.ready_zone_atr_low
            * atr
        )

        high = (
            anchor
            + config.ready_zone_atr_high
            * atr
        )

        if (
            previous_20d_high
            is not None
            and previous_20d_high
            > low
        ):

            high = min(
                high,
                previous_20d_high,
            )

    #
    # BREAKOUT
    #
    elif stage == "BREAKOUT":

        anchor = (
            previous_20d_high
            if previous_20d_high
            is not None
            else ma10
        )

        low = (
            anchor
            - config.breakout_zone_atr_low
            * atr
        )

        high = (
            anchor
            + config.breakout_zone_atr_high
            * atr
        )

    #
    # MOMENTUM
    #
    elif stage == "MOMENTUM":

        anchor = max(
            ma10,
            ma20,
        )

        low = (
            anchor
            - config.momentum_zone_atr
            * atr
        )

        high = (
            anchor
            + config.momentum_zone_atr
            * atr
        )

    #
    # EXTENDED
    #
    elif stage == "EXTENDED":

        anchors = [
            ma10,
            ma20,
        ]

        if (
            previous_20d_high
            is not None
            and previous_20d_high
            < close
        ):

            anchors.append(
                previous_20d_high
            )

        anchor = max(
            anchors
        )

        low = (
            anchor
            - config.extended_zone_atr
            * atr
        )

        high = (
            anchor
            + config.extended_zone_atr
            * atr
        )

    #
    # fallback
    #
    else:

        anchor = ma20

        low = (
            anchor
            - config.setup_zone_atr
            * atr
        )

        high = (
            anchor
            + config.setup_zone_atr
            * atr
        )

    low = max(
        0.01,
        float(low),
    )

    high = max(
        low,
        float(high),
    )

    return (
        low,
        high,
        anchor,
    )


def _build_risk_price(
    stage: str,
    buy_zone_low: float,
    buy_zone_high: float,
    metrics: dict[
        str,
        Optional[float],
    ],
    config: TradePlanV2Config,
) -> tuple[
    float,
    float,
    float,
]:

    entry_mid = (
        buy_zone_low
        + buy_zone_high
    ) / 2.0

    atr = float(
        metrics[
            "atr14"
        ]
        or entry_mid * 0.02
    )

    ma10 = metrics[
        "ma10"
    ]

    ma20 = metrics[
        "ma20"
    ]

    recent_low = metrics[
        "recent_low"
    ]

    previous_20d_high = (
        metrics[
            "previous_20d_high"
        ]
    )

    supports: list[
        float
    ] = []

    #
    # 基本支撐
    #
    for candidate in [
        ma20,
        recent_low,
    ]:

        if (
            candidate is not None
            and candidate
            < entry_mid
        ):

            supports.append(
                float(candidate)
            )

    stage = stage.upper()

    #
    # READY / MOMENTUM
    #
    if stage in {
        "READY",
        "MOMENTUM",
    }:

        if (
            ma10 is not None
            and ma10
            < entry_mid
        ):

            supports.append(
                float(ma10)
            )

    #
    # BREAKOUT / EXTENDED
    #
    if stage in {
        "BREAKOUT",
        "EXTENDED",
    }:

        if (
            previous_20d_high
            is not None
            and previous_20d_high
            < entry_mid
        ):

            supports.append(
                float(
                    previous_20d_high
                )
            )

    #
    # 一定保留一個買進區下方
    # 的波動支撐候選
    #
    supports.append(
        buy_zone_low
        - 0.50 * atr
    )

    supports = [
        x
        for x in supports
        if (
            x > 0
            and x < entry_mid
        )
    ]

    if supports:

        support = max(
            supports
        )

    else:

        support = (
            buy_zone_low
            - atr
        )

    risk_price = (
        support
        - config.risk_atr_buffer
        * atr
    )

    #
    # 風險價至少低於
    # 模型買進區下緣
    #
    risk_price = min(
        risk_price,
        buy_zone_low
        - 0.25 * atr,
    )

    #
    # 避免風險距離
    # 過度緊縮
    #
    minimum_risk_amount = (
        entry_mid
        * config.min_risk_pct
    )

    if (
        entry_mid
        - risk_price
        < minimum_risk_amount
    ):

        risk_price = (
            entry_mid
            - minimum_risk_amount
        )

    risk_price = max(
        0.01,
        risk_price,
    )

    risk_amount = max(
        0.0,
        entry_mid
        - risk_price,
    )

    risk_pct = (
        risk_amount
        / entry_mid
        if entry_mid > 0
        else 0.0
    )

    return (
        risk_price,
        risk_amount,
        risk_pct,
    )


def _entry_status(
    close: float,
    zone_low: float,
    zone_high: float,
    atr: float,
) -> str:

    if (
        zone_low
        <= close
        <= zone_high
    ):
        return (
            "IN_BUY_ZONE"
        )

    if close < zone_low:

        return (
            "BELOW_BUY_ZONE"
        )

    if (
        close
        <= zone_high
        + 0.50 * atr
    ):

        return (
            "SLIGHTLY_ABOVE_BUY_ZONE"
        )

    return (
        "ABOVE_BUY_ZONE"
    )


def _action_for(
    state: str,
    stage: str,
    risk_flags: list[str],
    entry_status: str,
) -> tuple[
    str,
    str,
]:

    state = state.upper()
    stage = stage.upper()

    flags = {
        x.upper()
        for x in risk_flags
    }

    #
    # 結構破壞
    #
    if (
        "STRUCTURE_BREAK"
        in flags
    ):

        return (
            "AVOID_STRUCTURE_BREAK",
            "🔴 結構轉弱，暫不列入進場候選",
        )

    #
    # Weak
    #
    if (
        state == "WEAK"
        or stage == "WEAK"
    ):

        return (
            "AVOID_WEAK",
            "🔴 看漲條件不足，暫不列入進場候選",
        )

    #
    # Extended
    #
    if (
        stage == "EXTENDED"
        or "EXTENDED"
        in flags
    ):

        return (
            "WAIT_PULLBACK",
            "🟡 強勢但已延伸，等待拉回模型參考區，不追價",
        )

    #
    # Breakout
    #
    if stage == "BREAKOUT":

        if (
            entry_status
            == "IN_BUY_ZONE"
        ):

            return (
                "BREAKOUT_RETEST_ZONE",
                "🟢 突破後位於模型回測區，可列入優先觀察",
            )

        if (
            entry_status
            == "SLIGHTLY_ABOVE_BUY_ZONE"
        ):

            return (
                "BREAKOUT_SLIGHTLY_HIGH",
                "🟡 突破成立但略高於參考區，避免追價",
            )

        if (
            entry_status
            == "ABOVE_BUY_ZONE"
        ):

            return (
                "WAIT_BREAKOUT_RETEST",
                "🟡 強勢突破但價格偏高，等待回測突破區",
            )

        return (
            "BREAKOUT_BELOW_ZONE",
            "🟡 已回到突破區下方，先確認支撐是否守住",
        )

    #
    # Ready
    #
    if stage == "READY":

        if (
            entry_status
            == "IN_BUY_ZONE"
        ):

            return (
                "READY_IN_ZONE",
                "🟢 接近發動且位於模型參考區，可列入明日優先觀察",
            )

        if (
            entry_status
            == "BELOW_BUY_ZONE"
        ):

            return (
                "READY_BELOW_ZONE",
                "🟡 價格低於模型參考區，先確認支撐與趨勢",
            )

        return (
            "READY_WAIT_ENTRY",
            "🟡 接近發動但價格偏高，等待回到模型參考區",
        )

    #
    # Setup
    #
    if stage == "SETUP":

        if (
            entry_status
            == "IN_BUY_ZONE"
        ):

            return (
                "SETUP_IN_ZONE",
                "🟢 整理蓄勢且位於模型參考區，等待量價轉強",
            )

        if (
            entry_status
            == "BELOW_BUY_ZONE"
        ):

            return (
                "SETUP_BELOW_ZONE",
                "🟡 低於整理參考區，先確認多頭結構是否仍完整",
            )

        return (
            "SETUP_WAIT",
            "🟡 整理結構仍在，但價格已離開參考區，等待回測或突破",
        )

    #
    # Momentum
    #
    if stage == "MOMENTUM":

        if (
            entry_status
            == "IN_BUY_ZONE"
        ):

            return (
                "MOMENTUM_PULLBACK_ZONE",
                "🟢 動能偏強且回到模型參考區，可列入觀察",
            )

        return (
            "MOMENTUM_WAIT_PULLBACK",
            "🟡 動能偏強，但等待拉回模型參考區再評估",
        )

    return (
        "WATCH",
        "⚪ 目前以觀察為主，尚未形成明確交易位置",
    )


def _empty_result(
    reason: Optional[str],
    reference_date: Optional[str],
    bullish_result: Optional[
        dict[str, Any]
    ],
    metrics: Optional[
        dict[
            str,
            Optional[float],
        ]
    ] = None,
) -> dict[str, Any]:

    bullish_result = (
        bullish_result
        or {}
    )

    return {
        "status":
            "INSUFFICIENT_DATA",

        "reason":
            reason,

        "reference_date":
            reference_date,

        "bullish_score":
            bullish_result.get(
                "score"
            ),

        "state":
            bullish_result.get(
                "state"
            ),

        "stage":
            bullish_result.get(
                "stage"
            ),

        "risk_flags":
            _normalize_risk_flags(
                bullish_result.get(
                    "risk_flags"
                )
            ),

        "latest_close":
            (
                metrics
                or {}
            ).get(
                "latest_close"
            ),

        "buy_zone_low":
            None,

        "buy_zone_high":
            None,

        "risk_price":
            None,

        "target_zone_low":
            None,

        "target_zone_high":
            None,

        "entry_mid":
            None,

        "risk_amount":
            None,

        "risk_pct":
            None,

        "entry_status":
            "NO_PLAN",

        "action_code":
            "NO_PLAN",

        "action":
            "⚪ 資料不足，暫不產生交易參考",

        "candidate_eligible":
            False,

        "metrics":
            metrics
            or {},
    }


def evaluate_trade_plan_v2(
    price_df: pd.DataFrame,
    bullish_result: dict[
        str,
        Any,
    ],
    reference_date: Optional[str] = None,
    config: TradePlanV2Config = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """
    依 Bullish v2 的 state / stage
    建立交易位置研究資料。

    輸出：

    latest_close
    buy_zone_low
    buy_zone_high
    risk_price
    target_zone_low
    target_zone_high
    entry_status
    action
    candidate_eligible

    注意：

    - 不修改 DB
    - 不使用 date.today()
    - target zone 是 Risk/Reward 參考
    - 不是價格預測
    - EXTENDED 可很看漲
      但會要求等待拉回
    """

    if not isinstance(
        bullish_result,
        dict,
    ):

        raise TypeError(
            "bullish_result 必須是 dict"
        )

    bullish_status = str(
        bullish_result.get(
            "data_status",
            "READY",
        )
    ).upper()

    if (
        bullish_status
        != "READY"
    ):

        return _empty_result(
            reason=(
                "Bullish v2 尚未 READY: "
                + bullish_status
            ),
            reference_date=(
                reference_date
            ),
            bullish_result=(
                bullish_result
            ),
        )

    df = _prepare_price_df(
        price_df,
        reference_date,
    )

    minimum_rows = max(
        21,
        config.atr_period + 1,
        config.recent_low_window,
    )

    if (
        len(df)
        < minimum_rows
    ):

        return _empty_result(
            reason=(
                f"Price 資料不足："
                f"{len(df)} rows，"
                f"至少需要 "
                f"{minimum_rows}"
            ),
            reference_date=(
                reference_date
            ),
            bullish_result=(
                bullish_result
            ),
        )

    actual_reference_date = str(
        df[
            "trade_date"
        ].iloc[-1]
    )

    metrics = (
        _calculate_price_metrics(
            df,
            config,
        )
    )

    state = str(
        bullish_result.get(
            "state",
            "NEUTRAL",
        )
    ).upper()

    stage = str(
        bullish_result.get(
            "stage",
            "BASE",
        )
    ).upper()

    risk_flags = (
        _normalize_risk_flags(
            bullish_result.get(
                "risk_flags"
            )
        )
    )

    risk_flag_set = {
        x.upper()
        for x in risk_flags
    }

    #
    # Weak / 結構破壞：
    # 不建立買進區
    #
    if (
        state == "WEAK"
        or stage == "WEAK"
        or "STRUCTURE_BREAK"
        in risk_flag_set
    ):

        result = (
            _empty_result(
                reason=None,
                reference_date=(
                    actual_reference_date
                ),
                bullish_result=(
                    bullish_result
                ),
                metrics=metrics,
            )
        )

        result[
            "status"
        ] = "READY"

        (
            result["action_code"],
            result["action"],
        ) = _action_for(
            state=state,
            stage=stage,
            risk_flags=risk_flags,
            entry_status="NO_PLAN",
        )

        return result

    (
        raw_low,
        raw_high,
        anchor,
    ) = _build_buy_zone(
        stage=stage,
        metrics=metrics,
        config=config,
    )

    if (
        raw_low is None
        or raw_high is None
    ):

        return _empty_result(
            reason=(
                "無法建立模型買進參考區"
            ),
            reference_date=(
                actual_reference_date
            ),
            bullish_result=(
                bullish_result
            ),
            metrics=metrics,
        )

    buy_zone_low = round_to_tick(
        raw_low,
        "down",
    )

    buy_zone_high = round_to_tick(
        raw_high,
        "up",
    )

    if (
        buy_zone_low is None
        or buy_zone_high is None
    ):

        return _empty_result(
            reason=(
                "模型買進參考區"
                "價格對齊失敗"
            ),
            reference_date=(
                actual_reference_date
            ),
            bullish_result=(
                bullish_result
            ),
            metrics=metrics,
        )

    if (
        buy_zone_low
        > buy_zone_high
    ):

        (
            buy_zone_low,
            buy_zone_high,
        ) = (
            buy_zone_high,
            buy_zone_low,
        )

    (
        raw_risk_price,
        _,
        _,
    ) = _build_risk_price(
        stage=stage,
        buy_zone_low=(
            buy_zone_low
        ),
        buy_zone_high=(
            buy_zone_high
        ),
        metrics=metrics,
        config=config,
    )

    risk_price = round_to_tick(
        raw_risk_price,
        "down",
    )

    entry_mid_raw = (
        buy_zone_low
        + buy_zone_high
    ) / 2.0

    if (
        risk_price is None
        or risk_price
        >= entry_mid_raw
    ):

        risk_price = round_to_tick(
            entry_mid_raw
            * (
                1.0
                - config.min_risk_pct
            ),
            "down",
        )

    if risk_price is None:

        return _empty_result(
            reason=(
                "風險參考價計算失敗"
            ),
            reference_date=(
                actual_reference_date
            ),
            bullish_result=(
                bullish_result
            ),
            metrics=metrics,
        )

    risk_amount = (
        entry_mid_raw
        - risk_price
    )

    risk_pct = (
        risk_amount
        / entry_mid_raw
        if entry_mid_raw > 0
        else None
    )

    target_zone_low = (
        round_to_tick(
            entry_mid_raw
            + risk_amount
            * config.target_r_low,
            "up",
        )
    )

    target_zone_high = (
        round_to_tick(
            entry_mid_raw
            + risk_amount
            * config.target_r_high,
            "up",
        )
    )

    latest_close = float(
        metrics[
            "latest_close"
        ]
    )

    atr = float(
        metrics[
            "atr14"
        ]
        or latest_close
        * 0.02
    )

    entry_status = (
        _entry_status(
            close=latest_close,
            zone_low=(
                buy_zone_low
            ),
            zone_high=(
                buy_zone_high
            ),
            atr=atr,
        )
    )

    (
        action_code,
        action,
    ) = _action_for(
        state=state,
        stage=stage,
        risk_flags=risk_flags,
        entry_status=(
            entry_status
        ),
    )

    #
    # Top 10 候選資格：
    #
    # - STRONG_BULLISH / BULLISH
    # - SETUP / READY / BREAKOUT / MOMENTUM
    # - 不能 EXTENDED
    # - 不能 STRUCTURE_BREAK
    # - 模型風險 <= 10%
    #
    candidate_eligible = (
        state
        in {
            "STRONG_BULLISH",
            "BULLISH",
        }

        and stage
        in {
            "SETUP",
            "READY",
            "BREAKOUT",
            "MOMENTUM",
        }

        and "EXTENDED"
        not in risk_flag_set

        and "STRUCTURE_BREAK"
        not in risk_flag_set

        and risk_pct
        is not None

        and risk_pct
        <= config.max_candidate_risk_pct
    )

    return {
        "status":
            "READY",

        "reason":
            None,

        "reference_date":
            actual_reference_date,

        "bullish_score":
            bullish_result.get(
                "score"
            ),

        "state":
            state,

        "stage":
            stage,

        "risk_flags":
            risk_flags,

        "latest_close":
            round_to_tick(
                latest_close,
                "nearest",
            ),

        "buy_zone_low":
            buy_zone_low,

        "buy_zone_high":
            buy_zone_high,

        "risk_price":
            risk_price,

        "target_zone_low":
            target_zone_low,

        "target_zone_high":
            target_zone_high,

        "entry_mid":
            round_to_tick(
                entry_mid_raw,
                "nearest",
            ),

        "risk_amount":
            round(
                risk_amount,
                4,
            ),

        "risk_pct":
            (
                round(
                    risk_pct,
                    6,
                )
                if risk_pct
                is not None
                else None
            ),

        "reward_r_low":
            config.target_r_low,

        "reward_r_high":
            config.target_r_high,

        "entry_status":
            entry_status,

        "action_code":
            action_code,

        "action":
            action,

        "candidate_eligible":
            candidate_eligible,

        "metrics": {
            **metrics,

            "trade_anchor":
                anchor,
        },

        "config":
            asdict(config),
    }


__all__ = [
    "TradePlanV2Config",
    "DEFAULT_CONFIG",
    "evaluate_trade_plan_v2",
    "round_to_tick",
]