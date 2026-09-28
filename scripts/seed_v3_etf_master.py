from __future__ import annotations

import os
import sys
from pathlib import Path

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


ETFS = [
    {
        "etf_id": "0050",
        "etf_name": "元大台灣50",
        "issuer_name": "元大投信",
        "source_url": "https://www.yuantaetfs.com/product/detail/0050/ratio",
        "sort_order": 10,
    },
    {
        "etf_id": "0056",
        "etf_name": "元大高股息",
        "issuer_name": "元大投信",
        "source_url": "https://www.yuantaetfs.com/product/detail/0056/ratio",
        "sort_order": 20,
    },
    {
        "etf_id": "00878",
        "etf_name": "國泰永續高股息",
        "issuer_name": "國泰投信",
        "source_url": "https://www.cathaysite.com.tw/ETF/purchase?code=CN",
        "sort_order": 30,
    },
    {
        "etf_id": "00919",
        "etf_name": "群益台灣精選高息",
        "issuer_name": "群益投信",
        "source_url": "https://www.capitalfund.com.tw/etf/product/detail/195/buyback",
        "sort_order": 40,
    },
    {
        "etf_id": "00929",
        "etf_name": "復華台灣科技優息",
        "issuer_name": "復華投信",
        "source_url": "https://www.fhtrust.com.tw/ETF/etf_list",
        "sort_order": 50,
    },
    {
        "etf_id": "00981A",
        "etf_name": "主動統一台股增長",
        "issuer_name": "統一投信",
        "source_url": "https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode=49YTW&tabName=asset",
        "sort_order": 60,
    },
    {
        "etf_id": "009816",
        "etf_name": "凱基台灣TOP50",
        "issuer_name": "凱基投信",
        "source_url": "https://www.kgifund.com.tw/Fund/Detail?fundID=J023",
        "sort_order": 70,
    },
]


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


def main():

    print("=" * 70)
    print("StockWaveScanner V3 - ETF Master Seed")
    print("=" * 70)

    conn = get_connection()

    try:

        for item in ETFS:

            conn.execute(
                """
                INSERT INTO etf_master (
                    etf_id,
                    etf_name,
                    issuer_name,
                    source_type,
                    source_url,
                    active,
                    sort_order,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, 'OFFICIAL', ?,
                    1, ?,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT(etf_id)
                DO UPDATE SET
                    etf_name = excluded.etf_name,
                    issuer_name = excluded.issuer_name,
                    source_type = excluded.source_type,
                    source_url = excluded.source_url,
                    active = excluded.active,
                    sort_order = excluded.sort_order,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    item["etf_id"],
                    item["etf_name"],
                    item["issuer_name"],
                    item["source_url"],
                    item["sort_order"],
                ),
            )

            print(
                f"[PASS] {item['etf_id']} "
                f"{item['etf_name']}"
            )

        conn.commit()

        print()
        print(f"TOTAL ETF = {len(ETFS)}")
        print("ETF MASTER SEED OK")

        return 0

    except Exception as exc:

        try:
            conn.rollback()
        except Exception:
            pass

        print()
        print("ERROR")
        print(
            f"{type(exc).__name__}: {exc}"
        )

        return 1

    finally:

        conn.close()


if __name__ == "__main__":
    sys.exit(main())