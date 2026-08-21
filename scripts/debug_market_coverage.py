from __future__ import annotations

from collections import Counter

from db.database import get_connection


TPEX_FOREIGN_SOURCE = "TPEX_QFII_STAT"


def _pct(
    numerator: int,
    denominator: int,
) -> str:
    if denominator <= 0:
        return "0.00%"

    return (
        f"{numerator / denominator * 100:.2f}%"
    )


def _print_section(
    title: str,
) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _get_active_stocks(
    conn,
):
    return conn.execute(
        """
        SELECT
            stock_id,
            stock_name,
            market
        FROM stocks
        WHERE is_active = 1
          AND market IN (
              'TWSE',
              'TPEx'
          )
        ORDER BY
            market,
            stock_id
        """
    ).fetchall()


def _get_price_counts(
    conn,
) -> dict[tuple[str, str], int]:
    rows = conn.execute(
        """
        SELECT
            stock_id,
            market,
            COUNT(*) AS cnt
        FROM daily_prices
        GROUP BY
            stock_id,
            market
        """
    ).fetchall()

    return {
        (
            str(row["stock_id"]),
            str(row["market"]),
        ):
            int(row["cnt"])
        for row in rows
    }


def _get_institutional_counts(
    conn,
) -> dict[tuple[str, str], int]:
    rows = conn.execute(
        """
        SELECT
            stock_id,
            market,
            COUNT(*) AS cnt
        FROM institutional_trades
        GROUP BY
            stock_id,
            market
        """
    ).fetchall()

    return {
        (
            str(row["stock_id"]),
            str(row["market"]),
        ):
            int(row["cnt"])
        for row in rows
    }


def _get_tdcc_counts(
    conn,
) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT
            stock_id,
            COUNT(
                DISTINCT data_date
            ) AS cnt
        FROM tdcc_holdings
        GROUP BY stock_id
        """
    ).fetchall()

    return {
        str(row["stock_id"]):
            int(row["cnt"])
        for row in rows
    }


def _get_latest_tpex_foreign_dates(
    conn,
) -> set[str]:
    """
    只用來確認 TPEx effective Foreign
    是否有可推論 ZERO_INFERRED 的
    crawl SUCCESS 日期。
    """
    rows = conn.execute(
        """
        SELECT DISTINCT
            request_key
        FROM crawl_logs
        WHERE source = ?
          AND status = 'SUCCESS'
        """,
        (
            TPEX_FOREIGN_SOURCE,
        ),
    ).fetchall()

    result = set()

    prefix = (
        f"{TPEX_FOREIGN_SOURCE}:"
    )

    for row in rows:
        request_key = str(
            row["request_key"]
        )

        if not request_key.startswith(
            prefix
        ):
            continue

        trade_date = request_key[
            len(prefix):
        ]

        if trade_date:
            result.add(
                trade_date
            )

    return result


def _get_latest_market_price_date(
    conn,
    market: str,
) -> str | None:
    row = conn.execute(
        """
        SELECT MAX(trade_date) AS trade_date
        FROM daily_prices
        WHERE market = ?
        """,
        (market,),
    ).fetchone()

    if (
        row is None
        or not row["trade_date"]
    ):
        return None

    return str(
        row["trade_date"]
    )


def _get_recent_tpex_week_dates(
    conn,
    limit_days: int = 20,
) -> list[str]:
    """
    取最近一段 TPEx 交易日，
    用來粗略檢查 Foreign effective
    是否已有足夠 coverage。

    這裡不是重新計算 Foreign /20，
    只是 coverage 診斷。
    """
    rows = conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM daily_prices
        WHERE market = 'TPEx'
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        (
            limit_days,
        ),
    ).fetchall()

    return [
        str(row["trade_date"])
        for row in rows
    ]


def main() -> None:
    conn = get_connection()

    try:
        active_rows = (
            _get_active_stocks(
                conn
            )
        )

        price_counts = (
            _get_price_counts(
                conn
            )
        )

        institutional_counts = (
            _get_institutional_counts(
                conn
            )
        )

        tdcc_counts = (
            _get_tdcc_counts(
                conn
            )
        )

        tpex_success_dates = (
            _get_latest_tpex_foreign_dates(
                conn
            )
        )

        recent_tpex_dates = (
            _get_recent_tpex_week_dates(
                conn
            )
        )

        latest_twse_date = (
            _get_latest_market_price_date(
                conn,
                "TWSE",
            )
        )

        latest_tpex_date = (
            _get_latest_market_price_date(
                conn,
                "TPEx",
            )
        )

        _print_section(
            "MARKET COVERAGE"
        )

        print(
            "latest TWSE daily price =",
            latest_twse_date,
        )

        print(
            "latest TPEx daily price =",
            latest_tpex_date,
        )

        total_active = len(
            active_rows
        )

        market_counter = Counter(
            str(row["market"])
            for row in active_rows
        )

        print()
        print(
            "active total =",
            total_active,
        )

        print(
            "active TWSE  =",
            market_counter["TWSE"],
        )

        print(
            "active TPEx  =",
            market_counter["TPEx"],
        )

        # =================================
        # Per-stock coverage
        # =================================

        coverage_rows = []

        for row in active_rows:
            stock_id = str(
                row["stock_id"]
            )

            stock_name = str(
                row["stock_name"]
            )

            market = str(
                row["market"]
            )

            price_count = (
                price_counts.get(
                    (
                        stock_id,
                        market,
                    ),
                    0,
                )
            )

            institutional_count = (
                institutional_counts.get(
                    (
                        stock_id,
                        market,
                    ),
                    0,
                )
            )

            tdcc_count = (
                tdcc_counts.get(
                    stock_id,
                    0,
                )
            )

            price_ok = (
                price_count >= 30
            )

            if market == "TWSE":
                foreign_ok = (
                    institutional_count > 0
                )

            else:
                #
                # TPEx effective Foreign：
                #
                # 即使該股票本身沒有
                # institutional row，
                # 只要近期 qfiiStat crawl
                # 已 SUCCESS，
                # ZERO_INFERRED 就能成立。
                #
                recent_success_count = sum(
                    trade_date
                    in tpex_success_dates
                    for trade_date
                    in recent_tpex_dates
                )

                foreign_ok = (
                    recent_success_count
                    >= 15
                )

            tdcc_ok = (
                tdcc_count >= 4
            )

            ranking_ready = (
                price_ok
                and foreign_ok
                and tdcc_ok
            )

            coverage_rows.append(
                {
                    "stock_id":
                        stock_id,
                    "stock_name":
                        stock_name,
                    "market":
                        market,
                    "price_count":
                        price_count,
                    "institutional_count":
                        institutional_count,
                    "tdcc_count":
                        tdcc_count,
                    "price_ok":
                        price_ok,
                    "foreign_ok":
                        foreign_ok,
                    "tdcc_ok":
                        tdcc_ok,
                    "ranking_ready":
                        ranking_ready,
                }
            )

        # =================================
        # Summary
        # =================================

        price_ready = sum(
            row["price_ok"]
            for row in coverage_rows
        )

        foreign_ready = sum(
            row["foreign_ok"]
            for row in coverage_rows
        )

        tdcc_ready = sum(
            row["tdcc_ok"]
            for row in coverage_rows
        )

        ranking_ready = sum(
            row["ranking_ready"]
            for row in coverage_rows
        )

        _print_section(
            "OVERALL SUMMARY"
        )

        print(
            "Active stocks       =",
            total_active,
        )

        print(
            "Price >= 30 days    =",
            price_ready,
            _pct(
                price_ready,
                total_active,
            ),
        )

        print(
            "Foreign ready       =",
            foreign_ready,
            _pct(
                foreign_ready,
                total_active,
            ),
        )

        print(
            "TDCC >= 4 dates     =",
            tdcc_ready,
            _pct(
                tdcc_ready,
                total_active,
            ),
        )

        print(
            "Ranking ready       =",
            ranking_ready,
            _pct(
                ranking_ready,
                total_active,
            ),
        )

        # =================================
        # Market summary
        # =================================

        _print_section(
            "MARKET SUMMARY"
        )

        for market in [
            "TWSE",
            "TPEx",
        ]:
            rows = [
                row
                for row in coverage_rows
                if row["market"] == market
            ]

            total = len(
                rows
            )

            market_price = sum(
                row["price_ok"]
                for row in rows
            )

            market_foreign = sum(
                row["foreign_ok"]
                for row in rows
            )

            market_tdcc = sum(
                row["tdcc_ok"]
                for row in rows
            )

            market_ready = sum(
                row["ranking_ready"]
                for row in rows
            )

            print()
            print(
                market
            )

            print(
                "  active       =",
                total,
            )

            print(
                "  price ready  =",
                market_price,
                _pct(
                    market_price,
                    total,
                ),
            )

            print(
                "  foreign ready=",
                market_foreign,
                _pct(
                    market_foreign,
                    total,
                ),
            )

            print(
                "  tdcc ready   =",
                market_tdcc,
                _pct(
                    market_tdcc,
                    total,
                ),
            )

            print(
                "  ranking ready=",
                market_ready,
                _pct(
                    market_ready,
                    total,
                ),
            )

        # =================================
        # Missing reason counts
        # =================================

        _print_section(
            "MISSING REASONS"
        )

        missing_price = [
            row
            for row in coverage_rows
            if not row["price_ok"]
        ]

        missing_foreign = [
            row
            for row in coverage_rows
            if not row["foreign_ok"]
        ]

        missing_tdcc = [
            row
            for row in coverage_rows
            if not row["tdcc_ok"]
        ]

        print(
            "missing price   =",
            len(missing_price),
        )

        print(
            "missing foreign =",
            len(missing_foreign),
        )

        print(
            "missing TDCC    =",
            len(missing_tdcc),
        )

        # =================================
        # TDCC distribution
        # =================================

        _print_section(
            "TDCC DATE COUNT DISTRIBUTION"
        )

        tdcc_distribution = Counter(
            row["tdcc_count"]
            for row in coverage_rows
        )

        for count in sorted(
            tdcc_distribution
        ):
            print(
                f"{count:3d} dates =",
                tdcc_distribution[
                    count
                ],
            )

        # =================================
        # Missing samples
        # =================================

        _print_section(
            "MISSING SAMPLE"
        )

        print()
        print(
            "Price < 30:"
        )

        for row in missing_price[:20]:
            print(
                f"  {row['market']:4s} "
                f"{row['stock_id']} "
                f"{row['stock_name']} "
                f"days={row['price_count']}"
            )

        print()
        print(
            "Foreign not ready:"
        )

        for row in (
            missing_foreign[:20]
        ):
            print(
                f"  {row['market']:4s} "
                f"{row['stock_id']} "
                f"{row['stock_name']} "
                f"rows="
                f"{row['institutional_count']}"
            )

        print()
        print(
            "TDCC < 4:"
        )

        for row in missing_tdcc[:30]:
            print(
                f"  {row['market']:4s} "
                f"{row['stock_id']} "
                f"{row['stock_name']} "
                f"dates="
                f"{row['tdcc_count']}"
            )

        # =================================
        # Ranking-ready sample
        # =================================

        _print_section(
            "RANKING READY SAMPLE"
        )

        ready_rows = [
            row
            for row in coverage_rows
            if row["ranking_ready"]
        ]

        for row in ready_rows[:40]:
            print(
                f"  {row['market']:4s} "
                f"{row['stock_id']} "
                f"{row['stock_name']} "
                f"price="
                f"{row['price_count']} "
                f"foreign="
                f"{row['institutional_count']} "
                f"tdcc="
                f"{row['tdcc_count']}"
            )

        print()
        print("=" * 72)
        print("DONE")
        print("=" * 72)

    finally:
        conn.close()


if __name__ == "__main__":
    main()