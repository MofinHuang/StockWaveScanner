from __future__ import annotations

import json
import math
import os
import statistics
import sys

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import libsql
from dotenv import load_dotenv


# ============================================================
# CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

ENV_FILE = ROOT / ".env"

OUTPUT_DIR = (
    ROOT
    / "docs"
    / "data"
    / "latest"
)

MODEL_VERSION = "V2.1-DRAFT-2"

TAIPEI = ZoneInfo(
    "Asia/Taipei"
)

PRICE_HISTORY_DAYS = 90
INSTITUTIONAL_HISTORY_DAYS = 20
REVENUE_HISTORY_MONTHS = 24
FINANCIAL_HISTORY_QUARTERS = 8


# ============================================================
# CONSOLE
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


# ============================================================
# TURSO DEV
# ============================================================


def load_dev_credentials(
) -> tuple[str, str]:

    load_dotenv(
        ENV_FILE
    )

    url = (
        os.getenv(
            "TURSO_DEV_DATABASE_URL",
            "",
        )
        .strip()
    )

    token = (
        os.getenv(
            "TURSO_DEV_AUTH_TOKEN",
            "",
        )
        .strip()
    )

    if not url:

        raise RuntimeError(
            "TURSO_DEV_DATABASE_URL missing"
        )

    if not token:

        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN missing"
        )

    lower_url = (
        url.lower()
    )

    if (
        "stockwave-dev"
        not in lower_url
    ):

        raise RuntimeError(
            "SAFETY STOP: "
            "database is not stockwave-dev"
        )

    if (
        "stockwave-prod"
        in lower_url
    ):

        raise RuntimeError(
            "SAFETY STOP: "
            "PROD database detected"
        )

    return (
        url,
        token,
    )


# ============================================================
# BASIC HELPERS
# ============================================================


def now_taipei_iso() -> str:

    return (
        datetime
        .now(
            TAIPEI
        )
        .isoformat(
            timespec="seconds"
        )
    )


def scalar(
    conn,
    sql: str,
    params: tuple[Any, ...] = (),
) -> Any:

    row = (
        conn.execute(
            sql,
            params,
        )
        .fetchone()
    )

    if row is None:

        return None

    return row[0]


def safe_float(
    value: Any,
) -> float | None:

    if value is None:

        return None

    try:

        result = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return None

    if not math.isfinite(
        result
    ):

        return None

    return result


def safe_int(
    value: Any,
) -> int | None:

    if value is None:

        return None

    try:

        return int(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


def round_or_none(
    value: float | None,
    digits: int = 2,
) -> float | None:

    if value is None:

        return None

    return round(
        value,
        digits,
    )


def mean_or_none(
    values: list[
        float
    ],
) -> float | None:

    if not values:

        return None

    return statistics.fmean(
        values
    )


def change_pct(
    current: float | None,
    previous: float | None,
) -> float | None:

    if (
        current is None
        or
        previous is None
        or
        previous == 0
    ):

        return None

    return (
        current
        /
        previous
        -
        1
    ) * 100.0


def period_label(
    year: int | None,
    quarter: int | None,
) -> str | None:

    if (
        year is None
        or
        quarter is None
    ):

        return None

    return (
        f"{year}-Q{quarter}"
    )


# ============================================================
# JSON
# ============================================================


def write_json(
    name: str,
    payload: Any,
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        OUTPUT_DIR
        /
        name
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


# ============================================================
# DATE WINDOWS
# ============================================================


def load_recent_trade_dates(
    conn,
    limit: int,
) -> list[str]:

    rows = (
        conn.execute(
            """
            SELECT DISTINCT trade_date

            FROM stock_price_daily

            ORDER BY trade_date DESC

            LIMIT ?
            """,
            (
                limit,
            ),
        )
        .fetchall()
    )

    return [
        str(
            row[0]
        )

        for row
        in rows
    ]


def load_recent_revenue_months(
    conn,
    limit: int,
) -> list[str]:

    rows = (
        conn.execute(
            """
            SELECT DISTINCT revenue_month

            FROM monthly_revenue

            ORDER BY revenue_month DESC

            LIMIT ?
            """,
            (
                limit,
            ),
        )
        .fetchall()
    )

    return [
        str(
            row[0]
        )

        for row
        in rows
    ]


# ============================================================
# STOCK MASTER
# ============================================================


def load_stock_master(
    conn,
) -> dict[
    str,
    dict[str, Any],
]:

    rows = (
        conn.execute(
            """
            SELECT

                stock_id,
                stock_name,
                short_name,
                market,

                industry_code,
                industry_name,

                listed_date,
                is_active

            FROM stock_master

            WHERE is_active = 1

              AND security_type =
                  'COMMON_STOCK'

            ORDER BY
                market,
                stock_id
            """
        )
        .fetchall()
    )

    result = {}

    for row in rows:

        stock_id = str(
            row[0]
        )

        result[
            stock_id
        ] = {
            "stock_id":
                stock_id,

            "stock_name":
                str(
                    row[1]
                    or
                    ""
                ),

            "short_name":
                str(
                    row[2]
                    or
                    row[1]
                    or
                    ""
                ),

            "market":
                str(
                    row[3]
                ),

            "industry_code":
                (
                    None
                    if row[4]
                    is None
                    else str(
                        row[4]
                    )
                ),

            "industry_name":
                (
                    None
                    if row[5]
                    is None
                    else str(
                        row[5]
                    )
                ),

            "listed_date":
                (
                    None
                    if row[6]
                    is None
                    else str(
                        row[6]
                    )
                ),

            "is_active":
                bool(
                    row[7]
                ),
        }

    return result


# ============================================================
# PRICE
# ============================================================


def load_price_history(
    conn,
    start_date: str,
) -> dict[
    str,
    list[
        dict[str, Any]
    ],
]:

    rows = (
        conn.execute(
            """
            SELECT

                stock_id,
                trade_date,

                open,
                high,
                low,
                close,

                volume

            FROM stock_price_daily

            WHERE trade_date >= ?

            ORDER BY
                stock_id,
                trade_date
            """,
            (
                start_date,
            ),
        )
        .fetchall()
    )

    result = defaultdict(
        list
    )

    for row in rows:

        result[
            str(
                row[0]
            )
        ].append(
            {
                "trade_date":
                    str(
                        row[1]
                    ),

                "open":
                    safe_float(
                        row[2]
                    ),

                "high":
                    safe_float(
                        row[3]
                    ),

                "low":
                    safe_float(
                        row[4]
                    ),

                "close":
                    safe_float(
                        row[5]
                    ),

                "volume":
                    safe_int(
                        row[6]
                    ),
            }
        )

    return dict(
        result
    )


def calculate_atr14(
    rows: list[
        dict[str, Any]
    ],
) -> float | None:

    if len(
        rows
    ) < 15:

        return None

    true_ranges = []

    start = max(
        1,
        len(
            rows
        )
        -
        14,
    )

    for index in range(
        start,
        len(
            rows
        ),
    ):

        current = (
            rows[
                index
            ]
        )

        previous = (
            rows[
                index - 1
            ]
        )

        high = current.get(
            "high"
        )

        low = current.get(
            "low"
        )

        previous_close = (
            previous.get(
                "close"
            )
        )

        if (
            high is None
            or
            low is None
            or
            previous_close is None
        ):

            continue

        true_range = max(
            high - low,
            abs(
                high
                -
                previous_close
            ),
            abs(
                low
                -
                previous_close
            ),
        )

        true_ranges.append(
            true_range
        )

    if not true_ranges:

        return None

    return (
        statistics.fmean(
            true_ranges
        )
    )


def price_snapshot(
    rows: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:

    if not rows:

        return {
            "history_days": 0,
            "status": "WAITING_HISTORY",
        }

    latest = (
        rows[-1]
    )

    previous = (
        rows[-2]
        if len(
            rows
        ) >= 2
        else None
    )

    closes = [
        float(
            row["close"]
        )

        for row
        in rows

        if row.get(
            "close"
        )
        is not None
    ]

    volumes = [
        float(
            row["volume"]
        )

        for row
        in rows

        if row.get(
            "volume"
        )
        is not None
    ]

    latest_close = (
        safe_float(
            latest.get(
                "close"
            )
        )
    )

    previous_close = (
        safe_float(
            previous.get(
                "close"
            )
        )
        if previous
        else None
    )

    def trailing_mean(
        length: int,
    ) -> float | None:

        if len(
            closes
        ) < length:

            return None

        return statistics.fmean(
            closes[
                -length:
            ]
        )

    def trailing_return(
        days: int,
    ) -> float | None:

        if len(
            closes
        ) <= days:

            return None

        base = (
            closes[
                -(days + 1)
            ]
        )

        return change_pct(
            closes[-1],
            base,
        )

    volume_ratio_20 = None

    if (
        latest.get(
            "volume"
        )
        is not None
        and
        len(
            volumes
        )
        >= 20
    ):

        average_volume = (
            statistics.fmean(
                volumes[
                    -20:
                ]
            )
        )

        if average_volume:

            volume_ratio_20 = (
                float(
                    latest[
                        "volume"
                    ]
                )
                /
                average_volume
            )

    atr14 = (
        calculate_atr14(
            rows
        )
    )

    history_days = len(
        rows
    )

    return {
        "trade_date":
            latest.get(
                "trade_date"
            ),

        "open":
            round_or_none(
                safe_float(
                    latest.get(
                        "open"
                    )
                ),
                2,
            ),

        "high":
            round_or_none(
                safe_float(
                    latest.get(
                        "high"
                    )
                ),
                2,
            ),

        "low":
            round_or_none(
                safe_float(
                    latest.get(
                        "low"
                    )
                ),
                2,
            ),

        "close":
            round_or_none(
                latest_close,
                2,
            ),

        "previous_close":
            round_or_none(
                previous_close,
                2,
            ),

        "change_pct":
            round_or_none(
                change_pct(
                    latest_close,
                    previous_close,
                ),
                2,
            ),

        "volume":
            latest.get(
                "volume"
            ),

        "history_days":
            history_days,

        "ma20":
            round_or_none(
                trailing_mean(
                    20
                ),
                2,
            ),

        "ma60":
            round_or_none(
                trailing_mean(
                    60
                ),
                2,
            ),

        "return_5d_pct":
            round_or_none(
                trailing_return(
                    5
                ),
                2,
            ),

        "return_10d_pct":
            round_or_none(
                trailing_return(
                    10
                ),
                2,
            ),

        "return_20d_pct":
            round_or_none(
                trailing_return(
                    20
                ),
                2,
            ),

        "atr14":
            round_or_none(
                atr14,
                2,
            ),

        "volume_ratio_20":
            round_or_none(
                volume_ratio_20,
                2,
            ),

        "status":
            (
                "READY"
                if history_days >= 60
                else
                "WAITING_HISTORY"
            ),
    }


# ============================================================
# INSTITUTIONAL
# ============================================================


def load_institutional_history(
    conn,
    start_date: str,
) -> dict[
    str,
    list[
        dict[str, Any]
    ],
]:

    rows = (
        conn.execute(
            """
            SELECT

                stock_id,
                trade_date,

                foreign_net,
                foreign_data_status,

                trust_net,
                trust_data_status,

                dealer_net,
                dealer_data_status

            FROM institutional_daily

            WHERE trade_date >= ?

            ORDER BY
                stock_id,
                trade_date
            """,
            (
                start_date,
            ),
        )
        .fetchall()
    )

    result = defaultdict(
        list
    )

    for row in rows:

        result[
            str(
                row[0]
            )
        ].append(
            {
                "trade_date":
                    str(
                        row[1]
                    ),

                "foreign_net":
                    safe_int(
                        row[2]
                    ),

                "foreign_status":
                    str(
                        row[3]
                    ),

                "trust_net":
                    safe_int(
                        row[4]
                    ),

                "trust_status":
                    str(
                        row[5]
                    ),

                "dealer_net":
                    safe_int(
                        row[6]
                    ),

                "dealer_status":
                    str(
                        row[7]
                    ),
            }
        )

    return dict(
        result
    )


def valid_institutional_value(
    row: dict[str, Any],
    value_key: str,
    status_key: str,
) -> int | None:

    status = (
        row.get(
            status_key
        )
    )

    if status not in {
        "STORED",
        "ZERO_INFERRED",
    }:

        return None

    return safe_int(
        row.get(
            value_key
        )
    )


def institutional_snapshot(
    rows: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:

    if not rows:

        return {
            "history_days": 0,
            "status": "WAITING_DATA",
        }

    def sum_recent(
        days: int,
        value_key: str,
        status_key: str,
    ) -> tuple[
        int | None,
        int,
    ]:

        selected = (
            rows[
                -days:
            ]
        )

        values = []

        for row in selected:

            value = (
                valid_institutional_value(
                    row,
                    value_key,
                    status_key,
                )
            )

            if value is not None:

                values.append(
                    value
                )

        if not values:

            return (
                None,
                0,
            )

        return (
            sum(
                values
            ),
            len(
                values
            ),
        )

    foreign_5d, foreign_5d_days = (
        sum_recent(
            5,
            "foreign_net",
            "foreign_status",
        )
    )

    foreign_20d, foreign_20d_days = (
        sum_recent(
            20,
            "foreign_net",
            "foreign_status",
        )
    )

    trust_5d, trust_5d_days = (
        sum_recent(
            5,
            "trust_net",
            "trust_status",
        )
    )

    dealer_5d, dealer_5d_days = (
        sum_recent(
            5,
            "dealer_net",
            "dealer_status",
        )
    )

    latest = (
        rows[-1]
    )

    return {
        "trade_date":
            latest.get(
                "trade_date"
            ),

        "history_days":
            len(
                rows
            ),

        "foreign_net_latest":
            valid_institutional_value(
                latest,
                "foreign_net",
                "foreign_status",
            ),

        "foreign_status_latest":
            latest.get(
                "foreign_status"
            ),

        "foreign_5d_net":
            foreign_5d,

        "foreign_5d_valid_days":
            foreign_5d_days,

        "foreign_20d_net":
            foreign_20d,

        "foreign_20d_valid_days":
            foreign_20d_days,

        "trust_5d_net":
            trust_5d,

        "trust_5d_valid_days":
            trust_5d_days,

        "dealer_5d_net":
            dealer_5d,

        "dealer_5d_valid_days":
            dealer_5d_days,

        "status":
            (
                "READY"
                if foreign_20d_days >= 15
                else
                "WAITING_HISTORY"
            ),
    }


# ============================================================
# TDCC
# ============================================================


def load_tdcc_latest(
    conn,
) -> tuple[
    str | None,
    dict[
        str,
        dict[str, Any]
    ],
]:

    latest_date = scalar(
        conn,
        """
        SELECT MAX(data_date)

        FROM tdcc_summary
        """,
    )

    if latest_date is None:

        return (
            None,
            {},
        )

    latest_date = str(
        latest_date
    )

    rows = (
        conn.execute(
            """
            SELECT

                stock_id,
                data_date,

                large_holder_pct,
                retail_holder_pct,

                large_holder_change,
                retail_holder_change

            FROM tdcc_summary

            WHERE data_date = ?
            """,
            (
                latest_date,
            ),
        )
        .fetchall()
    )

    result = {}

    for row in rows:

        result[
            str(
                row[0]
            )
        ] = {
            "data_date":
                str(
                    row[1]
                ),

            "large_holder_pct":
                round_or_none(
                    safe_float(
                        row[2]
                    ),
                    4,
                ),

            "retail_holder_pct":
                round_or_none(
                    safe_float(
                        row[3]
                    ),
                    4,
                ),

            "large_holder_change":
                round_or_none(
                    safe_float(
                        row[4]
                    ),
                    4,
                ),

            "retail_holder_change":
                round_or_none(
                    safe_float(
                        row[5]
                    ),
                    4,
                ),

            "status":
                "READY",
        }

    return (
        latest_date,
        result,
    )


# ============================================================
# REVENUE
# ============================================================


def load_revenue_history(
    conn,
    start_month: str,
) -> dict[
    str,
    list[
        dict[str, Any]
    ],
]:

    rows = (
        conn.execute(
            """
            SELECT

                stock_id,
                revenue_month,

                revenue,
                revenue_mom_pct,
                revenue_yoy_pct,

                cumulative_revenue,
                cumulative_yoy_pct

            FROM monthly_revenue

            WHERE revenue_month >= ?

            ORDER BY
                stock_id,
                revenue_month
            """,
            (
                start_month,
            ),
        )
        .fetchall()
    )

    result = defaultdict(
        list
    )

    for row in rows:

        result[
            str(
                row[0]
            )
        ].append(
            {
                "revenue_month":
                    str(
                        row[1]
                    ),

                "revenue":
                    safe_float(
                        row[2]
                    ),

                "revenue_mom_pct":
                    round_or_none(
                        safe_float(
                            row[3]
                        ),
                        2,
                    ),

                "revenue_yoy_pct":
                    round_or_none(
                        safe_float(
                            row[4]
                        ),
                        2,
                    ),

                "cumulative_revenue":
                    safe_float(
                        row[5]
                    ),

                "cumulative_yoy_pct":
                    round_or_none(
                        safe_float(
                            row[6]
                        ),
                        2,
                    ),
            }
        )

    return dict(
        result
    )


def revenue_snapshot(
    rows: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:

    if not rows:

        return {
            "history_months": 0,
            "status": "WAITING_HISTORY",
        }

    latest = (
        rows[-1]
    )

    history_months = len(
        rows
    )

    return {
        **latest,

        "history_months":
            history_months,

        "status":
            (
                "READY"
                if history_months
                >=
                REVENUE_HISTORY_MONTHS
                else
                "WAITING_HISTORY"
            ),
    }


# ============================================================
# FINANCIAL
# ============================================================


def load_financial_history(
    conn,
) -> dict[
    str,
    list[
        dict[str, Any]
    ],
]:

    rows = (
        conn.execute(
            """
            SELECT

                stock_id,

                fiscal_year,
                fiscal_quarter,

                report_type,

                revenue,
                gross_profit,
                operating_income,
                net_income,

                eps,

                gross_margin_pct,
                operating_margin_pct,
                net_margin_pct

            FROM quarterly_financial

            ORDER BY

                stock_id,
                fiscal_year,
                fiscal_quarter
            """
        )
        .fetchall()
    )

    result = defaultdict(
        list
    )

    for row in rows:

        result[
            str(
                row[0]
            )
        ].append(
            {
                "fiscal_year":
                    safe_int(
                        row[1]
                    ),

                "fiscal_quarter":
                    safe_int(
                        row[2]
                    ),

                "report_type":
                    str(
                        row[3]
                    ),

                "revenue":
                    safe_float(
                        row[4]
                    ),

                "gross_profit":
                    safe_float(
                        row[5]
                    ),

                "operating_income":
                    safe_float(
                        row[6]
                    ),

                "net_income":
                    safe_float(
                        row[7]
                    ),

                "eps":
                    round_or_none(
                        safe_float(
                            row[8]
                        ),
                        4,
                    ),

                "gross_margin_pct":
                    round_or_none(
                        safe_float(
                            row[9]
                        ),
                        2,
                    ),

                "operating_margin_pct":
                    round_or_none(
                        safe_float(
                            row[10]
                        ),
                        2,
                    ),

                "net_margin_pct":
                    round_or_none(
                        safe_float(
                            row[11]
                        ),
                        2,
                    ),
            }
        )

    return dict(
        result
    )


def financial_snapshot(
    rows: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:

    if not rows:

        return {
            "history_quarters": 0,
            "status": "WAITING_HISTORY",
        }

    latest = (
        rows[-1]
    )

    history_quarters = len(
        rows
    )

    year = (
        latest.get(
            "fiscal_year"
        )
    )

    quarter = (
        latest.get(
            "fiscal_quarter"
        )
    )

    return {
        **latest,

        "period":
            period_label(
                year,
                quarter,
            ),

        "history_quarters":
            history_quarters,

        "status":
            (
                "READY"
                if history_quarters
                >=
                FINANCIAL_HISTORY_QUARTERS
                else
                "WAITING_HISTORY"
            ),
    }


# ============================================================
# MARKET INDEX
# ============================================================


def load_market_history(
    conn,
) -> dict[
    str,
    list[
        dict[str, Any]
    ],
]:

    rows = (
        conn.execute(
            """
            SELECT

                market,
                index_code,
                trade_date,

                close,
                volume

            FROM market_index_daily

            ORDER BY
                market,
                index_code,
                trade_date
            """
        )
        .fetchall()
    )

    result = defaultdict(
        list
    )

    for row in rows:

        key = (
            f"{row[0]}:"
            f"{row[1]}"
        )

        result[
            key
        ].append(
            {
                "market":
                    str(
                        row[0]
                    ),

                "index_code":
                    str(
                        row[1]
                    ),

                "trade_date":
                    str(
                        row[2]
                    ),

                "close":
                    safe_float(
                        row[3]
                    ),

                "volume":
                    safe_float(
                        row[4]
                    ),
            }
        )

    return dict(
        result
    )


def market_index_snapshot(
    rows: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:

    if not rows:

        return {
            "status": "WAITING_HISTORY",
            "history_days": 0,
        }

    closes = [
        float(
            row["close"]
        )

        for row
        in rows

        if row.get(
            "close"
        )
        is not None
    ]

    latest = (
        rows[-1]
    )

    latest_close = (
        safe_float(
            latest.get(
                "close"
            )
        )
    )

    ma20 = (
        statistics.fmean(
            closes[
                -20:
            ]
        )
        if len(
            closes
        )
        >= 20
        else None
    )

    ma60 = (
        statistics.fmean(
            closes[
                -60:
            ]
        )
        if len(
            closes
        )
        >= 60
        else None
    )

    return {
        "market":
            latest.get(
                "market"
            ),

        "index_code":
            latest.get(
                "index_code"
            ),

        "trade_date":
            latest.get(
                "trade_date"
            ),

        "close":
            round_or_none(
                latest_close,
                2,
            ),

        "ma20":
            round_or_none(
                ma20,
                2,
            ),

        "ma60":
            round_or_none(
                ma60,
                2,
            ),

        "history_days":
            len(
                closes
            ),

        "status":
            (
                "READY"
                if len(
                    closes
                )
                >= 60
                else
                "WAITING_HISTORY"
            ),
    }


def calculate_market_regime(
    twse: dict[str, Any],
    tpex: dict[str, Any],
) -> dict[str, Any]:

    if (
        twse.get(
            "status"
        )
        != "READY"
        or
        tpex.get(
            "status"
        )
        != "READY"
    ):

        return {
            "code":
                "WAITING_DATA",

            "label":
                "資料補齊中",

            "model_status":
                "WAITING_HISTORY",

            "description":
                "市場指數歷史資料尚未達到 60 個交易日。",
        }

    def bullish(
        item: dict[str, Any],
    ) -> bool:

        close = item.get(
            "close"
        )

        ma20 = item.get(
            "ma20"
        )

        ma60 = item.get(
            "ma60"
        )

        return bool(
            close is not None
            and
            ma20 is not None
            and
            ma60 is not None
            and
            close > ma20 > ma60
        )

    def bearish(
        item: dict[str, Any],
    ) -> bool:

        close = item.get(
            "close"
        )

        ma20 = item.get(
            "ma20"
        )

        ma60 = item.get(
            "ma60"
        )

        return bool(
            close is not None
            and
            ma20 is not None
            and
            ma60 is not None
            and
            close < ma20 < ma60
        )

    if (
        bullish(
            twse
        )
        and
        bullish(
            tpex
        )
    ):

        return {
            "code":
                "BULLISH",

            "label":
                "偏多",

            "model_status":
                "PROVISIONAL",

            "description":
                "上市與上櫃指數均位於 MA20 / MA60 多頭排列。",
        }

    if (
        bearish(
            twse
        )
        and
        bearish(
            tpex
        )
    ):

        return {
            "code":
                "HIGH_RISK",

            "label":
                "高風險",

            "model_status":
                "PROVISIONAL",

            "description":
                "上市與上櫃指數均位於 MA20 / MA60 空頭排列。",
        }

    return {
        "code":
            "NEUTRAL",

        "label":
            "震盪 / 中性",

        "model_status":
            "PROVISIONAL",

        "description":
            "市場指數趨勢目前未形成一致方向。",
    }


# ============================================================
# SYNC STATE
# ============================================================


def load_sync_state(
    conn,
) -> list[
    dict[str, Any]
]:

    rows = (
        conn.execute(
            """
            SELECT

                dataset,
                last_data_date,
                last_success_at,
                last_attempt_at,
                status,
                records_processed,
                error_message

            FROM sync_state

            ORDER BY dataset
            """
        )
        .fetchall()
    )

    result = []

    for row in rows:

        result.append(
            {
                "dataset":
                    str(
                        row[0]
                    ),

                "last_data_date":
                    (
                        None
                        if row[1]
                        is None
                        else str(
                            row[1]
                        )
                    ),

                "last_success_at":
                    (
                        None
                        if row[2]
                        is None
                        else str(
                            row[2]
                        )
                    ),

                "last_attempt_at":
                    (
                        None
                        if row[3]
                        is None
                        else str(
                            row[3]
                        )
                    ),

                "status":
                    (
                        None
                        if row[4]
                        is None
                        else str(
                            row[4]
                        )
                    ),

                "records_processed":
                    safe_int(
                        row[5]
                    ),

                "error_message":
                    (
                        None
                        if row[6]
                        is None
                        else str(
                            row[6]
                        )
                    ),
            }
        )

    return result


# ============================================================
# READINESS
# ============================================================


def component_status(
    value: dict[str, Any],
) -> str:

    return str(
        value.get(
            "status",
            "WAITING_DATA",
        )
    )


def stock_readiness(
    price: dict[str, Any],
    institutional: dict[str, Any],
    tdcc: dict[str, Any],
    revenue: dict[str, Any],
    financial: dict[str, Any],
) -> dict[str, Any]:

    components = {
        "price":
            component_status(
                price
            ),

        "institutional":
            component_status(
                institutional
            ),

        "tdcc":
            component_status(
                tdcc
            ),

        "revenue":
            component_status(
                revenue
            ),

        "financial":
            component_status(
                financial
            ),
    }

    ready_count = sum(
        status == "READY"

        for status
        in components.values()
    )

    total_count = len(
        components
    )

    overall = (
        "READY"
        if ready_count
        ==
        total_count
        else
        "WAITING_DATA"
    )

    return {
        **components,

        "ready_components":
            ready_count,

        "total_components":
            total_count,

        "percent":
            round(
                ready_count
                /
                total_count
                *
                100,
                1,
            ),

        "overall":
            overall,
    }


# ============================================================
# BUILD STOCK SNAPSHOT
# ============================================================


def build_stocks(
    masters: dict[
        str,
        dict[str, Any]
    ],

    prices: dict[
        str,
        list[
            dict[str, Any]
        ]
    ],

    institutions: dict[
        str,
        list[
            dict[str, Any]
        ]
    ],

    tdcc: dict[
        str,
        dict[str, Any]
    ],

    revenues: dict[
        str,
        list[
            dict[str, Any]
        ]
    ],

    financials: dict[
        str,
        list[
            dict[str, Any]
        ]
    ],
) -> list[
    dict[str, Any]
]:

    result = []

    for (
        stock_id,
        master,
    ) in masters.items():

        price = (
            price_snapshot(
                prices.get(
                    stock_id,
                    [],
                )
            )
        )

        institutional = (
            institutional_snapshot(
                institutions.get(
                    stock_id,
                    [],
                )
            )
        )

        tdcc_snapshot = (
            tdcc.get(
                stock_id,
                {
                    "status":
                        "WAITING_DATA"
                },
            )
        )

        revenue = (
            revenue_snapshot(
                revenues.get(
                    stock_id,
                    [],
                )
            )
        )

        financial = (
            financial_snapshot(
                financials.get(
                    stock_id,
                    [],
                )
            )
        )

        readiness = (
            stock_readiness(
                price,
                institutional,
                tdcc_snapshot,
                revenue,
                financial,
            )
        )

        score_status = (
            "MODEL_PENDING"
            if readiness[
                "overall"
            ]
            == "READY"
            else
            "WAITING_DATA"
        )

        action = (
            "資料已完整，等待評分模型"
            if readiness[
                "overall"
            ]
            == "READY"
            else
            "等待資料補齊"
        )

        result.append(
            {
                **master,

                "latest":
                    price,

                "technical":
                    {
                        "ma20":
                            price.get(
                                "ma20"
                            ),

                        "ma60":
                            price.get(
                                "ma60"
                            ),

                        "atr14":
                            price.get(
                                "atr14"
                            ),

                        "return_5d_pct":
                            price.get(
                                "return_5d_pct"
                            ),

                        "return_10d_pct":
                            price.get(
                                "return_10d_pct"
                            ),

                        "return_20d_pct":
                            price.get(
                                "return_20d_pct"
                            ),

                        "volume_ratio_20":
                            price.get(
                                "volume_ratio_20"
                            ),
                    },

                "institutional":
                    institutional,

                "tdcc":
                    tdcc_snapshot,

                "fundamental":
                    {
                        "revenue":
                            revenue,

                        "financial":
                            financial,
                    },

                "readiness":
                    readiness,

                "scores":
                    {
                        "strength":
                            None,

                        "timing":
                            None,

                        "buy_priority":
                            None,

                        "trend":
                            None,

                        "relative_strength":
                            None,

                        "momentum_volume":
                            None,

                        "chip":
                            None,

                        "fundamental":
                            None,

                        "status":
                            score_status,
                    },

                "stage":
                    {
                        "code":
                            "WAITING_DATA",

                        "label":
                            "資料補齊中",
                    },

                "trade_plan":
                    {
                        "buy_zone_low":
                            None,

                        "buy_zone_high":
                            None,

                        "risk_price":
                            None,

                        "risk_pct":
                            None,

                        "target_low":
                            None,

                        "target_high":
                            None,
                    },

                "action":
                    action,
            }
        )

    result.sort(
        key=lambda item: (
            item.get(
                "market",
                "",
            ),
            item.get(
                "stock_id",
                "",
            ),
        )
    )

    return result


# ============================================================
# COVERAGE
# ============================================================


def coverage_summary(
    stocks: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:

    total = len(
        stocks
    )

    components = (
        "price",
        "institutional",
        "tdcc",
        "revenue",
        "financial",
    )

    result = {}

    for component in components:

        ready = sum(
            stock[
                "readiness"
            ].get(
                component
            )
            ==
            "READY"

            for stock
            in stocks
        )

        result[
            component
        ] = {
            "ready":
                ready,

            "total":
                total,

            "percent":
                (
                    round(
                        ready
                        /
                        total
                        *
                        100,
                        1,
                    )
                    if total
                    else
                    0
                ),
        }

    overall_ready = sum(
        stock[
            "readiness"
        ].get(
            "overall"
        )
        ==
        "READY"

        for stock
        in stocks
    )

    result[
        "overall"
    ] = {
        "ready":
            overall_ready,

        "total":
            total,

        "percent":
            (
                round(
                    overall_ready
                    /
                    total
                    *
                    100,
                    1,
                )
                if total
                else
                0
            ),
    }

    return result


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    configure_console()

    print(
        "=" * 80
    )

    print(
        "StockWaveScanner V2 - "
        "UI Snapshot Exporter"
    )

    print(
        "=" * 80
    )

    try:

        url, token = (
            load_dev_credentials()
        )

        print(
            "Target      : DEV"
        )

        print(
            "PROD Access : DISABLED"
        )

        conn = libsql.connect(
            database=url,
            auth_token=token,
        )

        try:

            print(
                "Loading Stock Master ..."
            )

            masters = (
                load_stock_master(
                    conn
                )
            )

            trade_dates = (
                load_recent_trade_dates(
                    conn,
                    PRICE_HISTORY_DAYS,
                )
            )

            if not trade_dates:

                raise RuntimeError(
                    "stock_price_daily is empty"
                )

            latest_data_date = (
                trade_dates[0]
            )

            price_start_date = (
                trade_dates[-1]
            )

            institutional_dates = (
                trade_dates[
                    :INSTITUTIONAL_HISTORY_DAYS
                ]
            )

            institutional_start_date = (
                institutional_dates[-1]
                if institutional_dates
                else
                price_start_date
            )

            print(
                "Loading Price History ..."
            )

            prices = (
                load_price_history(
                    conn,
                    price_start_date,
                )
            )

            print(
                "Loading Institutional ..."
            )

            institutions = (
                load_institutional_history(
                    conn,
                    institutional_start_date,
                )
            )

            print(
                "Loading TDCC ..."
            )

            (
                tdcc_date,
                tdcc,
            ) = load_tdcc_latest(
                conn
            )

            revenue_months = (
                load_recent_revenue_months(
                    conn,
                    REVENUE_HISTORY_MONTHS,
                )
            )

            revenues = {}

            if revenue_months:

                print(
                    "Loading Monthly Revenue ..."
                )

                revenues = (
                    load_revenue_history(
                        conn,
                        revenue_months[-1],
                    )
                )

            print(
                "Loading Quarterly Financial ..."
            )

            financials = (
                load_financial_history(
                    conn
                )
            )

            print(
                "Loading Market Index ..."
            )

            market_history = (
                load_market_history(
                    conn
                )
            )

            print(
                "Loading Sync State ..."
            )

            sync_state = (
                load_sync_state(
                    conn
                )
            )

        finally:

            conn.close()

        stocks = (
            build_stocks(
                masters,
                prices,
                institutions,
                tdcc,
                revenues,
                financials,
            )
        )

        coverage = (
            coverage_summary(
                stocks
            )
        )

        twse_index = (
            market_index_snapshot(
                market_history.get(
                    "TWSE:TAIEX",
                    [],
                )
            )
        )

        tpex_index = (
            market_index_snapshot(
                market_history.get(
                    "TPEX:TPEX",
                    [],
                )
            )
        )

        market_regime = (
            calculate_market_regime(
                twse_index,
                tpex_index,
            )
        )

        generated_at = (
            now_taipei_iso()
        )

        status_payload = {
            "model_version":
                MODEL_VERSION,

            "environment":
                "DEV",

            "data_date":
                latest_data_date,

            "generated_at":
                generated_at,

            "publish_status":
                "READY",

            "stock_count":
                len(
                    stocks
                ),

            "tdcc_date":
                tdcc_date,

            "coverage":
                coverage,

            "sync_state":
                sync_state,
        }

        market_payload = {
            "model_version":
                MODEL_VERSION,

            "data_date":
                latest_data_date,

            "generated_at":
                generated_at,

            "regime":
                market_regime,

            "indices":
                {
                    "TWSE":
                        twse_index,

                    "TPEX":
                        tpex_index,
                },
        }

        top10_payload = {
            "model_version":
                MODEL_VERSION,

            "data_date":
                latest_data_date,

            "generated_at":
                generated_at,

            "status":
                "WAITING_DATA",

            "message":
                (
                    "完整評分模型尚未啟用，"
                    "目前不產生假 TOP10。"
                ),

            "readiness":
                coverage.get(
                    "overall"
                ),

            "rows":
                [],
        }

        stocks_payload = {
            "model_version":
                MODEL_VERSION,

            "data_date":
                latest_data_date,

            "generated_at":
                generated_at,

            "count":
                len(
                    stocks
                ),

            "stocks":
                stocks,
        }

        analyst_payload = {
            "model_version":
                MODEL_VERSION,

            "data_date":
                latest_data_date,

            "generated_at":
                generated_at,

            "summary_status":
                "LIMITED",

            "message":
                (
                    "研究摘要來源尚未啟用，"
                    "目前不自行產生分析師觀點。"
                ),

            "market_view":
                None,

            "industries":
                [],

            "mentioned_stocks":
                [],

            "channels":
                [],
        }

        write_json(
            "status.json",
            status_payload,
        )

        write_json(
            "market.json",
            market_payload,
        )

        write_json(
            "top10.json",
            top10_payload,
        )

        write_json(
            "stocks.json",
            stocks_payload,
        )

        write_json(
            "analyst_digest.json",
            analyst_payload,
        )

        print()

        print(
            "=" * 80
        )

        print(
            "UI SNAPSHOT RESULT"
        )

        print(
            "=" * 80
        )

        print(
            f"Data Date       : "
            f"{latest_data_date}"
        )

        print(
            f"Stocks          : "
            f"{len(stocks):,}"
        )

        print(
            "Overall Ready   : "
            f"{coverage['overall']['ready']:,}"
            "/"
            f"{coverage['overall']['total']:,}"
        )

        print(
            "Financial Ready : "
            f"{coverage['financial']['ready']:,}"
            "/"
            f"{coverage['financial']['total']:,}"
        )

        print(
            "PROD Access     : DISABLED"
        )

        print()

        print(
            "[PASS] V2 UI snapshot generated"
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
            str(
                exc
            )
        )

        print()

        print(
            "No PROD database was accessed."
        )

        return 1


if __name__ == "__main__":

    sys.exit(
        main()
    )