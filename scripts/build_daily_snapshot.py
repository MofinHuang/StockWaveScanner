from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import argparse
import json
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from db.database import get_connection
from strategy.ranking import build_ranking, _get_ranking_reference_date


TPEX_FOREIGN_SOURCE = "TPEX_QFII_STAT"


def _scalar(conn, sql: str, params=()):
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return None
    return row[0]


def _coverage(conn, reference_date: str) -> dict:
    active_rows = conn.execute(
        """
        SELECT stock_id, stock_name, market
        FROM stocks
        WHERE is_active = 1 AND market IN ('TWSE', 'TPEx')
        ORDER BY market, stock_id
        """
    ).fetchall()

    price_rows = conn.execute(
        """
        SELECT stock_id, market, COUNT(*) AS cnt
        FROM daily_prices
        WHERE trade_date <= ?
        GROUP BY stock_id, market
        """,
        (reference_date,),
    ).fetchall()
    price_counts = {
        (str(row["stock_id"]), str(row["market"])): int(row["cnt"])
        for row in price_rows
    }

    inst_rows = conn.execute(
        """
        SELECT stock_id, market, COUNT(*) AS cnt
        FROM institutional_trades
        WHERE trade_date <= ?
        GROUP BY stock_id, market
        """,
        (reference_date,),
    ).fetchall()
    inst_counts = {
        (str(row["stock_id"]), str(row["market"])): int(row["cnt"])
        for row in inst_rows
    }

    tdcc_rows = conn.execute(
        """
        SELECT stock_id, COUNT(DISTINCT data_date) AS cnt
        FROM tdcc_holdings
        WHERE data_date <= ?
        GROUP BY stock_id
        """,
        (reference_date,),
    ).fetchall()
    tdcc_counts = {str(row["stock_id"]): int(row["cnt"]) for row in tdcc_rows}

    success_rows = conn.execute(
        """
        SELECT DISTINCT request_key
        FROM crawl_logs
        WHERE source = ? AND status = 'SUCCESS'
        """,
        (TPEX_FOREIGN_SOURCE,),
    ).fetchall()
    prefix = f"{TPEX_FOREIGN_SOURCE}:"
    tpex_success_dates = set()
    for row in success_rows:
        key = str(row["request_key"])
        if key.startswith(prefix):
            value = key[len(prefix):]
            if value <= reference_date:
                tpex_success_dates.add(value)

    recent_rows = conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM daily_prices
        WHERE market = 'TPEx' AND trade_date <= ?
        ORDER BY trade_date DESC
        LIMIT 20
        """,
        (reference_date,),
    ).fetchall()
    recent_tpex_dates = [str(row["trade_date"]) for row in recent_rows]
    recent_success_count = sum(d in tpex_success_dates for d in recent_tpex_dates)

    market_counter = Counter(str(row["market"]) for row in active_rows)
    rows = []
    for row in active_rows:
        stock_id = str(row["stock_id"])
        market = str(row["market"])
        price_ok = price_counts.get((stock_id, market), 0) >= 30
        if market == "TWSE":
            foreign_ok = inst_counts.get((stock_id, market), 0) > 0
        else:
            foreign_ok = recent_success_count >= 15
        tdcc_ok = tdcc_counts.get(stock_id, 0) >= 4
        rows.append(
            {
                "price_ok": price_ok,
                "foreign_ok": foreign_ok,
                "tdcc_ok": tdcc_ok,
                "ranking_ready": price_ok and foreign_ok and tdcc_ok,
            }
        )

    total = len(rows)
    return {
        "active_stocks": total,
        "active_twse": market_counter["TWSE"],
        "active_tpex": market_counter["TPEx"],
        "price_ready": sum(row["price_ok"] for row in rows),
        "foreign_ready": sum(row["foreign_ok"] for row in rows),
        "tdcc_ready": sum(row["tdcc_ok"] for row in rows),
        "ranking_ready": sum(row["ranking_ready"] for row in rows),
        "tpex_recent_foreign_success_days": recent_success_count,
    }



def _price_snapshot(conn, reference_date: str) -> dict[tuple[str, str], dict]:
    rows = conn.execute(
        """
        SELECT
            p.stock_id,
            p.market,
            p.open,
            p.high,
            p.low,
            p.close,
            p.volume,
            (
                SELECT p2.close
                FROM daily_prices p2
                WHERE p2.stock_id = p.stock_id
                  AND p2.market = p.market
                  AND p2.trade_date < p.trade_date
                ORDER BY p2.trade_date DESC
                LIMIT 1
            ) AS previous_close
        FROM daily_prices p
        WHERE p.trade_date = ?
        """,
        (reference_date,),
    ).fetchall()

    result = {}
    for row in rows:
        close = row["close"]
        previous_close = row["previous_close"]
        change = None
        change_pct = None
        if close is not None and previous_close not in (None, 0):
            change = float(close) - float(previous_close)
            change_pct = change / float(previous_close) * 100.0

        result[(str(row["stock_id"]), str(row["market"]))] = {
            "trade_date": reference_date,
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": close,
            "volume": row["volume"],
            "previous_close": previous_close,
            "change": round(change, 4) if change is not None else None,
            "change_pct": round(change_pct, 4) if change_pct is not None else None,
        }
    return result

def main() -> None:
    parser = argparse.ArgumentParser(description="建立 GitHub Pages 每日 snapshot")
    parser.add_argument("--date", required=True, help="as-of date YYYY-MM-DD")
    parser.add_argument("--output-dir", default="runtime")
    args = parser.parse_args()

    datetime.strptime(args.date, "%Y-%m-%d")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    try:
        reference_date = _get_ranking_reference_date(conn, as_of_date=args.date)
        if not reference_date:
            raise RuntimeError(f"{args.date} 以前找不到 daily_prices")

        ranking = build_ranking(conn, as_of_date=args.date)
        if ranking.empty:
            raise RuntimeError("build_ranking() 回傳空 DataFrame")

        coverage = _coverage(conn, reference_date)

        latest = {
            "twse_price": _scalar(
                conn,
                "SELECT MAX(trade_date) FROM daily_prices WHERE market='TWSE' AND trade_date <= ?",
                (reference_date,),
            ),
            "tpex_price": _scalar(
                conn,
                "SELECT MAX(trade_date) FROM daily_prices WHERE market='TPEx' AND trade_date <= ?",
                (reference_date,),
            ),
            "twse_foreign": _scalar(
                conn,
                "SELECT MAX(trade_date) FROM institutional_trades WHERE market='TWSE' AND trade_date <= ?",
                (reference_date,),
            ),
            "tpex_foreign": _scalar(
                conn,
                "SELECT MAX(trade_date) FROM institutional_trades WHERE market='TPEx' AND trade_date <= ?",
                (reference_date,),
            ),
            "tdcc": _scalar(
                conn,
                "SELECT MAX(data_date) FROM tdcc_holdings WHERE data_date <= ?",
                (reference_date,),
            ),
        }

        pass_counts = {
            "sleep_pass": int((ranking["sleep_status"] == "PASS").sum()),
            "foreign_pass": int((ranking["foreign_status"] == "PASS").sum()),
            "tdcc_pass": int((ranking["tdcc_status"] == "PASS").sum()),
            "chip_pass": int((ranking["chip_status"] == "PASS").sum()),
            "breakout_pass": int((ranking["breakout_status"] == "PASS").sum()),
            "final_pass": int((ranking["status"] == "PASS").sum()),
        }

        summary = {
            "requested_date": args.date,
            "reference_date": reference_date,
            "generated_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
            **coverage,
            "ranking_rows": int(len(ranking)),
            **pass_counts,
            "latest_dates": latest,
        }

        price_map = _price_snapshot(conn, reference_date)
        ranking_records = json.loads(
            ranking.to_json(orient="records", force_ascii=False)
        )
        for record in ranking_records:
            price = price_map.get(
                (str(record.get("stock_id")), str(record.get("market"))),
                {},
            )
            record.update({
                "price_date": price.get("trade_date"),
                "open": price.get("open"),
                "high": price.get("high"),
                "low": price.get("low"),
                "close": price.get("close"),
                "volume": price.get("volume"),
                "previous_close": price.get("previous_close"),
                "change": price.get("change"),
                "change_pct": price.get("change_pct"),
            })

        (output_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_dir / "ranking.json").write_text(
            json.dumps(ranking_records, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
