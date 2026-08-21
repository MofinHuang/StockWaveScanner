from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from strategy.foreign_data import (
    get_effective_foreign_net,
)


FOREIGN_MAX_SCORE = 20

FOREIGN_POSITIVE_SCORE = 10
FOREIGN_INCREASING_SCORE = 5
FOREIGN_NO_SPIKE_SCORE = 5

FOREIGN_SPIKE_MULTIPLIER = 2.5


@dataclass(frozen=True)
class ForeignWeek:
    week_start: str
    week_end: str

    market_dates: list[str]

    foreign_net: int | None

    stored_days: int
    zero_inferred_days: int
    insufficient_days: int


@dataclass(frozen=True)
class ForeignResult:
    stock_id: str
    market: str
    as_of_date: str

    status: str
    score: int | None

    condition_positive: bool | None
    condition_increasing: bool | None
    condition_no_spike: bool | None

    weeks: list[ForeignWeek]

    reason: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "stock_id": self.stock_id,
            "market": self.market,
            "as_of_date": self.as_of_date,
            "status": self.status,
            "score": self.score,
            "condition_positive":
                self.condition_positive,
            "condition_increasing":
                self.condition_increasing,
            "condition_no_spike":
                self.condition_no_spike,
            "weeks": [
                {
                    "week_start":
                        week.week_start,
                    "week_end":
                        week.week_end,
                    "market_dates":
                        week.market_dates,
                    "foreign_net":
                        week.foreign_net,
                    "stored_days":
                        week.stored_days,
                    "zero_inferred_days":
                        week.zero_inferred_days,
                    "insufficient_days":
                        week.insufficient_days,
                }
                for week in self.weeks
            ],
            "reason": self.reason,
        }


def _parse_date(
    value: str | date,
) -> date:
    if isinstance(value, date):
        return value

    try:
        return datetime.strptime(
            str(value),
            "%Y-%m-%d",
        ).date()

    except ValueError as exc:
        raise ValueError(
            "日期格式必須為 YYYY-MM-DD："
            f"{value!r}"
        ) from exc


def _monday(
    value: date,
) -> date:
    return (
        value
        - timedelta(
            days=value.weekday()
        )
    )


def _get_market_dates(
    conn,
    market: str,
    week_start: date,
) -> list[str]:
    week_end = (
        week_start
        + timedelta(days=6)
    )

    rows = conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM daily_prices
        WHERE market = ?
          AND trade_date >= ?
          AND trade_date <= ?
        ORDER BY trade_date ASC
        """,
        (
            market,
            week_start.isoformat(),
            week_end.isoformat(),
        ),
    ).fetchall()

    return [
        str(row["trade_date"])
        for row in rows
    ]


def _find_three_complete_weeks(
    conn,
    market: str,
    as_of_date: date,
) -> list[date]:
    """
    最近三個完整週。

    過去週：
        只要該週有市場交易日即可。

    as_of_date 所在週：
        只有 as_of_date 已到星期五
        或更晚時才納入。

    專案目前日資料通常以最近完整交易日
    作 as_of，因此 2026-08-14 星期五會納入：
        2026-08-10 ~ 2026-08-16
    """
    current_week = (
        _monday(
            as_of_date
        )
    )

    result: list[date] = []

    cursor = current_week

    for _ in range(12):
        market_dates = (
            _get_market_dates(
                conn=conn,
                market=market,
                week_start=cursor,
            )
        )

        if market_dates:
            is_current_week = (
                cursor
                == current_week
            )

            if not is_current_week:
                result.append(
                    cursor
                )

            elif (
                as_of_date.weekday()
                >= 4
            ):
                result.append(
                    cursor
                )

        if len(result) == 3:
            break

        cursor -= timedelta(
            days=7
        )

    if len(result) < 3:
        raise RuntimeError(
            f"{market} 找不到最近 "
            "3 個完整交易週"
        )

    return sorted(
        result
    )


def _evaluate_week(
    conn,
    stock_id: str,
    market: str,
    week_start: date,
) -> ForeignWeek:
    week_end = (
        week_start
        + timedelta(days=6)
    )

    market_dates = (
        _get_market_dates(
            conn=conn,
            market=market,
            week_start=week_start,
        )
    )

    if not market_dates:
        return ForeignWeek(
            week_start=(
                week_start.isoformat()
            ),
            week_end=(
                week_end.isoformat()
            ),
            market_dates=[],
            foreign_net=None,
            stored_days=0,
            zero_inferred_days=0,
            insufficient_days=1,
        )

    effective_rows = (
        get_effective_foreign_net(
            conn=conn,
            stock_id=stock_id,
            market=market,
            start_date=(
                week_start.isoformat()
            ),
            end_date=(
                week_end.isoformat()
            ),
        )
    )

    by_date = {
        row.trade_date: row
        for row in effective_rows
    }

    stored_days = 0
    zero_inferred_days = 0
    insufficient_days = 0

    values: list[int] = []

    for trade_date in market_dates:
        row = by_date.get(
            trade_date
        )

        #
        # 市場有交易，
        # 但這檔股票該日沒有 daily_price，
        # get_effective_foreign_net()
        # 就不會產生 row。
        #
        if row is None:
            insufficient_days += 1
            continue

        if (
            row.status
            == "INSUFFICIENT_DATA"
            or row.foreign_net is None
        ):
            insufficient_days += 1
            continue

        if row.status == "STORED":
            stored_days += 1

        elif (
            row.status
            == "ZERO_INFERRED"
        ):
            zero_inferred_days += 1

        else:
            raise RuntimeError(
                "未知 foreign data status："
                f"{row.status!r}"
            )

        values.append(
            int(row.foreign_net)
        )

    if (
        insufficient_days > 0
        or len(values)
        != len(market_dates)
    ):
        weekly_net = None

    else:
        weekly_net = sum(
            values
        )

    return ForeignWeek(
        week_start=(
            week_start.isoformat()
        ),
        week_end=(
            week_end.isoformat()
        ),
        market_dates=market_dates,
        foreign_net=weekly_net,
        stored_days=stored_days,
        zero_inferred_days=(
            zero_inferred_days
        ),
        insufficient_days=(
            insufficient_days
        ),
    )


def analyze_foreign_effective(
    conn,
    stock_id: str,
    market: str,
    as_of_date: str | date,
) -> ForeignResult:
    """
    Foreign /20 正式 effective-data evaluator。

    評分規則完全沿用既有規格：

    A.
    最近三個完整週 foreign_net 全部 > 0
    +10

    B.
    三週 foreign_net 連續增加
    +5

    C.
    增加幅度不可 > 前週 2.5x
    +5

    三條全部成立才 PASS。

    任一完整週資料不足：
        INSUFFICIENT_DATA
    """
    normalized_as_of = (
        _parse_date(
            as_of_date
        )
    )

    week_starts = (
        _find_three_complete_weeks(
            conn=conn,
            market=market,
            as_of_date=normalized_as_of,
        )
    )

    weeks = [
        _evaluate_week(
            conn=conn,
            stock_id=stock_id,
            market=market,
            week_start=week_start,
        )
        for week_start in week_starts
    ]

    if any(
        week.foreign_net is None
        for week in weeks
    ):
        return ForeignResult(
            stock_id=stock_id,
            market=market,
            as_of_date=(
                normalized_as_of
                .isoformat()
            ),
            status="INSUFFICIENT_DATA",
            score=None,
            condition_positive=None,
            condition_increasing=None,
            condition_no_spike=None,
            weeks=weeks,
            reason=(
                "最近 3 個完整週存在 "
                "foreign_net 資料不足"
            ),
        )

    weekly_nets = [
        int(week.foreign_net)
        for week in weeks
    ]

    condition_positive = all(
        value > 0
        for value in weekly_nets
    )

    condition_increasing = (
        weekly_nets[0]
        < weekly_nets[1]
        < weekly_nets[2]
    )

    #
    # 倍數比較只在三週皆 > 0 時具有
    # Foreign 累積買超的策略意義。
    #
    condition_no_spike = (
        condition_positive
        and (
            weekly_nets[1]
            <= weekly_nets[0]
            * FOREIGN_SPIKE_MULTIPLIER
        )
        and (
            weekly_nets[2]
            <= weekly_nets[1]
            * FOREIGN_SPIKE_MULTIPLIER
        )
    )

    score = 0

    if condition_positive:
        score += (
            FOREIGN_POSITIVE_SCORE
        )

    if condition_increasing:
        score += (
            FOREIGN_INCREASING_SCORE
        )

    if condition_no_spike:
        score += (
            FOREIGN_NO_SPIKE_SCORE
        )

    is_pass = (
        condition_positive
        and condition_increasing
        and condition_no_spike
    )

    return ForeignResult(
        stock_id=stock_id,
        market=market,
        as_of_date=(
            normalized_as_of.isoformat()
        ),
        status=(
            "PASS"
            if is_pass
            else "FAIL"
        ),
        score=score,
        condition_positive=(
            condition_positive
        ),
        condition_increasing=(
            condition_increasing
        ),
        condition_no_spike=(
            condition_no_spike
        ),
        weeks=weeks,
        reason=None,
    )