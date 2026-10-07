from __future__ import annotations

import json
import os
import sys

from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import libsql
from dotenv import load_dotenv


ROOT = Path(
    __file__
).resolve().parents[1]

ENV_FILE = (
    ROOT
    / ".env"
)

OUTPUT_FILE = (
    ROOT
    / "docs"
    / "data"
    / "latest"
    / "financial_holdings.json"
)


#
# UI 第一版先保留最近 24 個月。
#
# 足夠：
#
# 1. 最新資料
# 2. 近 12 月趨勢
# 3. 前一年同期觀察
#
# 避免元大金、國泰金多年歷史
# 全部塞進前端 JSON。
#
HISTORY_MONTHS = 24


#
# Master fallback。
#
# 正常情況會優先讀：
#
# financial_holding_master
#
# 但目前既有文件沒有完整記錄
# master table 的實際 column schema。
#
# 所以 exporter 不因 Master schema
# 小差異而無法輸出。
#
MASTER_FALLBACK = {
    "2880": {
        "stock_name": "華南金",
        "business_type": "BANK",
    },
    "2881": {
        "stock_name": "富邦金",
        "business_type": "INSURANCE",
    },
    "2882": {
        "stock_name": "國泰金",
        "business_type": "INSURANCE",
    },
    "2883": {
        "stock_name": "凱基金",
        "business_type": "MIXED",
    },
    "2884": {
        "stock_name": "玉山金",
        "business_type": "BANK",
    },
    "2885": {
        "stock_name": "元大金",
        "business_type": "SECURITIES",
    },
    "2886": {
        "stock_name": "兆豐金",
        "business_type": "BANK",
    },
    "2887": {
        "stock_name": "台新新光金",
        "business_type": "MIXED",
    },
    "2889": {
        "stock_name": "國票金",
        "business_type": "SECURITIES",
    },
    "2890": {
        "stock_name": "永豐金",
        "business_type": "BANK",
    },
    "2891": {
        "stock_name": "中信金",
        "business_type": "BANK",
    },
    "2892": {
        "stock_name": "第一金",
        "business_type": "BANK",
    },
    "5880": {
        "stock_name": "合庫金",
        "business_type": "BANK",
    },
}


BUSINESS_TYPE_LABELS = {
    "BANK": "銀行型",
    "INSURANCE": "壽險型",
    "SECURITIES": "證券型",
    "MIXED": "綜合型",
}


def configure_console():

    for stream in (
        sys.stdout,
        sys.stderr,
    ):

        reconfigure = getattr(
            stream,
            "reconfigure",
            None,
        )

        if callable(reconfigure):

            try:

                reconfigure(
                    encoding="utf-8",
                    errors="replace",
                )

            except Exception:
                pass


def get_connection():

    load_dotenv(
        ENV_FILE
    )

    database_url = (
        os.getenv(
            "TURSO_DEV_DATABASE_URL"
        )
        or ""
    ).strip()

    auth_token = (
        os.getenv(
            "TURSO_DEV_AUTH_TOKEN"
        )
        or ""
    ).strip()

    if not database_url:

        raise RuntimeError(
            "TURSO_DEV_DATABASE_URL "
            "is missing"
        )

    if not auth_token:

        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN "
            "is missing"
        )

    lower_url = (
        database_url.lower()
    )

    if (
        "stockwave-dev"
        not in lower_url
    ):

        raise RuntimeError(
            "SAFETY STOP: "
            "DEV database required"
        )

    if (
        "stockwave-prod"
        in lower_url
    ):

        raise RuntimeError(
            "SAFETY STOP: "
            "PROD database detected"
        )

    print(
        "[PASS] DEV database "
        "safety check"
    )

    return libsql.connect(
        database=database_url,
        auth_token=auth_token,
    )


def table_exists(
    conn,
    table_name,
):

    row = conn.execute(
        """
        SELECT
            name
        FROM sqlite_master
        WHERE
            type = 'table'
            AND name = ?
        LIMIT 1
        """,
        (
            table_name,
        ),
    ).fetchone()

    return (
        row is not None
    )


def get_table_columns(
    conn,
    table_name,
):

    rows = conn.execute(
        f"""
        PRAGMA table_info(
            {table_name}
        )
        """
    ).fetchall()

    return [
        str(
            row[1]
        )
        for row in rows
    ]


def find_column(
    columns,
    candidates,
):

    lookup = {
        column.lower():
        column
        for column in columns
    }

    for candidate in candidates:

        match = lookup.get(
            candidate.lower()
        )

        if match:
            return match

    return None


def load_master(
    conn,
):

    #
    # 先建立 fallback。
    #
    master = {
        stock_id: {
            "stock_id": stock_id,
            "stock_name": item[
                "stock_name"
            ],
            "business_type": item[
                "business_type"
            ],
        }
        for (
            stock_id,
            item,
        )
        in MASTER_FALLBACK.items()
    }

    if not table_exists(
        conn,
        "financial_holding_master",
    ):

        print(
            "[WARN] "
            "financial_holding_master "
            "not found; "
            "using documented fallback"
        )

        return master

    columns = get_table_columns(
        conn,
        "financial_holding_master",
    )

    stock_id_column = (
        find_column(
            columns,
            [
                "stock_id",
                "stock_code",
            ],
        )
    )

    stock_name_column = (
        find_column(
            columns,
            [
                "stock_name",
                "short_name",
                "name",
            ],
        )
    )

    business_type_column = (
        find_column(
            columns,
            [
                "business_type",
                "holding_type",
                "type",
            ],
        )
    )

    if not stock_id_column:

        print(
            "[WARN] "
            "financial_holding_master "
            "has no recognized "
            "stock_id column; "
            "using fallback"
        )

        return master

    select_parts = [
        stock_id_column,
    ]

    if stock_name_column:

        select_parts.append(
            stock_name_column
        )

    if business_type_column:

        select_parts.append(
            business_type_column
        )

    sql = (
        "SELECT "
        + ", ".join(
            select_parts
        )
        + " FROM "
        + "financial_holding_master"
    )

    rows = conn.execute(
        sql
    ).fetchall()

    for row in rows:

        index = 0

        stock_id = str(
            row[index]
        )

        index += 1

        if (
            stock_id
            not in master
        ):

            #
            # Financial Holding V1
            # 只輸出正式 13 家。
            #
            continue

        if stock_name_column:

            stock_name = (
                row[index]
            )

            index += 1

            if stock_name:

                master[
                    stock_id
                ][
                    "stock_name"
                ] = str(
                    stock_name
                )

        if business_type_column:

            business_type = (
                row[index]
            )

            if business_type:

                master[
                    stock_id
                ][
                    "business_type"
                ] = (
                    str(
                        business_type
                    )
                    .upper()
                )

    print(
        "[PASS] "
        "financial_holding_master "
        "loaded"
    )

    return master


def load_monthly_rows(
    conn,
):

    rows = conn.execute(
        """
        SELECT
            stock_id,
            data_month,
            monthly_net_profit,
            ytd_net_profit,
            ytd_eps,
            previous_year_ytd_net_profit,
            ytd_profit_yoy_pct,
            source_date,
            source_url,
            data_status
        FROM
            financial_holding_monthly
        ORDER BY
            stock_id,
            data_month
        """
    ).fetchall()

    result = []

    for row in rows:

        result.append(
            {
                "stock_id": (
                    str(
                        row[0]
                    )
                ),
                "data_month": (
                    row[1]
                ),
                "monthly_net_profit": (
                    row[2]
                ),
                "ytd_net_profit": (
                    row[3]
                ),
                "ytd_eps": (
                    row[4]
                ),
                "previous_year_ytd_net_profit": (
                    row[5]
                ),
                "ytd_profit_yoy_pct": (
                    row[6]
                ),
                "source_date": (
                    row[7]
                ),
                "source_url": (
                    row[8]
                ),
                "data_status": (
                    row[9]
                ),
            }
        )

    return result


def group_monthly_rows(
    rows,
):

    grouped = {}

    for row in rows:

        stock_id = row[
            "stock_id"
        ]

        grouped.setdefault(
            stock_id,
            [],
        ).append(
            row
        )

    return grouped


def build_coverage(
    rows,
):

    if not rows:

        return {
            "row_count": 0,
            "first_month": None,
            "last_month": None,
            "monthly_count": 0,
            "ytd_count": 0,
            "eps_count": 0,
            "yoy_count": 0,
        }

    return {
        "row_count": len(
            rows
        ),
        "first_month": rows[
            0
        ][
            "data_month"
        ],
        "last_month": rows[
            -1
        ][
            "data_month"
        ],
        "monthly_count": sum(
            1
            for row in rows
            if (
                row[
                    "monthly_net_profit"
                ]
                is not None
            )
        ),
        "ytd_count": sum(
            1
            for row in rows
            if (
                row[
                    "ytd_net_profit"
                ]
                is not None
            )
        ),
        "eps_count": sum(
            1
            for row in rows
            if (
                row[
                    "ytd_eps"
                ]
                is not None
            )
        ),
        "yoy_count": sum(
            1
            for row in rows
            if (
                row[
                    "ytd_profit_yoy_pct"
                ]
                is not None
            )
        ),
    }


def build_holding(
    master_row,
    rows,
):

    stock_id = master_row[
        "stock_id"
    ]

    business_type = (
        master_row.get(
            "business_type"
        )
        or "UNKNOWN"
    )

    rows = sorted(
        rows,
        key=lambda item:
            item[
                "data_month"
            ]
            or "",
    )

    latest = (
        rows[-1]
        if rows
        else None
    )

    history = (
        rows[
            -HISTORY_MONTHS:
        ]
        if rows
        else []
    )

    return {
        "stock_id": stock_id,
        "stock_name": (
            master_row.get(
                "stock_name"
            )
        ),
        "business_type": (
            business_type
        ),
        "business_type_label": (
            BUSINESS_TYPE_LABELS.get(
                business_type,
                business_type,
            )
        ),
        "latest": (
            latest
        ),
        "coverage": (
            build_coverage(
                rows
            )
        ),
        "history": (
            history
        ),
    }


def latest_month(
    holdings,
):

    months = [
        holding[
            "latest"
        ][
            "data_month"
        ]
        for holding in holdings
        if (
            holding[
                "latest"
            ]
            is not None
            and
            holding[
                "latest"
            ].get(
                "data_month"
            )
        )
    ]

    if not months:
        return None

    return max(
        months
    )


def build_summary(
    holdings,
):

    latest_data_month = (
        latest_month(
            holdings
        )
    )

    latest_period_holdings = [
        holding
        for holding in holdings
        if (
            holding.get(
                "latest"
            )
            is not None
            and
            holding[
                "latest"
            ].get(
                "data_month"
            )
            == latest_data_month
        )
    ]

    latest_period_monthly_count = 0
    latest_period_ytd_count = 0
    latest_period_eps_count = 0
    latest_period_yoy_count = 0

    latest_period_positive_yoy_count = 0
    latest_period_negative_yoy_count = 0
    latest_period_flat_yoy_count = 0

    type_distribution = {
        "BANK": 0,
        "INSURANCE": 0,
        "SECURITIES": 0,
        "MIXED": 0,
        "UNKNOWN": 0,
    }

    for holding in holdings:

        business_type = (
            holding.get(
                "business_type"
            )
            or "UNKNOWN"
        )

        if (
            business_type
            not in type_distribution
        ):

            type_distribution[
                business_type
            ] = 0

        type_distribution[
            business_type
        ] += 1

    for holding in latest_period_holdings:

        latest = holding.get(
            "latest"
        )

        if not latest:
            continue

        if (
            latest.get(
                "monthly_net_profit"
            )
            is not None
        ):

            latest_period_monthly_count += 1

        if (
            latest.get(
                "ytd_net_profit"
            )
            is not None
        ):

            latest_period_ytd_count += 1

        if (
            latest.get(
                "ytd_eps"
            )
            is not None
        ):

            latest_period_eps_count += 1

        yoy = latest.get(
            "ytd_profit_yoy_pct"
        )

        if yoy is None:
            continue

        latest_period_yoy_count += 1

        if yoy > 0:

            latest_period_positive_yoy_count += 1

        elif yoy < 0:

            latest_period_negative_yoy_count += 1

        else:

            latest_period_flat_yoy_count += 1

    return {
        "holding_count": len(
            holdings
        ),

        "latest_data_month": (
            latest_data_month
        ),

        "latest_period_holding_count": (
            len(
                latest_period_holdings
            )
        ),

        "latest_period_monthly_count": (
            latest_period_monthly_count
        ),

        "latest_period_ytd_count": (
            latest_period_ytd_count
        ),

        "latest_period_eps_count": (
            latest_period_eps_count
        ),

        "latest_period_yoy_count": (
            latest_period_yoy_count
        ),

        "latest_period_positive_yoy_count": (
            latest_period_positive_yoy_count
        ),

        "latest_period_negative_yoy_count": (
            latest_period_negative_yoy_count
        ),

        "latest_period_flat_yoy_count": (
            latest_period_flat_yoy_count
        ),

        "type_distribution": (
            type_distribution
        ),
    }
    

def build_payload(
    master,
    monthly_rows,
):

    grouped = group_monthly_rows(
        monthly_rows
    )

    holdings = []

    for stock_id in sorted(
        master.keys()
    ):

        holding = build_holding(
            master[
                stock_id
            ],
            grouped.get(
                stock_id,
                [],
            ),
        )

        holdings.append(
            holding
        )

    return {
        "generated_at": (
            datetime.now(
                timezone.utc
            )
            .isoformat(
                timespec="seconds"
            )
        ),
        "history_months": (
            HISTORY_MONTHS
        ),
        "summary": (
            build_summary(
                holdings
            )
        ),
        "holdings": (
            holdings
        ),
    }


def write_json(
    payload,
):

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
        newline="\n",
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


def print_summary(
    payload,
):

    summary = payload[
        "summary"
    ]

    print()
    print("=" * 78)
    print(
        "FINANCIAL HOLDING EXPORT SUMMARY"
    )
    print("=" * 78)

    print(
        "Holdings      :",
        summary[
            "holding_count"
        ],
    )

    print(
        "Latest month  :",
        summary[
            "latest_data_month"
        ],
    )

    print(
        "Latest period :",
        summary[
            "latest_period_holding_count"
        ],
    )

    print(
        "Latest Monthly:",
        summary[
            "latest_period_monthly_count"
        ],
    )

    print(
        "Latest YTD    :",
        summary[
            "latest_period_ytd_count"
        ],
    )

    print(
        "Latest EPS    :",
        summary[
            "latest_period_eps_count"
        ],
    )

    print(
        "Latest YoY    :",
        summary[
            "latest_period_yoy_count"
        ],
    )

    print(
        "YoY Positive  :",
        summary[
            "latest_period_positive_yoy_count"
        ],
    )

    print(
        "YoY Negative  :",
        summary[
            "latest_period_negative_yoy_count"
        ],
    )

    print(
        "YoY Flat      :",
        summary[
            "latest_period_flat_yoy_count"
        ],
    )    

    print()
    print(
        "TYPE DISTRIBUTION"
    )

    for (
        business_type,
        count,
    ) in (
        summary[
            "type_distribution"
        ].items()
    ):

        print(
            f"  "
            f"{business_type:<12}"
            f"{count}"
        )

    print()
    print(
        "HOLDING COVERAGE"
    )

    print(
        "-" * 78
    )

    print(
        f"{'Stock':<14}"
        f"{'Range':<22}"
        f"{'Rows':>6}"
        f"{'Monthly':>10}"
        f"{'YTD':>7}"
        f"{'EPS':>7}"
        f"{'YoY':>7}"
    )

    print(
        "-" * 78
    )

    for holding in payload[
        "holdings"
    ]:

        coverage = holding[
            "coverage"
        ]

        first_month = (
            coverage[
                "first_month"
            ]
            or "--"
        )

        last_month = (
            coverage[
                "last_month"
            ]
            or "--"
        )

        month_range = (
            f"{first_month}"
            f"~"
            f"{last_month}"
        )

        stock_text = (
            f"{holding['stock_id']} "
            f"{holding['stock_name']}"
        )

        print(
            f"{stock_text:<14}"
            f"{month_range:<22}"
            f"{coverage['row_count']:>6}"
            f"{coverage['monthly_count']:>10}"
            f"{coverage['ytd_count']:>7}"
            f"{coverage['eps_count']:>7}"
            f"{coverage['yoy_count']:>7}"
        )

    print(
        "=" * 78
    )


def main():

    configure_console()

    print(
        "=" * 78
    )

    print(
        "StockWaveScanner V3 - "
        "Export Financial Holdings"
    )

    print(
        "=" * 78
    )

    conn = get_connection()

    try:

        master = load_master(
            conn
        )

        monthly_rows = (
            load_monthly_rows(
                conn
            )
        )

    finally:

        conn.close()

    if not monthly_rows:

        raise RuntimeError(
            "financial_holding_monthly "
            "has no data"
        )

    payload = build_payload(
        master,
        monthly_rows,
    )

    write_json(
        payload
    )

    print_summary(
        payload
    )

    print()
    print(
        "[PASS] Exported:"
    )

    print(
        OUTPUT_FILE
    )

    print()
    print(
        "FINANCIAL HOLDING EXPORT OK"
    )

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )