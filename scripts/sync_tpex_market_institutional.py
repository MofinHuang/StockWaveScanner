from __future__ import annotations

import argparse
import inspect
import json
import sys
from datetime import datetime
from typing import Any, Callable

from crawler.tpex_market_institutional import (
    SOURCE,
    fetch_tpex_market_foreign,
)
from db.database import get_connection
from db import repository


DEFAULT_TEST_DATE = "2026-08-14"

REQUEST_KEY_PREFIX = "TPEX_QFII_STAT"

TPEX_QFII_URL = (
    "https://www.tpex.org.tw/"
    "www/zh-tw/insti/qfiiStat"
)


def _now_iso() -> str:
    return (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )


def _request_key(
    trade_date: str,
) -> str:
    return (
        f"{REQUEST_KEY_PREFIX}:"
        f"{trade_date}"
    )


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
            "db.repository."
            f"{name} 不是 callable"
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
            "缺少必要參數："
            f"{missing}\n"
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
    source: str,
    request_key: str,
    trade_date: str,
    search_type: str,
    payload: dict[str, Any],
) -> None:
    """
    Raw-first：

    不猜 raw_responses 的固定 schema。

    先透過：
        PRAGMA table_info(raw_responses)

    取得現有欄位，再將已知語意欄位安全對應。

    若 schema 含未支援且沒有 default 的
    NOT NULL 欄位，直接停止並列出欄位名稱。
    """
    raw_request_key = (
        f"{request_key}:"
        f"{search_type}"
    )

    request_params = {
        "type": "Daily",
        "date": trade_date.replace(
            "-",
            "/",
        ),
        "searchType": search_type,
    }

    request_json = json.dumps(
        request_params,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    response_json = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    downloaded_at = _now_iso()

    #
    # 同一語意提供多種常見 column alias。
    # 實際只會 INSERT raw_responses 真正存在的欄位。
    #
    known_values: dict[str, Any] = {
        # Source
        "source": source,

        # Request key
        "request_key": raw_request_key,
        "key": raw_request_key,

        # Date
        "trade_date": trade_date,
        "data_date": trade_date,
        "request_date": trade_date,

        # URL
        "url": TPEX_QFII_URL,
        "request_url": TPEX_QFII_URL,
        "endpoint": TPEX_QFII_URL,

        # HTTP method
        "method": "POST",
        "http_method": "POST",

        # Request
        "params": request_json,
        "request_params": request_json,
        "request_body": request_json,
        "request_data": request_json,

        # Raw response
        "response_text": response_json,
        "response_body": response_json,
        "raw_response": response_json,
        "raw_text": response_json,
        "response_json": response_json,
        "raw_json": response_json,
        "payload": response_json,
        "content": response_json,
        "body": response_json,

        # HTTP status
        "status_code": 200,
        "http_status": 200,
        "response_status": 200,

        # MIME
        "content_type":
            "application/json;charset=UTF-8",

        # Time
        "downloaded_at": downloaded_at,
        "created_at": downloaded_at,
        "fetched_at": downloaded_at,
        "updated_at": downloaded_at,
    }

    conn = get_connection()

    try:
        schema = (
            _get_raw_response_columns(
                conn
            )
        )

        insert_values: dict[
            str,
            Any,
        ] = {}

        unsupported_required: list[
            str
        ] = []

        for column in schema:
            name = column["name"]

            not_null = bool(
                column["notnull"]
            )

            default_value = (
                column["dflt_value"]
            )

            is_primary_key = bool(
                column["pk"]
            )

            #
            # INTEGER PRIMARY KEY 通常由 SQLite
            # 自動產生，不需要 INSERT。
            #
            if is_primary_key:
                continue

            if name in known_values:
                insert_values[name] = (
                    known_values[name]
                )
                continue

            #
            # 有 default 的欄位交給 DB。
            #
            if default_value is not None:
                continue

            #
            # Nullable 欄位不強行製造資料。
            #
            if not not_null:
                continue

            unsupported_required.append(
                name
            )

        if unsupported_required:
            schema_names = [
                column["name"]
                for column in schema
            ]

            raise RuntimeError(
                "raw_responses 存在尚未支援的 "
                "NOT NULL 欄位："
                f"{unsupported_required}\n"
                "目前 raw_responses 欄位："
                f"{schema_names}"
            )

        if not insert_values:
            raise RuntimeError(
                "無法建立 raw_responses INSERT："
                "沒有任何可對應欄位"
            )

        #
        # Raw response 本體必須真的被保存，
        # 不能只寫 metadata。
        #
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
            schema_names = [
                column["name"]
                for column in schema
            ]

            raise RuntimeError(
                "raw_responses 找不到可保存 "
                "raw response 本體的欄位。\n"
                "目前欄位："
                f"{schema_names}"
            )

        columns = list(
            insert_values.keys()
        )

        placeholders = ", ".join(
            "?"
            for _ in columns
        )

        column_sql = ", ".join(
            f'"{column}"'
            for column in columns
        )

        sql = (
            "INSERT INTO raw_responses "
            f"({column_sql}) "
            f"VALUES ({placeholders})"
        )

        conn.execute(
            sql,
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


def _upsert_institutional_trade(
    conn,
    record,
) -> None:
    conn.execute(
        """
        INSERT INTO institutional_trades (
            stock_id,
            market,
            trade_date,
            foreign_buy,
            foreign_sell,
            foreign_net,
            source,
            downloaded_at
        )
        VALUES (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
        ON CONFLICT (
            stock_id,
            market,
            trade_date
        )
        DO UPDATE SET
            foreign_buy = excluded.foreign_buy,
            foreign_sell = excluded.foreign_sell,
            foreign_net = excluded.foreign_net,
            source = excluded.source,
            downloaded_at = excluded.downloaded_at
        """,
        (
            record.stock_id,
            record.market,
            record.trade_date,
            record.foreign_buy,
            record.foreign_sell,
            record.foreign_net,
            record.source,
            record.downloaded_at,
        ),
    )


def _write_records(
    records,
) -> int:
    conn = get_connection()

    try:
        count = 0

        for record in records:
            _upsert_institutional_trade(
                conn,
                record,
            )

            count += 1

        conn.commit()

        return count

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def sync_one_day(
    trade_date: str,
    force: bool = False,
) -> None:
    request_key = (
        _request_key(
            trade_date
        )
    )

    print(
        "[INFO] TPEx Foreign "
        f"trade_date={trade_date}"
    )

    if (
        not force
        and _crawl_success_exists(
            source=SOURCE,
            request_key=request_key,
        )
    ):
        print(
            "[SKIP] 已有 SUCCESS "
            "crawl log："
            f"{request_key}"
        )
        return

    crawl_log_id = None

    try:
        crawl_log_id = (
            _start_crawl_log(
                source=SOURCE,
                request_key=request_key,
            )
        )

        print(
            "[INFO] 抓取 TPEx "
            "qfiiStat buy / sell..."
        )

        result = (
            fetch_tpex_market_foreign(
                trade_date
            )
        )

        if (
            result.trade_date
            != trade_date
        ):
            raise RuntimeError(
                "TPEx response 日期與 "
                "request 不一致："
                f"request={trade_date}, "
                f"response="
                f"{result.trade_date}"
            )

        print(
            "[INFO] 保存 raw response..."
        )

        _save_raw_response(
            source=SOURCE,
            request_key=request_key,
            trade_date=trade_date,
            search_type="buy",
            payload=result.buy_payload,
        )

        _save_raw_response(
            source=SOURCE,
            request_key=request_key,
            trade_date=trade_date,
            search_type="sell",
            payload=result.sell_payload,
        )

        print(
            "[INFO] normalized records = "
            f"{len(result.records)}"
        )

        if not result.records:
            raise RuntimeError(
                "TPEx Foreign "
                "normalized records = 0"
            )

        print(
            "[INFO] 寫入 "
            "institutional_trades..."
        )

        record_count = (
            _write_records(
                result.records
            )
        )

        _finish_crawl_success(
            crawl_log_id=crawl_log_id,
            source=SOURCE,
            request_key=request_key,
            record_count=record_count,
        )

        print(
            "[OK] TPEx Foreign "
            f"{trade_date}"
        )

        print(
            "[OK] record_count = "
            f"{record_count}"
        )

    except Exception as exc:
        error_message = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        print(
            "[ERROR] "
            f"{error_message}"
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


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "同步 TPEx 單日全市場 "
            "外資及陸資（不含自營商）資料"
        )
    )

    parser.add_argument(
        "--date",
        default=DEFAULT_TEST_DATE,
        help=(
            "交易日 YYYY-MM-DD，"
            "預設 2026-08-14"
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "忽略 SUCCESS crawl log "
            "重新抓取"
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    sync_one_day(
        trade_date=args.date,
        force=args.force,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(1)