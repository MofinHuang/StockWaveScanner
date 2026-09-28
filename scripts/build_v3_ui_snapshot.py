from __future__ import annotations

import json
import sys

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


# ============================================================
# CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = (
    ROOT
    / "docs"
    / "data"
    / "latest"
)

STOCKS_FILE = (
    DATA_DIR
    / "stocks.json"
)

TOP10_FILE = (
    DATA_DIR
    / "top10.json"
)

ACTION_PRIORITY_FILE = (
    DATA_DIR
    / "action_priority.json"
)

MARKET_FILE = (
    DATA_DIR
    / "market.json"
)

STATUS_FILE = (
    DATA_DIR
    / "status.json"
)

ETFS_FILE = (
    DATA_DIR
    / "etfs.json"
)

OUTPUT_FILE = (
    DATA_DIR
    / "v3_ui.json"
)

UI_VERSION = "V3-UI-ETF-V1"

TAIPEI = ZoneInfo(
    "Asia/Taipei"
)


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

        if callable(
            reconfigure
        ):

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
        .now(
            TAIPEI
        )
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

        return json.load(
            file
        )


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

        file.write(
            "\n"
        )

    print(
        f"[WRITE] {path}"
    )


def number(
    value: Any,
) -> float | None:

    if value is None:

        return None

    try:

        return float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


# ============================================================
# STAGE
# ============================================================

def stage_display(
    stage_code: str | None,
) -> dict[str, str]:

    mapping = {

        "BREAKOUT": {
            "code": "BREAKOUT",
            "label": "突破確認",
            "group": "ACTION",
        },

        "READY": {
            "code": "READY",
            "label": "接近買點",
            "group": "ACTION",
        },

        "SETUP": {
            "code": "SETUP",
            "label": "型態準備",
            "group": "ACTION",
        },

        "WATCH": {
            "code": "WATCH",
            "label": "持續觀察",
            "group": "WATCH",
        },

        "EXTENDED": {
            "code": "EXTENDED",
            "label": "漲幅延伸",
            "group": "RISK",
        },

        "AVOID": {
            "code": "AVOID",
            "label": "暫不關注",
            "group": "RISK",
        },

        "WAITING_DATA": {
            "code": "WAITING_DATA",
            "label": "資料補齊中",
            "group": "WAITING",
        },
    }

    return mapping.get(
        stage_code or "",
        {
            "code":
                stage_code
                or
                "UNKNOWN",

            "label":
                "未知",

            "group":
                "UNKNOWN",
        },
    )


# ============================================================
# STOCK CARD
# ============================================================

def build_stock_card(
    stock: dict[str, Any],
) -> dict[str, Any]:

    latest = (
        stock.get(
            "latest"
        )
        or {}
    )

    scores = (
        stock.get(
            "scores"
        )
        or {}
    )

    stage = (
        stock.get(
            "stage"
        )
        or {}
    )

    trade_plan = (
        stock.get(
            "trade_plan"
        )
        or {}
    )

    technical_v2 = (
        stock.get(
            "technical_v2"
        )
        or {}
    )

    stage_info = (
        stage_display(
            stage.get(
                "code"
            )
        )
    )

    return {

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

        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        "price": {

            "trade_date":
                latest.get(
                    "trade_date"
                ),

            "close":
                latest.get(
                    "close"
                ),

            "change_pct":
                latest.get(
                    "change_pct"
                ),
        },

        # ----------------------------------------------------
        # V3 SCORE
        # ----------------------------------------------------

        "score": {

            "overall":
                scores.get(
                    "overall"
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
        },

        # ----------------------------------------------------
        # TECHNICAL V2 DETAIL
        # ----------------------------------------------------

        "technical_detail": {

            "trend_structure":
                scores.get(
                    "trend_structure"
                ),

            "price_position":
                scores.get(
                    "price_position"
                ),

            "momentum_quality":
                scores.get(
                    "momentum_quality"
                ),

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
        },

        # ----------------------------------------------------
        # STAGE
        # ----------------------------------------------------

        "stage":
            stage_info,

        "action":
            stock.get(
                "action"
            ),

        # ----------------------------------------------------
        # TRADE PLAN
        # ----------------------------------------------------

        "trade_plan": {

            "buy_zone_low":
                trade_plan.get(
                    "buy_zone_low"
                ),

            "buy_zone_high":
                trade_plan.get(
                    "buy_zone_high"
                ),

            "distance_to_buy_zone_pct":
                trade_plan.get(
                    "distance_to_buy_zone_pct"
                ),

            "breakout_price":
                trade_plan.get(
                    "breakout_price"
                ),

            "breakout_distance_pct":
                trade_plan.get(
                    "breakout_distance_pct"
                ),

            "risk_price":
                trade_plan.get(
                    "risk_price"
                ),

            "current_risk_pct":
                trade_plan.get(
                    "current_risk_pct"
                ),

            "target_low":
                trade_plan.get(
                    "target_low"
                ),

            "target_high":
                trade_plan.get(
                    "target_high"
                ),

            "reward_risk_ratio":
                trade_plan.get(
                    "reward_risk_ratio"
                ),
        },

        # ----------------------------------------------------
        # READINESS
        # ----------------------------------------------------

        "status":
            scores.get(
                "status"
            ),
    }


# ============================================================
# FIND STOCK
# ============================================================

def build_stock_map(
    stocks: list[
        dict[str, Any]
    ],
) -> dict[
    str,
    dict[str, Any],
]:

    return {

        str(
            stock.get(
                "stock_id"
            )
        ):
            stock

        for stock in stocks

        if stock.get(
            "stock_id"
        )
        is not None
    }


# ============================================================
# RANKING
# ============================================================

def build_ranking_cards(
    ranking_payload: dict[str, Any],
    stock_map: dict[
        str,
        dict[str, Any],
    ],
) -> list[
    dict[str, Any]
]:

    result = []

    for ranking_row in (
        ranking_payload.get(
            "rows"
        )
        or []
    ):

        stock_id = str(
            ranking_row.get(
                "stock_id"
            )
            or
            ""
        )

        stock = (
            stock_map.get(
                stock_id
            )
        )

        if stock is None:

            continue

        card = (
            build_stock_card(
                stock
            )
        )

        card[
            "rank"
        ] = ranking_row.get(
            "rank"
        )

        result.append(
            card
        )

    return result


# ============================================================
# STAGE DISTRIBUTION
# ============================================================

def build_stage_distribution(
    stocks: list[
        dict[str, Any]
    ],
) -> dict[str, int]:

    result = {

        "BREAKOUT": 0,
        "READY": 0,
        "SETUP": 0,
        "WATCH": 0,
        "EXTENDED": 0,
        "AVOID": 0,
        "WAITING_DATA": 0,
    }

    for stock in stocks:

        stage_code = (
            stock.get(
                "stage",
                {},
            ).get(
                "code"
            )
        )

        if stage_code in result:

            result[
                stage_code
            ] += 1

        else:

            result[
                "WAITING_DATA"
            ] += 1

    return result


# ============================================================
# SCORE SUMMARY
# ============================================================

def build_score_summary(
    stocks: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:

    ready = [

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
    ]

    def average_score(
        key: str,
    ) -> float | None:

        values = []

        for stock in ready:

            value = number(
                stock.get(
                    "scores",
                    {},
                ).get(
                    key
                )
            )

            if value is not None:

                values.append(
                    value
                )

        if not values:

            return None

        return round(
            sum(values)
            /
            len(values),
            2,
        )

    return {

        "ready_count":
            len(
                ready
            ),

        "fundamental_avg":
            average_score(
                "fundamental"
            ),

        "chip_avg":
            average_score(
                "chip"
            ),

        "technical_avg":
            average_score(
                "technical"
            ),

        "overall_avg":
            average_score(
                "overall"
            ),
    }


# ============================================================
# ETF
# ============================================================

def build_etf_domain(
    etf_payload: dict[str, Any],
) -> dict[str, Any]:

    etfs = (
        etf_payload.get(
            "etfs"
        )
        or []
    )

    consensus = (
        etf_payload.get(
            "consensus"
        )
        or {}
    )

    return {

        "title":
            "ETF 持股異動",

        "description":
            (
                "依各 ETF 官方持股快照比較持股變化，"
                "不代表實際市場成交買進或賣出。"
            ),

        "note":
            etf_payload.get(
                "note"
            ),

        "schema_version":
            etf_payload.get(
                "schema_version"
            ),

        "generated_at":
            etf_payload.get(
                "generated_at"
            ),

        "change_type_labels":
            etf_payload.get(
                "change_type_labels"
            )
            or {},

        "metric_type_labels":
            etf_payload.get(
                "metric_type_labels"
            )
            or {},

        "period_labels":
            etf_payload.get(
                "period_labels"
            )
            or {},

        "etf_count":
            len(
                etfs
            ),

        "etfs":
            etfs,

        "consensus":
            consensus,
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
        "- UI Snapshot Builder"
    )

    print(
        "=" * 80
    )

    try:

        stocks_payload = (
            load_json(
                STOCKS_FILE
            )
        )

        top10_payload = (
            load_json(
                TOP10_FILE
            )
        )

        action_payload = (
            load_json(
                ACTION_PRIORITY_FILE
            )
        )

        market_payload = (
            load_json(
                MARKET_FILE
            )
        )

        status_payload = (
            load_json(
                STATUS_FILE
            )
        )

        etf_payload = (
            load_json(
                ETFS_FILE
            )
        )

        stocks = (
            stocks_payload.get(
                "stocks"
            )
            or []
        )

        stock_map = (
            build_stock_map(
                stocks
            )
        )

        top10 = (
            build_ranking_cards(
                top10_payload,
                stock_map,
            )
        )

        action_priority = (
            build_ranking_cards(
                action_payload,
                stock_map,
            )
        )

        stage_distribution = (
            build_stage_distribution(
                stocks
            )
        )

        score_summary = (
            build_score_summary(
                stocks
            )
        )

        etf_domain = (
            build_etf_domain(
                etf_payload
            )
        )

        payload = {

            "ui_version":
                UI_VERSION,

            "model_version":
                stocks_payload.get(
                    "score_model_version"
                ),

            "data_date":
                stocks_payload.get(
                    "data_date"
                ),

            "generated_at":
                now_iso(),

            # ------------------------------------------------
            # MARKET
            # ------------------------------------------------

            "market":
                market_payload,

            # ------------------------------------------------
            # ETF
            # ------------------------------------------------

            "etf":
                etf_domain,

            # ------------------------------------------------
            # SUMMARY
            # ------------------------------------------------

            "summary": {

                "total_stocks":
                    len(
                        stocks
                    ),

                "ready_stocks":
                    score_summary.get(
                        "ready_count"
                    ),

                "stage_distribution":
                    stage_distribution,

                "scores":
                    score_summary,
            },

            # ------------------------------------------------
            # RESEARCH PRIORITY
            # ------------------------------------------------

            "research_priority": {

                "title":
                    "個股研究排行",

                "description":
                    "依 Overall Score 排序，"
                    "用於找出值得優先研究的股票。",

                "ranking_method":
                    top10_payload.get(
                        "ranking_method"
                    ),

                "rows":
                    top10,
            },

            # ------------------------------------------------
            # ACTION PRIORITY
            # ------------------------------------------------

            "action_priority": {

                "title":
                    "今日優先觀察",

                "description":
                    "依 BREAKOUT → READY → SETUP "
                    "排序，同 Stage 內依 Overall Score。",

                "ranking_method":
                    action_payload.get(
                        "ranking_method"
                    ),

                "stage_counts":
                    action_payload.get(
                        "stage_counts"
                    ),

                "rows":
                    action_priority,
            },

            # ------------------------------------------------
            # STOCK LIST
            # ------------------------------------------------

            "stocks": [

                build_stock_card(
                    stock
                )

                for stock
                in stocks
            ],

            # ------------------------------------------------
            # STATUS
            # ------------------------------------------------

            "system_status":
                status_payload,
        }

        write_json(
            OUTPUT_FILE,
            payload,
        )

        print()

        print(
            "=" * 80
        )

        print(
            "V3 UI RESULT"
        )

        print(
            "=" * 80
        )

        print(
            f"Total Stocks      : "
            f"{len(stocks):,}"
        )

        print(
            f"Research Priority : "
            f"{len(top10):,}"
        )

        print(
            f"Action Priority   : "
            f"{len(action_priority):,}"
        )

        print(
            f"ETF Count         : "
            f"{etf_domain.get('etf_count', 0):,}"
        )

        print()

        print(
            "Stage Distribution"
        )

        print(
            "------------------"
        )

        for key in (
            "BREAKOUT",
            "READY",
            "SETUP",
            "WATCH",
            "EXTENDED",
            "AVOID",
            "WAITING_DATA",
        ):

            print(
                f"{key:12} : "
                f"{stage_distribution.get(key, 0)}"
            )

        print()

        print(
            "[PASS] V3 UI snapshot generated"
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