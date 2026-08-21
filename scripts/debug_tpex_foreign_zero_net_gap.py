from __future__ import annotations

import argparse
from datetime import datetime

from db.database import get_connection


SOURCE = "TPEX_QFII_STAT"


def _get_latest_tpex_foreign_date(
    conn,
) -> str:
    row = conn.execute(
        """
        SELECT MAX(trade_date) AS trade_date
        FROM institutional_trades
        WHERE market = 'TPEx'
          AND source = ?
        """,
        (SOURCE,),
    ).fetchone()

    if row is None or not row["trade_date"]:
        raise RuntimeError(
            "institutional_trades 尚無 TPEx Foreign 資料"
        )

    return str(row["trade_date"])


def _check_date_format(
    value: str,
) -> str:
    try:
        datetime.strptime(
            value,
            "%Y-%m-%d",
        )
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "日期格式必須為 YYYY-MM-DD"
        ) from exc

    return value


def _print_schema(
    conn,
) -> None:
    print()
    print("=" * 72)
    print("institutional_trades SCHEMA")
    print("=" * 72)

    rows = conn.execute(
        """
        PRAGMA table_info(institutional_trades)
        """
    ).fetchall()

    for row in rows:
        print(
            f"{row['name']:20s} "
            f"type={row['type']:10s} "
            f"notnull={row['notnull']} "
            f"default={row['dflt_value']!r} "
            f"pk={row['pk']}"
        )


def _print_crawl_status(
    conn,
    trade_date: str,
) -> bool:
    request_key = (
        f"TPEX_QFII_STAT:{trade_date}"
    )

    row = conn.execute(
        """
        SELECT
            status,
            record_count,
            error_message,
            started_at,
            finished_at
        FROM crawl_logs
        WHERE source = ?
          AND request_key = ?
        ORDER BY started_at DESC
        LIMIT 1
        """,
        (
            SOURCE,
            request_key,
        ),
    ).fetchone()

    print()
    print("=" * 72)
    print("CRAWL STATUS")
    print("=" * 72)

    print(
        "request_key =",
        request_key,
    )

    if row is None:
        print(
            "crawl log = NOT FOUND"
        )
        return False

    print(
        "status       =",
        row["status"],
    )

    print(
        "record_count =",
        row["record_count"],
    )

    print(
        "error        =",
        row["error_message"],
    )

    return (
        row["status"]
        == "SUCCESS"
    )


def _get_market_stock_count(
    conn,
    trade_date: str,
) -> int:
    """
    用該日存在 TPEx daily_prices 的
    4 碼 active 股票當可觀察母體。

    不直接用全部 stocks，
    避免把該日沒有行情的股票算進來。
    """
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT p.stock_id) AS cnt
        FROM daily_prices p
        JOIN stocks s
          ON s.stock_id = p.stock_id
         AND s.market = p.market
        WHERE p.market = 'TPEx'
          AND p.trade_date = ?
          AND s.is_active = 1
          AND LENGTH(p.stock_id) = 4
          AND p.stock_id GLOB '[0-9][0-9][0-9][0-9]'
        """,
        (trade_date,),
    ).fetchone()

    return int(
        row["cnt"] or 0
    )


def _get_foreign_stock_count(
    conn,
    trade_date: str,
) -> int:
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT stock_id) AS cnt
        FROM institutional_trades
        WHERE market = 'TPEx'
          AND trade_date = ?
          AND source = ?
        """,
        (
            trade_date,
            SOURCE,
        ),
    ).fetchone()

    return int(
        row["cnt"] or 0
    )


def _get_missing_stocks(
    conn,
    trade_date: str,
):
    """
    該日有 TPEx 日 K，
    但沒有 qfiiStat normalized row 的股票。
    """
    return conn.execute(
        """
        SELECT DISTINCT
            p.stock_id,
            s.stock_name
        FROM daily_prices p
        JOIN stocks s
          ON s.stock_id = p.stock_id
         AND s.market = p.market
        LEFT JOIN institutional_trades i
          ON i.stock_id = p.stock_id
         AND i.market = p.market
         AND i.trade_date = p.trade_date
         AND i.source = ?
        WHERE p.market = 'TPEx'
          AND p.trade_date = ?
          AND s.is_active = 1
          AND LENGTH(p.stock_id) = 4
          AND p.stock_id GLOB '[0-9][0-9][0-9][0-9]'
          AND i.stock_id IS NULL
        ORDER BY p.stock_id
        """,
        (
            SOURCE,
            trade_date,
        ),
    ).fetchall()


def _get_zero_net_rows(
    conn,
    trade_date: str,
) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM institutional_trades
        WHERE market = 'TPEx'
          AND trade_date = ?
          AND source = ?
          AND foreign_net = 0
        """,
        (
            trade_date,
            SOURCE,
        ),
    ).fetchone()

    return int(
        row["cnt"] or 0
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "診斷 TPEx qfiiStat "
            "zero-net 股票缺 row 問題"
        )
    )

    parser.add_argument(
        "--date",
        type=_check_date_format,
        default=None,
        help=(
            "YYYY-MM-DD；"
            "未指定則使用最新 TPEx Foreign 日期"
        ),
    )

    args = parser.parse_args()

    conn = get_connection()

    try:
        trade_date = (
            args.date
            or _get_latest_tpex_foreign_date(
                conn
            )
        )

        print("=" * 72)
        print("TPEx Foreign Zero-Net Gap")
        print("=" * 72)

        print(
            "trade_date =",
            trade_date,
        )

        crawl_success = (
            _print_crawl_status(
                conn,
                trade_date,
            )
        )

        market_count = (
            _get_market_stock_count(
                conn,
                trade_date,
            )
        )

        foreign_count = (
            _get_foreign_stock_count(
                conn,
                trade_date,
            )
        )

        zero_net_count = (
            _get_zero_net_rows(
                conn,
                trade_date,
            )
        )

        missing_rows = (
            _get_missing_stocks(
                conn,
                trade_date,
            )
        )

        print()
        print("=" * 72)
        print("COVERAGE")
        print("=" * 72)

        print(
            "TPEx active stocks with daily price =",
            market_count,
        )

        print(
            "qfiiStat normalized rows          =",
            foreign_count,
        )

        print(
            "stored foreign_net = 0 rows       =",
            zero_net_count,
        )

        print(
            "daily-price stocks without row     =",
            len(missing_rows),
        )

        if market_count:
            coverage_pct = (
                foreign_count
                / market_count
                * 100
            )

            print(
                "normalized coverage              =",
                f"{coverage_pct:.2f}%",
            )

        print()
        print(
            "First 30 stocks without "
            "institutional row:"
        )

        for row in missing_rows[:30]:
            print(
                f"  {row['stock_id']} "
                f"{row['stock_name']}"
            )

        _print_schema(
            conn
        )

        print()
        print("=" * 72)
        print("SEMANTIC CHECK")
        print("=" * 72)

        if not crawl_success:
            print(
                "[FAIL] 此日沒有 SUCCESS crawl log。"
            )

            print(
                "不能把缺少的 row 解讀成 "
                "foreign_net = 0。"
            )

        elif not missing_rows:
            print(
                "[OK] 該日沒有 zero-net row gap。"
            )

        else:
            print(
                "[CONFIRMED GAP]"
            )

            print(
                "此日 qfiiStat 已完整抓取 SUCCESS，"
            )

            print(
                "但仍有",
                len(missing_rows),
                "檔有日 K、沒有 institutional row。"
            )

            print()
            print(
                "依先前 qfiiStat buy/sell 驗證："
            )

            print(
                "  buy 已排到 foreign_net = 0"
            )

            print(
                "  sell 已排到 foreign_net = 0"
            )

            print(
                "  所有 positive / negative net "
                "均已涵蓋"
            )

            print()
            print(
                "因此這些未出現股票可確認："
            )

            print(
                "  foreign_net = 0"
            )

            print(
                "但不能確認："
            )

            print(
                "  foreign_buy"
            )

            print(
                "  foreign_sell"
            )

            print()
            print(
                "下一階段必須在 DB 層或策略層"
                "明確表示這個差異，"
                "不能把缺 row 當 "
                "INSUFFICIENT_DATA。"
            )

    finally:
        conn.close()


if __name__ == "__main__":
    main()