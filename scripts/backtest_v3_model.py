from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import libsql
from dotenv import load_dotenv

# Reuse the exact formulas currently used by the project.
import build_v2_scores as model
import export_v2_ui_snapshot as exporter


# ============================================================
# CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
OUTPUT_DIR = ROOT / "docs" / "data" / "backtest" / "v3"

TAIPEI = ZoneInfo("Asia/Taipei")

DEFAULT_WINDOW_DAYS = 120
DEFAULT_SIGNAL_STEP = 5
PRICE_LOOKBACK_ROWS = 90
FUTURE_DAYS = 20
INSTITUTIONAL_LOOKBACK_ROWS = 20

# monthly_revenue does not currently store an actual announcement date.
# To prevent look-ahead bias, Research v1 uses a conservative availability
# proxy: the 15th calendar day of the following month.
REVENUE_AVAILABLE_DAY = 15

# ============================================================
# BACKTEST RESEARCH READINESS
# ============================================================
#
# 正式 UI Snapshot 仍維持：
# Revenue 24 months
# Financial 8 quarters
#
# Backtest 因目前歷史資料覆蓋不足，
# 先採 Research Gate。
#
# 這只影響 Backtest 是否允許評分，
# 不改 Fundamental Score 本身公式。
# ============================================================

BACKTEST_REVENUE_MIN_MONTHS = 12
BACKTEST_FINANCIAL_MIN_QUARTERS = 4

STAGE_ORDER = (
    "AVOID",
    "WATCH",
    "SETUP",
    "READY",
    "BREAKOUT",
    "EXTENDED",
)


# ============================================================
# BASIC HELPERS
# ============================================================


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def now_iso() -> str:
    return datetime.now(TAIPEI).isoformat(timespec="seconds")


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def round_or_none(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def mean_or_none(values: list[float | None]) -> float | None:
    valid = [float(v) for v in values if v is not None]
    if not valid:
        return None
    return statistics.fmean(valid)


def median_or_none(values: list[float | None]) -> float | None:
    valid = [float(v) for v in values if v is not None]
    if not valid:
        return None
    return statistics.median(valid)


def parse_iso_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def revenue_available_date(revenue_month: str) -> date | None:
    """
    Conservative Research v1 proxy because monthly_revenue currently has no
    real announcement timestamp/source_date.

    Example:
        2026-08 -> available from 2026-09-15
    """
    text = str(revenue_month).strip()
    parts = text.replace("/", "-").split("-")
    if len(parts) < 2:
        return None
    try:
        year = int(parts[0])
        month = int(parts[1])
    except ValueError:
        return None
    if month < 1 or month > 12:
        return None
    year, month = next_month(year, month)
    return date(year, month, REVENUE_AVAILABLE_DAY)


def financial_proxy_available_date(
    fiscal_year: int | None,
    fiscal_quarter: int | None,
) -> date | None:
    """
    Research-only conservative proxy.

    quarterly_financial 目前大量歷史資料沒有 source_date，
    因此 Backtest 無法知道當時真正公告日期。

    為避免 look-ahead bias，
    使用偏保守的季度可用日期：

        Q1 -> 06/01
        Q2 -> 09/01
        Q3 -> 12/01
        Q4 -> 次年 04/01

    這不是正式公告日期，
    只供 V3 Research Backtest 使用。
    """

    if (
        fiscal_year is None
        or fiscal_quarter is None
    ):
        return None

    if fiscal_quarter == 1:
        return date(
            fiscal_year,
            6,
            1,
        )

    if fiscal_quarter == 2:
        return date(
            fiscal_year,
            9,
            1,
        )

    if fiscal_quarter == 3:
        return date(
            fiscal_year,
            12,
            1,
        )

    if fiscal_quarter == 4:
        return date(
            fiscal_year + 1,
            4,
            1,
        )

    return None


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[WRITE] {path}")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"[WRITE] {path}")


# ============================================================
# TURSO DEV SAFETY
# ============================================================


def load_dev_credentials() -> tuple[str, str]:
    load_dotenv(ENV_FILE)

    url = os.getenv("TURSO_DEV_DATABASE_URL", "").strip()
    token = os.getenv("TURSO_DEV_AUTH_TOKEN", "").strip()

    if not url:
        raise RuntimeError("TURSO_DEV_DATABASE_URL missing from .env")
    if not token:
        raise RuntimeError("TURSO_DEV_AUTH_TOKEN missing from .env")

    lower_url = url.lower()

    if "stockwave-dev" not in lower_url:
        raise RuntimeError(
            "SAFETY STOP: TURSO_DEV_DATABASE_URL is not stockwave-dev"
        )
    if "stockwave-prod" in lower_url:
        raise RuntimeError("SAFETY STOP: PROD database detected")

    return url, token


# ============================================================
# LOAD RAW HISTORY
# ============================================================


def load_trade_dates(conn) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT trade_date
        FROM stock_price_daily
        ORDER BY trade_date
        """
    ).fetchall()
    return [str(row[0]) for row in rows]


def load_stock_master_all_common(conn) -> dict[str, dict[str, Any]]:
    """
    Do not filter is_active=1 for backtest. Eligibility is determined by actual
    price data on each signal date, reducing current-survivor-only bias.
    """
    rows = conn.execute(
        """
        SELECT
            stock_id,
            stock_name,
            short_name,
            market,
            industry_code,
            industry_name,
            listed_date,
            is_active
        FROM stock_master
        WHERE security_type = 'COMMON_STOCK'
        ORDER BY market, stock_id
        """
    ).fetchall()

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        stock_id = str(row[0])
        result[stock_id] = {
            "stock_id": stock_id,
            "stock_name": str(row[1] or ""),
            "short_name": str(row[2] or row[1] or ""),
            "market": str(row[3] or ""),
            "industry_code": None if row[4] is None else str(row[4]),
            "industry_name": None if row[5] is None else str(row[5]),
            "listed_date": None if row[6] is None else str(row[6]),
            "is_active": bool(row[7]),
        }
    return result


def load_prices(conn, start_date: str, end_date: str) -> dict[str, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT stock_id, trade_date, open, high, low, close, volume
        FROM stock_price_daily
        WHERE trade_date >= ?
          AND trade_date <= ?
        ORDER BY stock_id, trade_date
        """,
        (start_date, end_date),
    ).fetchall()

    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[str(row[0])].append(
            {
                "trade_date": str(row[1]),
                "open": safe_float(row[2]),
                "high": safe_float(row[3]),
                "low": safe_float(row[4]),
                "close": safe_float(row[5]),
                "volume": safe_int(row[6]),
            }
        )
    return dict(result)


def load_institutions(conn, start_date: str, end_date: str) -> dict[str, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT
            stock_id,
            trade_date,
            foreign_net,
            foreign_data_status,
            trust_net,
            trust_data_status,
            dealer_net,
            dealer_data_status
        FROM institutional_daily
        WHERE trade_date >= ?
          AND trade_date <= ?
        ORDER BY stock_id, trade_date
        """,
        (start_date, end_date),
    ).fetchall()

    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[str(row[0])].append(
            {
                "trade_date": str(row[1]),
                "foreign_net": safe_int(row[2]),
                "foreign_status": str(row[3]),
                "trust_net": safe_int(row[4]),
                "trust_status": str(row[5]),
                "dealer_net": safe_int(row[6]),
                "dealer_status": str(row[7]),
            }
        )
    return dict(result)


def load_tdcc(conn, end_date: str) -> dict[str, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT
            stock_id,
            data_date,
            large_holder_pct,
            retail_holder_pct,
            large_holder_change,
            retail_holder_change
        FROM tdcc_summary
        WHERE data_date <= ?
        ORDER BY stock_id, data_date
        """,
        (end_date,),
    ).fetchall()

    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[str(row[0])].append(
            {
                "data_date": str(row[1]),
                "large_holder_pct": safe_float(row[2]),
                "retail_holder_pct": safe_float(row[3]),
                "large_holder_change": safe_float(row[4]),
                "retail_holder_change": safe_float(row[5]),
                "status": "READY",
            }
        )
    return dict(result)


def load_revenues(conn) -> dict[str, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT
            stock_id,
            revenue_month,
            revenue,
            revenue_mom_pct,
            revenue_yoy_pct,
            cumulative_revenue,
            cumulative_yoy_pct
        FROM monthly_revenue
        ORDER BY stock_id, revenue_month
        """
    ).fetchall()

    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        month = str(row[1])
        result[str(row[0])].append(
            {
                "revenue_month": month,
                "available_date": revenue_available_date(month),
                "revenue": safe_float(row[2]),
                "revenue_mom_pct": safe_float(row[3]),
                "revenue_yoy_pct": safe_float(row[4]),
                "cumulative_revenue": safe_float(row[5]),
                "cumulative_yoy_pct": safe_float(row[6]),
            }
        )
    return dict(result)


def load_financials(conn) -> tuple[dict[str, list[dict[str, Any]]], int]:
    rows = conn.execute(
        """
        SELECT
            stock_id,
            fiscal_year,
            fiscal_quarter,
            report_type,
            revenue,
            gross_profit,
            operating_income,
            net_income,
            eps,
            gross_margin_pct,
            operating_margin_pct,
            net_margin_pct,
            source_date
        FROM quarterly_financial
        ORDER BY stock_id, fiscal_year, fiscal_quarter
        """
    ).fetchall()

    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    missing_source_date = 0

    for row in rows:
        source_available_date = (
            parse_iso_date(
                row[12]
            )
        )

        fiscal_year = (
            safe_int(
                row[1]
            )
        )

        fiscal_quarter = (
            safe_int(
                row[2]
            )
        )

        if source_available_date is None:

            missing_source_date += 1

            available_date = (
                financial_proxy_available_date(
                    fiscal_year,
                    fiscal_quarter,
                )
            )

        else:

            available_date = (
                source_available_date
            )

        result[str(row[0])].append(
            {
                "fiscal_year": safe_int(row[1]),
                "fiscal_quarter": safe_int(row[2]),
                "report_type": str(row[3] or ""),
                "revenue": safe_float(row[4]),
                "gross_profit": safe_float(row[5]),
                "operating_income": safe_float(row[6]),
                "net_income": safe_float(row[7]),
                "eps": safe_float(row[8]),
                "gross_margin_pct": safe_float(row[9]),
                "operating_margin_pct": safe_float(row[10]),
                "net_margin_pct": safe_float(row[11]),
                "source_date": None if row[12] is None else str(row[12]),
                "available_date": available_date,
            }
        )

    return dict(result), missing_source_date


# ============================================================
# AS-OF HELPERS
# ============================================================


def rows_up_to_date(
    rows: list[dict[str, Any]],
    date_key: str,
    signal_date: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if not rows:
        return []
    dates = [str(row[date_key]) for row in rows]
    end = bisect.bisect_right(dates, signal_date)
    selected = rows[:end]
    if limit is not None:
        selected = selected[-limit:]
    return selected


def latest_tdcc_asof(rows: list[dict[str, Any]], signal_date: str) -> dict[str, Any]:
    selected = rows_up_to_date(rows, "data_date", signal_date)
    if not selected:
        return {"status": "WAITING_DATA"}
    return dict(selected[-1])


def revenue_asof(rows: list[dict[str, Any]], signal_date: str) -> dict[str, Any]:
    signal = parse_iso_date(signal_date)
    if signal is None:
        return {"status": "WAITING_HISTORY", "history_months": 0}

    selected = [
        row
        for row in rows
        if row.get("available_date") is not None
        and row["available_date"] <= signal
    ]

    if not selected:
        return {"status": "WAITING_HISTORY", "history_months": 0}

    latest = dict(selected[-1])
    latest.pop("available_date", None)
    latest["history_months"] = len(selected)
    latest["status"] = (
        "READY"
        if len(selected)
        >= BACKTEST_REVENUE_MIN_MONTHS
        else "WAITING_HISTORY"
    )
    return latest


def financial_asof(rows: list[dict[str, Any]], signal_date: str) -> dict[str, Any]:
    """
    STRICT mode: a quarterly financial row is usable only when source_date is
    present and <= signal_date. Rows without source_date are deliberately not
    backfilled with guessed filing dates.
    """
    signal = parse_iso_date(signal_date)
    if signal is None:
        return {"status": "WAITING_HISTORY", "history_quarters": 0}

    selected = [
        row
        for row in rows
        if row.get("available_date") is not None
        and row["available_date"] <= signal
    ]

    if not selected:
        return {"status": "WAITING_HISTORY", "history_quarters": 0}

    latest = dict(selected[-1])
    latest.pop("available_date", None)

    year = latest.get("fiscal_year")
    quarter = latest.get("fiscal_quarter")
    latest["period"] = (
        f"{year}-Q{quarter}"
        if year is not None and quarter is not None
        else None
    )
    latest["history_quarters"] = len(selected)
    latest["status"] = (
        "READY"
        if len(selected)
        >= BACKTEST_FINANCIAL_MIN_QUARTERS
        else "WAITING_HISTORY"
    )
    return latest


# ============================================================
# HISTORICAL SNAPSHOT
# ============================================================


def build_price_snapshot(price_rows: list[dict[str, Any]]) -> dict[str, Any]:
    price = exporter.price_snapshot(price_rows)

    previous_rows = price_rows[:-1] if len(price_rows) >= 2 else []
    recent_highs = [
        safe_float(row.get("high"))
        for row in previous_rows[-20:]
    ]
    valid_highs = [value for value in recent_highs if value is not None]

    breakout_price_candidate = max(valid_highs) if valid_highs else None
    price["breakout_price_candidate"] = round_or_none(
        breakout_price_candidate,
        2,
    )
    return price


def build_historical_stock(
    master: dict[str, Any],
    signal_date: str,
    price_rows: list[dict[str, Any]],
    institutional_rows: list[dict[str, Any]],
    tdcc_rows: list[dict[str, Any]],
    revenue_rows: list[dict[str, Any]],
    financial_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not price_rows or price_rows[-1].get("trade_date") != signal_date:
        return None

    listed_date = master.get("listed_date")
    if listed_date and str(listed_date) > signal_date:
        return None

    price = build_price_snapshot(price_rows)
    institutional = exporter.institutional_snapshot(institutional_rows)
    tdcc = latest_tdcc_asof(tdcc_rows, signal_date)
    revenue = revenue_asof(revenue_rows, signal_date)
    financial = financial_asof(financial_rows, signal_date)

    readiness = exporter.stock_readiness(
        price,
        institutional,
        tdcc,
        revenue,
        financial,
    )

    return {
        **master,
        "latest": price,
        "technical": {
            "ma20": price.get("ma20"),
            "ma60": price.get("ma60"),
            "atr14": price.get("atr14"),
            "return_5d_pct": price.get("return_5d_pct"),
            "return_10d_pct": price.get("return_10d_pct"),
            "return_20d_pct": price.get("return_20d_pct"),
            "volume_ratio_20": price.get("volume_ratio_20"),
            "breakout_price_candidate": price.get("breakout_price_candidate"),
        },
        "institutional": institutional,
        "tdcc": tdcc,
        "fundamental": {
            "revenue": revenue,
            "financial": financial,
        },
        "readiness": readiness,
        "scores": {},
        "stage": {
            "code": "WAITING_DATA",
            "label": "資料補齊中",
        },
        "trade_plan": {},
        "action": "等待評分",
    }


# ============================================================
# FUTURE PERFORMANCE
# ============================================================


def future_performance(
    all_price_rows: list[dict[str, Any]],
    signal_date: str,
) -> dict[str, float | None]:
    dates = [str(row["trade_date"]) for row in all_price_rows]
    index = bisect.bisect_left(dates, signal_date)

    if index >= len(all_price_rows) or dates[index] != signal_date:
        return {
            "future_return_5d": None,
            "future_return_10d": None,
            "future_return_20d": None,
            "max_gain_20d": None,
            "max_drawdown_20d": None,
        }

    base_close = safe_float(all_price_rows[index].get("close"))
    if base_close is None or base_close <= 0:
        return {
            "future_return_5d": None,
            "future_return_10d": None,
            "future_return_20d": None,
            "max_gain_20d": None,
            "max_drawdown_20d": None,
        }

    def future_return(days: int) -> float | None:
        target_index = index + days
        if target_index >= len(all_price_rows):
            return None
        target_close = safe_float(all_price_rows[target_index].get("close"))
        if target_close is None:
            return None
        return (target_close / base_close - 1.0) * 100.0

    end = min(index + FUTURE_DAYS, len(all_price_rows) - 1)
    future_rows = all_price_rows[index + 1 : end + 1]

    highs = [safe_float(row.get("high")) for row in future_rows]
    lows = [safe_float(row.get("low")) for row in future_rows]
    valid_highs = [value for value in highs if value is not None]
    valid_lows = [value for value in lows if value is not None]

    max_gain = (
        (max(valid_highs) / base_close - 1.0) * 100.0
        if valid_highs
        else None
    )
    max_drawdown = (
        (min(valid_lows) / base_close - 1.0) * 100.0
        if valid_lows
        else None
    )

    return {
        "future_return_5d": round_or_none(future_return(5), 4),
        "future_return_10d": round_or_none(future_return(10), 4),
        "future_return_20d": round_or_none(future_return(20), 4),
        "max_gain_20d": round_or_none(max_gain, 4),
        "max_drawdown_20d": round_or_none(max_drawdown, 4),
    }


# ============================================================
# SUMMARY
# ============================================================


def overall_bucket(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value < 40:
        return "00-39"
    if value < 50:
        return "40-49"
    if value < 60:
        return "50-59"
    if value < 70:
        return "60-69"
    if value < 80:
        return "70-79"
    return "80+"


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    returns_5 = [safe_float(row.get("future_return_5d")) for row in rows]
    returns_10 = [safe_float(row.get("future_return_10d")) for row in rows]
    returns_20 = [safe_float(row.get("future_return_20d")) for row in rows]
    gains = [safe_float(row.get("max_gain_20d")) for row in rows]
    drawdowns = [safe_float(row.get("max_drawdown_20d")) for row in rows]

    valid_20 = [value for value in returns_20 if value is not None]
    win_rate_20 = (
        sum(value > 0 for value in valid_20) / len(valid_20) * 100.0
        if valid_20
        else None
    )

    return {
        "count": len(rows),
        "future_20d_count": len(valid_20),
        "avg_5d_pct": round_or_none(mean_or_none(returns_5), 3),
        "avg_10d_pct": round_or_none(mean_or_none(returns_10), 3),
        "avg_20d_pct": round_or_none(mean_or_none(returns_20), 3),
        "median_20d_pct": round_or_none(median_or_none(returns_20), 3),
        "win_rate_20d_pct": round_or_none(win_rate_20, 2),
        "avg_max_gain_20d_pct": round_or_none(mean_or_none(gains), 3),
        "avg_max_drawdown_20d_pct": round_or_none(mean_or_none(drawdowns), 3),
    }


def build_stage_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("stage") or "UNKNOWN")].append(row)

    result = []
    for stage in STAGE_ORDER:
        summary = summarize_group(grouped.get(stage, []))
        result.append({"stage": stage, **summary})
    return result


def build_bucket_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = ("00-39", "40-49", "50-59", "60-69", "70-79", "80+")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[overall_bucket(safe_float(row.get("overall")))].append(row)

    result = []
    for bucket in order:
        summary = summarize_group(grouped.get(bucket, []))
        result.append({"overall_bucket": bucket, **summary})
    return result


# ============================================================
# BACKTEST
# ============================================================


def run_backtest(window_days: int, signal_step: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url, token = load_dev_credentials()

    print("Target      : DEV")
    print("PROD Access : DISABLED")
    print(f"Model       : {model.SCORE_MODEL_VERSION}")

    conn = libsql.connect(database=url, auth_token=token)

    try:
        trade_dates = load_trade_dates(conn)

        minimum_dates = PRICE_LOOKBACK_ROWS + FUTURE_DAYS + 1
        if len(trade_dates) < minimum_dates:
            raise RuntimeError(
                f"Not enough stock_price_daily history: {len(trade_dates)} trade dates"
            )

        latest_signal_index = len(trade_dates) - FUTURE_DAYS - 1
        earliest_signal_index = max(
            PRICE_LOOKBACK_ROWS - 1,
            latest_signal_index - window_days + 1,
        )

        candidate_indices = list(
            range(earliest_signal_index, latest_signal_index + 1, signal_step)
        )
        if candidate_indices[-1] != latest_signal_index:
            candidate_indices.append(latest_signal_index)

        signal_dates = [trade_dates[index] for index in candidate_indices]

        first_signal_index = candidate_indices[0]
        last_signal_index = candidate_indices[-1]

        raw_start_index = max(0, first_signal_index - PRICE_LOOKBACK_ROWS - 10)
        raw_end_index = min(
            len(trade_dates) - 1,
            last_signal_index + FUTURE_DAYS + 5,
        )

        raw_start_date = trade_dates[raw_start_index]
        raw_end_date = trade_dates[raw_end_index]

        inst_start_index = max(0, first_signal_index - INSTITUTIONAL_LOOKBACK_ROWS - 10)
        inst_start_date = trade_dates[inst_start_index]

        print(f"Signal Dates: {len(signal_dates)}")
        print(f"Signal Range: {signal_dates[0]} -> {signal_dates[-1]}")
        print(f"Price Range : {raw_start_date} -> {raw_end_date}")

        print("Loading Stock Master ...")
        masters = load_stock_master_all_common(conn)

        print("Loading Price History ...")
        prices = load_prices(conn, raw_start_date, raw_end_date)

        print("Loading Institutional ...")
        institutions = load_institutions(conn, inst_start_date, signal_dates[-1])

        print("Loading TDCC ...")
        tdcc = load_tdcc(conn, signal_dates[-1])

        print("Loading Monthly Revenue ...")
        revenues = load_revenues(conn)

        print("Loading Quarterly Financial ...")
        financials, missing_financial_source_dates = load_financials(conn)

    finally:
        conn.close()

    price_dates_by_stock = {
        stock_id: [str(row["trade_date"]) for row in rows]
        for stock_id, rows in prices.items()
    }
    inst_dates_by_stock = {
        stock_id: [str(row["trade_date"]) for row in rows]
        for stock_id, rows in institutions.items()
    }

    output_rows: list[dict[str, Any]] = []
    coverage_by_date: list[dict[str, Any]] = []

    for signal_no, signal_date in enumerate(signal_dates, start=1):
        snapshots: list[dict[str, Any]] = []
        source_price_rows: dict[str, list[dict[str, Any]]] = {}

        for stock_id, master in masters.items():
            all_price_rows = prices.get(stock_id, [])
            if not all_price_rows:
                continue

            price_dates = price_dates_by_stock[stock_id]
            price_end = bisect.bisect_right(price_dates, signal_date)
            if price_end <= 0 or price_dates[price_end - 1] != signal_date:
                continue

            historical_prices = all_price_rows[
                max(0, price_end - PRICE_LOOKBACK_ROWS) : price_end
            ]

            all_inst_rows = institutions.get(stock_id, [])
            inst_dates = inst_dates_by_stock.get(stock_id, [])
            inst_end = bisect.bisect_right(inst_dates, signal_date)
            historical_inst = all_inst_rows[
                max(0, inst_end - INSTITUTIONAL_LOOKBACK_ROWS) : inst_end
            ]

            stock = build_historical_stock(
                master=master,
                signal_date=signal_date,
                price_rows=historical_prices,
                institutional_rows=historical_inst,
                tdcc_rows=tdcc.get(stock_id, []),
                revenue_rows=revenues.get(stock_id, []),
                financial_rows=financials.get(stock_id, []),
            )

            if stock is None:
                continue

            snapshots.append(stock)
            source_price_rows[stock_id] = all_price_rows

        maps = model.build_percentile_maps(snapshots)

        scored = 0
        stage_counter: Counter[str] = Counter()

        for stock in snapshots:
            if not model.score_stock(stock, maps):
                continue

            scored += 1
            stage = str(stock.get("stage", {}).get("code") or "UNKNOWN")
            stage_counter[stage] += 1

            stock_id = str(stock["stock_id"])
            performance = future_performance(
                source_price_rows[stock_id],
                signal_date,
            )

            scores = stock.get("scores", {})
            trade_plan = stock.get("trade_plan", {})

            output_rows.append(
                {
                    "signal_date": signal_date,
                    "stock_id": stock_id,
                    "short_name": stock.get("short_name"),
                    "market": stock.get("market"),
                    "industry_name": stock.get("industry_name"),
                    "close": stock.get("latest", {}).get("close"),
                    "ma20": stock.get(
                        "technical",
                        {},
                    ).get("ma20"),

                    "ma60": stock.get(
                        "technical",
                        {},
                    ).get("ma60"),

                    "atr14": stock.get(
                        "technical",
                        {},
                    ).get("atr14"),

                    "return_5d_pct": stock.get(
                        "technical",
                        {},
                    ).get("return_5d_pct"),

                    "return_10d_pct": stock.get(
                        "technical",
                        {},
                    ).get("return_10d_pct"),

                    "return_20d_pct": stock.get(
                        "technical",
                        {},
                    ).get("return_20d_pct"),

                    "volume_ratio_20": stock.get(
                        "technical",
                        {},
                    ).get("volume_ratio_20"),
                    "trend": scores.get("trend"),
                    "relative_strength": scores.get(
                        "relative_strength"
                    ),
                    "momentum_volume": scores.get(
                        "momentum_volume"
                    ),

                    "fundamental": scores.get(
                        "fundamental"
                    ),
                    "chip": scores.get(
                        "chip"
                    ),
                    "technical": scores.get(
                        "technical"
                    ),
                    "overall": scores.get(
                        "overall"
                    ),
                    "timing": scores.get(
                        "timing"
                    ),
                    "stage": stage,
                    "buy_zone_distance_pct": trade_plan.get(
                        "distance_to_buy_zone_pct"
                    ),
                    "breakout_distance_pct": trade_plan.get(
                        "breakout_distance_pct"
                    ),
                    "current_risk_pct": trade_plan.get("current_risk_pct"),
                    **performance,
                }
            )

        coverage_by_date.append(
            {
                "signal_date": signal_date,
                "snapshot_stocks": len(snapshots),
                "scored_stocks": scored,
                "score_rate_pct": round(
                    scored / len(snapshots) * 100.0,
                    2,
                )
                if snapshots
                else 0.0,
                **{f"stage_{key.lower()}": stage_counter.get(key, 0) for key in STAGE_ORDER},
            }
        )

        print(
            f"[{signal_no:02}/{len(signal_dates):02}] "
            f"{signal_date} | snapshots={len(snapshots):,} "
            f"scored={scored:,}"
        )

    meta = {
        "generated_at": now_iso(),
        "environment": "DEV",
        "prod_access": False,
        "model_version": model.SCORE_MODEL_VERSION,
        "window_days": window_days,
        "signal_step": signal_step,
        "signal_dates": signal_dates,
        "signal_count": len(signal_dates),
        "row_count": len(output_rows),
        "price_lookback_rows": PRICE_LOOKBACK_ROWS,
        "future_days": FUTURE_DAYS,
        "revenue_availability_rule": (
            f"revenue_month is treated as available on day {REVENUE_AVAILABLE_DAY} "
            "of the following month because monthly_revenue has no real announcement date"
        ),
        "financial_availability_rule": (
            "STRICT: only quarterly_financial rows with source_date <= signal_date are used; "
            "rows without source_date are excluded"
        ),
        "financial_rows_missing_source_date": missing_financial_source_dates,
        "known_limitations": [
            "monthly revenue availability uses a conservative proxy, not the actual announcement timestamp",
            "historical stock universe depends on stock_master rows retained in DEV; no explicit delisting date exists in schema",
            "this Research v1 backtest measures signal-date close to future closes and does not include transaction costs, slippage, limit-up/down execution, or position sizing",
        ],
        "coverage_by_date": coverage_by_date,
    }

    return output_rows, meta


# ============================================================
# OUTPUT / CONSOLE
# ============================================================


def print_summary(stage_summary: list[dict[str, Any]]) -> None:
    print()
    print("=" * 100)
    print("STAGE BACKTEST SUMMARY")
    print("=" * 100)
    print(
        "stage       count  avg5D   avg10D  avg20D  median20  win20%  maxGain20  maxDD20"
    )

    for row in stage_summary:
        def fmt(key: str, width: int = 7) -> str:
            value = row.get(key)
            if value is None:
                return f"{'-':>{width}}"
            return f"{float(value):>{width}.2f}"

        print(
            f"{row['stage']:10} "
            f"{row['count']:6} "
            f"{fmt('avg_5d_pct')} "
            f"{fmt('avg_10d_pct')} "
            f"{fmt('avg_20d_pct')} "
            f"{fmt('median_20d_pct', 8)} "
            f"{fmt('win_rate_20d_pct', 7)} "
            f"{fmt('avg_max_gain_20d_pct', 9)} "
            f"{fmt('avg_max_drawdown_20d_pct', 8)}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="StockWaveScanner V3 Research Backtest (DEV read-only)"
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help="Most recent eligible market trading-day window (default: 120)",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=DEFAULT_SIGNAL_STEP,
        help="Evaluate every N market trading days (default: 5)",
    )
    return parser.parse_args()


def main() -> int:
    configure_console()
    args = parse_args()

    if args.window_days < 20:
        print("ERROR: --window-days must be >= 20")
        return 1
    if args.step < 1:
        print("ERROR: --step must be >= 1")
        return 1

    print("=" * 80)
    print("StockWaveScanner V3 - Historical Backtest Research v1")
    print("=" * 80)

    try:
        rows, meta = run_backtest(
            window_days=args.window_days,
            signal_step=args.step,
        )

        if not rows:
            raise RuntimeError(
                "Backtest produced 0 scored rows. Check historical source-date coverage."
            )

        stage_summary = build_stage_summary(rows)
        bucket_summary = build_bucket_summary(rows)

        row_fields = [
            "signal_date",
            "stock_id",
            "short_name",
            "market",
            "industry_name",
            "close",
            "ma20",
            "ma60",
            "atr14",
            "return_5d_pct",
            "return_10d_pct",
            "return_20d_pct",
            "volume_ratio_20",
            "trend",
            "relative_strength",
            "momentum_volume",
            "fundamental",
            "chip",
            "technical",
            "overall",
            "timing",
            "stage",
            "buy_zone_distance_pct",
            "breakout_distance_pct",
            "current_risk_pct",
            "future_return_5d",
            "future_return_10d",
            "future_return_20d",
            "max_gain_20d",
            "max_drawdown_20d",
        ]

        stage_fields = [
            "stage",
            "count",
            "future_20d_count",
            "avg_5d_pct",
            "avg_10d_pct",
            "avg_20d_pct",
            "median_20d_pct",
            "win_rate_20d_pct",
            "avg_max_gain_20d_pct",
            "avg_max_drawdown_20d_pct",
        ]

        bucket_fields = [
            "overall_bucket",
            "count",
            "future_20d_count",
            "avg_5d_pct",
            "avg_10d_pct",
            "avg_20d_pct",
            "median_20d_pct",
            "win_rate_20d_pct",
            "avg_max_gain_20d_pct",
            "avg_max_drawdown_20d_pct",
        ]

        write_csv(OUTPUT_DIR / "backtest_rows.csv", rows, row_fields)
        write_csv(OUTPUT_DIR / "stage_summary.csv", stage_summary, stage_fields)
        write_csv(OUTPUT_DIR / "overall_bucket_summary.csv", bucket_summary, bucket_fields)
        write_json(OUTPUT_DIR / "backtest_meta.json", meta)

        print_summary(stage_summary)

        print()
        print("=" * 80)
        print("BACKTEST RESULT")
        print("=" * 80)
        print(f"Signals      : {meta['signal_count']:,}")
        print(f"Scored Rows  : {len(rows):,}")
        print(
            "Financial rows missing source_date: "
            f"{meta['financial_rows_missing_source_date']:,}"
        )
        print()
        print("[PASS] V3 historical backtest generated")
        return 0

    except Exception as exc:
        print()
        print("=" * 80)
        print("ERROR")
        print("=" * 80)
        print(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
