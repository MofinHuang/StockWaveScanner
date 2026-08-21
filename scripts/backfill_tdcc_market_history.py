from __future__ import annotations

import argparse
import inspect
import json
import sys
import time
from datetime import datetime
from typing import Any, Callable

import requests
import urllib3
from bs4 import BeautifulSoup

from db.database import get_connection
from db import repository


HOME_URL = (
    "https://www.tdcc.com.tw/"
    "portal/zh/"
)

QUERY_URL = (
    "https://www.tdcc.com.tw/"
    "portal/zh/smWeb/qryStock"
)

SOURCE = "TDCC_HISTORY"

DEFAULT_HISTORY_WEEKS = 3
DEFAULT_LIMIT = 10
DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_RETRIES = 2


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0.0.0 "
        "Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "*/*;q=0.8"
    ),
    "Accept-Language": (
        "zh-TW,zh;q=0.9,"
        "en-US;q=0.8,en;q=0.7"
    ),
    "Accept-Encoding": (
        "gzip, deflate"
    ),
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}


def _now_iso() -> str:
    return (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )


def _normalize_date(
    value: str,
) -> str:
    return datetime.strptime(
        str(value).strip(),
        "%Y%m%d",
    ).strftime(
        "%Y-%m-%d"
    )


def _is_embedded_403(
    response: requests.Response,
) -> bool:
    return (
        "HTTP 403 Forbidden"
        in (response.text or "")
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
            f"缺少必要參數：{missing}"
        )

    return func(
        **kwargs
    )


def _crawl_success_exists(
    request_key: str,
) -> bool:
    return bool(
        _call_repository_function(
            "crawl_success_exists",
            {
                "source": SOURCE,
                "request_key": request_key,
            },
        )
    )


def _start_crawl_log(
    request_key: str,
):
    return _call_repository_function(
        "start_crawl_log",
        {
            "source": SOURCE,
            "request_key": request_key,
            "status": "RUNNING",
            "started_at": _now_iso(),
        },
    )


def _finish_crawl_success(
    crawl_log_id,
    request_key: str,
    record_count: int,
) -> None:
    _call_repository_function(
        "finish_crawl_success",
        {
            "crawl_log_id": crawl_log_id,
            "log_id": crawl_log_id,
            "id": crawl_log_id,
            "source": SOURCE,
            "request_key": request_key,
            "status": "SUCCESS",
            "record_count": record_count,
            "finished_at": _now_iso(),
        },
    )


def _finish_crawl_error(
    crawl_log_id,
    request_key: str,
    error_message: str,
) -> None:
    _call_repository_function(
        "finish_crawl_error",
        {
            "crawl_log_id": crawl_log_id,
            "log_id": crawl_log_id,
            "id": crawl_log_id,
            "source": SOURCE,
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
    stock_id: str,
    sca_date: str,
    response_text: str,
) -> None:
    data_date = _normalize_date(
        sca_date
    )

    downloaded_at = _now_iso()

    request_body = json.dumps(
        {
            "method": "submit",
            "firDate": "<dynamic>",
            "scaDate": sca_date,
            "sqlMethod": "StockNo",
            "stockNo": stock_id,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

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
            QUERY_URL,

        "request_url":
            QUERY_URL,

        "endpoint":
            QUERY_URL,

        "method":
            "POST",

        "http_method":
            "POST",

        "params":
            request_body,

        "request_params":
            request_body,

        "request_body":
            request_body,

        "request_data":
            request_body,

        "response_text":
            response_text,

        "response_body":
            response_text,

        "raw_response":
            response_text,

        "raw_text":
            response_text,

        "content":
            response_text,

        "body":
            response_text,

        "status_code":
            200,

        "http_status":
            200,

        "response_status":
            200,

        "content_type":
            "text/html;charset=UTF-8",

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
            "content",
            "body",
        }

        if not (
            response_columns
            & set(insert_values)
        ):
            raise RuntimeError(
                "raw_responses 找不到可保存 "
                "HTML response 本體的欄位"
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


def _get_required_input(
    soup: BeautifulSoup,
    name: str,
) -> str:
    node = soup.find(
        "input",
        attrs={
            "name": name,
        },
    )

    if node is None:
        raise RuntimeError(
            f"找不到 input：{name}"
        )

    value = str(
        node.get(
            "value",
            "",
        )
    ).strip()

    if not value:
        raise RuntimeError(
            f"{name} 沒有 value"
        )

    return value


def _get_sca_dates(
    soup: BeautifulSoup,
) -> list[str]:
    node = soup.find(
        "select",
        attrs={
            "name": "scaDate",
        },
    )

    if node is None:
        raise RuntimeError(
            "找不到 scaDate"
        )

    result = []

    for option in node.find_all(
        "option"
    ):
        value = str(
            option.get(
                "value",
                "",
            )
        ).strip()

        if value:
            result.append(
                value
            )

    return result


def _bootstrap_session(
    session: requests.Session,
) -> None:
    response = session.get(
        HOME_URL,
        timeout=30,
        verify=False,
    )

    response.raise_for_status()

    if _is_embedded_403(
        response
    ):
        raise RuntimeError(
            "TDCC homepage embedded 403"
        )

    if not any(
        cookie.name == "JSESSIONID"
        for cookie in session.cookies
    ):
        raise RuntimeError(
            "TDCC homepage 未取得 JSESSIONID"
        )


def _get_query_contract(
    session: requests.Session,
) -> dict[str, Any]:
    response = session.get(
        QUERY_URL,
        headers={
            "Referer": HOME_URL,
        },
        timeout=30,
        verify=False,
    )

    response.raise_for_status()

    if _is_embedded_403(
        response
    ):
        raise RuntimeError(
            "TDCC qryStock embedded 403"
        )

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    return {
        "token":
            _get_required_input(
                soup,
                "SYNCHRONIZER_TOKEN",
            ),

        "uri":
            _get_required_input(
                soup,
                "SYNCHRONIZER_URI",
            ),

        "fir_date":
            _get_required_input(
                soup,
                "firDate",
            ),

        "dates":
            _get_sca_dates(
                soup
            ),
    }


def _post_query(
    session: requests.Session,
    *,
    stock_id: str,
    sca_date: str,
    token: str,
    uri: str,
    fir_date: str,
) -> requests.Response:
    response = session.post(
        QUERY_URL,
        headers={
            "Referer":
                QUERY_URL,

            "Origin":
                "https://www.tdcc.com.tw",

            "Content-Type":
                "application/"
                "x-www-form-urlencoded",
        },
        data={
            "SYNCHRONIZER_TOKEN":
                token,

            "SYNCHRONIZER_URI":
                uri,

            "method":
                "submit",

            "firDate":
                fir_date,

            "scaDate":
                sca_date,

            "sqlMethod":
                "StockNo",

            "stockNo":
                stock_id,

            "stockName":
                "",
        },
        timeout=30,
        verify=False,
    )

    response.raise_for_status()

    if _is_embedded_403(
        response
    ):
        raise RuntimeError(
            "TDCC POST embedded 403"
        )

    return response


def _find_result_table(
    soup: BeautifulSoup,
):
    candidates = []

    for table in soup.find_all(
        "table"
    ):
        text = table.get_text(
            " ",
            strip=True,
        )

        score = sum(
            keyword in text
            for keyword in [
                "持股/單位數分級",
                "人數",
                "股數/單位數",
                "占集保庫存數比例",
            ]
        )

        if score:
            candidates.append(
                (
                    score,
                    table,
                )
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return candidates[0][1]


def _extract_rows(
    table,
) -> list[list[str]]:
    rows = []

    for tr in table.find_all(
        "tr"
    ):
        cells = [
            cell.get_text(
                " ",
                strip=True,
            )
            for cell in tr.find_all(
                [
                    "th",
                    "td",
                ]
            )
        ]

        if cells:
            rows.append(
                cells
            )

    return rows


def _parse_strategy_values(
    html: str,
) -> tuple[
    str,
    float | None,
    float | None,
]:
    """
    回傳：

    status:
        DATA
        NO_DATA

    large_holder_pct
    retail_holder_pct
    """
    if (
        "查無資料"
        in html
        or "查無此資料"
        in html
    ):
        return (
            "NO_DATA",
            None,
            None,
        )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    table = _find_result_table(
        soup
    )

    if table is None:
        raise RuntimeError(
            "TDCC response 找不到 "
            "持股分級結果 table"
        )

    rows = _extract_rows(
        table
    )

    levels: dict[
        str,
        float,
    ] = {}

    for row in rows:
        if len(row) < 5:
            continue

        level = str(
            row[0]
        ).strip()

        if level not in {
            "1",
            "2",
            "15",
        }:
            continue

        pct_text = (
            str(row[4])
            .replace("%", "")
            .replace(",", "")
            .strip()
        )

        levels[level] = float(
            pct_text
        )

    missing = (
        {
            "1",
            "2",
            "15",
        }
        - set(levels)
    )

    if missing:
        raise RuntimeError(
            "TDCC result 缺少策略 levels："
            f"{sorted(missing)}"
        )

    retail_holder_pct = (
        levels["1"]
        + levels["2"]
    )

    large_holder_pct = (
        levels["15"]
    )

    return (
        "DATA",
        large_holder_pct,
        retail_holder_pct,
    )


def _upsert_tdcc_holding(
    *,
    stock_id: str,
    data_date: str,
    large_holder_pct: float,
    retail_holder_pct: float,
) -> None:
    conn = get_connection()

    try:
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
                stock_id,
                data_date,
                large_holder_pct,
                retail_holder_pct,
                SOURCE,
                _now_iso(),
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def _holding_exists(
    stock_id: str,
    data_date: str,
) -> bool:
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT 1
            FROM tdcc_holdings
            WHERE stock_id = ?
              AND data_date = ?
            LIMIT 1
            """,
            (
                stock_id,
                data_date,
            ),
        ).fetchone()

        return row is not None

    finally:
        conn.close()


def _get_active_stocks(
    limit: int | None,
) -> list[dict[str, str]]:
    conn = get_connection()

    try:
        sql = """
            SELECT
                stock_id,
                stock_name,
                market
            FROM stocks
            WHERE is_active = 1
              AND market IN (
                  'TWSE',
                  'TPEx'
              )
              AND LENGTH(stock_id) = 4
              AND stock_id GLOB
                  '[0-9][0-9][0-9][0-9]'
            ORDER BY
                market,
                stock_id
        """

        rows = conn.execute(
            sql
        ).fetchall()

    finally:
        conn.close()

    result = [
        {
            "stock_id":
                str(row["stock_id"]),
            "stock_name":
                str(row["stock_name"]),
            "market":
                str(row["market"]),
        }
        for row in rows
    ]

    if (
        limit is not None
        and limit > 0
    ):
        return result[:limit]

    return result


def _request_key(
    stock_id: str,
    sca_date: str,
) -> str:
    return (
        f"TDCC_HISTORY:"
        f"{stock_id}:"
        f"{sca_date}"
    )


def _query_one(
    session: requests.Session,
    *,
    stock_id: str,
    sca_date: str,
    retries: int,
) -> tuple[
    str,
    str,
    float | None,
    float | None,
]:
    """
    每次 POST 前一定重新 GET qryStock，
    取得新的 SYNCHRONIZER_TOKEN。

    回傳：
        html
        status
        large_holder_pct
        retail_holder_pct
    """
    last_error = None

    for attempt in range(
        1,
        retries + 2,
    ):
        try:
            contract = (
                _get_query_contract(
                    session
                )
            )

            if (
                sca_date
                not in contract["dates"]
            ):
                raise RuntimeError(
                    "目標日期不在目前 "
                    "scaDate options："
                    f"{sca_date}"
                )

            response = _post_query(
                session,
                stock_id=stock_id,
                sca_date=sca_date,
                token=(
                    contract["token"]
                ),
                uri=(
                    contract["uri"]
                ),
                fir_date=(
                    contract["fir_date"]
                ),
            )

            (
                status,
                large_pct,
                retail_pct,
            ) = (
                _parse_strategy_values(
                    response.text
                )
            )

            return (
                response.text,
                status,
                large_pct,
                retail_pct,
            )

        except Exception as exc:
            last_error = exc

            print(
                "[RETRY] "
                f"{stock_id} "
                f"{sca_date} "
                f"attempt="
                f"{attempt}/"
                f"{retries + 1} "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            if (
                attempt
                <= retries
            ):
                time.sleep(
                    2.0
                    * attempt
                )

    raise RuntimeError(
        "TDCC historical query "
        "重試後仍失敗："
        f"{stock_id} {sca_date}: "
        f"{last_error}"
    )


def _sync_one(
    session: requests.Session,
    *,
    stock_id: str,
    stock_name: str,
    market: str,
    sca_date: str,
    retries: int,
) -> str:
    request_key = _request_key(
        stock_id,
        sca_date,
    )

    data_date = _normalize_date(
        sca_date
    )

    if _crawl_success_exists(
        request_key
    ):
        print(
            "[SKIP SUCCESS] "
            f"{market} "
            f"{stock_id} "
            f"{stock_name} "
            f"{data_date}"
        )

        return "SKIP"

    if _holding_exists(
        stock_id,
        data_date,
    ):
        print(
            "[SKIP DB] "
            f"{market} "
            f"{stock_id} "
            f"{stock_name} "
            f"{data_date}"
        )

        return "SKIP"

    crawl_log_id = None

    try:
        crawl_log_id = (
            _start_crawl_log(
                request_key
            )
        )

        (
            raw_html,
            query_status,
            large_pct,
            retail_pct,
        ) = _query_one(
            session,
            stock_id=stock_id,
            sca_date=sca_date,
            retries=retries,
        )

        _save_raw_response(
            request_key=request_key,
            stock_id=stock_id,
            sca_date=sca_date,
            response_text=raw_html,
        )

        if (
            query_status
            == "NO_DATA"
        ):
            _finish_crawl_success(
                crawl_log_id,
                request_key,
                0,
            )

            print(
                "[NO DATA] "
                f"{market} "
                f"{stock_id} "
                f"{stock_name} "
                f"{data_date}"
            )

            return "NO_DATA"

        if (
            large_pct is None
            or retail_pct is None
        ):
            raise RuntimeError(
                "TDCC DATA 狀態但 "
                "strategy pct 為 None"
            )

        _upsert_tdcc_holding(
            stock_id=stock_id,
            data_date=data_date,
            large_holder_pct=(
                large_pct
            ),
            retail_holder_pct=(
                retail_pct
            ),
        )

        _finish_crawl_success(
            crawl_log_id,
            request_key,
            1,
        )

        print(
            "[OK] "
            f"{market} "
            f"{stock_id} "
            f"{stock_name} "
            f"{data_date} "
            f"large={large_pct:.2f} "
            f"retail={retail_pct:.2f}"
        )

        return "SUCCESS"

    except Exception as exc:
        error_message = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        if crawl_log_id is not None:
            try:
                _finish_crawl_error(
                    crawl_log_id,
                    request_key,
                    error_message,
                )
            except Exception as log_exc:
                print(
                    "[ERROR] crawl log "
                    "ERROR 更新失敗："
                    f"{log_exc}"
                )

        print(
            "[ERROR] "
            f"{market} "
            f"{stock_id} "
            f"{stock_name} "
            f"{data_date}: "
            f"{error_message}"
        )

        return "ERROR"


def _discover_target_dates(
    session: requests.Session,
    history_weeks: int,
) -> list[str]:
    contract = (
        _get_query_contract(
            session
        )
    )

    dates = contract[
        "dates"
    ]

    if len(dates) < (
        history_weeks + 1
    ):
        raise RuntimeError(
            "TDCC scaDate options 不足："
            f"目前 {len(dates)}，"
            f"至少需要 "
            f"{history_weeks + 1}"
        )

    #
    # [0] 為 latest，
    # 已由全市場 OpenAPI 處理。
    #
    return dates[
        1:
        history_weeks + 1
    ]


def backfill(
    *,
    limit: int | None,
    history_weeks: int,
    sleep_seconds: float,
    retries: int,
) -> None:
    urllib3.disable_warnings(
        urllib3.exceptions.InsecureRequestWarning
    )

    session = requests.Session()

    session.headers.update(
        BROWSER_HEADERS
    )

    print("=" * 72)
    print("TDCC Market Historical Backfill")
    print("=" * 72)

    print(
        "[INFO] bootstrap TDCC session..."
    )

    _bootstrap_session(
        session
    )

    print(
        "[INFO] discover target dates..."
    )

    target_dates = (
        _discover_target_dates(
            session,
            history_weeks,
        )
    )

    print(
        "[INFO] historical dates =",
        target_dates,
    )

    print(
        "[INFO] normalized dates =",
        [
            _normalize_date(
                value
            )
            for value
            in target_dates
        ],
    )

    stocks = _get_active_stocks(
        limit
    )

    print(
        "[INFO] stocks =",
        len(stocks),
    )

    total_units = (
        len(stocks)
        * len(target_dates)
    )

    print(
        "[INFO] query units =",
        total_units,
    )

    print()

    counts = {
        "SUCCESS": 0,
        "SKIP": 0,
        "NO_DATA": 0,
        "ERROR": 0,
    }

    errors = []

    unit_index = 0

    for stock in stocks:
        for sca_date in target_dates:
            unit_index += 1

            print()
            print("-" * 72)

            print(
                f"[{unit_index}/"
                f"{total_units}] "
                f"{stock['market']} "
                f"{stock['stock_id']} "
                f"{stock['stock_name']} "
                f"{_normalize_date(sca_date)}"
            )

            result = _sync_one(
                session,
                stock_id=(
                    stock[
                        "stock_id"
                    ]
                ),
                stock_name=(
                    stock[
                        "stock_name"
                    ]
                ),
                market=(
                    stock[
                        "market"
                    ]
                ),
                sca_date=sca_date,
                retries=retries,
            )

            counts[result] += 1

            if result == "ERROR":
                errors.append(
                    (
                        stock["stock_id"],
                        sca_date,
                    )
                )

            if (
                unit_index
                < total_units
                and sleep_seconds > 0
            ):
                time.sleep(
                    sleep_seconds
                )

    print()
    print("=" * 72)
    print("BACKFILL SUMMARY")
    print("=" * 72)

    print(
        "Units    :",
        total_units,
    )

    print(
        "SUCCESS  :",
        counts["SUCCESS"],
    )

    print(
        "SKIP     :",
        counts["SKIP"],
    )

    print(
        "NO_DATA  :",
        counts["NO_DATA"],
    )

    print(
        "ERROR    :",
        counts["ERROR"],
    )

    if errors:
        print()
        print(
            "Error sample:"
        )

        for (
            stock_id,
            sca_date,
        ) in errors[:20]:
            print(
                " ",
                stock_id,
                sca_date,
            )

        raise RuntimeError(
            "TDCC historical backfill "
            f"仍有 {len(errors)} "
            "個查詢單位失敗"
        )

    print()
    print(
        "[OK] TDCC historical "
        "backfill 完成"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "回補 active TWSE + TPEx "
            "最近 N 個 TDCC 歷史週"
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=(
            "只處理前 N 檔。"
            "預設 10；"
            "全市場請使用 --limit 0"
        ),
    )

    parser.add_argument(
        "--weeks",
        type=int,
        default=(
            DEFAULT_HISTORY_WEEKS
        ),
        help=(
            "回補歷史週數，"
            "預設 3"
        ),
    )

    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=(
            DEFAULT_SLEEP_SECONDS
        ),
        help=(
            "每個查詢單位之間等待秒數，"
            "預設 1.0"
        ),
    )

    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=(
            "單筆額外重試次數，"
            "預設 2"
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    limit = (
        None
        if args.limit == 0
        else args.limit
    )

    backfill(
        limit=limit,
        history_weeks=(
            args.weeks
        ),
        sleep_seconds=(
            args.sleep_seconds
        ),
        retries=(
            args.retries
        ),
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as exc:
        print(
            "[FATAL] "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        sys.exit(1)