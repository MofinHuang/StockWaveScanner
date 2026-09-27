from __future__ import annotations

import math
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import libsql
from dotenv import load_dotenv


# ============================================================
# CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

MODEL_VERSION = "V3-SECTOR-RESEARCH-1"

PRICE_LOOKBACK_DAYS = 20
TDCC_SOURCE_NAME = "TDCC"


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
# DEV SAFETY
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
            "TURSO_DEV_DATABASE_URL is missing from .env"
        )

    if not token:

        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN is missing from .env"
        )

    lower_url = (
        url.lower()
    )

    if (
        "stockwave-dev"
        not in lower_url
    ):

        raise RuntimeError(
            "SAFETY STOP: database is not stockwave-dev"
        )

    if (
        "stockwave-prod"
        in lower_url
    ):

        raise RuntimeError(
            "SAFETY STOP: PROD database detected"
        )

    return (
        url,
        token,
    )


# ============================================================
# HELPERS
# ============================================================


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


def mean_or_none(
    values: list[float],
) -> float | None:

    if not values:

        return None

    return statistics.fmean(
        values
    )


def pct_change(
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


# ============================================================
# TRADE DATES
# ============================================================


def load_trade_dates(
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


# ============================================================
# SECTOR MASTER
# ============================================================


def load_industry_sectors(
    conn,
) -> dict[
    str,
    dict[str, Any],
]:

    rows = (
        conn.execute(
            """
            SELECT

                sector_id,
                sector_name

            FROM sector_master

            WHERE sector_type = 'INDUSTRY'
              AND active = 1

            ORDER BY sector_id
            """
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

            "sector_id":
                str(
                    row[0]
                ),

            "sector_name":
                str(
                    row[1]
                ),
        }

    return result


def load_sector_relations(
    conn,
) -> dict[
    str,
    list[str],
]:

    rows = (
        conn.execute(
            """
            SELECT

                sector_id,
                stock_id

            FROM stock_sector_rel

            WHERE is_primary = 1

            ORDER BY
                sector_id,
                stock_id
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
            str(
                row[1]
            )
        )

    return dict(
        result
    )


# ============================================================
# PRICE HISTORY
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
                high,
                close

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

                "high":
                    safe_float(
                        row[2]
                    ),

                "close":
                    safe_float(
                        row[3]
                    ),
            }
        )

    return dict(
        result
    )


def build_price_metric(
    rows: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:

    if not rows:

        return {
            "ready":
                False,
        }

    closes = [
        safe_float(
            row.get(
                "close"
            )
        )

        for row
        in rows
    ]

    closes = [
        value

        for value
        in closes

        if value is not None
    ]

    if not closes:

        return {
            "ready":
                False,
        }

    latest_close = (
        closes[-1]
    )

    previous_close = (
        closes[-2]
        if len(
            closes
        ) >= 2
        else None
    )

    return_1d = pct_change(
        latest_close,
        previous_close,
    )

    return_5d = None

    if len(
        closes
    ) >= 6:

        return_5d = pct_change(
            latest_close,
            closes[-6],
        )

    return_20d = None

    if len(
        closes
    ) >= 21:

        return_20d = pct_change(
            latest_close,
            closes[-21],
        )

    ma20 = None

    if len(
        closes
    ) >= 20:

        ma20 = statistics.fmean(
            closes[-20:]
        )

    above_ma20 = (
        latest_close > ma20
        if ma20 is not None
        else None
    )

    previous_rows = (
        rows[:-1]
        if len(
            rows
        ) >= 2
        else []
    )

    previous_highs = [
        safe_float(
            row.get(
                "high"
            )
        )

        for row
        in previous_rows[-20:]
    ]

    previous_highs = [
        value

        for value
        in previous_highs

        if value is not None
    ]

    new_high = None

    if previous_highs:

        new_high = (
            latest_close
            >
            max(
                previous_highs
            )
        )

    return {

        "ready":
            True,

        "latest_close":
            latest_close,

        "return_1d":
            return_1d,

        "return_5d":
            return_5d,

        "return_20d":
            return_20d,

        "above_ma20":
            above_ma20,

        "new_high":
            new_high,
    }


# ============================================================
# INSTITUTIONAL
# ============================================================


def load_institutional_latest(
    conn,
    trade_date: str,
) -> dict[
    str,
    dict[str, int | None],
]:

    rows = (
        conn.execute(
            """
            SELECT

                stock_id,
                foreign_net,
                trust_net,
                dealer_net

            FROM institutional_daily

            WHERE trade_date = ?
            """,
            (
                trade_date,
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

            "foreign_net":
                safe_int(
                    row[1]
                ),

            "trust_net":
                safe_int(
                    row[2]
                ),

            "dealer_net":
                safe_int(
                    row[3]
                ),
        }

    return result


# ============================================================
# TDCC
# ============================================================


def load_tdcc_latest(
    conn,
) -> tuple[
    str | None,
    dict[
        str,
        float | None
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
                large_holder_change

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
        ] = (
            safe_float(
                row[1]
            )
        )

    return (
        latest_date,
        result,
    )


# ============================================================
# SECTOR CALCULATION
# ============================================================


def calculate_breadth_score(
    stock_count: int,
    up_count: int,
    above_ma20_count: int,
    new_high_count: int,
) -> float | None:

    if stock_count <= 0:

        return None

    up_ratio = (
        up_count
        /
        stock_count
    )

    above_ma20_ratio = (
        above_ma20_count
        /
        stock_count
    )

    new_high_ratio = (
        new_high_count
        /
        stock_count
    )

    score = (
        up_ratio
        * 40.0
        +
        above_ma20_ratio
        * 45.0
        +
        new_high_ratio
        * 15.0
    )

    return round(
        score,
        2,
    )


def calculate_technical_score(
    sector_return_1d: float | None,
    sector_return_5d: float | None,
    sector_return_20d: float | None,
    breadth_score: float | None,
) -> float | None:

    values = []

    if breadth_score is not None:

        values.append(
            breadth_score
        )

    return_points = []

    if sector_return_1d is not None:

        return_points.append(
            max(
                0.0,
                min(
                    100.0,
                    50.0
                    +
                    sector_return_1d
                    * 10.0,
                ),
            )
        )

    if sector_return_5d is not None:

        return_points.append(
            max(
                0.0,
                min(
                    100.0,
                    50.0
                    +
                    sector_return_5d
                    * 4.0,
                ),
            )
        )

    if sector_return_20d is not None:

        return_points.append(
            max(
                0.0,
                min(
                    100.0,
                    50.0
                    +
                    sector_return_20d
                    * 2.0,
                ),
            )
        )

    if return_points:

        values.append(
            statistics.fmean(
                return_points
            )
        )

    if not values:

        return None

    return round(
        statistics.fmean(
            values
        ),
        2,
    )


def calculate_status(
    technical_score: float | None,
) -> str:

    if technical_score is None:

        return "WAITING_DATA"

    if technical_score >= 70:

        return "STRONG"

    if technical_score >= 55:

        return "IMPROVING"

    if technical_score >= 40:

        return "NEUTRAL"

    return "WEAK"


def build_sector_snapshot(
    sector_id: str,
    stock_ids: list[str],
    price_history: dict[
        str,
        list[
            dict[str, Any]
        ],
    ],
    institutional: dict[
        str,
        dict[str, int | None],
    ],
    tdcc: dict[
        str,
        float | None
    ],
) -> dict[str, Any]:

    metrics = []

    foreign_values = []
    trust_values = []
    dealer_values = []
    tdcc_values = []

    for stock_id in stock_ids:

        price_metric = (
            build_price_metric(
                price_history.get(
                    stock_id,
                    [],
                )
            )
        )

        if price_metric.get(
            "ready"
        ):

            metrics.append(
                price_metric
            )

        institutional_row = (
            institutional.get(
                stock_id
            )
        )

        if institutional_row:

            foreign_value = (
                institutional_row.get(
                    "foreign_net"
                )
            )

            trust_value = (
                institutional_row.get(
                    "trust_net"
                )
            )

            dealer_value = (
                institutional_row.get(
                    "dealer_net"
                )
            )

            if foreign_value is not None:

                foreign_values.append(
                    foreign_value
                )

            if trust_value is not None:

                trust_values.append(
                    trust_value
                )

            if dealer_value is not None:

                dealer_values.append(
                    dealer_value
                )

        tdcc_value = (
            tdcc.get(
                stock_id
            )
        )

        if tdcc_value is not None:

            tdcc_values.append(
                tdcc_value
            )

    stock_count = len(
        metrics
    )

    up_count = sum(
        (
            metric.get(
                "return_1d"
            )
            is not None
            and
            metric.get(
                "return_1d"
            )
            >
            0
        )

        for metric
        in metrics
    )

    down_count = sum(
        (
            metric.get(
                "return_1d"
            )
            is not None
            and
            metric.get(
                "return_1d"
            )
            <
            0
        )

        for metric
        in metrics
    )

    above_ma20_count = sum(
        metric.get(
            "above_ma20"
        )
        is True

        for metric
        in metrics
    )

    new_high_count = sum(
        metric.get(
            "new_high"
        )
        is True

        for metric
        in metrics
    )

    return_1d_values = [
        float(
            metric[
                "return_1d"
            ]
        )

        for metric
        in metrics

        if metric.get(
            "return_1d"
        )
        is not None
    ]

    return_5d_values = [
        float(
            metric[
                "return_5d"
            ]
        )

        for metric
        in metrics

        if metric.get(
            "return_5d"
        )
        is not None
    ]

    return_20d_values = [
        float(
            metric[
                "return_20d"
            ]
        )

        for metric
        in metrics

        if metric.get(
            "return_20d"
        )
        is not None
    ]

    sector_return_1d = mean_or_none(
        return_1d_values
    )

    sector_return_5d = mean_or_none(
        return_5d_values
    )

    sector_return_20d = mean_or_none(
        return_20d_values
    )

    breadth_score = calculate_breadth_score(
        stock_count,
        up_count,
        above_ma20_count,
        new_high_count,
    )

    technical_score = calculate_technical_score(
        sector_return_1d,
        sector_return_5d,
        sector_return_20d,
        breadth_score,
    )

    status = calculate_status(
        technical_score
    )

    return {

        "sector_id":
            sector_id,

        "stock_count":
            stock_count,

        "up_count":
            up_count,

        "down_count":
            down_count,

        "above_ma20_count":
            above_ma20_count,

        "new_high_count":
            new_high_count,

        "foreign_net":
            sum(
                foreign_values
            )
            if foreign_values
            else None,

        "trust_net":
            sum(
                trust_values
            )
            if trust_values
            else None,

        "dealer_net":
            sum(
                dealer_values
            )
            if dealer_values
            else None,

        "large_holder_change":
            round_or_none(
                mean_or_none(
                    tdcc_values
                ),
                4,
            ),

        "sector_return_1d":
            round_or_none(
                sector_return_1d,
                2,
            ),

        "sector_return_5d":
            round_or_none(
                sector_return_5d,
                2,
            ),

        "sector_return_20d":
            round_or_none(
                sector_return_20d,
                2,
            ),

        "breadth_score":
            breadth_score,

        "technical_score":
            technical_score,

        "status":
            status,
    }


# ============================================================
# UPSERT
# ============================================================


def upsert_snapshot(
    conn,
    trade_date: str,
    rows: list[
        dict[str, Any]
    ],
) -> None:

    conn.execute(
        "BEGIN"
    )

    try:

        for row in rows:

            conn.execute(
                """
                INSERT INTO sector_snapshot_daily (

                    trade_date,
                    sector_id,

                    stock_count,
                    up_count,
                    down_count,

                    above_ma20_count,
                    new_high_count,

                    foreign_net,
                    trust_net,
                    dealer_net,

                    large_holder_change,

                    sector_return_1d,
                    sector_return_5d,
                    sector_return_20d,

                    breadth_score,
                    technical_score,

                    status,
                    model_version,

                    created_at,
                    updated_at

                )
                VALUES (

                    ?,
                    ?,

                    ?,
                    ?,
                    ?,

                    ?,
                    ?,

                    ?,
                    ?,
                    ?,

                    ?,

                    ?,
                    ?,
                    ?,

                    ?,
                    ?,

                    ?,
                    ?,

                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP

                )

                ON CONFLICT(
                    trade_date,
                    sector_id
                )
                DO UPDATE SET

                    stock_count =
                        excluded.stock_count,

                    up_count =
                        excluded.up_count,

                    down_count =
                        excluded.down_count,

                    above_ma20_count =
                        excluded.above_ma20_count,

                    new_high_count =
                        excluded.new_high_count,

                    foreign_net =
                        excluded.foreign_net,

                    trust_net =
                        excluded.trust_net,

                    dealer_net =
                        excluded.dealer_net,

                    large_holder_change =
                        excluded.large_holder_change,

                    sector_return_1d =
                        excluded.sector_return_1d,

                    sector_return_5d =
                        excluded.sector_return_5d,

                    sector_return_20d =
                        excluded.sector_return_20d,

                    breadth_score =
                        excluded.breadth_score,

                    technical_score =
                        excluded.technical_score,

                    status =
                        excluded.status,

                    model_version =
                        excluded.model_version,

                    updated_at =
                        CURRENT_TIMESTAMP
                """,
                (
                    trade_date,
                    row[
                        "sector_id"
                    ],

                    row[
                        "stock_count"
                    ],
                    row[
                        "up_count"
                    ],
                    row[
                        "down_count"
                    ],

                    row[
                        "above_ma20_count"
                    ],
                    row[
                        "new_high_count"
                    ],

                    row[
                        "foreign_net"
                    ],
                    row[
                        "trust_net"
                    ],
                    row[
                        "dealer_net"
                    ],

                    row[
                        "large_holder_change"
                    ],

                    row[
                        "sector_return_1d"
                    ],
                    row[
                        "sector_return_5d"
                    ],
                    row[
                        "sector_return_20d"
                    ],

                    row[
                        "breadth_score"
                    ],
                    row[
                        "technical_score"
                    ],

                    row[
                        "status"
                    ],
                    MODEL_VERSION,
                ),
            )

        conn.commit()

    except BaseException:

        try:

            conn.rollback()

        except Exception:
            pass

        raise


# ============================================================
# VERIFY
# ============================================================


def verify(
    conn,
    trade_date: str,
    expected_count: int,
) -> None:

    actual_count = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)

            FROM sector_snapshot_daily

            WHERE trade_date = ?
            """,
            (
                trade_date,
            ),
        )
        or 0
    )

    print()

    print(
        "=" * 80
    )

    print(
        "V3 SECTOR SNAPSHOT VERIFICATION"
    )

    print(
        "=" * 80
    )

    print(
        f"Trade Date      : {trade_date}"
    )

    print(
        f"Expected Sector : {expected_count:,}"
    )

    print(
        f"Actual Snapshot : {actual_count:,}"
    )

    if (
        actual_count
        !=
        expected_count
    ):

        raise RuntimeError(
            "Sector snapshot count mismatch"
        )

    rows = (
        conn.execute(
            """
            SELECT

                s.sector_name,

                d.stock_count,

                d.sector_return_1d,
                d.sector_return_5d,
                d.sector_return_20d,

                d.breadth_score,
                d.technical_score,

                d.foreign_net,
                d.trust_net,

                d.status

            FROM sector_snapshot_daily d

            INNER JOIN sector_master s

                ON s.sector_id =
                   d.sector_id

            WHERE d.trade_date = ?

            ORDER BY
                d.technical_score DESC,
                d.breadth_score DESC

            LIMIT 20
            """,
            (
                trade_date,
            ),
        )
        .fetchall()
    )

    print()

    print(
        "Top Sector Sample:"
    )

    for row in rows:

        print(
            f"  {str(row[0]):<16} "
            f"| stocks={row[1]} "
            f"| 1D={row[2]} "
            f"| 5D={row[3]} "
            f"| 20D={row[4]} "
            f"| breadth={row[5]} "
            f"| tech={row[6]} "
            f"| foreign={row[7]} "
            f"| trust={row[8]} "
            f"| {row[9]}"
        )

    print()

    print(
        "[PASS] V3 sector snapshot generated"
    )


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    configure_console()

    print(
        "=" * 80
    )

    print(
        "StockWaveScanner V3 - Sector Snapshot Builder"
    )

    print(
        "=" * 80
    )

    print()

    try:

        url, token = (
            load_dev_credentials()
        )

        print(
            "Environment : DEV"
        )

        print(
            "Database    : stockwave-dev"
        )

        print(
            "PROD Access : DISABLED"
        )

        print()

        conn = libsql.connect(
            database=url,
            auth_token=token,
        )

        try:

            trade_dates = (
                load_trade_dates(
                    conn,
                    PRICE_LOOKBACK_DAYS + 1,
                )
            )

            if not trade_dates:

                raise RuntimeError(
                    "stock_price_daily is empty"
                )

            trade_date = (
                trade_dates[0]
            )

            start_date = (
                trade_dates[-1]
            )

            print(
                f"Trade Date : {trade_date}"
            )

            print(
                f"Start Date : {start_date}"
            )

            print()

            sectors = (
                load_industry_sectors(
                    conn
                )
            )

            if not sectors:

                raise RuntimeError(
                    "sector_master has no active INDUSTRY sectors"
                )

            relations = (
                load_sector_relations(
                    conn
                )
            )

            price_history = (
                load_price_history(
                    conn,
                    start_date,
                )
            )

            institutional = (
                load_institutional_latest(
                    conn,
                    trade_date,
                )
            )

            (
                tdcc_date,
                tdcc,
            ) = load_tdcc_latest(
                conn
            )

            print(
                f"Industry Sectors : "
                f"{len(sectors):,}"
            )

            print(
                f"Price Stocks     : "
                f"{len(price_history):,}"
            )

            print(
                f"Institutional    : "
                f"{len(institutional):,}"
            )

            print(
                f"TDCC Date        : "
                f"{tdcc_date}"
            )

            print()

            snapshots = []

            for sector_id in sectors:

                stock_ids = (
                    relations.get(
                        sector_id,
                        [],
                    )
                )

                snapshot = (
                    build_sector_snapshot(
                        sector_id,
                        stock_ids,
                        price_history,
                        institutional,
                        tdcc,
                    )
                )

                snapshots.append(
                    snapshot
                )

            upsert_snapshot(
                conn,
                trade_date,
                snapshots,
            )

            verify(
                conn,
                trade_date,
                len(
                    snapshots
                ),
            )

        finally:

            conn.close()

        print()

        print(
            "=" * 80
        )

        print(
            "V3 SECTOR SNAPSHOT BUILD OK"
        )

        print(
            "=" * 80
        )

        print()

        print(
            "No PROD database was accessed."
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