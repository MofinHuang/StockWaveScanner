from __future__ import annotations

import os
import sys
from pathlib import Path

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


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

        if callable(reconfigure):
            try:
                reconfigure(
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception:
                pass


def load_dev_credentials() -> tuple[str, str]:
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

    lower_url = url.lower()

    if "stockwave-dev" not in lower_url:
        raise RuntimeError(
            "SAFETY STOP: database is not stockwave-dev"
        )

    if "stockwave-prod" in lower_url:
        raise RuntimeError(
            "SAFETY STOP: PROD database detected"
        )

    return (
        url,
        token,
    )


ANALYSTS = [
    (
        "A001",
        "鐘崑禎",
        "鐘崑禎",
        "摩爾證券投資顧問股份有限公司",
        1,
    ),
    (
        "A002",
        "王倚隆",
        "王倚隆（老王）",
        "浦惠證券投資顧問股份有限公司",
        2,
    ),
    (
        "A003",
        "黎志建",
        "黎志建（Vic）",
        "浦惠證券投資顧問股份有限公司",
        3,
    ),
    (
        "A004",
        "陳於晨",
        "陳於晨",
        "浦惠證券投資顧問股份有限公司",
        4,
    ),
    (
        "A005",
        "林睿閎",
        "林睿閎",
        None,
        5,
    ),
]


SOURCES = [
    (
        "SRC_A001_YOUTUBE",
        "A001",
        "YOUTUBE",
        "鐘崑禎分析師_摩爾證券投顧",
        "https://www.youtube.com/channel/UCZn9BeImRq3SDLC8WVrVmUw",
        "UCZn9BeImRq3SDLC8WVrVmUw",
        10,
        1,
    ),
    (
        "SRC_A001_WEBSITE",
        "A001",
        "WEBSITE",
        "摩爾投顧",
        "https://www.morerich.com.tw/",
        None,
        20,
        1,
    ),
    (
        "SRC_A002_YOUTUBE",
        "A002",
        "YOUTUBE",
        "老王愛說笑",
        "https://www.youtube.com/channel/UCvnLmiWt_zIVIh0zUm_j4Hw",
        "UCvnLmiWt_zIVIh0zUm_j4Hw",
        10,
        1,
    ),
    (
        "SRC_A002_WEBSITE",
        "A002",
        "WEBSITE",
        "浦惠投顧",
        "https://www.inclusion.com.tw/",
        None,
        20,
        1,
    ),
    (
        "SRC_A003_YOUTUBE",
        "A003",
        "YOUTUBE",
        "辣個分析師-黎志建(Vic)",
        "https://www.youtube.com/channel/UCkf2mVeZAK7JUwR9JzeVlkQ",
        "UCkf2mVeZAK7JUwR9JzeVlkQ",
        10,
        1,
    ),
    (
        "SRC_A003_WEBSITE",
        "A003",
        "WEBSITE",
        "浦惠投顧",
        "https://www.inclusion.com.tw/",
        None,
        20,
        1,
    ),
    (
        "SRC_A004_YOUTUBE",
        "A004",
        "YOUTUBE",
        "好股之計在於晨",
        "https://www.youtube.com/channel/UCLbdUFB1vHhDeDsj5aRhDjg",
        "UCLbdUFB1vHhDeDsj5aRhDjg",
        10,
        1,
    ),
    (
        "SRC_A004_WEBSITE",
        "A004",
        "WEBSITE",
        "浦惠投顧",
        "https://www.inclusion.com.tw/project/001ABB83B2B83C1CF6618A7AF3E1E98D",
        None,
        20,
        1,
    ),
    (
        "SRC_A005_YOUTUBE",
        "A005",
        "YOUTUBE",
        "林睿閎分析師-John",
        "https://www.youtube.com/channel/UCXB8cCqwOHP3BmyhYLAUs0g",
        "UCXB8cCqwOHP3BmyhYLAUs0g",
        10,
        1,
    ),
]


def table_exists(
    conn,
    table_name: str,
) -> bool:

    row = (
        conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (table_name,),
        )
        .fetchone()
    )

    return row is not None


def upsert_analysts(
    conn,
) -> None:

    for (
        analyst_id,
        analyst_name,
        display_name,
        organization_name,
        sort_order,
    ) in ANALYSTS:

        conn.execute(
            """
            INSERT INTO analyst_master (
                analyst_id,
                analyst_name,
                display_name,
                organization_name,
                active,
                sort_order,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, 1, ?,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(analyst_id)
            DO UPDATE SET
                analyst_name = excluded.analyst_name,
                display_name = excluded.display_name,
                organization_name = excluded.organization_name,
                active = 1,
                sort_order = excluded.sort_order,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                analyst_id,
                analyst_name,
                display_name,
                organization_name,
                sort_order,
            ),
        )


def upsert_sources(
    conn,
) -> None:

    for (
        source_id,
        analyst_id,
        source_type,
        source_name,
        source_url,
        source_account_id,
        source_priority,
        is_official,
    ) in SOURCES:

        conn.execute(
            """
            INSERT INTO analyst_source (
                source_id,
                analyst_id,
                source_type,
                source_name,
                source_url,
                source_account_id,
                source_priority,
                is_official,
                is_enabled,
                usage_mode,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                1,
                'METADATA_SUMMARY',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(source_id)
            DO UPDATE SET
                analyst_id = excluded.analyst_id,
                source_type = excluded.source_type,
                source_name = excluded.source_name,
                source_url = excluded.source_url,
                source_account_id = excluded.source_account_id,
                source_priority = excluded.source_priority,
                is_official = excluded.is_official,
                is_enabled = 1,
                usage_mode = 'METADATA_SUMMARY',
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                source_id,
                analyst_id,
                source_type,
                source_name,
                source_url,
                source_account_id,
                source_priority,
                is_official,
            ),
        )


def print_result(
    conn,
) -> None:

    print()
    print("Analysts")
    print("-" * 70)

    rows = (
        conn.execute(
            """
            SELECT
                analyst_id,
                analyst_name,
                display_name,
                organization_name,
                active,
                sort_order
            FROM analyst_master
            ORDER BY
                sort_order,
                analyst_id
            """
        )
        .fetchall()
    )

    for row in rows:
        print(
            f"{row[0]:<6} "
            f"| {row[1]:<8} "
            f"| active={row[4]} "
            f"| sort={row[5]}"
        )

    print()
    print("Sources")
    print("-" * 70)

    rows = (
        conn.execute(
            """
            SELECT
                source_id,
                analyst_id,
                source_type,
                source_name,
                source_account_id,
                is_official,
                is_enabled
            FROM analyst_source
            ORDER BY
                analyst_id,
                source_priority,
                source_id
            """
        )
        .fetchall()
    )

    for row in rows:

        account_id = row[4] or "-"

        print(
            f"{row[0]:<24} "
            f"| {row[1]} "
            f"| {row[2]:<8} "
            f"| {row[3]} "
            f"| account={account_id} "
            f"| official={row[5]} "
            f"| enabled={row[6]}"
        )


def main() -> int:

    configure_console()

    print("=" * 70)
    print("StockWaveScanner V3 - Analyst Master Seed")
    print("=" * 70)

    try:

        url, token = load_dev_credentials()

        print()
        print("Environment : DEV")
        print("Database    : stockwave-dev")
        print("PROD Access : DISABLED")

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

            if not test or test[0] != 1:
                raise RuntimeError(
                    "Turso DEV connection validation failed"
                )

            if not table_exists(
                conn,
                "analyst_master",
            ):
                raise RuntimeError(
                    "analyst_master table does not exist"
                )

            if not table_exists(
                conn,
                "analyst_source",
            ):
                raise RuntimeError(
                    "analyst_source table does not exist"
                )

            print()
            print("[PASS] Turso DEV connection")

            conn.execute(
                "BEGIN"
            )

            try:

                upsert_analysts(
                    conn
                )

                upsert_sources(
                    conn
                )

                conn.commit()

            except BaseException:

                try:
                    conn.rollback()
                except Exception:
                    pass

                raise

            print()
            print("[PASS] Analyst master seed completed")

            print_result(
                conn
            )

        finally:
            conn.close()

        print()
        print("=" * 70)
        print("V3 ANALYST MASTER SEED OK")
        print("=" * 70)

        print()
        print("No PROD database was accessed.")

        return 0

    except Exception as exc:

        print()
        print("=" * 70)
        print("ERROR")
        print("=" * 70)

        print(
            str(exc)
        )

        print()
        print("No PROD database was accessed.")

        return 1


if __name__ == "__main__":

    sys.exit(
        main()
    )