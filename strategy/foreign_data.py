from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


TWSE_FOREIGN_SOURCE = "TWSE_T86_MARKET"
TPEX_FOREIGN_SOURCE = "TPEX_QFII_STAT"


@dataclass(frozen=True)
class EffectiveForeignNet:
    stock_id: str
    market: str
    trade_date: str

    foreign_net: Optional[int]

    source: Optional[str]

    # STORED
    # ZERO_INFERRED
    # INSUFFICIENT_DATA
    status: str


def get_effective_foreign_net(
    conn,
    stock_id: str,
    market: str,
    start_date: str,
    end_date: str,
    allow_twse_zero_inferred: bool = False,
) -> list[EffectiveForeignNet]:
    """
    取得某檔股票指定期間的 effective foreign_net。

    ------------------------------------------------------------
    TWSE
    ------------------------------------------------------------

    production / legacy 預設：

        allow_twse_zero_inferred = False

        institutional_trades 有 row
        -> STORED

        institutional row 缺失
        -> INSUFFICIENT_DATA

    Bullish v2 research 可啟用：

        allow_twse_zero_inferred = True

        institutional row 缺失，
        但：

            - 該股票當日有 TWSE daily_price
            - TWSE_T86_MARKET crawl SUCCESS

        經 2026-09-10 research 驗證：

            - 89 組 T86 missing stock/date
            - 89 組全部在官方 TWT38U 也 absent
            - 無 parser dropped
            - 無 normalized DB write missing

        因此 Bullish v2 research 可推論：

            foreign_net = 0
            status = ZERO_INFERRED

    ------------------------------------------------------------
    TPEx
    ------------------------------------------------------------

    institutional_trades 有 row
    -> 使用官方 foreign_net
    -> STORED

    institutional row 缺失，
    但：

        - 當日有 TPEx daily_price
        - TPEX_QFII_STAT crawl SUCCESS

    -> foreign_net = 0
    -> ZERO_INFERRED

    其他：

    -> INSUFFICIENT_DATA

    ------------------------------------------------------------
    Important
    ------------------------------------------------------------

    ZERO_INFERRED 只代表：

        foreign_net = 0

    絕對不能推論：

        foreign_buy = 0
        foreign_sell = 0

    ZERO_INFERRED 不會寫假 row 到 institutional_trades。
    它只存在 effective semantic layer。
    """

    if market == "TPEx":
        return _get_tpex_effective_foreign_net(
            conn=conn,
            stock_id=stock_id,
            start_date=start_date,
            end_date=end_date,
        )

    if (
        market == "TWSE"
        and allow_twse_zero_inferred
    ):
        return _get_twse_effective_foreign_net(
            conn=conn,
            stock_id=stock_id,
            start_date=start_date,
            end_date=end_date,
        )

    return _get_normal_market_foreign_net(
        conn=conn,
        stock_id=stock_id,
        market=market,
        start_date=start_date,
        end_date=end_date,
    )


def _get_normal_market_foreign_net(
    conn,
    stock_id: str,
    market: str,
    start_date: str,
    end_date: str,
) -> list[EffectiveForeignNet]:
    """
    Legacy / production semantic。

    institutional row 缺失
    -> INSUFFICIENT_DATA

    此函式保留，
    避免 Bullish v2 research
    直接改變既有 production 行為。
    """

    rows = conn.execute(
        """
        SELECT
            p.trade_date,
            i.foreign_net,
            i.source

        FROM daily_prices p

        LEFT JOIN institutional_trades i
          ON i.stock_id = p.stock_id
         AND i.market = p.market
         AND i.trade_date = p.trade_date

        WHERE
            p.stock_id = ?
            AND p.market = ?
            AND p.trade_date >= ?
            AND p.trade_date <= ?

        GROUP BY
            p.trade_date,
            i.foreign_net,
            i.source

        ORDER BY p.trade_date ASC
        """,
        (
            stock_id,
            market,
            start_date,
            end_date,
        ),
    ).fetchall()

    result: list[
        EffectiveForeignNet
    ] = []

    for row in rows:

        if row["foreign_net"] is None:

            result.append(
                EffectiveForeignNet(
                    stock_id=stock_id,
                    market=market,
                    trade_date=row[
                        "trade_date"
                    ],
                    foreign_net=None,
                    source=None,
                    status=(
                        "INSUFFICIENT_DATA"
                    ),
                )
            )

        else:

            result.append(
                EffectiveForeignNet(
                    stock_id=stock_id,
                    market=market,
                    trade_date=row[
                        "trade_date"
                    ],
                    foreign_net=int(
                        row["foreign_net"]
                    ),
                    source=row["source"],
                    status="STORED",
                )
            )

    return result


def _get_twse_effective_foreign_net(
    conn,
    stock_id: str,
    start_date: str,
    end_date: str,
) -> list[EffectiveForeignNet]:
    """
    TWSE Bullish v2 research semantic。

    使用「該股票自己的 daily_prices 日期」
    作為需要 Foreign coverage 的日期。

    優先順序：

    1. institutional_trades 有官方 row
       -> STORED

    2. institutional row 缺失
       + 股票當日有 daily_price
       + TWSE_T86_MARKET crawl SUCCESS
       -> foreign_net = 0
       -> ZERO_INFERRED

    3. 其他
       -> INSUFFICIENT_DATA

    注意：

    ZERO_INFERRED 不會寫入 normalized DB。

    foreign_buy / foreign_sell
    仍然保持 unknown。
    """

    rows = conn.execute(
        """
        WITH trading_dates AS (

            SELECT DISTINCT
                trade_date

            FROM daily_prices

            WHERE
                stock_id = ?
                AND market = 'TWSE'
                AND trade_date >= ?
                AND trade_date <= ?
        )

        SELECT
            d.trade_date,

            i.foreign_net,
            i.source,

            CASE
                WHEN EXISTS (

                    SELECT 1

                    FROM crawl_logs c

                    WHERE
                        c.source = ?
                        AND c.request_key =
                            REPLACE(
                                d.trade_date,
                                '-',
                                ''
                            )
                        AND c.status = 'SUCCESS'
                )
                THEN 1
                ELSE 0
            END AS crawl_success

        FROM trading_dates d

        LEFT JOIN institutional_trades i
          ON i.stock_id = ?
         AND i.market = 'TWSE'
         AND i.trade_date = d.trade_date

        ORDER BY
            d.trade_date ASC
        """,
        (
            stock_id,
            start_date,
            end_date,
            TWSE_FOREIGN_SOURCE,
            stock_id,
        ),
    ).fetchall()

    result: list[
        EffectiveForeignNet
    ] = []

    for row in rows:

        trade_date = row[
            "trade_date"
        ]

        stored_net = row[
            "foreign_net"
        ]

        crawl_success = bool(
            row["crawl_success"]
        )

        #
        # 第一順位：
        # normalized DB 有官方資料。
        #
        if stored_net is not None:

            result.append(
                EffectiveForeignNet(
                    stock_id=stock_id,
                    market="TWSE",
                    trade_date=(
                        trade_date
                    ),
                    foreign_net=int(
                        stored_net
                    ),
                    source=row["source"],
                    status="STORED",
                )
            )

            continue

        #
        # 第二順位：
        #
        # 此股票當日有 daily_price
        # + T86 crawl SUCCESS
        # + institutional row missing
        #
        # 2026-09-10 research：
        #
        # T86 missing = 89
        # TWT38U absent = 89
        #
        # Bullish v2 research
        # 推論 foreign_net = 0。
        #
        if crawl_success:

            result.append(
                EffectiveForeignNet(
                    stock_id=stock_id,
                    market="TWSE",
                    trade_date=(
                        trade_date
                    ),
                    foreign_net=0,
                    source=(
                        TWSE_FOREIGN_SOURCE
                    ),
                    status=(
                        "ZERO_INFERRED"
                    ),
                )
            )

            continue

        #
        # 沒有 institutional row
        # 又沒有 SUCCESS crawl 證據。
        #
        result.append(
            EffectiveForeignNet(
                stock_id=stock_id,
                market="TWSE",
                trade_date=trade_date,
                foreign_net=None,
                source=None,
                status=(
                    "INSUFFICIENT_DATA"
                ),
            )
        )

    return result


def _get_tpex_effective_foreign_net(
    conn,
    stock_id: str,
    start_date: str,
    end_date: str,
) -> list[EffectiveForeignNet]:
    """
    TPEx 專用 foreign_net semantic layer。
    """

    rows = conn.execute(
        """
        WITH trading_dates AS (

            SELECT DISTINCT
                trade_date

            FROM daily_prices

            WHERE
                stock_id = ?
                AND market = 'TPEx'
                AND trade_date >= ?
                AND trade_date <= ?
        )

        SELECT
            d.trade_date,

            i.foreign_net,
            i.source,

            CASE
                WHEN EXISTS (

                    SELECT 1

                    FROM crawl_logs c

                    WHERE
                        c.source = ?
                        AND c.request_key =
                            ? || d.trade_date
                        AND c.status =
                            'SUCCESS'
                )
                THEN 1
                ELSE 0
            END AS crawl_success

        FROM trading_dates d

        LEFT JOIN institutional_trades i
          ON i.stock_id = ?
         AND i.market = 'TPEx'
         AND i.trade_date = d.trade_date

        ORDER BY
            d.trade_date ASC
        """,
        (
            stock_id,
            start_date,
            end_date,
            TPEX_FOREIGN_SOURCE,
            TPEX_FOREIGN_SOURCE
            + ":",
            stock_id,
        ),
    ).fetchall()

    result: list[
        EffectiveForeignNet
    ] = []

    for row in rows:

        trade_date = row[
            "trade_date"
        ]

        stored_net = row[
            "foreign_net"
        ]

        crawl_success = bool(
            row["crawl_success"]
        )

        #
        # 第一順位：
        # DB 有官方 normalized row。
        #
        if stored_net is not None:

            result.append(
                EffectiveForeignNet(
                    stock_id=stock_id,
                    market="TPEx",
                    trade_date=(
                        trade_date
                    ),
                    foreign_net=int(
                        stored_net
                    ),
                    source=row["source"],
                    status="STORED",
                )
            )

            continue

        #
        # 第二順位：
        #
        # 此股票當日有日 K
        # + qfiiStat 全日 crawl SUCCESS
        # + institutional row 缺失
        #
        # 已驗證表示 foreign_net = 0。
        #
        if crawl_success:

            result.append(
                EffectiveForeignNet(
                    stock_id=stock_id,
                    market="TPEx",
                    trade_date=(
                        trade_date
                    ),
                    foreign_net=0,
                    source=(
                        TPEX_FOREIGN_SOURCE
                    ),
                    status=(
                        "ZERO_INFERRED"
                    ),
                )
            )

            continue

        #
        # 沒有 institutional row，
        # 又無 SUCCESS crawl 證據。
        #
        result.append(
            EffectiveForeignNet(
                stock_id=stock_id,
                market="TPEx",
                trade_date=(
                    trade_date
                ),
                foreign_net=None,
                source=None,
                status=(
                    "INSUFFICIENT_DATA"
                ),
            )
        )

    return result