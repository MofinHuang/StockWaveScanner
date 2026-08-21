import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

from config import DATABASE_PATH

from db.database import (
    get_connection,
)

from crawler.tdcc import (
    parse_tdcc_rows,
)

from strategy.foreign import (
    build_weekly_foreign,
    evaluate_foreign,
)

from strategy.tdcc import (
    evaluate_tdcc,
)

from strategy.chip import (
    evaluate_chip,
)

from strategy.sleep import (
    evaluate_sleep,
)

from strategy.breakout import (
    evaluate_breakout,
)

from strategy.analyzer import (
    evaluate_stock,
)

from strategy.ranking import (
    build_ranking,
)

st.set_page_config(
    page_title="台股波段掃描器",
    page_icon="📈",
    layout="wide",
)


st.title(
    "📈 台股波段三關掃描器"
)

st.caption(
    "上市 + 上櫃｜沉睡 → 籌碼 → 突破"
)


# =====================================
# 共用資料
# =====================================

conn = get_connection()

stocks_df = pd.read_sql_query(
    """
    SELECT
        stock_id,
        stock_name,
        market,
        is_active
    FROM stocks
    ORDER BY
        market,
        stock_id
    """,
    conn,
)


analysis_df = pd.read_sql_query(
    """
    SELECT
        stock_id,
        market,
        analysis_date,

        sleep_pass,
        chip_pass,
        breakout_pass,

        sleep_score,
        chip_score,
        breakout_score,

        total_score,
        signal

    FROM analysis_results

    WHERE analysis_date =
    (
        SELECT MAX(analysis_date)
        FROM analysis_results
    )

    ORDER BY total_score DESC

    LIMIT 10
    """,
    conn,
)


conn.close()


# =====================================
# UI
# =====================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "🔥 今日 Top 10",
        "📋 股票主檔",
        "🔎 日K資料驗證",
        "💰 外資資料",
        "🏦 TDCC資料",
        "⚙️ 爬蟲紀錄",
    ]
)


# =====================================
# Top 10
# =====================================

with tab1:

    st.header(
        "🏆 StockWaveScanner Top 10"
    )

    st.caption(
        "Sleep /30 + Chip /40 + "
        "Breakout /30 = 100 分"
    )

    # =================================
    # Top 10 專用 DB Connection
    # =================================

    ranking_conn = get_connection()

    try:

        ranking_df = build_ranking(
            ranking_conn
        )
        
        st.caption(
            f"目前可完整評分股票："
            f"{len(ranking_df):,} 檔"
        )

    finally:

        ranking_conn.close()

    # =================================
    # Ranking UI
    # =================================

    if ranking_df.empty:

        st.warning(
            "目前沒有可評分股票"
        )

    else:

        top10_df = (
            ranking_df
            .head(10)
            .copy()
        )

        display_df = (
            top10_df[
                [
                    "rank",
                    "stock_id",
                    "stock_name",
                    "market",
                    "sleep_score",
                    "chip_score",
                    "breakout_score",
                    "total_score",
                    "status",
                ]
            ]
            .rename(
                columns={
                    "rank":
                        "排名",

                    "stock_id":
                        "代號",

                    "stock_name":
                        "名稱",

                    "market":
                        "市場",

                    "sleep_score":
                        "Sleep /30",

                    "chip_score":
                        "Chip /40",

                    "breakout_score":
                        "Breakout /30",

                    "total_score":
                        "總分 /100",

                    "status":
                        "狀態",
                }
            )
        )

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )

        leader = (
            top10_df.iloc[0]
        )

        st.divider()

        st.subheader(
            "目前最高分"
        )

        leader_col1, leader_col2 = (
            st.columns(2)
        )

        with leader_col1:

            st.metric(
                "股票",
                (
                    f"{leader['stock_id']} "
                    f"{leader['stock_name']}"
                ),
            )

        with leader_col2:

            st.metric(
                "總分",
                (
                    f"{leader['total_score']} "
                    "/ 100"
                ),
            )

        st.write(
            "狀態："
            f"{leader['status']}"
        )

        st.write(
            "原因："
            f"{leader['reason']}"
        )

        st.divider()

        st.subheader(
            "完整評分明細"
        )

        detail_df = (
            ranking_df[
                [
                    "rank",
                    "stock_id",
                    "stock_name",
                    "sleep_score",
                    "sleep_status",
                    "foreign_score",
                    "foreign_status",
                    "tdcc_score",
                    "tdcc_status",
                    "chip_score",
                    "chip_status",
                    "breakout_score",
                    "breakout_status",
                    "total_score",
                    "status",
                ]
            ]
            .rename(
                columns={
                    "rank":
                        "排名",

                    "stock_id":
                        "代號",

                    "stock_name":
                        "名稱",

                    "sleep_score":
                        "Sleep",

                    "sleep_status":
                        "Sleep狀態",

                    "foreign_score":
                        "外資",

                    "foreign_status":
                        "外資狀態",

                    "tdcc_score":
                        "TDCC",

                    "tdcc_status":
                        "TDCC狀態",

                    "chip_score":
                        "Chip",

                    "chip_status":
                        "Chip狀態",

                    "breakout_score":
                        "Breakout",

                    "breakout_status":
                        "Breakout狀態",

                    "total_score":
                        "總分",

                    "status":
                        "最終狀態",
                }
            )
        )

        st.dataframe(
            detail_df,
            use_container_width=True,
            hide_index=True,
        )


# =====================================
# 股票主檔
# =====================================

with tab2:

    st.subheader(
        "目前股票主檔"
    )

    st.write(
        f"共 {len(stocks_df)} 檔"
    )

    if stocks_df.empty:

        st.warning(
            "股票主檔目前沒有資料。"
        )

    else:

        st.dataframe(
            stocks_df,
            use_container_width=True,
            hide_index=True,
        )


# =====================================
# 日K資料驗證
# =====================================

with tab3:

    st.subheader(
        "日K資料驗證"
    )

    conn = get_connection()

    stocks = pd.read_sql_query(
        """
        SELECT
            stock_id,
            stock_name,
            market
        FROM stocks
        ORDER BY stock_id
        """,
        conn,
    )

    if stocks.empty:

        st.warning(
            "目前沒有股票。"
        )

    else:

        options = {
            (
                f"{row['stock_id']} "
                f"{row['stock_name']} "
                f"[{row['market']}]"
            ):
            (
                row["stock_id"],
                row["market"],
            )

            for _, row
            in stocks.iterrows()
        }

        selected_label = st.selectbox(
            "選擇股票",
            options.keys(),
        )

        selected_stock, selected_market = (
            options[selected_label]
        )

        prices = pd.read_sql_query(
            """
            SELECT
                trade_date,
                open,
                high,
                low,
                close,
                volume,
                source,
                downloaded_at

            FROM daily_prices

            WHERE
                stock_id = ?
                AND market = ?

            ORDER BY trade_date DESC

            LIMIT 30
            """,
            conn,
            params=(
                selected_stock,
                selected_market,
            ),
        )

        st.write(
            f"最近 {len(prices)} 筆"
        )

        st.dataframe(
            prices,
            use_container_width=True,
            hide_index=True,
        )

        # =================================
        # 第一關：Sleep Analyzer / 30
        # =================================

        st.divider()

        st.subheader(
            "第一關｜Sleep Analyzer"
        )

        sleep_result = evaluate_sleep(
            prices
        )

        if (
            sleep_result["status"]
            == "PASS"
        ):
            st.success(
                "✅ 第一關 PASS"
            )

        elif (
            sleep_result["status"]
            == "INSUFFICIENT_DATA"
        ):
            st.warning(
                "⚠️ 第一關 INSUFFICIENT_DATA"
            )

        else:
            st.error(
                "❌ 第一關 FAIL"
            )

        st.metric(
            "Sleep 分數",
            (
                f"{sleep_result['score']} "
                f"/ {sleep_result['max_score']}"
            ),
        )

        # -----------------------------
        # 子條件
        # -----------------------------

        if sleep_result["conditions"]:

            cols = st.columns(3)

            for index, condition in enumerate(
                sleep_result["conditions"]
            ):

                with cols[index]:

                    st.write(
                        condition["name"]
                    )

                    if condition["passed"]:

                        st.success(
                            "✅ "
                            f"{condition['score']} / "
                            f"{condition['max_score']}"
                        )

                    else:

                        st.error(
                            "❌ "
                            f"{condition['score']} / "
                            f"{condition['max_score']}"
                        )

        # -----------------------------
        # 指標
        # -----------------------------

        metrics = sleep_result[
            "metrics"
        ]

        if metrics:

            st.subheader(
                "Sleep 指標"
            )

            metric_col1, metric_col2 = (
                st.columns(2)
            )

            with metric_col1:

                st.metric(
                    "最新收盤",
                    (
                        f"{metrics['latest_close']:.2f}"
                    ),
                )

                st.metric(
                    "MA20",
                    f"{metrics['ma']:.2f}",
                )

                st.metric(
                    "距 MA20",
                    (
                        f"{metrics['ma_distance_pct'] * 100:.2f}%"
                    ),
                )

            with metric_col2:

                if (
                    metrics[
                        "volatility_ratio"
                    ]
                    is not None
                ):

                    st.metric(
                        "波動比",
                        (
                            f"{metrics['volatility_ratio']:.2f}"
                        ),
                    )

                if (
                    metrics[
                        "volume_ratio"
                    ]
                    is not None
                ):

                    st.metric(
                        "量能比",
                        (
                            f"{metrics['volume_ratio']:.2f}"
                        ),
                    )

        st.write(
            "判斷原因："
            f"{sleep_result['reason']}"
        )

        st.caption(
            "Sleep v1："
            "收盤距 MA20 ≤ 5%；"
            "最近 10 日平均振幅 ≤ "
            "前 20 日平均振幅 × 0.80；"
            "最近 10 日平均量 ≤ "
            "前 20 日平均量 × 0.80。"
        )

        # =================================
        # 第三關：Breakout Analyzer / 30
        # =================================

        st.divider()

        st.subheader(
            "第三關｜Breakout Analyzer"
        )

        breakout_result = (
            evaluate_breakout(
                prices
            )
        )

        if (
            breakout_result["status"]
            == "PASS"
        ):

            st.success(
                "✅ 第三關 PASS"
            )

        elif (
            breakout_result["status"]
            == "INSUFFICIENT_DATA"
        ):

            st.warning(
                "⚠️ 第三關 "
                "INSUFFICIENT_DATA"
            )

        else:

            st.error(
                "❌ 第三關 FAIL"
            )

        st.metric(
            "Breakout 分數",
            (
                f"{breakout_result['score']} "
                f"/ "
                f"{breakout_result['max_score']}"
            ),
        )

        # =================================
        # 子條件
        # =================================

        if breakout_result[
            "conditions"
        ]:

            breakout_cols = (
                st.columns(3)
            )

            for index, condition in enumerate(
                breakout_result[
                    "conditions"
                ]
            ):

                with breakout_cols[
                    index
                ]:

                    st.write(
                        condition["name"]
                    )

                    if condition[
                        "passed"
                    ]:

                        st.success(
                            "✅ "
                            f"{condition['score']} / "
                            f"{condition['max_score']}"
                        )

                    else:

                        st.error(
                            "❌ "
                            f"{condition['score']} / "
                            f"{condition['max_score']}"
                        )

        # =================================
        # 指標
        # =================================

        breakout_metrics = (
            breakout_result[
                "metrics"
            ]
        )

        if breakout_metrics:

            st.subheader(
                "Breakout 指標"
            )

            bcol1, bcol2 = (
                st.columns(2)
            )

            with bcol1:

                st.metric(
                    "最新收盤",
                    (
                        f"{breakout_metrics['latest_close']:.2f}"
                    ),
                )

                st.metric(
                    "前 20 日最高",
                    (
                        f"{breakout_metrics['previous_high']:.2f}"
                    ),
                )

                if (
                    breakout_metrics[
                        "breakout_pct"
                    ]
                    is not None
                ):

                    st.metric(
                        "突破幅度",
                        (
                            f"{breakout_metrics['breakout_pct'] * 100:.2f}%"
                        ),
                    )

            with bcol2:

                if (
                    breakout_metrics[
                        "volume_ratio"
                    ]
                    is not None
                ):

                    st.metric(
                        "量能倍數",
                        (
                            f"{breakout_metrics['volume_ratio']:.2f}x"
                        ),
                    )

                if (
                    breakout_metrics[
                        "close_from_high_ratio"
                    ]
                    is not None
                ):

                    st.metric(
                        "收盤距當日高點",
                        (
                            f"{breakout_metrics['close_from_high_ratio'] * 100:.2f}%"
                        ),
                    )

        st.write(
            "判斷原因："
            f"{breakout_result['reason']}"
        )

        st.caption(
            "Breakout v1："
            "最新收盤需突破前 20 日最高價；"
            "成交量需達前 20 日平均量 1.5 倍以上；"
            "收盤需位於當日 K 棒上緣 25% 內。"
        )


        # =================================
        # 三關總整合 / 100
        # =================================

        st.divider()

        st.subheader(
            "三關總評｜Stock Analyzer"
        )

        # =================================
        # 外資
        # =================================

        analyzer_foreign_df = (
            pd.read_sql_query(
                """
                SELECT
                    trade_date,
                    foreign_buy,
                    foreign_sell,
                    foreign_net

                FROM institutional_trades

                WHERE stock_id = ?

                ORDER BY trade_date ASC
                """,
                conn,
                params=(
                    selected_stock,
                ),
            )
        )

        if analyzer_foreign_df.empty:

            analyzer_foreign_result = {
                "status":
                    "INSUFFICIENT_DATA",

                "score":
                    0,

                "reason":
                    "沒有外資歷史資料",
            }

        else:

            analyzer_foreign_df[
                "trade_date"
            ] = pd.to_datetime(
                analyzer_foreign_df[
                    "trade_date"
                ],
                errors="coerce",
            )

            analyzer_weekly_foreign = (
                build_weekly_foreign(
                    analyzer_foreign_df
                )
            )

            analyzer_foreign_result = (
                evaluate_foreign(
                    analyzer_weekly_foreign
                )
            )

        # =================================
        # TDCC
        # =================================

        analyzer_tdcc_df = (
            pd.read_sql_query(
                """
                SELECT
                    data_date,
                    large_holder_pct,
                    retail_holder_pct

                FROM tdcc_holdings

                WHERE stock_id = ?

                ORDER BY data_date ASC
                """,
                conn,
                params=(
                    selected_stock,
                ),
            )
        )

        analyzer_tdcc_result = (
            evaluate_tdcc(
                analyzer_tdcc_df,
                required_weeks=4,
            )
        )

        # =================================
        # Chip /40
        # =================================

        analyzer_chip_result = (
            evaluate_chip(
                foreign_result=(
                    analyzer_foreign_result
                ),
                tdcc_result=(
                    analyzer_tdcc_result
                ),
            )
        )

        # =================================
        # Total /100
        # =================================

        analyzer_result = evaluate_stock(
            sleep_result=(
                sleep_result
            ),
            chip_result=(
                analyzer_chip_result
            ),
            breakout_result=(
                breakout_result
            ),
        )

        # =================================
        # Status
        # =================================

        if (
            analyzer_result["status"]
            == "PASS"
        ):

            st.success(
                "✅ 三關全部通過"
            )

        elif (
            analyzer_result["status"]
            == "INSUFFICIENT_DATA"
        ):

            st.warning(
                "⚠️ INSUFFICIENT_DATA"
            )

        else:

            st.error(
                "❌ 三關未全部通過"
            )

        # =================================
        # Total Score
        # =================================

        st.metric(
            "總分",
            (
                f"{analyzer_result['score']} "
                f"/ "
                f"{analyzer_result['max_score']}"
            ),
        )

        # =================================
        # 三關拆解
        # =================================

        total_col1, total_col2, total_col3 = (
            st.columns(3)
        )

        with total_col1:

            st.metric(
                "Sleep",
                (
                    f"{analyzer_result['sleep_score']}"
                    " / 30"
                ),
            )

            st.write(
                "狀態："
                f"{analyzer_result['sleep_status']}"
            )

        with total_col2:

            st.metric(
                "Chip",
                (
                    f"{analyzer_result['chip_score']}"
                    " / 40"
                ),
            )

            st.write(
                "狀態："
                f"{analyzer_result['chip_status']}"
            )

        with total_col3:

            st.metric(
                "Breakout",
                (
                    f"{analyzer_result['breakout_score']}"
                    " / 30"
                ),
            )

            st.write(
                "狀態："
                f"{analyzer_result['breakout_status']}"
            )

        st.write(
            "最終判斷："
            f"{analyzer_result['reason']}"
        )

        st.caption(
            "總分 = Sleep 30 + Chip 40 + Breakout 30。"
            "目前最終 PASS 採三關全部通過制，"
            "不是單純以總分門檻判斷。"
        )

    conn.close()


# =====================================
# 外資資料
# =====================================

with tab4:

    st.subheader(
        "外資買賣超"
    )

    conn = get_connection()

    stocks = pd.read_sql_query(
        """
        SELECT
            stock_id,
            stock_name,
            market
        FROM stocks
        WHERE is_active = 1
        ORDER BY
            market,
            stock_id
        """,
        conn,
    )

    if stocks.empty:

        st.warning(
            "目前沒有可用股票。"
        )

    else:

        options = {
            (
                f"{row['stock_id']} "
                f"{row['stock_name']} "
                f"[{row['market']}]"
            ):
            (
                row["stock_id"],
                row["market"],
            )

            for _, row
            in stocks.iterrows()
        }

        selected_label = st.selectbox(
            "選擇股票",
            options.keys(),
            key="institutional_stock",
        )

        selected_stock, selected_market = (
            options[selected_label]
        )

        institutional = pd.read_sql_query(
            """
            SELECT
                trade_date,
                foreign_buy,
                foreign_sell,
                foreign_net,
                source,
                downloaded_at

            FROM institutional_trades

            WHERE
                stock_id = ?
                AND market = ?

            ORDER BY trade_date DESC

            LIMIT 120
            """,
            conn,
            params=(
                selected_stock,
                selected_market,
            ),
        )

        conn.close()

        st.caption(
            f"{selected_stock} "
            f"[{selected_market}]"
        )

        st.subheader(
            "每日外資資料"
        )

        if institutional.empty:

            st.warning(
                "目前沒有法人資料。"
            )

        else:

            st.write(
                f"目前讀取 {len(institutional)} 筆"
            )

            st.dataframe(
                institutional.head(30),
                use_container_width=True,
                hide_index=True,
            )

            weekly = build_weekly_foreign(
                institutional,
                reference_date=date.today(),
            )

            st.divider()

            st.subheader(
                "完整週外資買賣超"
            )

            st.caption(
                "目前所在的未完成週不會納入計算。"
            )

            if weekly.empty:

                st.warning(
                    "目前沒有足夠的完整週資料。"
                )

            else:

                weekly_display = (
                    weekly
                    .tail(8)
                    .sort_values(
                        "week_start",
                        ascending=False,
                    )
                    .copy()
                )

                st.dataframe(
                    weekly_display,
                    use_container_width=True,
                    hide_index=True,
                )

                st.subheader(
                    "最近 3 個完整週"
                )

                recent_three = (
                    weekly
                    .tail(3)
                    .copy()
                )

                if len(recent_three) < 3:

                    st.warning(
                        "完整週資料不足 3 週。"
                    )

                else:

                    st.dataframe(
                        recent_three[
                            [
                                "week_start",
                                "week_end",
                                "foreign_buy",
                                "foreign_sell",
                                "foreign_net",
                                "trading_days",
                            ]
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )

                st.divider()

                st.subheader(
                    "外資布局判斷"
                )

                result = evaluate_foreign(
                    weekly,
                    required_weeks=3,
                    max_jump_ratio=2.5,
                )

                if result["status"] == "PASS":

                    st.success(
                        "✅ PASS"
                    )

                elif (
                    result["status"]
                    == "INSUFFICIENT_DATA"
                ):

                    st.warning(
                        "⚠️ INSUFFICIENT_DATA"
                    )

                else:

                    st.error(
                        "❌ FAIL"
                    )

                st.metric(
                    "外資分數",
                    f"{result['score']} / 20"
                )

                col1, col2, col3 = st.columns(3)

                with col1:

                    st.write(
                        "連續買超"
                    )

                    st.write(
                        "✅ 10 / 10"
                        if result["all_positive"]
                        else "❌ 0 / 10"
                    )

                with col2:

                    st.write(
                        "逐週增加"
                    )

                    st.write(
                        "✅ 5 / 5"
                        if result["growing"]
                        else "❌ 0 / 5"
                    )

                with col3:

                    st.write(
                        "增幅穩定"
                    )

                    st.write(
                        "✅ 5 / 5"
                        if result["stable"]
                        else "❌ 0 / 5"
                    )

                if result["weeks"]:

                    strategy_weeks = pd.DataFrame(
                        result["weeks"]
                    )

                    strategy_weeks[
                        "ratio_to_previous"
                    ] = (
                        strategy_weeks[
                            "ratio_to_previous"
                        ]
                        .apply(
                            lambda value:
                            None
                            if pd.isna(value)
                            else round(value, 2)
                        )
                    )

                    st.subheader(
                        "策略使用的最近 3 個完整週"
                    )

                    st.dataframe(
                        strategy_weeks,
                        use_container_width=True,
                        hide_index=True,
                    )

                st.write(
                    result["reason"]
                )


# =====================================
# TDCC 資料
# =====================================

with tab5:

    st.subheader(
        "TDCC 集保戶股權分散資料"
    )

    conn = get_connection()

    active_stocks = pd.read_sql_query(
        """
        SELECT
            stock_id,
            stock_name,
            market

        FROM stocks

        WHERE is_active = 1

        ORDER BY
            market,
            stock_id
        """,
        conn,
    )

    if active_stocks.empty:

        st.warning(
            "目前沒有可用股票。"
        )

        conn.close()

    else:

        tdcc_options = {
            (
                f"{row['stock_id']} "
                f"{row['stock_name']} "
                f"[{row['market']}]"
            ):
            row["stock_id"]

            for _, row
            in active_stocks.iterrows()
        }

        selected_tdcc_label = st.selectbox(
            "選擇股票",
            tdcc_options.keys(),
            key="tdcc_stock",
        )

        selected_tdcc_stock = (
            tdcc_options[
                selected_tdcc_label
            ]
        )


        # =================================
        # 正規化 TDCC 摘要
        # =================================

        tdcc_summary = pd.read_sql_query(
            """
            SELECT
                data_date,
                large_holder_pct,
                retail_holder_pct,
                source,
                downloaded_at

            FROM tdcc_holdings

            WHERE stock_id = ?

            ORDER BY data_date DESC

            LIMIT 12
            """,
            conn,
            params=(
                selected_tdcc_stock,
            ),
        )


        if tdcc_summary.empty:

            st.warning(
                "目前沒有 TDCC 正規化資料。"
            )

            st.code(
                "python -m scripts.sync_tdcc"
            )

        else:

            latest = (
                tdcc_summary.iloc[0]
            )

            latest_date = (
                latest["data_date"]
            )

            large_holder_pct = float(
                latest[
                    "large_holder_pct"
                ]
            )

            retail_holder_pct = float(
                latest[
                    "retail_holder_pct"
                ]
            )

            st.caption(
                f"最新資料日期：{latest_date}"
            )

            col1, col2 = st.columns(2)

            with col1:

                st.metric(
                    "🏦 大戶持股比例",
                    f"{large_holder_pct:.2f} %",
                    help=(
                        "目前定義："
                        "持股 1,000,001 股以上"
                    ),
                )

            with col2:

                st.metric(
                    "👤 散戶持股比例",
                    f"{retail_holder_pct:.2f} %",
                    help=(
                        "目前定義："
                        "持股 1～5,000 股"
                    ),
                )

            st.caption(
                "大戶：TDCC level 15｜"
                "散戶：TDCC level 1 + level 2"
            )

            st.subheader(
                "TDCC 歷史摘要"
            )

            history_display = (
                tdcc_summary.rename(
                    columns={
                        "data_date":
                            "資料日期",

                        "large_holder_pct":
                            "大戶持股比例%",

                        "retail_holder_pct":
                            "散戶持股比例%",

                        "source":
                            "資料來源",

                        "downloaded_at":
                            "下載時間",
                    }
                )
            )

            st.dataframe(
                history_display,
                use_container_width=True,
                hide_index=True,
            )

        # =================================
        # TDCC 4 週策略判斷
        # =================================

        st.divider()

        st.subheader(
            "TDCC 最近 4 週籌碼判斷【新版 UI】"
        )

        tdcc_result = evaluate_tdcc(
            tdcc_summary,
            required_weeks=4,
        )

        if (
            tdcc_result["status"]
            == "PASS"
        ):

            st.success(
                "✅ PASS"
            )

        elif (
            tdcc_result["status"]
            == "INSUFFICIENT_DATA"
        ):

            st.warning(
                "⚠️ INSUFFICIENT_DATA"
            )

        else:

            st.error(
                "❌ FAIL"
            )

        st.metric(
            "TDCC 分數",
            f"{tdcc_result['score']} / 20",
        )

        col1, col2 = st.columns(2)

        with col1:

            st.write(
                "🏦 大戶連續增加"
            )

            if tdcc_result[
                "large_holder_growing"
            ]:

                st.success(
                    "✅ 10 / 10"
                )

            else:

                st.error(
                    "❌ 0 / 10"
                )

        with col2:

            st.write(
                "👤 散戶連續下降"
            )

            if tdcc_result[
                "retail_holder_falling"
            ]:

                st.success(
                    "✅ 10 / 10"
                )

            else:

                st.error(
                    "❌ 0 / 10"
                )

        if tdcc_result["weeks"]:

            strategy_df = pd.DataFrame(
                tdcc_result["weeks"]
            )

            strategy_df[
                "large_holder_pct"
            ] = (
                strategy_df[
                    "large_holder_pct"
                ]
                .round(2)
            )

            strategy_df[
                "retail_holder_pct"
            ] = (
                strategy_df[
                    "retail_holder_pct"
                ]
                .round(2)
            )

            strategy_df[
                "large_change"
            ] = (
                strategy_df[
                    "large_change"
                ]
                .round(2)
            )

            strategy_df[
                "retail_change"
            ] = (
                strategy_df[
                    "retail_change"
                ]
                .round(2)
            )

            strategy_df = (
                strategy_df.rename(
                    columns={
                        "data_date":
                            "資料日期",

                        "large_holder_pct":
                            "大戶比例%",

                        "large_change":
                            "大戶週變化",

                        "retail_holder_pct":
                            "散戶比例%",

                        "retail_change":
                            "散戶週變化",
                    }
                )
            )

            st.subheader(
                "策略使用的最近 4 週"
            )

            st.dataframe(
                strategy_df,
                use_container_width=True,
                hide_index=True,
            )

        st.caption(
            "規則：最近 4 週大戶持股比例"
            "需逐週增加；散戶持股比例"
            "需逐週下降。"
        )

        st.write(
            tdcc_result["reason"]
        )
    
        # =================================
        # 第二關：Chip Analyzer / 40
        # =================================

        st.divider()

        st.subheader(
            "第二關｜籌碼面 Chip Analyzer"
        )

        # -----------------------------
        # 讀取同一檔股票的外資資料
        # -----------------------------

        chip_foreign_df = pd.read_sql_query(
            """
            SELECT
                trade_date,
                foreign_buy,
                foreign_sell,
                foreign_net

            FROM institutional_trades

            WHERE stock_id = ?

            ORDER BY trade_date ASC
            """,
            conn,
            params=(
                selected_tdcc_stock,
            ),
        )

        if chip_foreign_df.empty:

            chip_foreign_result = {
                "status":
                    "INSUFFICIENT_DATA",

                "score":
                    0,

                "reason":
                    "沒有外資歷史資料",
            }

        else:

            chip_foreign_df[
                "trade_date"
            ] = pd.to_datetime(
                chip_foreign_df[
                    "trade_date"
                ],
                errors="coerce",
            )

            chip_weekly_foreign = (
                build_weekly_foreign(
                    chip_foreign_df
                )
            )

            chip_foreign_result = (
                evaluate_foreign(
                    chip_weekly_foreign
                )
            )

        # -----------------------------
        # TDCC 已經在上方算好
        # -----------------------------

        chip_result = evaluate_chip(
            foreign_result=(
                chip_foreign_result
            ),
            tdcc_result=(
                tdcc_result
            ),
        )

        # -----------------------------
        # 第二關狀態
        # -----------------------------

        if (
            chip_result["status"]
            == "PASS"
        ):

            st.success(
                "✅ 第二關 PASS"
            )

        elif (
            chip_result["status"]
            == "INSUFFICIENT_DATA"
        ):

            st.warning(
                "⚠️ 第二關 "
                "INSUFFICIENT_DATA"
            )

        else:

            st.error(
                "❌ 第二關 FAIL"
            )

        st.metric(
            "籌碼面總分",
            f"{chip_result['score']} / 40",
        )

        # -----------------------------
        # 分數拆解
        # -----------------------------

        chip_col1, chip_col2 = (
            st.columns(2)
        )

        with chip_col1:

            st.metric(
                "外資",
                (
                    f"{chip_result['foreign_score']}"
                    " / 20"
                ),
            )

            st.caption(
                "最近 3 個完整週"
            )

            st.write(
                "狀態："
                f"{chip_result['foreign_status']}"
            )

        with chip_col2:

            st.metric(
                "TDCC",
                (
                    f"{chip_result['tdcc_score']}"
                    " / 20"
                ),
            )

            st.caption(
                "最近 4 週"
            )

            st.write(
                "狀態："
                f"{chip_result['tdcc_status']}"
            )

        st.write(
            "判斷原因："
            f"{chip_result['reason']}"
        )
            
        # =================================
        # Raw Response 分級驗證
        # =================================

        st.divider()

        st.subheader(
            "TDCC 原始分級資料驗證"
        )

        st.caption(
            "以下保留 LV1～17，"
            "用來人工核對上方大戶 / 散戶摘要。"
        )

        raw_row = conn.execute(
            """
            SELECT
                request_key,
                content,
                downloaded_at

            FROM raw_responses

            WHERE source = ?

            ORDER BY downloaded_at DESC

            LIMIT 1
            """,
            (
                "TDCC_SHAREHOLDING",
            ),
        ).fetchone()

        conn.close()

        if raw_row is None:

            st.warning(
                "目前沒有 TDCC Raw 資料。"
            )

        else:

            raw_text = raw_row[1]

            try:

                parsed = parse_tdcc_rows(
                    raw_text=raw_text,
                    target_stock_ids=[
                        selected_tdcc_stock
                    ],
                )

            except Exception as ex:

                st.error(
                    f"TDCC Raw 解析失敗：{ex}"
                )

                parsed = []

            if not parsed:

                st.warning(
                    "最新 TDCC Raw 中找不到這檔股票。"
                )

            else:

                raw_df = pd.DataFrame(
                    parsed
                )

                raw_df = (
                    raw_df
                    .sort_values(
                        "holding_level"
                    )
                    .copy()
                )

                display_raw = (
                    raw_df.rename(
                        columns={
                            "stock_id":
                                "證券代號",

                            "data_date":
                                "資料日期",

                            "holding_level":
                                "持股分級",

                            "holders":
                                "人數",

                            "shares":
                                "股數",

                            "percentage":
                                "占集保庫存數比例%",
                        }
                    )
                )

                st.dataframe(
                    display_raw[
                        [
                            "證券代號",
                            "資料日期",
                            "持股分級",
                            "人數",
                            "股數",
                            "占集保庫存數比例%",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

                # -------------------------
                # Raw 人工驗證摘要
                # -------------------------

                retail_raw = (
                    raw_df[
                        raw_df[
                            "holding_level"
                        ].isin(
                            [
                                1,
                                2,
                            ]
                        )
                    ][
                        "percentage"
                    ]
                    .sum()
                )

                large_raw = (
                    raw_df[
                        raw_df[
                            "holding_level"
                        ]
                        == 15
                    ][
                        "percentage"
                    ]
                    .sum()
                )

                st.write(
                    "Raw 分級重新計算："
                )

                col1, col2 = st.columns(2)

                with col1:

                    st.metric(
                        "Raw LV15 大戶",
                        f"{large_raw:.2f} %",
                    )

                with col2:

                    st.metric(
                        "Raw LV1 + LV2 散戶",
                        f"{retail_raw:.2f} %",
                    )

                if not tdcc_summary.empty:

                    large_match = (
                        abs(
                            large_raw
                            - large_holder_pct
                        )
                        < 0.001
                    )

                    retail_match = (
                        abs(
                            retail_raw
                            - retail_holder_pct
                        )
                        < 0.001
                    )

                    if (
                        large_match
                        and retail_match
                    ):

                        st.success(
                            "✅ tdcc_holdings "
                            "與官方 Raw 分級計算一致"
                        )

                    else:

                        st.error(
                            "❌ tdcc_holdings "
                            "與 Raw 分級計算不一致"
                        )


# =====================================
# 爬蟲紀錄
# =====================================

with tab6:

    st.subheader(
        "最近爬蟲紀錄"
    )

    conn = get_connection()

    logs = pd.read_sql_query(
        """
        SELECT
            source,
            request_key,
            status,
            record_count,
            error_message,
            started_at,
            finished_at

        FROM crawl_logs

        ORDER BY started_at DESC

        LIMIT 100
        """,
        conn,
    )

    conn.close()

    if logs.empty:

        st.info(
            "目前沒有爬蟲紀錄。"
        )

    else:

        st.dataframe(
            logs,
            use_container_width=True,
            hide_index=True,
        )