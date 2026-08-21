from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta
from typing import Any

from crawler.http_client import tpex_post
from db.database import get_connection
from scripts.sync_tpex_market_institutional import (
    sync_one_day,
)


DEFAULT_CALENDAR_DAYS = 90
DEFAULT_SLEEP_SECONDS = 1.0

TPEX_DAILY_URL = (
    "https://www.tpex.org.tw/"
    "www/zh-tw/afterTrading/dailyQuotes"
)

TPEX_DAILY_REFERER = (
    "https://www.tpex.org.tw/"
    "zh-tw/mainboard/trading/info/pricing.html"
)


def _parse_date(
    value: str,
) -> date:
    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "日期格式必須為 YYYY-MM-DD"
        ) from exc


def _get_latest_tpex_price_date() -> date:
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT MAX(trade_date) AS max_trade_date
            FROM daily_prices
            WHERE market = 'TPEx'
            """
        ).fetchone()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "daily_prices 查不到 TPEx 資料"
        )

    value = row["max_trade_date"]

    if not value:
        raise RuntimeError(
            "daily_prices 沒有 TPEx trade_date"
        )

    try:
        return datetime.strptime(
            str(value),
            "%Y-%m-%d",
        ).date()

    except ValueError as exc:
        raise RuntimeError(
            "daily_prices.trade_date "
            "格式錯誤："
            f"{value!r}"
        ) from exc


def _get_local_tpex_trading_dates(
    start_date: date,
    end_date: date,
) -> set[date]:
    """
    優先使用已存在的 TPEx daily_prices
    當交易日來源。
    """
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT DISTINCT trade_date
            FROM daily_prices
            WHERE market = 'TPEx'
              AND trade_date >= ?
              AND trade_date <= ?
            """,
            (
                start_date.isoformat(),
                end_date.isoformat(),
            ),
        ).fetchall()

    finally:
        conn.close()

    result: set[date] = set()

    for row in rows:
        value = row["trade_date"]

        try:
            parsed = datetime.strptime(
                str(value),
                "%Y-%m-%d",
            ).date()

        except ValueError as exc:
            raise RuntimeError(
                "daily_prices.trade_date "
                "格式錯誤："
                f"{value!r}"
            ) from exc

        result.add(parsed)

    return result


def _normalize_tpex_date(
    value: Any,
) -> str:
    text = str(value).strip()

    try:
        return datetime.strptime(
            text,
            "%Y%m%d",
        ).strftime(
            "%Y-%m-%d"
        )

    except ValueError as exc:
        raise RuntimeError(
            "TPEx dailyQuotes "
            "回傳無法識別 date："
            f"{value!r}"
        ) from exc


def _probe_tpex_trading_day(
    target_date: date,
) -> bool:
    """
    當 daily_prices 尚未涵蓋該日期時，
    用 TPEx 官方 dailyQuotes 判斷。

    HTTP / JSON / schema 異常：
        raise
        不可誤當休市。

    JSON 正常但 stat != ok：
        視為該日沒有正式行情資料，
        因而不進 Foreign crawler。
    """
    request_date = (
        target_date.strftime(
            "%Y/%m/%d"
        )
    )

    response = tpex_post(
        TPEX_DAILY_URL,
        data={
            "date": request_date,
            "response": "json",
        },
        headers={
            "Referer":
                TPEX_DAILY_REFERER,
        },
    )

    response.raise_for_status()

    content_type = (
        response.headers.get(
            "Content-Type",
            "",
        )
    )

    if "json" not in content_type.lower():
        raise RuntimeError(
            "TPEx dailyQuotes "
            "response 不是 JSON："
            f"date={target_date}, "
            f"Content-Type="
            f"{content_type!r}"
        )

    try:
        payload = response.json()

    except ValueError as exc:
        raise RuntimeError(
            "TPEx dailyQuotes "
            "JSON decode failed："
            f"{target_date}"
        ) from exc

    stat = payload.get(
        "stat"
    )

    if stat != "ok":
        print(
            "[NO TRADE] "
            f"{target_date} "
            "TPEx dailyQuotes "
            f"stat={stat!r}"
        )

        return False

    response_date = (
        _normalize_tpex_date(
            payload.get("date")
        )
    )

    if (
        response_date
        != target_date.isoformat()
    ):
        raise RuntimeError(
            "TPEx dailyQuotes "
            "response 日期不符："
            f"request={target_date}, "
            f"response={response_date}"
        )

    tables = payload.get(
        "tables"
    )

    if not isinstance(
        tables,
        list,
    ):
        raise RuntimeError(
            "TPEx dailyQuotes "
            "tables 不是 list："
            f"{target_date}"
        )

    if not tables:
        raise RuntimeError(
            "TPEx dailyQuotes "
            "stat=ok 但 tables 為空："
            f"{target_date}"
        )

    #
    # 至少要存在一個有 data 的 table。
    #
    has_rows = False

    for table in tables:
        if not isinstance(
            table,
            dict,
        ):
            continue

        data = table.get(
            "data"
        )

        if (
            isinstance(data, list)
            and len(data) > 0
        ):
            has_rows = True
            break

        if not has_rows:
            print(
                "[NO TRADE] "
                f"{target_date} "
                "TPEx dailyQuotes "
                "stat=ok but no market data"
            )

            return False

        return True


def _build_trading_dates(
    start_date: date,
    end_date: date,
    local_dates: set[date],
    probe_sleep_seconds: float,
) -> list[date]:
    """
    建立完整 90 曆日交易日集合。

    優先順序：

    1. daily_prices 已知交易日
    2. 六、日直接跳過
    3. 其餘日期查 TPEx dailyQuotes

    因此即使 daily_prices 只有最近 60 日，
    仍能安全找到前面的 TPEx 交易日。
    """
    result: list[date] = []

    current = start_date

    while current <= end_date:
        if current in local_dates:
            print(
                "[CALENDAR LOCAL] "
                f"{current}"
            )

            result.append(
                current
            )

            current += timedelta(
                days=1
            )

            continue

        #
        # 週末不需要打官方 API。
        #
        if current.weekday() >= 5:
            print(
                "[CALENDAR WEEKEND] "
                f"{current}"
            )

            current += timedelta(
                days=1
            )

            continue

        print(
            "[CALENDAR PROBE] "
            f"{current}"
        )

        is_trading_day = (
            _probe_tpex_trading_day(
                current
            )
        )

        if is_trading_day:
            print(
                "[CALENDAR TPEx] "
                f"{current} "
                "is trading day"
            )

            result.append(
                current
            )

        if probe_sleep_seconds > 0:
            time.sleep(
                probe_sleep_seconds
            )

        current += timedelta(
            days=1
        )

    return result


def backfill(
    *,
    end_date: date,
    calendar_days: int,
    sleep_seconds: float,
    probe_sleep_seconds: float,
    force: bool,
) -> None:
    if calendar_days <= 0:
        raise ValueError(
            "calendar_days 必須 > 0"
        )

    if sleep_seconds < 0:
        raise ValueError(
            "sleep_seconds 不可 < 0"
        )

    if probe_sleep_seconds < 0:
        raise ValueError(
            "probe_sleep_seconds "
            "不可 < 0"
        )

    start_date = (
        end_date
        - timedelta(
            days=calendar_days - 1
        )
    )

    print("=" * 72)
    print("TPEx Foreign 90-Day Coverage")
    print("=" * 72)

    print(
        "[INFO] calendar range = "
        f"{start_date} ~ {end_date}"
    )

    local_dates = (
        _get_local_tpex_trading_dates(
            start_date=start_date,
            end_date=end_date,
        )
    )

    print(
        "[INFO] daily_prices known "
        "TPEx dates = "
        f"{len(local_dates)}"
    )

    print()
    print(
        "[INFO] 建立 TPEx "
        "完整交易日清單..."
    )

    trading_dates = (
        _build_trading_dates(
            start_date=start_date,
            end_date=end_date,
            local_dates=local_dates,
            probe_sleep_seconds=(
                probe_sleep_seconds
            ),
        )
    )

    if not trading_dates:
        raise RuntimeError(
            "指定期間沒有找到 "
            "TPEx 交易日"
        )

    print()
    print("=" * 72)
    print("TRADING CALENDAR READY")
    print("=" * 72)

    print(
        "Trading dates :",
        len(trading_dates),
    )

    print(
        "First date    :",
        trading_dates[0],
    )

    print(
        "Last date     :",
        trading_dates[-1],
    )

    success_count = 0

    error_dates: list[
        tuple[str, str]
    ] = []

    total = len(
        trading_dates
    )

    for index, trade_date in enumerate(
        trading_dates,
        start=1,
    ):
        trade_date_text = (
            trade_date.isoformat()
        )

        print()
        print("-" * 72)

        print(
            f"[{index}/{total}] "
            f"{trade_date_text}"
        )

        print("-" * 72)

        try:
            sync_one_day(
                trade_date=trade_date_text,
                force=force,
            )

            success_count += 1

        except Exception as exc:
            message = (
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            error_dates.append(
                (
                    trade_date_text,
                    message,
                )
            )

            print(
                "[BACKFILL ERROR] "
                f"{trade_date_text}"
            )

            print(
                "[BACKFILL ERROR] "
                f"{message}"
            )

        finally:
            if (
                index < total
                and sleep_seconds > 0
            ):
                time.sleep(
                    sleep_seconds
                )

    print()
    print("=" * 72)
    print("BACKFILL SUMMARY")
    print("=" * 72)

    print(
        "Trading dates :",
        total,
    )

    print(
        "Completed     :",
        success_count,
    )

    print(
        "Errors        :",
        len(error_dates),
    )

    if error_dates:
        print()
        print(
            "Error dates:"
        )

        for (
            trade_date_text,
            message,
        ) in error_dates:
            print(
                f"  {trade_date_text}"
                f" -> {message}"
            )

        raise RuntimeError(
            "TPEx Foreign backfill "
            f"仍有 {len(error_dates)} "
            "個交易日失敗"
        )

    print()
    print(
        "[OK] TPEx Foreign "
        "90-day coverage 完成"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "回補 TPEx 最近 N 個曆日 "
            "外資及陸資（不含自營商）"
        )
    )

    parser.add_argument(
        "--end-date",
        type=_parse_date,
        default=None,
        help=(
            "截止日 YYYY-MM-DD。"
            "未指定則使用 "
            "daily_prices 最新 TPEx 日期"
        ),
    )

    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_CALENDAR_DAYS,
        help=(
            "曆日數，預設 90"
        ),
    )

    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help=(
            "Foreign 交易日之間等待秒數，"
            "預設 1.0"
        ),
    )

    parser.add_argument(
        "--probe-sleep-seconds",
        type=float,
        default=0.5,
        help=(
            "dailyQuotes 交易日探測之間 "
            "等待秒數，預設 0.5"
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "忽略 SUCCESS crawl log "
            "重新抓取"
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.end_date is None:
        end_date = (
            _get_latest_tpex_price_date()
        )

        print(
            "[INFO] 使用 daily_prices "
            "最新 TPEx 日期："
            f"{end_date}"
        )

    else:
        end_date = args.end_date

    backfill(
        end_date=end_date,
        calendar_days=args.days,
        sleep_seconds=(
            args.sleep_seconds
        ),
        probe_sleep_seconds=(
            args.probe_sleep_seconds
        ),
        force=args.force,
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as exc:
        print(
            "[ERROR] "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        sys.exit(1)