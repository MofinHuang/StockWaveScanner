import pandas as pd

from strategy.sleep import (
    evaluate_sleep,
)
from strategy.foreign import (
    build_weekly_foreign,
    build_weekly_foreign_effective,
    evaluate_foreign,
)
from strategy.tdcc import (
    evaluate_tdcc,
)
from strategy.chip import (
    evaluate_chip,
)
from strategy.breakout import (
    evaluate_breakout,
)
from strategy.analyzer import (
    evaluate_stock,
)


TPEX_FOREIGN_SOURCE = "TPEX_QFII_STAT"


def evaluate_stock_from_data(
    stock_id: str,
    stock_name: str,
    market: str,
    price_df: pd.DataFrame,
    institutional_df: pd.DataFrame,
    tdcc_df: pd.DataFrame,
    conn=None,
    reference_date=None,
):
    """
    對單一股票執行完整三關評分。

    回傳格式適合直接組成排名 DataFrame。

    Foreign 資料來源：

    TWSE
        institutional_df
        -> build_weekly_foreign()

    TPEx
        若提供 conn：
        -> build_weekly_foreign_effective()

        這樣可以正確處理：
        - STORED
        - ZERO_INFERRED
        - INSUFFICIENT_DATA

    為維持既有相容性：
    若沒有 conn，仍使用原本 institutional_df 路徑。
    """

    # =================================
    # Sleep /30
    # =================================

    sleep_result = evaluate_sleep(
        price_df
    )

    # =================================
    # Foreign /20
    # =================================

    if (
        market == "TPEx"
        and conn is not None
    ):
        weekly_foreign = (
            build_weekly_foreign_effective(
                conn=conn,
                stock_id=stock_id,
                market=market,
                reference_date=(
                    reference_date
                ),
            )
        )

        foreign_result = (
            evaluate_foreign(
                weekly_foreign
            )
        )

    else:
        if institutional_df.empty:
            foreign_result = {
                "status":
                    "INSUFFICIENT_DATA",

                "passed":
                    False,

                "score":
                    0,

                "reason":
                    "沒有外資歷史資料",
            }

        else:
            foreign_df = (
                institutional_df
                .copy()
            )

            foreign_df[
                "trade_date"
            ] = pd.to_datetime(
                foreign_df[
                    "trade_date"
                ],
                errors="coerce",
            )

            weekly_foreign = (
                build_weekly_foreign(
                    foreign_df,
                    reference_date=(
                        reference_date
                    ),
                )
            )

            foreign_result = (
                evaluate_foreign(
                    weekly_foreign
                )
            )

    # =================================
    # TDCC /20
    # =================================

    tdcc_result = evaluate_tdcc(
        tdcc_df,
        required_weeks=4,
    )

    # =================================
    # Chip /40
    # =================================

    chip_result = evaluate_chip(
        foreign_result=(
            foreign_result
        ),
        tdcc_result=(
            tdcc_result
        ),
    )

    # =================================
    # Breakout /30
    # =================================

    breakout_result = (
        evaluate_breakout(
            price_df
        )
    )

    # =================================
    # Total /100
    # =================================

    total_result = evaluate_stock(
        sleep_result=(
            sleep_result
        ),
        chip_result=(
            chip_result
        ),
        breakout_result=(
            breakout_result
        ),
    )

    return {
        "stock_id":
            stock_id,

        "stock_name":
            stock_name,

        "market":
            market,

        "sleep_score":
            sleep_result[
                "score"
            ],

        "sleep_status":
            sleep_result[
                "status"
            ],

        "foreign_score":
            foreign_result.get(
                "score",
                0,
            ),

        "foreign_status":
            foreign_result.get(
                "status",
                "INSUFFICIENT_DATA",
            ),

        "tdcc_score":
            tdcc_result[
                "score"
            ],

        "tdcc_status":
            tdcc_result[
                "status"
            ],

        "chip_score":
            chip_result[
                "score"
            ],

        "chip_status":
            chip_result[
                "status"
            ],

        "breakout_score":
            breakout_result[
                "score"
            ],

        "breakout_status":
            breakout_result[
                "status"
            ],

        "total_score":
            total_result[
                "score"
            ],

        "status":
            total_result[
                "status"
            ],

        "reason":
            total_result[
                "reason"
            ],
    }


def _get_ranking_reference_date(
    conn,
    as_of_date=None,
):
    """
    Ranking 使用資料庫中最新的市場日 K 日期，
    不直接使用 date.today()。

    這樣：
    - 週末
    - 假日
    - DB 尚未同步到今天

    都不會讓 Foreign 完整週判斷飄動。
    """
    if as_of_date is None:
        row = conn.execute(
            """
            SELECT MAX(trade_date) AS trade_date
            FROM daily_prices
            """
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT MAX(trade_date) AS trade_date
            FROM daily_prices
            WHERE trade_date <= ?
            """,
            (str(as_of_date),),
        ).fetchone()

    if (
        row is None
        or not row["trade_date"]
    ):
        return None

    return str(
        row["trade_date"]
    )


def build_ranking(
    conn,
    as_of_date=None,
):
    """
    從資料庫讀取 active stocks，
    執行完整三關 Analyzer，
    產生排名 DataFrame。

    Data-complete 初步篩選：

    1. active stock
    2. daily_prices >= 30
    3. Foreign：
       - TWSE 必須已有 institutional row
       - TPEx 只要已有成功的 qfiiStat crawl
         即可進 effective Foreign 判定
    4. TDCC >= 4 個 distinct data_date

    TPEx 不再硬性要求：
        institutional_trades EXISTS

    原因：
    TPEx 某股票可能 foreign_net 全為 0，
    官方 qfiiStat 不一定會留下 normalized row，
    但在 crawl SUCCESS 時仍可由
    ZERO_INFERRED 正確判定 foreign_net=0。
    """

    reference_date = (
        _get_ranking_reference_date(
            conn,
            as_of_date=as_of_date,
        )
    )

    stocks = pd.read_sql_query(
        """
        SELECT
            s.stock_id,
            s.stock_name,
            s.market

        FROM stocks s

        WHERE
            s.is_active = 1

            AND (
                SELECT COUNT(*)

                FROM daily_prices dp

                WHERE
                    dp.stock_id = s.stock_id
                    AND dp.market = s.market
                    AND dp.trade_date <= ?
            ) >= 30

            AND (
                (
                    s.market = 'TWSE'

                    AND EXISTS (
                        SELECT 1

                        FROM institutional_trades it

                        WHERE
                            it.stock_id = s.stock_id
                            AND it.market = s.market
                            AND it.trade_date <= ?
                    )
                )

                OR

                (
                    s.market = 'TPEx'

                    AND EXISTS (
                        SELECT 1

                        FROM crawl_logs cl

                        WHERE
                            cl.source = ?
                            AND cl.status = 'SUCCESS'
                            AND cl.request_key <= ?
                    )
                )
            )

            AND (
                SELECT COUNT(
                    DISTINCT th.data_date
                )

                FROM tdcc_holdings th

                WHERE
                    th.stock_id = s.stock_id
                    AND th.data_date <= ?
            ) >= 4

        ORDER BY
            s.market,
            s.stock_id
        """,
        conn,
        params=(
            reference_date,
            reference_date,
            TPEX_FOREIGN_SOURCE,
            f"{TPEX_FOREIGN_SOURCE}:{reference_date}",
            reference_date,
        ),
    )

    if stocks.empty:
        return pd.DataFrame()

    results = []

    for _, stock in stocks.iterrows():
        stock_id = str(
            stock["stock_id"]
        )

        stock_name = str(
            stock["stock_name"]
        )

        market = str(
            stock["market"]
        )

        # =================================
        # 日K
        # =================================

        price_df = pd.read_sql_query(
            """
            SELECT
                trade_date,
                open,
                high,
                low,
                close,
                volume

            FROM daily_prices

            WHERE
                stock_id = ?
                AND market = ?
                AND trade_date <= ?

            ORDER BY trade_date ASC
            """,
            conn,
            params=(
                stock_id,
                market,
                reference_date,
            ),
        )

        # =================================
        # 外資
        #
        # TWSE：
        # 正式直接使用這份 DataFrame。
        #
        # TPEx：
        # evaluate_stock_from_data()
        # 會改走 effective-data builder。
        #
        # 仍保留 institutional_df，
        # 以維持既有函式介面。
        # =================================

        institutional_df = (
            pd.read_sql_query(
                """
                SELECT
                    trade_date,
                    foreign_buy,
                    foreign_sell,
                    foreign_net

                FROM institutional_trades

                WHERE
                    stock_id = ?
                    AND market = ?
                    AND trade_date <= ?

                ORDER BY trade_date ASC
                """,
                conn,
                params=(
                    stock_id,
                    market,
                    reference_date,
                ),
            )
        )

        # =================================
        # TDCC
        # =================================

        tdcc_df = pd.read_sql_query(
            """
            SELECT
                data_date,
                large_holder_pct,
                retail_holder_pct

            FROM tdcc_holdings

            WHERE stock_id = ?
              AND data_date <= ?

            ORDER BY data_date ASC
            """,
            conn,
            params=(
                stock_id,
                reference_date,
            ),
        )

        result = (
            evaluate_stock_from_data(
                stock_id=stock_id,
                stock_name=stock_name,
                market=market,
                price_df=price_df,
                institutional_df=(
                    institutional_df
                ),
                tdcc_df=tdcc_df,
                conn=conn,
                reference_date=(
                    reference_date
                ),
            )
        )

        results.append(
            result
        )

    ranking = pd.DataFrame(
        results
    )

    if ranking.empty:
        return ranking

    # =================================
    # 排名
    #
    # 先以總分排序。
    #
    # 同分：
    # Chip > Sleep > Breakout
    # =================================

    ranking = (
        ranking
        .sort_values(
            by=[
                "total_score",
                "chip_score",
                "sleep_score",
                "breakout_score",
                "stock_id",
            ],
            ascending=[
                False,
                False,
                False,
                False,
                True,
            ],
        )
        .reset_index(
            drop=True
        )
    )

    ranking.insert(
        0,
        "rank",
        range(
            1,
            len(ranking) + 1,
        ),
    )

    return ranking