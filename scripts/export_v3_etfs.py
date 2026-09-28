from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

OUTPUT_FILE = (
    ROOT
    / "docs"
    / "data"
    / "latest"
    / "etfs.json"
)


PERIODS = {
    "1d": 1,
    "5d": 5,
    "20d": 20,
}


def configure_console():

    for stream in (
        sys.stdout,
        sys.stderr,
    ):

        fn = getattr(
            stream,
            "reconfigure",
            None,
        )

        if callable(fn):

            try:

                fn(
                    encoding="utf-8",
                    errors="replace",
                )

            except Exception:
                pass


def get_connection():

    load_dotenv(
        ENV_FILE
    )

    url = os.getenv(
        "TURSO_DEV_DATABASE_URL",
        "",
    ).strip()

    token = os.getenv(
        "TURSO_DEV_AUTH_TOKEN",
        "",
    ).strip()

    if not url:
        raise RuntimeError(
            "TURSO_DEV_DATABASE_URL missing"
        )

    if not token:
        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN missing"
        )

    lower_url = url.lower()

    if "stockwave-dev" not in lower_url:
        raise RuntimeError(
            "SAFETY STOP: DEV database required"
        )

    if "stockwave-prod" in lower_url:
        raise RuntimeError(
            "SAFETY STOP: PROD database detected"
        )

    return libsql.connect(
        database=url,
        auth_token=token,
    )


def fetch_all(
    cursor,
):

    rows = cursor.fetchall()

    return rows


def get_etf_master(
    conn,
):

    cursor = conn.execute(
        """
        SELECT
            etf_id,
            etf_name,
            issuer_name,
            source_type,
            source_url,
            active,
            sort_order
        FROM etf_master
        WHERE active = 1
        ORDER BY
            sort_order,
            etf_id
        """
    )

    result = []

    for row in fetch_all(
        cursor
    ):

        result.append(
            {
                "etf_id":
                    row[0],

                "etf_name":
                    row[1],

                "issuer_name":
                    row[2],

                "source_type":
                    row[3],

                "source_url":
                    row[4],

                "active":
                    row[5],

                "sort_order":
                    row[6],
            }
        )

    return result


def get_snapshot_dates(
    conn,
    etf_id: str,
    limit: int = 21,
):

    cursor = conn.execute(
        """
        SELECT DISTINCT
            trade_date
        FROM etf_holding_daily
        WHERE etf_id = ?
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        (
            etf_id,
            limit,
        ),
    )

    return [
        row[0]
        for row in fetch_all(
            cursor
        )
    ]


def get_holdings(
    conn,
    etf_id: str,
    trade_date: str,
):

    cursor = conn.execute(
        """
        SELECT
            stock_id,
            stock_name,
            shares,
            weight_pct,
            market_value,
            source_url
        FROM etf_holding_daily
        WHERE etf_id = ?
          AND trade_date = ?
        ORDER BY
            CASE
                WHEN weight_pct IS NULL
                THEN -1
                ELSE weight_pct
            END DESC,
            stock_id
        """,
        (
            etf_id,
            trade_date,
        ),
    )

    result = {}

    for row in fetch_all(
        cursor
    ):

        stock_id = str(
            row[0]
        ).strip()

        result[
            stock_id
        ] = {
            "stock_id":
                stock_id,

            "stock_name":
                row[1],

            "shares":
                row[2],

            "weight_pct":
                row[3],

            "market_value":
                row[4],

            "source_url":
                row[5],
        }

    return result


def determine_metric_type(
    current: dict,
    previous: dict,
):

    current_shares = (
        current.get(
            "shares"
        )
        if current
        else None
    )

    previous_shares = (
        previous.get(
            "shares"
        )
        if previous
        else None
    )

    if (
        current_shares is not None
        or previous_shares is not None
    ):

        if (
            current_shares is not None
            and previous_shares is not None
        ):
            return "SHARES"

    return "WEIGHT"


def classify_change(
    current: dict | None,
    previous: dict | None,
):

    if (
        current is not None
        and previous is None
    ):

        return {
            "change_type":
                "NEW",

            "metric_type":
                (
                    "SHARES"
                    if current.get(
                        "shares"
                    ) is not None
                    else "WEIGHT"
                ),

            "change_value":
                (
                    current.get(
                        "shares"
                    )
                    if current.get(
                        "shares"
                    ) is not None
                    else current.get(
                        "weight_pct"
                    )
                ),
        }

    if (
        current is None
        and previous is not None
    ):

        return {
            "change_type":
                "REMOVED",

            "metric_type":
                (
                    "SHARES"
                    if previous.get(
                        "shares"
                    ) is not None
                    else "WEIGHT"
                ),

            "change_value":
                (
                    -previous.get(
                        "shares"
                    )
                    if previous.get(
                        "shares"
                    ) is not None
                    else (
                        -previous.get(
                            "weight_pct"
                        )
                        if previous.get(
                            "weight_pct"
                        ) is not None
                        else None
                    )
                ),
        }

    if (
        current is None
        or previous is None
    ):

        raise RuntimeError(
            "Unexpected comparison state"
        )

    metric_type = (
        determine_metric_type(
            current,
            previous,
        )
    )

    if metric_type == "SHARES":

        current_value = (
            current.get(
                "shares"
            )
        )

        previous_value = (
            previous.get(
                "shares"
            )
        )

    else:

        current_value = (
            current.get(
                "weight_pct"
            )
        )

        previous_value = (
            previous.get(
                "weight_pct"
            )
        )

    if (
        current_value is None
        or previous_value is None
    ):

        change_value = None
        change_type = "UNCHANGED"

    else:

        change_value = (
            float(current_value)
            - float(previous_value)
        )

        epsilon = (
            0.5
            if metric_type == "SHARES"
            else 0.000001
        )

        if change_value > epsilon:

            change_type = (
                "INCREASE"
            )

        elif change_value < -epsilon:

            change_type = (
                "DECREASE"
            )

        else:

            change_type = (
                "UNCHANGED"
            )

    return {
        "change_type":
            change_type,

        "metric_type":
            metric_type,

        "change_value":
            change_value,
    }


def build_comparison(
    current_date: str,
    previous_date: str,
    current_holdings: dict,
    previous_holdings: dict,
):

    stock_ids = sorted(
        set(
            current_holdings.keys()
        )
        | set(
            previous_holdings.keys()
        )
    )

    changes = []

    for stock_id in stock_ids:

        current = (
            current_holdings.get(
                stock_id
            )
        )

        previous = (
            previous_holdings.get(
                stock_id
            )
        )

        change_info = (
            classify_change(
                current,
                previous,
            )
        )

        source = (
            current
            if current is not None
            else previous
        )

        current_shares = (
            current.get(
                "shares"
            )
            if current
            else None
        )

        previous_shares = (
            previous.get(
                "shares"
            )
            if previous
            else None
        )

        current_weight = (
            current.get(
                "weight_pct"
            )
            if current
            else None
        )

        previous_weight = (
            previous.get(
                "weight_pct"
            )
            if previous
            else None
        )

        shares_change = None

        if (
            current_shares is not None
            and previous_shares is not None
        ):

            shares_change = (
                float(current_shares)
                - float(previous_shares)
            )

        weight_change = None

        if (
            current_weight is not None
            and previous_weight is not None
        ):

            weight_change = (
                float(current_weight)
                - float(previous_weight)
            )

        changes.append(
            {
                "stock_id":
                    stock_id,

                "stock_name":
                    source.get(
                        "stock_name"
                    ),

                "change_type":
                    change_info[
                        "change_type"
                    ],

                "metric_type":
                    change_info[
                        "metric_type"
                    ],

                "change_value":
                    change_info[
                        "change_value"
                    ],

                "current_shares":
                    current_shares,

                "previous_shares":
                    previous_shares,

                "shares_change":
                    shares_change,

                "current_weight_pct":
                    current_weight,

                "previous_weight_pct":
                    previous_weight,

                "weight_change_pct":
                    weight_change,

                "current_market_value":
                    (
                        current.get(
                            "market_value"
                        )
                        if current
                        else None
                    ),

                "source_url":
                    source.get(
                        "source_url"
                    ),
            }
        )

    type_order = {
        "NEW": 1,
        "INCREASE": 2,
        "DECREASE": 3,
        "REMOVED": 4,
        "UNCHANGED": 5,
    }

    changes.sort(
        key=lambda x: (
            type_order.get(
                x[
                    "change_type"
                ],
                99,
            ),
            -abs(
                x[
                    "change_value"
                ]
                or 0
            ),
            x[
                "stock_id"
            ],
        )
    )

    summary = {
        "new":
            sum(
                1
                for x in changes
                if x[
                    "change_type"
                ] == "NEW"
            ),

        "increase":
            sum(
                1
                for x in changes
                if x[
                    "change_type"
                ] == "INCREASE"
            ),

        "decrease":
            sum(
                1
                for x in changes
                if x[
                    "change_type"
                ] == "DECREASE"
            ),

        "removed":
            sum(
                1
                for x in changes
                if x[
                    "change_type"
                ] == "REMOVED"
            ),

        "unchanged":
            sum(
                1
                for x in changes
                if x[
                    "change_type"
                ] == "UNCHANGED"
            ),
    }

    return {
        "available":
            True,

        "current_date":
            current_date,

        "previous_date":
            previous_date,

        "summary":
            summary,

        "changes":
            changes,
    }


def build_period(
    conn,
    etf_id: str,
    dates: list[str],
    offset: int,
):

    if len(
        dates
    ) <= offset:

        return {
            "available":
                False,

            "reason":
                "INSUFFICIENT_SNAPSHOTS",

            "required_snapshots":
                offset + 1,

            "available_snapshots":
                len(dates),

            "current_date":
                (
                    dates[0]
                    if dates
                    else None
                ),

            "previous_date":
                None,

            "summary":
                None,

            "changes":
                [],
        }

    current_date = (
        dates[0]
    )

    previous_date = (
        dates[offset]
    )

    current_holdings = get_holdings(
        conn,
        etf_id,
        current_date,
    )

    previous_holdings = get_holdings(
        conn,
        etf_id,
        previous_date,
    )

    return build_comparison(
        current_date,
        previous_date,
        current_holdings,
        previous_holdings,
    )


def build_latest_holdings(
    conn,
    etf_id: str,
    latest_date: str,
):

    holdings = get_holdings(
        conn,
        etf_id,
        latest_date,
    )

    rows = list(
        holdings.values()
    )

    rows.sort(
        key=lambda x: (
            -(
                x.get(
                    "weight_pct"
                )
                or 0
            ),
            x[
                "stock_id"
            ],
        )
    )

    return rows


def build_etf(
    conn,
    master: dict,
):

    etf_id = (
        master[
            "etf_id"
        ]
    )

    dates = get_snapshot_dates(
        conn,
        etf_id,
        21,
    )

    if not dates:

        return {
            **master,

            "latest_date":
                None,

            "snapshot_count":
                0,

            "snapshot_dates":
                [],

            "latest_holdings":
                [],

            "periods": {
                key: {
                    "available":
                        False,
                    "reason":
                        "NO_SNAPSHOT",
                    "changes":
                        [],
                }
                for key in PERIODS
            },
        }

    periods = {}

    for key, offset in (
        PERIODS.items()
    ):

        periods[
            key
        ] = build_period(
            conn,
            etf_id,
            dates,
            offset,
        )

    latest_holdings = (
        build_latest_holdings(
            conn,
            etf_id,
            dates[0],
        )
    )

    shares_available = (
        sum(
            1
            for row
            in latest_holdings
            if row.get(
                "shares"
            ) is not None
        )
    )

    weight_available = (
        sum(
            1
            for row
            in latest_holdings
            if row.get(
                "weight_pct"
            ) is not None
        )
    )

    default_metric = (
        "SHARES"
        if (
            shares_available
            == len(
                latest_holdings
            )
            and shares_available > 0
        )
        else "WEIGHT"
    )

    return {
        **master,

        "latest_date":
            dates[0],

        "snapshot_count":
            len(dates),

        "snapshot_dates":
            dates,

        "holding_count":
            len(
                latest_holdings
            ),

        "default_change_metric":
            default_metric,

        "shares_available_count":
            shares_available,

        "weight_available_count":
            weight_available,

        "latest_holdings":
            latest_holdings,

        "periods":
            periods,
    }


def build_consensus(
    etfs: list[dict],
    period_key: str,
):

    stocks = {}

    for etf in etfs:

        period = (
            etf.get(
                "periods",
                {},
            )
            .get(
                period_key,
                {},
            )
        )

        if not period.get(
            "available"
        ):
            continue

        for change in (
            period.get(
                "changes"
            )
            or []
        ):

            change_type = (
                change.get(
                    "change_type"
                )
            )

            if change_type not in (
                "NEW",
                "INCREASE",
                "DECREASE",
                "REMOVED",
            ):
                continue

            stock_id = (
                change[
                    "stock_id"
                ]
            )

            item = stocks.setdefault(
                stock_id,
                {
                    "stock_id":
                        stock_id,

                    "stock_name":
                        change.get(
                            "stock_name"
                        ),

                    "increase_etfs":
                        [],

                    "decrease_etfs":
                        [],
                },
            )

            etf_info = {
                "etf_id":
                    etf[
                        "etf_id"
                    ],

                "etf_name":
                    etf[
                        "etf_name"
                    ],

                "change_type":
                    change_type,

                "metric_type":
                    change.get(
                        "metric_type"
                    ),

                "change_value":
                    change.get(
                        "change_value"
                    ),
            }

            if change_type in (
                "NEW",
                "INCREASE",
            ):

                item[
                    "increase_etfs"
                ].append(
                    etf_info
                )

            elif change_type in (
                "DECREASE",
                "REMOVED",
            ):

                item[
                    "decrease_etfs"
                ].append(
                    etf_info
                )

    result = []

    for item in (
        stocks.values()
    ):

        item[
            "increase_count"
        ] = len(
            item[
                "increase_etfs"
            ]
        )

        item[
            "decrease_count"
        ] = len(
            item[
                "decrease_etfs"
            ]
        )

        item[
            "net_etf_count"
        ] = (
            item[
                "increase_count"
            ]
            - item[
                "decrease_count"
            ]
        )

        result.append(
            item
        )

    result.sort(
        key=lambda x: (
            -abs(
                x[
                    "net_etf_count"
                ]
            ),
            -(
                x[
                    "increase_count"
                ]
                + x[
                    "decrease_count"
                ]
            ),
            x[
                "stock_id"
            ],
        )
    )

    return result


def main():

    configure_console()

    print("=" * 70)

    print(
        "StockWaveScanner V3 - "
        "ETF Export"
    )

    print("=" * 70)

    conn = get_connection()

    try:

        masters = get_etf_master(
            conn
        )

        etfs = []

        for master in masters:

            print(
                f"[EXPORT] "
                f"{master['etf_id']} "
                f"{master['etf_name']}"
            )

            item = build_etf(
                conn,
                master,
            )

            etfs.append(
                item
            )

            print(
                f"    latest="
                f"{item.get('latest_date')} "
                f"snapshots="
                f"{item.get('snapshot_count')} "
                f"holdings="
                f"{item.get('holding_count', 0)}"
            )

        payload = {
            "schema_version":
                "v3-etf-1",

            "generated_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "note":
                (
                    "ETF change data represents "
                    "differences between official "
                    "holding snapshots. "
                    "It does not represent confirmed "
                    "market buy/sell transactions."
                ),

            "change_type_labels": {
                "NEW":
                    "新進",

                "INCREASE":
                    "持股增加",

                "DECREASE":
                    "持股減少",

                "REMOVED":
                    "剔除",

                "UNCHANGED":
                    "持平",
            },

            "metric_type_labels": {
                "SHARES":
                    "持股變化",

                "WEIGHT":
                    "權重變化",
            },

            "period_labels": {
                "1d":
                    "當日",

                "5d":
                    "近5日",

                "20d":
                    "近20日",
            },

            "etfs":
                etfs,

            "consensus": {
                "1d":
                    build_consensus(
                        etfs,
                        "1d",
                    ),

                "5d":
                    build_consensus(
                        etfs,
                        "5d",
                    ),

                "20d":
                    build_consensus(
                        etfs,
                        "20d",
                    ),
            },
        }

        OUTPUT_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        OUTPUT_FILE.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print()
        print(
            f"[PASS] {OUTPUT_FILE}"
        )

        print(
            f"ETF COUNT = "
            f"{len(etfs)}"
        )

        print(
            "ETF EXPORT OK"
        )

        print("=" * 70)

        return 0

    except Exception as exc:

        print()
        print("=" * 70)
        print("ERROR")
        print("=" * 70)

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return 1

    finally:

        conn.close()


if __name__ == "__main__":
    sys.exit(
        main()
    )