from __future__ import annotations

import sys

import libsql

import migrate_v1_core_to_turso as base


# ============================================================
# V2 COMMON-STOCK UNIVERSE POLICY
# ============================================================

# V1 曾包含，但 V2 普通股研究宇宙不納入。
EXCLUDED_NON_COMMON_IDS = {
    "0050",
    "0051",
    "0052",
    "0053",
    "0055",
    "0056",
    "0057",
    "0061",
}


# V1 歷史期間存在，但目前官方 Stock Master
# 已因終止上市 / 上櫃而不存在。
#
# 為避免 Survivorship Bias，仍保留歷史資料，
# 但 Stock Master 標示 is_active = 0。
HISTORICAL_COMMON_STOCKS = {
    "2867": {
        "name": "三商壽",
        "market": "TWSE",
    },
    "4130": {
        "name": "健亞",
        "market": "TPEX",
    },
    "4987": {
        "name": "科誠",
        "market": "TPEX",
    },
    "5371": {
        "name": "中光電",
        "market": "TPEX",
    },
    "6806": {
        "name": "森崴能源",
        "market": "TWSE",
    },
}


def seed_historical_stock_master(
    conn,
    stock_ids: set[str],
) -> None:
    if not stock_ids:
        print(
            "[PASS] Historical Stock Master "
            "already complete"
        )
        return

    print()
    print(
        "Seeding historical inactive "
        "common stocks ..."
    )

    for stock_id in sorted(
        stock_ids
    ):
        meta = (
            HISTORICAL_COMMON_STOCKS[
                stock_id
            ]
        )

        conn.execute(
            """
            INSERT INTO stock_master (
                stock_id,
                stock_name,
                short_name,
                market,
                security_type,

                industry_code,
                industry_name,

                listed_date,
                issued_common_shares,
                source_date,

                is_active,

                created_at,
                updated_at
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                'COMMON_STOCK',

                NULL,
                NULL,

                NULL,
                NULL,
                NULL,

                0,

                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(stock_id)
            DO NOTHING
            """,
            (
                stock_id,
                meta["name"],
                meta["name"],
                meta["market"],
            ),
        )

        print(
            f"  {stock_id} "
            f"{meta['name']} "
            f"| {meta['market']} "
            f"| active=0"
        )

    conn.commit()

    print(
        f"[PASS] Seeded "
        f"{len(stock_ids)} "
        f"historical stock(s)"
    )


def verify_historical_master(
    conn,
) -> None:
    print()
    print("=" * 74)
    print(
        "HISTORICAL STOCK MASTER"
    )
    print("=" * 74)

    for stock_id in sorted(
        HISTORICAL_COMMON_STOCKS
    ):
        row = conn.execute(
            """
            SELECT
                stock_name,
                market,
                security_type,
                is_active
            FROM stock_master
            WHERE stock_id = ?
            """,
            (stock_id,),
        ).fetchone()

        if row is None:
            raise RuntimeError(
                "Historical Stock Master "
                f"missing: {stock_id}"
            )

        if row[2] != "COMMON_STOCK":
            raise RuntimeError(
                "Unexpected security_type: "
                f"{stock_id}"
            )

        if int(row[3]) != 0:
            raise RuntimeError(
                "Historical stock "
                "unexpectedly active: "
                f"{stock_id}"
            )

        print(
            f"[PASS] {stock_id} "
            f"{row[0]} "
            f"| {row[1]} "
            f"| active={row[3]}"
        )


def verify_excluded_ids(
    conn,
) -> None:
    placeholders = ",".join(
        "?"
        for _ in EXCLUDED_NON_COMMON_IDS
    )

    ids = tuple(
        sorted(
            EXCLUDED_NON_COMMON_IDS
        )
    )

    institutional = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM institutional_daily
        WHERE source LIKE 'V1_MIGRATION|%'
          AND stock_id IN (
              {placeholders}
          )
        """,
        ids,
    ).fetchone()[0]

    tdcc = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM tdcc_summary
        WHERE source LIKE 'V1_MIGRATION|%'
          AND stock_id IN (
              {placeholders}
          )
        """,
        ids,
    ).fetchone()[0]

    print()
    print("=" * 74)
    print(
        "NON-COMMON SECURITY VERIFICATION"
    )
    print("=" * 74)

    print(
        f"Institutional ETF Rows : "
        f"{institutional:,}"
    )

    print(
        f"TDCC ETF Rows          : "
        f"{tdcc:,}"
    )

    if institutional != 0:
        raise RuntimeError(
            "Excluded ETF institutional "
            "rows were migrated"
        )

    if tdcc != 0:
        raise RuntimeError(
            "Excluded ETF TDCC rows "
            "were migrated"
        )

    print(
        "[PASS] Non-common securities excluded"
    )


def main() -> int:
    print("=" * 74)
    print(
        "StockWaveScanner V2 - "
        "V1 Core Migration Retry"
    )
    print("=" * 74)
    print()

    print(
        f"V1 Database : "
        f"{base.V1_DB_PATH}"
    )

    print(
        "V1 Mode     : READ ONLY"
    )

    try:
        url, token = (
            base.load_dev_credentials()
        )

        print(
            "Target      : DEV"
        )

        print(
            f"Database    : "
            f"{base.mask_url(url)}"
        )

        print(
            "PROD Access : DISABLED"
        )

        v1_conn = (
            base.connect_v1()
        )

        turso_conn = libsql.connect(
            database=url,
            auth_token=token,
        )

        try:
            result = (
                turso_conn
                .execute(
                    "SELECT 1"
                )
                .fetchone()
            )

            if (
                not result
                or result[0] != 1
            ):
                raise RuntimeError(
                    "Turso DEV connection "
                    "validation failed"
                )

            print()
            print(
                "[PASS] V1 READ ONLY connection"
            )

            print(
                "[PASS] Turso DEV connection"
            )

            base.validate_v1_schema(
                v1_conn
            )

            source_ids = (
                base.get_v1_source_stock_ids(
                    v1_conn
                )
            )

            target_ids = (
                base.get_turso_stock_ids(
                    turso_conn
                )
            )

            excluded_present = (
                source_ids
                & EXCLUDED_NON_COMMON_IDS
            )

            eligible_ids = (
                source_ids
                - EXCLUDED_NON_COMMON_IDS
            )

            missing_ids = (
                eligible_ids
                - target_ids
            )

            historical_missing = (
                missing_ids
                & set(
                    HISTORICAL_COMMON_STOCKS
                )
            )

            unknown_missing = (
                missing_ids
                - set(
                    HISTORICAL_COMMON_STOCKS
                )
            )

            print()
            print("=" * 74)
            print("PREFLIGHT")
            print("=" * 74)

            print(
                f"V1 Source Stocks       : "
                f"{len(source_ids):,}"
            )

            print(
                f"Excluded ETF IDs       : "
                f"{len(excluded_present):,}"
            )

            print(
                f"Eligible Common Stocks : "
                f"{len(eligible_ids):,}"
            )

            print(
                f"Historical Missing     : "
                f"{len(historical_missing):,}"
            )

            print(
                f"Unknown Missing        : "
                f"{len(unknown_missing):,}"
            )

            print()
            print(
                "Excluded:"
            )

            print(
                "  "
                + ", ".join(
                    sorted(
                        excluded_present
                    )
                )
            )

            print()
            print(
                "Historical:"
            )

            print(
                "  "
                + ", ".join(
                    sorted(
                        historical_missing
                    )
                )
            )

            if unknown_missing:
                print()
                print(
                    "Unknown IDs:"
                )

                for stock_id in sorted(
                    unknown_missing
                ):
                    print(
                        f"  {stock_id}"
                    )

                raise RuntimeError(
                    "Unknown missing "
                    "Stock Master IDs"
                )

            print()
            print(
                "[PASS] All missing IDs classified"
            )

            seed_historical_stock_master(
                turso_conn,
                historical_missing,
            )

            target_ids = (
                base.get_turso_stock_ids(
                    turso_conn
                )
            )

            remaining_missing = (
                eligible_ids
                - target_ids
            )

            if remaining_missing:
                raise RuntimeError(
                    "Eligible FK still missing: "
                    + ", ".join(
                        sorted(
                            remaining_missing
                        )
                    )
                )

            print(
                "[PASS] Foreign key compatibility"
            )

            print()
            print(
                "Loading V1 Institutional ..."
            )

            institutional_all = (
                base.load_institutional_rows(
                    v1_conn
                )
            )

            institutional_rows = [
                row
                for row
                in institutional_all
                if row[0]
                not in EXCLUDED_NON_COMMON_IDS
            ]

            institutional_skipped = (
                len(institutional_all)
                - len(institutional_rows)
            )

            print(
                f"[PASS] Eligible="
                f"{len(institutional_rows):,}, "
                f"Excluded="
                f"{institutional_skipped:,}"
            )

            print()
            print(
                "Loading V1 TDCC Summary ..."
            )

            tdcc_all = (
                base.load_tdcc_rows(
                    v1_conn
                )
            )

            tdcc_rows = [
                row
                for row
                in tdcc_all
                if row[0]
                not in EXCLUDED_NON_COMMON_IDS
            ]

            tdcc_skipped = (
                len(tdcc_all)
                - len(tdcc_rows)
            )

            print(
                f"[PASS] Eligible="
                f"{len(tdcc_rows):,}, "
                f"Excluded="
                f"{tdcc_skipped:,}"
            )

            base.write_batches(
                turso_conn,
                base.INSTITUTIONAL_INSERT_SQL,
                institutional_rows,
                "Institutional",
            )

            base.write_batches(
                turso_conn,
                base.TDCC_INSERT_SQL,
                tdcc_rows,
                "TDCC Summary",
            )

            institutional_last_date = (
                base.scalar(
                    v1_conn,
                    """
                    SELECT MAX(trade_date)
                    FROM institutional_trades
                    """
                )
            )

            tdcc_last_date = (
                base.scalar(
                    v1_conn,
                    """
                    SELECT MAX(data_date)
                    FROM tdcc_holdings
                    """
                )
            )

            base.update_sync_state(
                turso_conn,
                "v1_institutional_migration",
                institutional_last_date,
                len(
                    institutional_rows
                ),
            )

            base.update_sync_state(
                turso_conn,
                "v1_tdcc_summary_migration",
                tdcc_last_date,
                len(tdcc_rows),
            )

            turso_conn.commit()

            verify_historical_master(
                turso_conn
            )

            base.verify_institutional(
                turso_conn,
                len(
                    institutional_rows
                ),
            )

            base.verify_tdcc(
                turso_conn,
                len(tdcc_rows),
            )

            verify_excluded_ids(
                turso_conn
            )

            print()
            print("=" * 74)
            print("SYNC STATE")
            print("=" * 74)

            rows = turso_conn.execute(
                """
                SELECT
                    dataset,
                    last_data_date,
                    status,
                    records_processed
                FROM sync_state
                WHERE dataset IN (
                    'v1_institutional_migration',
                    'v1_tdcc_summary_migration'
                )
                ORDER BY dataset
                """
            ).fetchall()

            for row in rows:
                print(
                    f"{row[0]:<32} "
                    f"| date={row[1]} "
                    f"| status={row[2]} "
                    f"| rows={row[3]}"
                )

        finally:
            v1_conn.close()
            turso_conn.close()

        print()
        print("=" * 74)
        print(
            "V1 CORE MIGRATION OK"
        )
        print("=" * 74)

        print()
        print(
            "ETF rows were excluded."
        )

        print(
            "Historical delisted common "
            "stocks were retained as inactive."
        )

        print(
            "V1 database remained READ ONLY."
        )

        print(
            "No PROD database was accessed."
        )

        return 0

    except Exception as exc:
        print()
        print("=" * 74)
        print("ERROR")
        print("=" * 74)

        print(
            str(exc)
        )

        print()
        print(
            "V1 database remained READ ONLY."
        )

        print(
            "No PROD database was accessed."
        )

        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )