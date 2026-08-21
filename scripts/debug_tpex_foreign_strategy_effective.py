from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from db.database import get_connection
from strategy.foreign_data import (
    get_effective_foreign_net,
)


MARKET = "TPEx"

DEFAULT_STOCK_ID = "1294"


@dataclass(frozen=True)
class WeekResult:
    week_start: str
    week_end: str
    market_dates: list[str]
    foreign_net: int | None
    stored_days: int
    zero_inferred_days: int
    insufficient_days: int


def _parse_date(
    value: str,
) -> date:
    return datetime.strptime(
        value,
        "%Y-%m-%d",
    ).date()


def _monday(
    value: date,
) -> date:
    return (
        value
        - timedelta(
            days=value.weekday()
        )
    )


def _get_latest_tpex_date(
    conn,
) -> date:
    row = conn.execute(
        """
        SELECT MAX(trade_date) AS trade_date
        FROM daily_prices
        WHERE market = 'TPEx'
        """
    ).fetchone()

    if (
        row is None
        or not row["trade_date"]
    ):
        raise RuntimeError(
            "找不到 TPEx daily_prices"
        )

    return _parse_date(
        str(row["trade_date"])
    )


def _get_market_dates_for_week(
    conn,
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
        WHERE market = 'TPEx'
          AND trade_date >= ?
          AND trade_date <= ?
        ORDER BY trade_date ASC
        """,
        (
            week_start.isoformat(),
            week_end.isoformat(),
        ),
    ).fetchall()

    return [
        str(row["trade_date"])
        for row in rows
    ]


def _is_complete_market_week(
    conn,
    week_start: date,
    as_of_date: date,
) -> bool:
    """
    以 daily_prices 的市場交易日判斷該週是否完整。

    若該週最後一個已知 TPEx 交易日
    <= as_of_date，且 as_of_date 已到該週
    最後交易日，視為完整週。

    例如：
    2026-08-14 是週五且為該週最後交易日，
    則 2026-08-10 ~ 2026-08-16
    可視為完整交易週。
    """
    market_dates = (
        _get_market_dates_for_week(
            conn,
            week_start,
        )
    )

    if not market_dates:
        return False

    latest_market_date = (
        _parse_date(
            market_dates[-1]
        )
    )

    return (
        latest_market_date
        <= as_of_date
    )


def _find_last_three_complete_weeks(
    conn,
    as_of_date: date,
) -> list[date]:
    """
    從 as_of_date 所在週往前找，
    取得最近三個有 TPEx 行情的完整交易週。
    """
    result: list[date] = []

    cursor = _monday(
        as_of_date
    )

    max_scan_weeks = 12

    for _ in range(
        max_scan_weeks
    ):
        market_dates = (
            _get_market_dates_for_week(
                conn,
                cursor,
            )
        )

        if (
            market_dates
            and _is_complete_market_week(
                conn,
                cursor,
                as_of_date,
            )
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
            "找不到最近 3 個完整 TPEx 交易週"
        )

    #
    # 回傳 chronological：
    # oldest -> newest
    #
    return sorted(
        result
    )


def _evaluate_week(
    conn,
    stock_id: str,
    week_start: date,
) -> WeekResult:
    week_end = (
        week_start
        + timedelta(days=6)
    )

    market_dates = (
        _get_market_dates_for_week(
            conn,
            week_start,
        )
    )

    effective_rows = (
        get_effective_foreign_net(
            conn=conn,
            stock_id=stock_id,
            market=MARKET,
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
        # 市場有交易日，
        # 但這檔股票連 daily_price 都沒有，
        # 不能自行假設 foreign_net = 0。
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
                "未知 effective foreign "
                f"status：{row.status}"
            )

        values.append(
            int(row.foreign_net)
        )

    if insufficient_days > 0:
        weekly_net = None

    elif len(values) != len(
        market_dates
    ):
        weekly_net = None

    else:
        weekly_net = sum(
            values
        )

    return WeekResult(
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


def _score_foreign(
    weeks: list[WeekResult],
) -> dict:
    """
    Foreign /20

    A.
    最近 3 個完整週 foreign_net 都 > 0
    +10

    B.
    weekly foreign_net 連續增加
    +5

    C.
    週與週之間不可跳升 > 2.5x
    +5

    全部符合才 PASS。
    """
    if any(
        week.foreign_net is None
        for week in weeks
    ):
        return {
            "status":
                "INSUFFICIENT_DATA",
            "score": None,
            "weekly_nets": None,
            "condition_a": None,
            "condition_b": None,
            "condition_c": None,
        }

    weekly_nets = [
        int(week.foreign_net)
        for week in weeks
    ]

    condition_a = all(
        value > 0
        for value in weekly_nets
    )

    condition_b = (
        weekly_nets[0]
        < weekly_nets[1]
        < weekly_nets[2]
    )

    #
    # 爆量檢查只在三週均為正值時
    # 才有明確倍數意義。
    #
    condition_c = (
        condition_a
        and weekly_nets[1]
        <= weekly_nets[0] * 2.5
        and weekly_nets[2]
        <= weekly_nets[1] * 2.5
    )

    score = 0

    if condition_a:
        score += 10

    if condition_b:
        score += 5

    if condition_c:
        score += 5

    status = (
        "PASS"
        if (
            condition_a
            and condition_b
            and condition_c
        )
        else "FAIL"
    )

    return {
        "status": status,
        "score": score,
        "weekly_nets":
            weekly_nets,
        "condition_a":
            condition_a,
        "condition_b":
            condition_b,
        "condition_c":
            condition_c,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "驗證 TPEx Foreign /20 "
            "是否正確使用 ZERO_INFERRED"
        )
    )

    parser.add_argument(
        "--stock-id",
        default=DEFAULT_STOCK_ID,
    )

    parser.add_argument(
        "--as-of-date",
        default=None,
        help=(
            "YYYY-MM-DD；"
            "未指定則使用最新 TPEx 日 K 日期"
        ),
    )

    args = parser.parse_args()

    conn = get_connection()

    try:
        if args.as_of_date:
            as_of_date = (
                _parse_date(
                    args.as_of_date
                )
            )
        else:
            as_of_date = (
                _get_latest_tpex_date(
                    conn
                )
            )

        print("=" * 72)
        print(
            "TPEx Foreign /20 "
            "Effective Data Validation"
        )
        print("=" * 72)

        print(
            "stock_id   =",
            args.stock_id,
        )

        print(
            "as_of_date =",
            as_of_date,
        )

        week_starts = (
            _find_last_three_complete_weeks(
                conn,
                as_of_date,
            )
        )

        weeks = [
            _evaluate_week(
                conn=conn,
                stock_id=args.stock_id,
                week_start=week_start,
            )
            for week_start in week_starts
        ]

        print()
        print("=" * 72)
        print("WEEKLY DATA")
        print("=" * 72)

        for index, week in enumerate(
            weeks,
            start=1,
        ):
            print()
            print(
                f"Week {index}: "
                f"{week.week_start} "
                f"~ {week.week_end}"
            )

            print(
                "market dates      =",
                len(
                    week.market_dates
                ),
            )

            print(
                "stored days       =",
                week.stored_days,
            )

            print(
                "zero inferred days=",
                week.zero_inferred_days,
            )

            print(
                "insufficient days =",
                week.insufficient_days,
            )

            print(
                "weekly foreign_net=",
                week.foreign_net,
            )

        score = (
            _score_foreign(
                weeks
            )
        )

        print()
        print("=" * 72)
        print("FOREIGN /20")
        print("=" * 72)

        print(
            "status      =",
            score["status"],
        )

        print(
            "score       =",
            score["score"],
        )

        print(
            "weekly nets =",
            score["weekly_nets"],
        )

        print()
        print(
            "A. 3 weeks > 0      =",
            score["condition_a"],
            "(+10)",
        )

        print(
            "B. continuously up   =",
            score["condition_b"],
            "(+5)",
        )

        print(
            "C. no jump > 2.5x    =",
            score["condition_c"],
            "(+5)",
        )

        print()
        print("=" * 72)
        print("ZERO-INFERRED CHECK")
        print("=" * 72)

        total_zero_inferred = sum(
            week.zero_inferred_days
            for week in weeks
        )

        print(
            "zero inferred days =",
            total_zero_inferred,
        )

        if (
            total_zero_inferred > 0
            and score["status"]
            != "INSUFFICIENT_DATA"
        ):
            print(
                "[OK] ZERO_INFERRED 已成功"
                "參與 weekly foreign_net，"
                "沒有被誤判成資料不足。"
            )

        elif total_zero_inferred == 0:
            print(
                "[INFO] 此股票最近三週沒有"
                " ZERO_INFERRED 日，"
                "可換另一檔再驗證。"
            )

        else:
            print(
                "[CHECK] 雖然有 ZERO_INFERRED，"
                "但仍存在其他真正缺資料日。"
            )

    finally:
        conn.close()


if __name__ == "__main__":
    main()