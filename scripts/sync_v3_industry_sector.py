from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import libsql
from dotenv import load_dotenv


# ============================================================
# CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

SECTOR_SOURCE = "OFFICIAL_INDUSTRY"


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


def normalize_text(
    value: Any,
) -> str | None:

    if value is None:

        return None

    text = (
        str(
            value
        )
        .strip()
    )

    if not text:

        return None

    return text


def build_sector_id(
    market: str,
    industry_code: str,
) -> str:

    return (
        "INDUSTRY:"
        f"{market}:"
        f"{industry_code}"
    )


# ============================================================
# LOAD STOCK MASTER
# ============================================================


def load_stock_industries(
    conn,
) -> list[dict[str, str]]:

    rows = (
        conn.execute(
            """
            SELECT

                stock_id,
                market,
                industry_code,
                industry_name

            FROM stock_master

            WHERE is_active = 1

              AND security_type =
                  'COMMON_STOCK'

              AND industry_code IS NOT NULL
              AND TRIM(industry_code) <> ''

              AND industry_name IS NOT NULL
              AND TRIM(industry_name) <> ''

            ORDER BY
                market,
                industry_code,
                stock_id
            """
        )
        .fetchall()
    )

    result: list[
        dict[
            str,
            str
        ]
    ] = []

    for row in rows:

        stock_id = normalize_text(
            row[0]
        )

        market = normalize_text(
            row[1]
        )

        industry_code = normalize_text(
            row[2]
        )

        industry_name = normalize_text(
            row[3]
        )

        if (
            stock_id is None
            or
            market is None
            or
            industry_code is None
            or
            industry_name is None
        ):

            continue

        result.append(
            {
                "stock_id":
                    stock_id,

                "market":
                    market,

                "industry_code":
                    industry_code,

                "industry_name":
                    industry_name,

                "sector_id":
                    build_sector_id(
                        market,
                        industry_code,
                    ),
            }
        )

    return result


# ============================================================
# BUILD INDUSTRY MASTER
# ============================================================


def build_industry_master(
    stocks: list[
        dict[
            str,
            str
        ]
    ],
) -> list[
    dict[
        str,
        str
    ]
]:

    result: dict[
        str,
        dict[
            str,
            str
        ]
    ] = {}

    for stock in stocks:

        sector_id = (
            stock[
                "sector_id"
            ]
        )

        result[
            sector_id
        ] = {

            "sector_id":
                sector_id,

            "sector_name":
                stock[
                    "industry_name"
                ],

            "sector_type":
                "INDUSTRY",

            "market":
                stock[
                    "market"
                ],

            "industry_code":
                stock[
                    "industry_code"
                ],
        }

    rows = list(
        result.values()
    )

    rows.sort(
        key=lambda item: (
            item[
                "market"
            ],
            item[
                "industry_code"
            ],
        )
    )

    return rows


# ============================================================
# UPSERT SECTOR MASTER
# ============================================================


def upsert_sector_master(
    conn,
    sectors: list[
        dict[
            str,
            str
        ]
    ],
) -> None:

    for sector in sectors:

        conn.execute(
            """
            INSERT INTO sector_master (

                sector_id,
                sector_name,
                sector_type,
                parent_sector_id,
                source,
                sort_order,
                active,
                created_at,
                updated_at

            )
            VALUES (

                ?,
                ?,
                'INDUSTRY',
                NULL,
                ?,
                ?,
                1,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP

            )

            ON CONFLICT(sector_id)
            DO UPDATE SET

                sector_name =
                    excluded.sector_name,

                sector_type =
                    excluded.sector_type,

                source =
                    excluded.source,

                sort_order =
                    excluded.sort_order,

                active =
                    1,

                updated_at =
                    CURRENT_TIMESTAMP
            """,
            (
                sector[
                    "sector_id"
                ],

                sector[
                    "sector_name"
                ],

                SECTOR_SOURCE,

                int(
                    sector[
                        "industry_code"
                    ]
                )
                if sector[
                    "industry_code"
                ].isdigit()
                else 9999,
            ),
        )


# ============================================================
# UPSERT STOCK SECTOR REL
# ============================================================


def upsert_stock_sector_rel(
    conn,
    stocks: list[
        dict[
            str,
            str
        ]
    ],
) -> None:

    conn.execute(
        """
        DELETE FROM stock_sector_rel

        WHERE source = ?
        """,
        (
            SECTOR_SOURCE,
        ),
    )

    for stock in stocks:

        conn.execute(
            """
            INSERT INTO stock_sector_rel (

                stock_id,
                sector_id,
                is_primary,
                source,
                effective_date,
                created_at,
                updated_at

            )
            VALUES (

                ?,
                ?,
                1,
                ?,
                DATE('now'),
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP

            )

            ON CONFLICT(
                stock_id,
                sector_id
            )
            DO UPDATE SET

                is_primary =
                    1,

                source =
                    excluded.source,

                effective_date =
                    excluded.effective_date,

                updated_at =
                    CURRENT_TIMESTAMP
            """,
            (
                stock[
                    "stock_id"
                ],

                stock[
                    "sector_id"
                ],

                SECTOR_SOURCE,
            ),
        )


# ============================================================
# DEACTIVATE OLD INDUSTRY SECTORS
# ============================================================


def deactivate_missing_industry_sectors(
    conn,
    sectors: list[
        dict[
            str,
            str
        ]
    ],
) -> None:

    active_ids = {
        sector[
            "sector_id"
        ]
        for sector
        in sectors
    }

    rows = (
        conn.execute(
            """
            SELECT sector_id

            FROM sector_master

            WHERE sector_type = 'INDUSTRY'
              AND source = ?
            """,
            (
                SECTOR_SOURCE,
            ),
        )
        .fetchall()
    )

    for row in rows:

        sector_id = str(
            row[0]
        )

        if sector_id in active_ids:

            continue

        conn.execute(
            """
            UPDATE sector_master

            SET
                active = 0,
                updated_at =
                    CURRENT_TIMESTAMP

            WHERE sector_id = ?
            """,
            (
                sector_id,
            ),
        )


# ============================================================
# SYNC
# ============================================================


def sync_industry_sectors(
    conn,
) -> tuple[
    int,
    int,
]:

    stocks = (
        load_stock_industries(
            conn
        )
    )

    if not stocks:

        raise RuntimeError(
            "No stock industry data found in stock_master"
        )

    sectors = (
        build_industry_master(
            stocks
        )
    )

    conn.execute(
        "BEGIN"
    )

    try:

        upsert_sector_master(
            conn,
            sectors,
        )

        deactivate_missing_industry_sectors(
            conn,
            sectors,
        )

        upsert_stock_sector_rel(
            conn,
            stocks,
        )

        conn.commit()

    except BaseException:

        try:

            conn.rollback()

        except Exception:
            pass

        raise

    return (
        len(
            sectors
        ),
        len(
            stocks
        ),
    )


# ============================================================
# VERIFY
# ============================================================


def verify(
    conn,
) -> None:

    sector_count = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)

            FROM sector_master

            WHERE sector_type = 'INDUSTRY'
              AND source = ?
              AND active = 1
            """,
            (
                SECTOR_SOURCE,
            ),
        )
        or 0
    )

    relation_count = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)

            FROM stock_sector_rel

            WHERE source = ?
              AND is_primary = 1
            """,
            (
                SECTOR_SOURCE,
            ),
        )
        or 0
    )

    stock_with_industry_count = int(
        scalar(
            conn,
            """
            SELECT COUNT(*)

            FROM stock_master

            WHERE is_active = 1

              AND security_type =
                  'COMMON_STOCK'

              AND industry_code IS NOT NULL
              AND TRIM(industry_code) <> ''

              AND industry_name IS NOT NULL
              AND TRIM(industry_name) <> ''
            """
        )
        or 0
    )

    print()

    print(
        "=" * 70
    )

    print(
        "V3 INDUSTRY SECTOR VERIFICATION"
    )

    print(
        "=" * 70
    )

    print(
        f"Active Industry Sectors : "
        f"{sector_count:,}"
    )

    print(
        f"Stock Relations         : "
        f"{relation_count:,}"
    )

    print(
        f"Stock Master Industry   : "
        f"{stock_with_industry_count:,}"
    )

    if (
        relation_count
        !=
        stock_with_industry_count
    ):

        raise RuntimeError(
            "Stock-sector relation count mismatch"
        )

    rows = (
        conn.execute(
            """
            SELECT

                s.sector_id,
                s.sector_name,
                COUNT(r.stock_id) AS stock_count

            FROM sector_master s

            LEFT JOIN stock_sector_rel r

                ON r.sector_id =
                   s.sector_id

               AND r.source = ?

            WHERE s.sector_type =
                  'INDUSTRY'

              AND s.source = ?

              AND s.active = 1

            GROUP BY

                s.sector_id,
                s.sector_name

            ORDER BY

                stock_count DESC,
                s.sector_id

            LIMIT 20
            """,
            (
                SECTOR_SOURCE,
                SECTOR_SOURCE,
            ),
        )
        .fetchall()
    )

    print()

    print(
        "Industry Sample:"
    )

    for row in rows:

        print(
            f"  {row[0]:<20} "
            f"| {row[1]:<16} "
            f"| stocks={int(row[2]):,}"
        )

    print()

    print(
        "[PASS] Official industry sectors synchronized"
    )


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    configure_console()

    print(
        "=" * 70
    )

    print(
        "StockWaveScanner V3 - Official Industry Sector Sync"
    )

    print(
        "=" * 70
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

            print(
                "[PASS] Turso DEV connection"
            )

            print()

            print(
                "Synchronizing official industry sectors ..."
            )

            (
                sector_count,
                relation_count,
            ) = sync_industry_sectors(
                conn
            )

            print(
                "[PASS] Synchronization completed"
            )

            print(
                f"Industry Sectors : "
                f"{sector_count:,}"
            )

            print(
                f"Stock Relations  : "
                f"{relation_count:,}"
            )

            verify(
                conn
            )

        finally:

            conn.close()

        print()

        print(
            "=" * 70
        )

        print(
            "V3 INDUSTRY SECTOR SYNC OK"
        )

        print(
            "=" * 70
        )

        print()

        print(
            "No PROD database was accessed."
        )

        return 0

    except Exception as exc:

        print()

        print(
            "=" * 70
        )

        print(
            "ERROR"
        )

        print(
            "=" * 70
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