from __future__ import annotations

import os
import sys
from pathlib import Path

import libsql
from dotenv import load_dotenv

from parse_v3_financial_holding_yuanta import parse_yuanta
from parse_v3_financial_holding_cathay import parse_cathay
from parse_v3_financial_holding_fubon import parse_fubon
from parse_v3_financial_holding_taishin import parse_taishin
from parse_v3_financial_holding_huanan import parse_huanan
from parse_v3_financial_holding_esun import parse_esun
from parse_v3_financial_holding_mega import parse_mega
from parse_v3_financial_holding_sinopac import parse_sinopac
from parse_v3_financial_holding_ctbc import parse_ctbc
from parse_v3_financial_holding_first import parse_first


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

LATEST_MONTHS = 3


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

    load_dotenv(ENV_FILE)

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


def latest_rows(
    rows,
    limit=LATEST_MONTHS,
):

    rows = sorted(
        rows,
        key=lambda x: x["data_month"],
        reverse=True,
    )

    return rows[:limit]


def sync_rows(
    conn,
    rows,
):

    sql = """
    INSERT INTO financial_holding_monthly (
        stock_id,
        data_month,
        monthly_net_profit,
        ytd_net_profit,
        ytd_eps,
        previous_year_ytd_net_profit,
        ytd_profit_yoy_pct,
        source_date,
        source_url,
        data_status,
        created_at,
        updated_at
    )
    VALUES (
        ?,
        ?,
        ?,
        ?,
        ?,
        NULL,
        NULL,
        NULL,
        ?,
        'STORED',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    )
    ON CONFLICT(stock_id, data_month)
    DO UPDATE SET
        monthly_net_profit = excluded.monthly_net_profit,
        ytd_net_profit = excluded.ytd_net_profit,
        ytd_eps = excluded.ytd_eps,
        source_url = excluded.source_url,
        data_status = excluded.data_status,
        updated_at = CURRENT_TIMESTAMP
    """

    for row in rows:

        conn.execute(
            sql,
            (
                row["stock_id"],
                row["data_month"],
                row["monthly_net_profit"],
                row["ytd_net_profit"],
                row["ytd_eps"],
                row["source_url"],
            ),
        )

    return len(rows)


def update_yoy_metrics(
    conn,
    affected_rows,
):

    update_sql = """
    UPDATE financial_holding_monthly
    SET
        previous_year_ytd_net_profit = ?,
        ytd_profit_yoy_pct = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE stock_id = ?
      AND data_month = ?
    """

    update_count = 0

    for row in affected_rows:

        stock_id = row["stock_id"]
        data_month = row["data_month"]
        current_ytd = row["ytd_net_profit"]

        if current_ytd is None:
            continue

        year, month = data_month.split("-")

        previous_month = (
            f"{int(year) - 1}-{month}"
        )

        previous_row = conn.execute(
            """
            SELECT
                ytd_net_profit
            FROM financial_holding_monthly
            WHERE stock_id = ?
              AND data_month = ?
              AND ytd_net_profit IS NOT NULL
            LIMIT 1
            """,
            (
                stock_id,
                previous_month,
            ),
        ).fetchone()

        if previous_row is None:
            continue

        previous_ytd = previous_row[0]

        if previous_ytd is None:
            continue

        if previous_ytd == 0:

            yoy_pct = None

        else:

            yoy_pct = round(
                (
                    (
                        current_ytd
                        / previous_ytd
                    )
                    - 1
                )
                * 100,
                2,
            )

        conn.execute(
            update_sql,
            (
                previous_ytd,
                yoy_pct,
                stock_id,
                data_month,
            ),
        )

        update_count += 1

    return update_count


def verify_stock(
    conn,
    stock_id,
    limit=5,
):

    return conn.execute(
        """
        SELECT
            stock_id,
            data_month,
            monthly_net_profit,
            ytd_net_profit,
            ytd_eps,
            previous_year_ytd_net_profit,
            ytd_profit_yoy_pct
        FROM financial_holding_monthly
        WHERE stock_id = ?
        ORDER BY data_month DESC
        LIMIT ?
        """,
        (
            stock_id,
            limit,
        ),
    ).fetchall()


def print_verify(
    stock_name,
    rows,
):

    print()
    print(
        f"[VERIFY] {stock_name}"
    )

    if not rows:

        print(
            "  NO DATA"
        )

        return

    for row in rows:

        prev_ytd_text = (
            row[5]
            if row[5] is not None
            else "N/A"
        )

        yoy_text = (
            f"{row[6]:.2f}%"
            if row[6] is not None
            else "N/A"
        )

        print(
            f"  {row[1]} "
            f"Monthly={row[2]} "
            f"YTD={row[3]} "
            f"EPS={row[4]} "
            f"PrevYTD={prev_ytd_text} "
            f"YoY={yoy_text}"
        )


def main():

    configure_console()

    print("=" * 70)

    print(
        "StockWaveScanner V3 - "
        "Financial Holding Monthly Incremental Sync"
    )

    print("=" * 70)

    print()

    print(
        f"Incremental Months: "
        f"{LATEST_MONTHS}"
    )

    conn = get_connection()

    try:

        yuanta_rows = latest_rows(
            parse_yuanta()
        )

        cathay_rows = latest_rows(
            parse_cathay()
        )

        fubon_rows = latest_rows(
            parse_fubon()
        )

        taishin_rows = latest_rows(
            parse_taishin()
        )

        huanan_rows = latest_rows(
            parse_huanan()
        )

        esun_rows = latest_rows(
            parse_esun()
        )

        mega_rows = latest_rows(
            parse_mega()
        )

        sinopac_rows = latest_rows(
            parse_sinopac()
        )

        ctbc_rows = latest_rows(
            parse_ctbc()
        )

        first_rows = latest_rows(
            parse_first()
        )

        all_rows = (
            yuanta_rows
            + cathay_rows
            + fubon_rows
            + taishin_rows
            + huanan_rows
            + esun_rows
            + mega_rows
            + sinopac_rows
            + ctbc_rows
            + first_rows
        )

        yuanta_count = sync_rows(
            conn,
            yuanta_rows,
        )

        cathay_count = sync_rows(
            conn,
            cathay_rows,
        )

        fubon_count = sync_rows(
            conn,
            fubon_rows,
        )

        taishin_count = sync_rows(
            conn,
            taishin_rows,
        )

        huanan_count = sync_rows(
            conn,
            huanan_rows,
        )

        esun_count = sync_rows(
            conn,
            esun_rows,
        )

        mega_count = sync_rows(
            conn,
            mega_rows,
        )

        sinopac_count = sync_rows(
            conn,
            sinopac_rows,
        )

        ctbc_count = sync_rows(
            conn,
            ctbc_rows,
        )

        first_count = sync_rows(
            conn,
            first_rows,
        )

        yoy_count = update_yoy_metrics(
            conn,
            all_rows,
        )

        conn.commit()

        print()

        print(
            f"[PASS] Yuanta synced rows: "
            f"{yuanta_count}"
        )

        print(
            f"[PASS] Cathay synced rows: "
            f"{cathay_count}"
        )

        print(
            f"[PASS] Fubon synced rows: "
            f"{fubon_count}"
        )

        print(
            f"[PASS] Taishin synced rows: "
            f"{taishin_count}"
        )

        print(
            f"[PASS] Hua Nan synced rows: "
            f"{huanan_count}"
        )

        print(
            f"[PASS] E.SUN synced rows: "
            f"{esun_count}"
        )

        print(
            f"[PASS] Mega synced rows: "
            f"{mega_count}"
        )

        print(
            f"[PASS] SinoPac synced rows: "
            f"{sinopac_count}"
        )

        print(
            f"[PASS] CTBC synced rows: "
            f"{ctbc_count}"
        )

        print(
            f"[PASS] First Financial synced rows: "
            f"{first_count}"
        )

        print(
            f"[PASS] YoY updated rows: "
            f"{yoy_count}"
        )

        print_verify(
            "2885 元大金",
            verify_stock(
                conn,
                "2885",
            ),
        )

        print_verify(
            "2882 國泰金",
            verify_stock(
                conn,
                "2882",
            ),
        )

        print_verify(
            "2881 富邦金",
            verify_stock(
                conn,
                "2881",
            ),
        )

        print_verify(
            "2887 台新新光金",
            verify_stock(
                conn,
                "2887",
            ),
        )

        print_verify(
            "2880 華南金",
            verify_stock(
                conn,
                "2880",
            ),
        )

        print_verify(
            "2884 玉山金",
            verify_stock(
                conn,
                "2884",
            ),
        )

        print_verify(
            "2886 兆豐金",
            verify_stock(
                conn,
                "2886",
            ),
        )

        print_verify(
            "2890 永豐金",
            verify_stock(
                conn,
                "2890",
            ),
        )

        print_verify(
            "2891 中信金",
            verify_stock(
                conn,
                "2891",
            ),
        )

        print_verify(
            "2892 第一金",
            verify_stock(
                conn,
                "2892",
            ),
        )

        print()

        print("=" * 70)

        print(
            "FINANCIAL HOLDING "
            "MONTHLY INCREMENTAL SYNC OK"
        )

        print("=" * 70)

        return 0

    except Exception as exc:

        conn.rollback()

        print()
        print("ERROR")

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