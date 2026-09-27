from __future__ import annotations

import json
import os
import sys
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

OUTPUT_FILE = (
    OUTPUT_DIR
    / "sectors.json"
)

MODEL_VERSION = "V3-SECTOR-RESEARCH-1"

TAIPEI = ZoneInfo(
    "Asia/Taipei"
)


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


def safe_float(
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


def write_json(
    payload: dict[str, Any],
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
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
        f"[WRITE] {OUTPUT_FILE}"
    )


# ============================================================
# DATE
# ============================================================


def load_latest_trade_date(
    conn,
) -> str:

    value = scalar(
        conn,
        """
        SELECT MAX(trade_date)

        FROM sector_snapshot_daily
        """,
    )

    if value is None:

        raise RuntimeError(
            "sector_snapshot_daily is empty"
        )

    return str(
        value
    )


# ============================================================
# SECTOR ROWS
# ============================================================


def load_sector_rows(
    conn,
    trade_date: str,
) -> list[
    dict[str, Any]
]:

    rows = (
        conn.execute(
            """
            SELECT

                s.sector_id,
                s.sector_name,
                s.sector_type,
                s.parent_sector_id,
                s.source,

                d.trade_date,

                d.stock_count,
                d.up_count,
                d.down_count,

                d.above_ma20_count,
                d.new_high_count,

                d.foreign_net,
                d.trust_net,
                d.dealer_net,

                d.large_holder_change,

                d.sector_return_1d,
                d.sector_return_5d,
                d.sector_return_20d,

                d.breadth_score,
                d.technical_score,

                d.status,
                d.model_version

            FROM sector_master s

            INNER JOIN sector_snapshot_daily d

                ON d.sector_id =
                   s.sector_id

            WHERE s.active = 1

              AND s.sector_type =
                  'INDUSTRY'

              AND d.trade_date = ?

            ORDER BY

                d.technical_score DESC,
                d.breadth_score DESC,
                s.sector_name
            """,
            (
                trade_date,
            ),
        )
        .fetchall()
    )

    result = []

    for row in rows:

        stock_count = (
            safe_int(
                row[6]
            )
            or 0
        )

        up_count = (
            safe_int(
                row[7]
            )
            or 0
        )

        down_count = (
            safe_int(
                row[8]
            )
            or 0
        )

        above_ma20_count = (
            safe_int(
                row[9]
            )
            or 0
        )

        new_high_count = (
            safe_int(
                row[10]
            )
            or 0
        )

        up_ratio = (
            round(
                up_count
                /
                stock_count
                *
                100.0,
                2,
            )
            if stock_count > 0
            else None
        )

        above_ma20_ratio = (
            round(
                above_ma20_count
                /
                stock_count
                *
                100.0,
                2,
            )
            if stock_count > 0
            else None
        )

        new_high_ratio = (
            round(
                new_high_count
                /
                stock_count
                *
                100.0,
                2,
            )
            if stock_count > 0
            else None
        )

        result.append(
            {
                "rank":
                    len(
                        result
                    )
                    + 1,

                "sector_id":
                    str(
                        row[0]
                    ),

                "sector_name":
                    str(
                        row[1]
                    ),

                "sector_type":
                    str(
                        row[2]
                    ),

                "parent_sector_id":
                    (
                        None
                        if row[3] is None
                        else str(
                            row[3]
                        )
                    ),

                "source":
                    (
                        None
                        if row[4] is None
                        else str(
                            row[4]
                        )
                    ),

                "trade_date":
                    str(
                        row[5]
                    ),

                "stock_count":
                    stock_count,

                "up_count":
                    up_count,

                "down_count":
                    down_count,

                "up_ratio_pct":
                    up_ratio,

                "above_ma20_count":
                    above_ma20_count,

                "above_ma20_ratio_pct":
                    above_ma20_ratio,

                "new_high_count":
                    new_high_count,

                "new_high_ratio_pct":
                    new_high_ratio,

                "institutional":
                    {
                        "foreign_net":
                            safe_int(
                                row[11]
                            ),

                        "trust_net":
                            safe_int(
                                row[12]
                            ),

                        "dealer_net":
                            safe_int(
                                row[13]
                            ),
                    },

                "large_holder_change":
                    safe_float(
                        row[14]
                    ),

                "returns":
                    {
                        "return_1d_pct":
                            safe_float(
                                row[15]
                            ),

                        "return_5d_pct":
                            safe_float(
                                row[16]
                            ),

                        "return_20d_pct":
                            safe_float(
                                row[17]
                            ),
                    },

                "breadth_score":
                    safe_float(
                        row[18]
                    ),

                "technical_score":
                    safe_float(
                        row[19]
                    ),

                "status":
                    str(
                        row[20]
                        or
                        "WAITING_DATA"
                    ),

                "model_version":
                    (
                        None
                        if row[21] is None
                        else str(
                            row[21]
                        )
                    ),
            }
        )

    return result


# ============================================================
# STOCK MEMBERS
# ============================================================


def load_sector_members(
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

                r.sector_id,

                m.stock_id,
                m.short_name,
                m.market,
                m.industry_code,
                m.industry_name

            FROM stock_sector_rel r

            INNER JOIN stock_master m

                ON m.stock_id =
                   r.stock_id

            INNER JOIN sector_master s

                ON s.sector_id =
                   r.sector_id

            WHERE r.is_primary = 1

              AND m.is_active = 1

              AND s.active = 1

              AND s.sector_type =
                  'INDUSTRY'

            ORDER BY

                r.sector_id,
                m.stock_id
            """
        )
        .fetchall()
    )

    result: dict[
        str,
        list[
            dict[str, Any]
        ],
    ] = {}

    for row in rows:

        sector_id = str(
            row[0]
        )

        if sector_id not in result:

            result[
                sector_id
            ] = []

        result[
            sector_id
        ].append(
            {
                "stock_id":
                    str(
                        row[1]
                    ),

                "short_name":
                    str(
                        row[2]
                        or
                        ""
                    ),

                "market":
                    str(
                        row[3]
                        or
                        ""
                    ),

                "industry_code":
                    (
                        None
                        if row[4] is None
                        else str(
                            row[4]
                        )
                    ),

                "industry_name":
                    (
                        None
                        if row[5] is None
                        else str(
                            row[5]
                        )
                    ),
            }
        )

    return result


# ============================================================
# SUMMARY
# ============================================================


def build_summary(
    sectors: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:

    status_count = {

        "STRONG":
            0,

        "IMPROVING":
            0,

        "NEUTRAL":
            0,

        "WEAK":
            0,

        "WAITING_DATA":
            0,
    }

    for sector in sectors:

        status = str(
            sector.get(
                "status",
                "WAITING_DATA",
            )
        )

        if status not in status_count:

            status_count[
                status
            ] = 0

        status_count[
            status
        ] += 1

    top_strong = [
        {
            "sector_id":
                item[
                    "sector_id"
                ],

            "sector_name":
                item[
                    "sector_name"
                ],

            "technical_score":
                item[
                    "technical_score"
                ],

            "breadth_score":
                item[
                    "breadth_score"
                ],

            "return_5d_pct":
                item[
                    "returns"
                ].get(
                    "return_5d_pct"
                ),
        }

        for item
        in sectors[:5]
    ]

    return {

        "sector_count":
            len(
                sectors
            ),

        "status_distribution":
            status_count,

        "top_strong":
            top_strong,
    }


# ============================================================
# BUILD PAYLOAD
# ============================================================


def build_payload(
    conn,
) -> dict[str, Any]:

    trade_date = (
        load_latest_trade_date(
            conn
        )
    )

    sectors = (
        load_sector_rows(
            conn,
            trade_date,
        )
    )

    if not sectors:

        raise RuntimeError(
            "No sector rows found for latest trade date"
        )

    members = (
        load_sector_members(
            conn
        )
    )

    for sector in sectors:

        sector_id = (
            sector[
                "sector_id"
            ]
        )

        sector[
            "members"
        ] = (
            members.get(
                sector_id,
                [],
            )
        )

    summary = (
        build_summary(
            sectors
        )
    )

    return {

        "model_version":
            MODEL_VERSION,

        "data_date":
            trade_date,

        "generated_at":
            now_taipei_iso(),

        "status":
            "READY",

        "summary":
            summary,

        "sectors":
            sectors,
    }


# ============================================================
# VERIFY
# ============================================================


def verify_payload(
    payload: dict[str, Any],
) -> None:

    sectors = (
        payload.get(
            "sectors"
        )
        or []
    )

    if not sectors:

        raise RuntimeError(
            "Generated sectors payload is empty"
        )

    print()

    print(
        "=" * 80
    )

    print(
        "V3 SECTOR JSON VERIFICATION"
    )

    print(
        "=" * 80
    )

    print(
        f"Data Date    : "
        f"{payload.get('data_date')}"
    )

    print(
        f"Sector Count : "
        f"{len(sectors):,}"
    )

    print()

    print(
        "Top Sector:"
    )

    for item in sectors[:10]:

        returns = (
            item.get(
                "returns"
            )
            or {}
        )

        institutional = (
            item.get(
                "institutional"
            )
            or {}
        )

        print(
            f"  #{item.get('rank')} "
            f"{item.get('sector_name')} "
            f"| tech={item.get('technical_score')} "
            f"| breadth={item.get('breadth_score')} "
            f"| 1D={returns.get('return_1d_pct')} "
            f"| 5D={returns.get('return_5d_pct')} "
            f"| 20D={returns.get('return_20d_pct')} "
            f"| foreign={institutional.get('foreign_net')} "
            f"| trust={institutional.get('trust_net')} "
            f"| {item.get('status')}"
        )

    print()

    print(
        "[PASS] V3 sectors.json ready"
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
        "StockWaveScanner V3 - Sector JSON Export"
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

            test = (
                conn.execute(
                    "SELECT 1"
                )
                .fetchone()
            )

            if (
                not test
                or
                test[0] != 1
            ):

                raise RuntimeError(
                    "Turso DEV connection validation failed"
                )

            payload = (
                build_payload(
                    conn
                )
            )

        finally:

            conn.close()

        verify_payload(
            payload
        )

        write_json(
            payload
        )

        print()

        print(
            "=" * 80
        )

        print(
            "V3 SECTOR JSON EXPORT OK"
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