from __future__ import annotations

import argparse
import inspect
import json
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from crawler.http_client import tdcc_get
from db.database import get_connection
from db import repository


URL = (
    "https://openapi.tdcc.com.tw/"
    "v1/opendata/1-5"
)

SOURCE = "TDCC_SHAREHOLDING"

REQUEST_KEY_PREFIX = "TDCC_SHAREHOLDING_LATEST"


def _now_iso() -> str:
    return (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )


def _request_key(run_date: str) -> str:
    """
    latest endpoint 沒有歷史日期參數。

    run_date 只代表本次排程執行日，
    真正 TDCC 資料日期仍完全以官方 response
    的 data_date 為準，不做日期推論。
    """
    datetime.strptime(run_date, "%Y-%m-%d")
    return f"{REQUEST_KEY_PREFIX}:{run_date}"


def _normalize_key(
    value: object,
) -> str:
    return (
        str(value)
        .replace("\ufeff", "")
        .strip()
    )


def _normalize_row(
    row: dict,
) -> dict:
    return {
        _normalize_key(key): value
        for key, value in row.items()
    }


def _normalize_stock_id(
    value: object,
) -> str:
    return str(value).strip()


def _normalize_data_date(
    value: object,
) -> str:
    text = str(value).strip()

    try:
        parsed = datetime.strptime(
            text,
            "%Y%m%d",
        )
    except ValueError as exc:
        raise RuntimeError(
            "TDCC 無法識別資料日期："
            f"{value!r}"
        ) from exc

    return parsed.strftime(
        "%Y-%m-%d"
    )


def _parse_pct(
    value: object,
) -> Decimal:
    text = str(value).strip()

    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise RuntimeError(
            "TDCC 無法解析比例："
            f"{value!r}"
        ) from exc


def _require_repository_function(
    name: str,
) -> Callable[..., Any]:
    func = getattr(
        repository,
        name,
        None,
    )

    if func is None:
        raise RuntimeError(
            "db.repository 缺少必要函式："
            f"{name}"
        )

    if not callable(func):
        raise RuntimeError(
            f"db.repository.{name} "
            "不是 callable"
        )

    return func


def _call_repository_function(
    name: str,
    values: dict[str, Any],
) -> Any:
    func = _require_repository_function(
        name
    )

    signature = inspect.signature(
        func
    )

    kwargs: dict[str, Any] = {}
    missing: list[str] = []

    for param_name, param in (
        signature.parameters.items()
    ):
        if param.kind in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }:
            continue

        if param_name in values:
            kwargs[param_name] = (
                values[param_name]
            )
            continue

        if (
            param.default
            is inspect.Parameter.empty
        ):
            missing.append(
                param_name
            )

    if missing:
        raise RuntimeError(
            f"無法呼叫 repository.{name}"
            f"{signature}。\n"
            f"缺少必要參數：{missing}\n"
            "目前同步器可提供："
            f"{sorted(values.keys())}"
        )

    return func(
        **kwargs
    )


def _crawl_success_exists(
    source: str,
    request_key: str,
) -> bool:
    return bool(
        _call_repository_function(
            "crawl_success_exists",
            {
                "source": source,
                "request_key": request_key,
            },
        )
    )


def _start_crawl_log(
    source: str,
    request_key: str,
) -> Any:
    return _call_repository_function(
        "start_crawl_log",
        {
            "source": source,
            "request_key": request_key,
            "status": "RUNNING",
            "started_at": _now_iso(),
        },
    )


def _finish_crawl_success(
    crawl_log_id: Any,
    source: str,
    request_key: str,
    record_count: int,
) -> None:
    _call_repository_function(
        "finish_crawl_success",
        {
            "crawl_log_id": crawl_log_id,
            "log_id": crawl_log_id,
            "id": crawl_log_id,
            "source": source,
            "request_key": request_key,
            "status": "SUCCESS",
            "record_count": record_count,
            "finished_at": _now_iso(),
        },
    )


def _finish_crawl_error(
    crawl_log_id: Any,
    source: str,
    request_key: str,
    error_message: str,
) -> None:
    _call_repository_function(
        "finish_crawl_error",
        {
            "crawl_log_id": crawl_log_id,
            "log_id": crawl_log_id,
            "id": crawl_log_id,
            "source": source,
            "request_key": request_key,
            "status": "ERROR",
            "error_message": error_message,
            "finished_at": _now_iso(),
        },
    )


def _get_raw_response_columns(
    conn,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        PRAGMA table_info(raw_responses)
        """
    ).fetchall()

    if not rows:
        raise RuntimeError(
            "找不到 raw_responses table"
        )

    return [
        dict(row)
        for row in rows
    ]


def _save_raw_response(
    *,
    request_key: str,
    payload: list[dict],
    data_date: str,
) -> None:
    """
    沿用 Raw-first 原則。

    不假設 raw_responses 固定欄位名稱，
    依目前實際 schema 自動對應。
    """
    raw_text = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    downloaded_at = _now_iso()

    known_values: dict[str, Any] = {
        "source":
            SOURCE,

        "request_key":
            request_key,

        "key":
            request_key,

        "data_date":
            data_date,

        "trade_date":
            data_date,

        "request_date":
            data_date,

        "url":
            URL,

        "request_url":
            URL,

        "endpoint":
            URL,

        "method":
            "GET",

        "http_method":
            "GET",

        "response_text":
            raw_text,

        "response_body":
            raw_text,

        "raw_response":
            raw_text,

        "raw_text":
            raw_text,

        "response_json":
            raw_text,

        "raw_json":
            raw_text,

        "payload":
            raw_text,

        "content":
            raw_text,

        "body":
            raw_text,

        "status_code":
            200,

        "http_status":
            200,

        "response_status":
            200,

        "content_type":
            "application/json",

        "downloaded_at":
            downloaded_at,

        "created_at":
            downloaded_at,

        "fetched_at":
            downloaded_at,

        "updated_at":
            downloaded_at,
    }

    conn = get_connection()

    try:
        schema = (
            _get_raw_response_columns(
                conn
            )
        )

        insert_values = {}
        unsupported_required = []

        for column in schema:
            name = column["name"]

            if bool(
                column["pk"]
            ):
                continue

            if name in known_values:
                insert_values[name] = (
                    known_values[name]
                )
                continue

            if (
                column["dflt_value"]
                is not None
            ):
                continue

            if not bool(
                column["notnull"]
            ):
                continue

            unsupported_required.append(
                name
            )

        if unsupported_required:
            raise RuntimeError(
                "raw_responses 存在尚未支援的 "
                "NOT NULL 欄位："
                f"{unsupported_required}"
            )

        response_columns = {
            "response_text",
            "response_body",
            "raw_response",
            "raw_text",
            "response_json",
            "raw_json",
            "payload",
            "content",
            "body",
        }

        if not (
            response_columns
            & set(insert_values)
        ):
            raise RuntimeError(
                "raw_responses 找不到可保存 "
                "response 本體的欄位"
            )

        columns = list(
            insert_values
        )

        column_sql = ", ".join(
            f'"{column}"'
            for column in columns
        )

        placeholders = ", ".join(
            "?"
            for _ in columns
        )

        conn.execute(
            (
                "INSERT INTO raw_responses "
                f"({column_sql}) "
                f"VALUES ({placeholders})"
            ),
            [
                insert_values[column]
                for column in columns
            ],
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def _get_active_stock_ids() -> set[str]:
    """
    TDCC Open Data 包含 ETF 等大量商品。

    正式 normalized data 不靠「4 碼」
    單獨判斷，而是跟目前 active
    TWSE + TPEx 股票主檔做 intersection。
    """
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                stock_id,
                COUNT(
                    DISTINCT market
                ) AS market_count
            FROM stocks
            WHERE is_active = 1
              AND LENGTH(stock_id) = 4
              AND stock_id GLOB
                  '[0-9][0-9][0-9][0-9]'
            GROUP BY stock_id
            ORDER BY stock_id
            """
        ).fetchall()

    finally:
        conn.close()

    duplicates = [
        str(row["stock_id"])
        for row in rows
        if int(
            row["market_count"]
        ) > 1
    ]

    if duplicates:
        raise RuntimeError(
            "active stocks 出現跨市場重複 "
            "stock_id，但 tdcc_holdings "
            "schema 沒有 market："
            f"{duplicates[:20]}"
        )

    return {
        str(row["stock_id"])
        for row in rows
    }


def _fetch_payload() -> list[dict]:
    response = tdcc_get(
        URL
    )

    response.raise_for_status()

    content_type = (
        response.headers.get(
            "Content-Type",
            "",
        )
    )

    if "json" not in content_type.lower():
        raise RuntimeError(
            "TDCC OpenAPI response "
            "不是 JSON："
            f"{content_type!r}"
        )

    try:
        payload = response.json()

    except ValueError as exc:
        raise RuntimeError(
            "TDCC OpenAPI JSON "
            "decode failed"
        ) from exc

    if not isinstance(
        payload,
        list,
    ):
        raise RuntimeError(
            "TDCC OpenAPI top-level "
            "不是 list"
        )

    if not payload:
        raise RuntimeError(
            "TDCC OpenAPI rows = 0"
        )

    return payload


def _parse_payload(
    payload: list[dict],
    active_stock_ids: set[str],
) -> tuple[
    str,
    list[dict[str, Any]],
]:
    """
    策略只需要：

    retail_holder_pct
        = level 1 + level 2

    large_holder_pct
        = level 15
    """
    by_stock: dict[
        str,
        dict[str, Decimal],
    ] = {}

    dates: set[str] = set()

    for raw_row in payload:
        if not isinstance(
            raw_row,
            dict,
        ):
            continue

        row = _normalize_row(
            raw_row
        )

        stock_id = (
            _normalize_stock_id(
                row.get(
                    "證券代號",
                    "",
                )
            )
        )

        if (
            stock_id
            not in active_stock_ids
        ):
            continue

        level = str(
            row.get(
                "持股分級",
                "",
            )
        ).strip()

        if level not in {
            "1",
            "2",
            "15",
        }:
            continue

        raw_date = row.get(
            "資料日期"
        )

        if raw_date is None:
            raise RuntimeError(
                "TDCC row 缺少資料日期："
                f"{stock_id}"
            )

        data_date = (
            _normalize_data_date(
                raw_date
            )
        )

        dates.add(
            data_date
        )

        pct = _parse_pct(
            row.get(
                "占集保庫存數比例%",
            )
        )

        stock_values = (
            by_stock.setdefault(
                stock_id,
                {},
            )
        )

        if level in stock_values:
            raise RuntimeError(
                "TDCC 同股票同 level "
                "出現重複資料："
                f"{stock_id} level={level}"
            )

        stock_values[level] = pct

    if len(dates) != 1:
        raise RuntimeError(
            "TDCC latest OpenAPI "
            "預期單一資料日期，"
            f"實際={sorted(dates)}"
        )

    data_date = next(
        iter(dates)
    )

    records = []

    incomplete = []

    for stock_id in sorted(
        active_stock_ids
    ):
        values = by_stock.get(
            stock_id
        )

        if values is None:
            #
            # TDCC 本身可能沒有該證券資料，
            # 不製造假值。
            #
            continue

        missing_levels = (
            {
                "1",
                "2",
                "15",
            }
            - set(values)
        )

        if missing_levels:
            incomplete.append(
                (
                    stock_id,
                    sorted(
                        missing_levels
                    ),
                )
            )
            continue

        retail_pct = (
            values["1"]
            + values["2"]
        )

        large_pct = (
            values["15"]
        )

        records.append(
            {
                "stock_id":
                    stock_id,

                "data_date":
                    data_date,

                "large_holder_pct":
                    float(
                        large_pct
                    ),

                "retail_holder_pct":
                    float(
                        retail_pct
                    ),

                "source":
                    SOURCE,

                "downloaded_at":
                    _now_iso(),
            }
        )

    if incomplete:
        print(
            "[WARN] 有 active 股票 "
            "缺 level 1/2/15："
            f"{len(incomplete)}"
        )

        print(
            "[WARN] sample =",
            incomplete[:10],
        )

    return (
        data_date,
        records,
    )


def _write_records(
    records: list[dict[str, Any]],
) -> int:
    """
    直接使用已確認的 tdcc_holdings schema：

    PK:
        (stock_id, data_date)
    """
    conn = get_connection()

    try:
        for record in records:
            conn.execute(
                """
                INSERT INTO tdcc_holdings (
                    stock_id,
                    data_date,
                    large_holder_pct,
                    retail_holder_pct,
                    source,
                    downloaded_at
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                )
                ON CONFLICT (
                    stock_id,
                    data_date
                )
                DO UPDATE SET
                    large_holder_pct =
                        excluded.large_holder_pct,
                    retail_holder_pct =
                        excluded.retail_holder_pct,
                    source =
                        excluded.source,
                    downloaded_at =
                        excluded.downloaded_at
                """,
                (
                    record["stock_id"],
                    record["data_date"],
                    record[
                        "large_holder_pct"
                    ],
                    record[
                        "retail_holder_pct"
                    ],
                    record["source"],
                    record[
                        "downloaded_at"
                    ],
                ),
            )

        conn.commit()

        return len(
            records
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="同步 TDCC 最新全市場持股分級資料"
    )
    parser.add_argument(
        "--run-date",
        required=True,
        help=(
            "排程執行日 YYYY-MM-DD。這不是 TDCC 歷史查詢日期；"
            "資料日期仍以官方 latest response 為準。"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    request_key = _request_key(args.run_date)

    print("=" * 72)
    print("TDCC Market Latest Sync")
    print("=" * 72)

    print(
        "[INFO] request_key =",
        request_key,
    )

    if _crawl_success_exists(
        SOURCE,
        request_key,
    ):
        print(
            "[SKIP] 今日已有 SUCCESS"
        )
        return

    crawl_log_id = None

    try:
        crawl_log_id = (
            _start_crawl_log(
                SOURCE,
                request_key,
            )
        )

        print(
            "[INFO] 讀取 active "
            "TWSE + TPEx 股票主檔..."
        )

        active_stock_ids = (
            _get_active_stock_ids()
        )

        print(
            "[INFO] active 4-digit "
            "stocks =",
            len(active_stock_ids),
        )

        print(
            "[INFO] 抓取 TDCC "
            "Open Data 1-5..."
        )

        payload = (
            _fetch_payload()
        )

        print(
            "[INFO] raw rows =",
            len(payload),
        )

        data_date, records = (
            _parse_payload(
                payload=payload,
                active_stock_ids=(
                    active_stock_ids
                ),
            )
        )

        print(
            "[INFO] data_date =",
            data_date,
        )

        print(
            "[INFO] normalized "
            "active-stock rows =",
            len(records),
        )

        if not records:
            raise RuntimeError(
                "TDCC normalized "
                "records = 0"
            )

        print(
            "[INFO] 保存 Raw..."
        )

        _save_raw_response(
            request_key=(
                request_key
            ),
            payload=payload,
            data_date=data_date,
        )

        print(
            "[INFO] 寫入 "
            "tdcc_holdings..."
        )

        record_count = (
            _write_records(
                records
            )
        )

        _finish_crawl_success(
            crawl_log_id=(
                crawl_log_id
            ),
            source=SOURCE,
            request_key=request_key,
            record_count=(
                record_count
            ),
        )

        print()
        print(
            "[OK] TDCC Market Latest"
        )

        print(
            "[OK] data_date =",
            data_date,
        )

        print(
            "[OK] record_count =",
            record_count,
        )

    except Exception as exc:
        error_message = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        print(
            "[ERROR]",
            error_message,
        )

        if crawl_log_id is not None:
            try:
                _finish_crawl_error(
                    crawl_log_id=(
                        crawl_log_id
                    ),
                    source=SOURCE,
                    request_key=(
                        request_key
                    ),
                    error_message=(
                        error_message
                    ),
                )
            except Exception as log_exc:
                print(
                    "[ERROR] crawl log "
                    "ERROR 更新失敗："
                    f"{log_exc}"
                )

        raise


if __name__ == "__main__":
    try:
        main()

    except Exception:
        sys.exit(1)