from __future__ import annotations

import sys
from typing import Any

import migrate_v1_core_to_turso as base
import migrate_v1_core_retry as retry


# 每一個 SQL statement 寫 100 rows。
# 每 10 個 statement 才 commit，一次 commit 約 1,000 rows。
#
# 每 row 7 個 parameters：
# 100 × 7 = 700
#
# 保守控制在 SQLite 常見 parameter limit 以內。
SQL_BATCH_ROWS = 100
COMMIT_GROUP_ROWS = 1000


INSTITUTIONAL_VALUE_SQL = """
(
    ?, ?,
    ?, ?, ?,
    NULL, NULL, NULL,
    NULL, NULL, NULL,
    ?,
    'INSUFFICIENT_DATA',
    'INSUFFICIENT_DATA',
    ?,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
"""


INSTITUTIONAL_PREFIX_SQL = """
INSERT INTO institutional_daily (
    stock_id,
    trade_date,

    foreign_buy,
    foreign_sell,
    foreign_net,

    trust_buy,
    trust_sell,
    trust_net,

    dealer_buy,
    dealer_sell,
    dealer_net,

    foreign_data_status,
    trust_data_status,
    dealer_data_status,

    source,

    created_at,
    updated_at
)
VALUES
"""


INSTITUTIONAL_SUFFIX_SQL = """
ON CONFLICT(stock_id, trade_date)
DO NOTHING
"""


TDCC_VALUE_SQL = """
(
    ?, ?,
    ?, ?,
    ?, ?,
    ?,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
"""


TDCC_PREFIX_SQL = """
INSERT INTO tdcc_summary (
    stock_id,
    data_date,

    large_holder_pct,
    retail_holder_pct,

    large_holder_change,
    retail_holder_change,

    source,

    created_at,
    updated_at
)
VALUES
"""


TDCC_SUFFIX_SQL = """
ON CONFLICT(stock_id, data_date)
DO NOTHING
"""


def flatten(
    rows: list[tuple[Any, ...]],
) -> tuple[Any, ...]:
    result: list[Any] = []

    for row in rows:
        result.extend(row)

    return tuple(result)


def get_existing_keys(
    conn,
    label: str,
) -> set[tuple[str, str]]:
    if label == "Institutional":
        rows = conn.execute(
            """
            SELECT
                stock_id,
                trade_date
            FROM institutional_daily
            WHERE source LIKE 'V1_MIGRATION|%'
            """
        ).fetchall()

    elif label == "TDCC Summary":
        rows = conn.execute(
            """
            SELECT
                stock_id,
                data_date
            FROM tdcc_summary
            WHERE source LIKE 'V1_MIGRATION|%'
            """
        ).fetchall()

    else:
        raise RuntimeError(
            f"Unsupported migration label: {label}"
        )

    return {
        (
            str(row[0]).strip(),
            str(row[1]).strip(),
        )
        for row in rows
    }


def build_sql(
    label: str,
    row_count: int,
) -> str:
    if label == "Institutional":
        prefix = INSTITUTIONAL_PREFIX_SQL
        value_sql = INSTITUTIONAL_VALUE_SQL
        suffix = INSTITUTIONAL_SUFFIX_SQL

    elif label == "TDCC Summary":
        prefix = TDCC_PREFIX_SQL
        value_sql = TDCC_VALUE_SQL
        suffix = TDCC_SUFFIX_SQL

    else:
        raise RuntimeError(
            f"Unsupported migration label: {label}"
        )

    values = ",\n".join(
        value_sql
        for _ in range(row_count)
    )

    return (
        prefix
        + "\n"
        + values
        + "\n"
        + suffix
    )


def fast_write_batches(
    conn,
    _original_sql: str,
    rows: list[tuple[Any, ...]],
    label: str,
) -> None:
    print()
    print("=" * 76)
    print(f"FAST WRITE - {label}")
    print("=" * 76)

    existing_keys = get_existing_keys(
        conn,
        label,
    )

    pending_rows = [
        row
        for row in rows
        if (
            str(row[0]).strip(),
            str(row[1]).strip(),
        )
        not in existing_keys
    ]

    source_total = len(rows)
    already_committed = (
        source_total
        - len(pending_rows)
    )

    remaining = len(
        pending_rows
    )

    print(
        f"Eligible Source Rows : "
        f"{source_total:,}"
    )

    print(
        f"Already Committed    : "
        f"{already_committed:,}"
    )

    print(
        f"Remaining            : "
        f"{remaining:,}"
    )

    print(
        f"SQL Rows / Statement : "
        f"{SQL_BATCH_ROWS:,}"
    )

    print(
        f"Rows / Commit Group  : "
        f"{COMMIT_GROUP_ROWS:,}"
    )

    if remaining == 0:
        print()
        print(
            f"[PASS] {label} already complete"
        )
        return

    print()
    print(
        f"Writing remaining {label} ..."
    )

    processed = 0

    for group_start in range(
        0,
        remaining,
        COMMIT_GROUP_ROWS,
    ):
        group = pending_rows[
            group_start:
            group_start
            + COMMIT_GROUP_ROWS
        ]

        try:
            for batch_start in range(
                0,
                len(group),
                SQL_BATCH_ROWS,
            ):
                batch = group[
                    batch_start:
                    batch_start
                    + SQL_BATCH_ROWS
                ]

                sql = build_sql(
                    label,
                    len(batch),
                )

                params = flatten(
                    batch
                )

                conn.execute(
                    sql,
                    params,
                )

            conn.commit()

        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

            raise

        processed += len(
            group
        )

        print(
            f"  {processed:,}"
            f" / "
            f"{remaining:,}"
        )

    print()
    print(
        f"[PASS] {label} fast write complete"
    )


def main() -> int:
    print("=" * 76)
    print(
        "StockWaveScanner V2 - "
        "FAST V1 Core Migration"
    )
    print("=" * 76)

    print()
    print(
        "Resume Mode : ENABLED"
    )

    print(
        "Existing committed rows will be skipped."
    )

    print(
        "PROD Access : DISABLED"
    )

    print()

    # migrate_v1_core_retry.py 內部呼叫的是
    # base.write_batches。
    #
    # 在本次執行期間暫時替換成快速 multi-row writer。
    base.write_batches = (
        fast_write_batches
    )

    return retry.main()


if __name__ == "__main__":
    sys.exit(
        main()
    )