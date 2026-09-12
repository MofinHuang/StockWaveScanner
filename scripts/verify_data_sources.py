from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


USER_AGENT = "Mozilla/5.0 StockWaveScanner-V2-Data-Verification/1.0"
TIMEOUT = 45

# 固定使用已知有資料的歷史月份 / 交易日做驗證，
# 避免週末、休市日造成假失敗。
HIST_MONTH_DATE = "20260701"
HIST_MONTH_TPEX = "2026/07/01"
SAMPLE_TRADE_DATE = "20260911"


@dataclass
class Result:
    name: str
    status: str
    detail: str


RESULTS: list[Result] = []


class VerificationError(Exception):
    pass


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise VerificationError("Unable to decode response text")


def curl_path() -> str | None:
    return shutil.which("curl.exe") or shutil.which("curl")


def fetch_with_curl(
    url: str,
    method: str = "GET",
    form: dict[str, str] | None = None,
) -> bytes:
    curl = curl_path()

    if not curl:
        raise VerificationError("curl not found")

    cmd = [
        curl,
        "--location",
        "--http1.1",
        "--retry",
        "2",
        "--retry-all-errors",
        "--connect-timeout",
        "15",
        "--max-time",
        str(TIMEOUT),
        "-A",
        USER_AGENT,
        "-sS",
    ]

    if method.upper() == "POST":
        cmd.extend(["-X", "POST"])

        for key, value in (form or {}).items():
            cmd.extend(["--data-urlencode", f"{key}={value}"])

    cmd.append(url)

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise VerificationError(
            f"curl failed ({result.returncode}): {error}"
        )

    if not result.stdout:
        raise VerificationError("empty response")

    return result.stdout


def fetch_with_urllib(
    url: str,
    method: str = "GET",
    form: dict[str, str] | None = None,
) -> bytes:
    data = None

    if method.upper() == "POST":
        data = urllib.parse.urlencode(form or {}).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        method=method.upper(),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        },
    )

    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        content = response.read()

    if not content:
        raise VerificationError("empty response")

    return content


def fetch(
    url: str,
    method: str = "GET",
    form: dict[str, str] | None = None,
    prefer_curl: bool = False,
) -> bytes:
    errors: list[str] = []

    methods: list[Callable[[], bytes]]

    if prefer_curl:
        methods = [
            lambda: fetch_with_curl(url, method, form),
            lambda: fetch_with_urllib(url, method, form),
        ]
    else:
        methods = [
            lambda: fetch_with_urllib(url, method, form),
            lambda: fetch_with_curl(url, method, form),
        ]

    for loader in methods:
        try:
            return loader()
        except Exception as exc:
            errors.append(str(exc))

    raise VerificationError(" | ".join(errors))


def load_json(
    url: str,
    method: str = "GET",
    form: dict[str, str] | None = None,
    prefer_curl: bool = False,
) -> Any:
    raw = fetch(
        url=url,
        method=method,
        form=form,
        prefer_curl=prefer_curl,
    )

    try:
        return json.loads(decode_text(raw))
    except json.JSONDecodeError as exc:
        raise VerificationError(
            f"invalid JSON: {exc}; payload={len(raw)} bytes"
        ) from exc


def load_csv(
    url: str,
    prefer_curl: bool = False,
) -> list[dict[str, str]]:
    raw = fetch(url, prefer_curl=prefer_curl)
    text = decode_text(raw)

    try:
        rows = list(csv.DictReader(io.StringIO(text)))
    except Exception as exc:
        raise VerificationError(f"invalid CSV: {exc}") from exc

    if not rows:
        raise VerificationError("CSV contains no rows")

    return rows


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def extract_rows(obj: Any) -> list[Any]:
    if isinstance(obj, list):
        return obj

    if not isinstance(obj, dict):
        return []

    for key in ("data", "records", "result"):
        value = obj.get(key)
        if isinstance(value, list):
            return value

    tables = obj.get("tables")

    if isinstance(tables, list) and tables:
        table = tables[0]

        if isinstance(table, dict):
            data = table.get("data")

            if isinstance(data, list):
                return data

    return []


def run(
    name: str,
    test: Callable[[], str],
    optional: bool = False,
) -> None:
    try:
        detail = test()
        RESULTS.append(Result(name, "PASS", detail))
        print(f"[PASS] {name}")
        print(f"       {detail}")

    except Exception as exc:
        status = "WARN" if optional else "FAIL"
        RESULTS.append(Result(name, status, str(exc)))

        print(f"[{status}] {name}")
        print(f"       {exc}")


# ============================================================
# Stock Master
# ============================================================

def test_twse_stock_master() -> str:
    url = (
        "https://openapi.twse.com.tw/v1/"
        "opendata/t187ap03_L"
    )

    data = load_json(url)

    ensure(isinstance(data, list), "response is not a JSON array")
    ensure(len(data) > 500, f"unexpected record count: {len(data)}")

    first = data[0]

    for field in ("公司代號", "公司名稱", "公司簡稱", "產業別", "上市日期"):
        ensure(field in first, f"missing field: {field}")

    return (
        f"records={len(data)}, "
        f"first={first.get('公司代號')} {first.get('公司簡稱')}"
    )


def test_tpex_stock_master() -> str:
    url = (
        "https://mopsfin.twse.com.tw/"
        "opendata/t187ap03_O.csv"
    )

    rows = load_csv(url)

    ensure(len(rows) > 500, f"unexpected record count: {len(rows)}")

    first = rows[0]

    for field in ("公司代號", "公司名稱", "公司簡稱", "產業別", "上櫃日期"):
        ensure(field in first, f"missing field: {field}")

    return (
        f"records={len(rows)}, "
        f"first={first.get('公司代號')} {first.get('公司簡稱')}"
    )


# ============================================================
# Market Index
# ============================================================

def test_twse_index_current() -> str:
    url = (
        "https://openapi.twse.com.tw/v1/"
        "indicesReport/MI_5MINS_HIST"
    )

    data = load_json(url)

    ensure(isinstance(data, list), "response is not a JSON array")
    ensure(len(data) > 0, "no current index rows")

    first = data[0]
    last = data[-1]

    for field in (
        "Date",
        "OpeningIndex",
        "HighestIndex",
        "LowestIndex",
        "ClosingIndex",
    ):
        ensure(field in first, f"missing field: {field}")

    return (
        f"records={len(data)}, "
        f"range={first.get('Date')}..{last.get('Date')}"
    )


def test_twse_index_history() -> str:
    url = (
        "https://www.twse.com.tw/"
        "indicesReport/MI_5MINS_HIST"
        f"?response=json&date={HIST_MONTH_DATE}"
    )

    data = load_json(url)

    ensure(
        str(data.get("stat", "")).upper() == "OK",
        f"stat={data.get('stat')}",
    )

    rows = data.get("data", [])

    ensure(
        len(rows) >= 20,
        f"unexpected historical count: {len(rows)}",
    )

    return (
        f"2026-07 records={len(rows)}, "
        f"first={rows[0][0]}, last={rows[-1][0]}"
    )


def test_tpex_index_current() -> str:
    url = (
        "https://www.tpex.org.tw/"
        "openapi/v1/tpex_index"
    )

    data = load_json(url, prefer_curl=True)

    ensure(isinstance(data, list), "response is not a JSON array")
    ensure(len(data) > 0, "no current index rows")

    first = data[0]
    last = data[-1]

    for field in ("Date", "Open", "High", "Low", "Close"):
        ensure(field in first, f"missing field: {field}")

    return (
        f"records={len(data)}, "
        f"range={first.get('Date')}..{last.get('Date')}"
    )


def test_tpex_index_history() -> str:
    url = (
        "https://www.tpex.org.tw/"
        "www/zh-tw/indexInfo/inx"
    )

    data = load_json(
        url,
        method="POST",
        form={
            "date": HIST_MONTH_TPEX,
            "response": "json",
        },
        prefer_curl=True,
    )

    ensure(
        str(data.get("stat", "")).lower() == "ok",
        f"stat={data.get('stat')}",
    )

    tables = data.get("tables", [])

    ensure(tables, "tables is empty")

    table = tables[0]
    rows = table.get("data", [])

    ensure(
        len(rows) >= 20,
        f"unexpected historical count: {len(rows)}",
    )

    ensure(
        table.get("date") == "115/07",
        f"unexpected month: {table.get('date')}",
    )

    return (
        f"2026-07 records={len(rows)}, "
        f"first={rows[0][0]}, last={rows[-1][0]}"
    )


# ============================================================
# Daily Price
# ============================================================

def test_twse_daily_price() -> str:
    url = (
        "https://openapi.twse.com.tw/v1/"
        "exchangeReport/STOCK_DAY_ALL"
    )

    data = load_json(url)

    ensure(isinstance(data, list), "response is not a JSON array")
    ensure(len(data) > 500, f"unexpected record count: {len(data)}")

    first = data[0]

    return (
        f"records={len(data)}, "
        f"sample_keys={','.join(list(first.keys())[:6])}"
    )


def test_tpex_daily_price() -> str:
    url = (
        "https://www.tpex.org.tw/openapi/v1/"
        "tpex_mainboard_daily_close_quotes"
    )

    data = load_json(url, prefer_curl=True)

    ensure(isinstance(data, list), "response is not a JSON array")
    ensure(len(data) > 300, f"unexpected record count: {len(data)}")

    first = data[0]

    return (
        f"records={len(data)}, "
        f"sample_keys={','.join(list(first.keys())[:6])}"
    )


# ============================================================
# Institutional
# ============================================================

def test_twse_institutional_history() -> str:
    url = (
        "https://www.twse.com.tw/rwd/zh/fund/T86"
        f"?date={SAMPLE_TRADE_DATE}"
        "&selectType=ALLBUT0999"
        "&response=json"
    )

    data = load_json(url)

    ensure(
        str(data.get("stat", "")).upper() == "OK",
        f"stat={data.get('stat')}",
    )

    rows = data.get("data", [])

    ensure(len(rows) > 300, f"unexpected record count: {len(rows)}")

    return (
        f"{SAMPLE_TRADE_DATE} records={len(rows)}, "
        f"fields={len(data.get('fields', []))}"
    )


def test_tpex_institutional_current() -> str:
    url = (
        "https://www.tpex.org.tw/openapi/v1/"
        "tpex_3insti_daily_trading"
    )

    data = load_json(url, prefer_curl=True)

    ensure(isinstance(data, list), "response is not a JSON array")
    ensure(len(data) > 300, f"unexpected record count: {len(data)}")

    first = data[0]

    return (
        f"records={len(data)}, "
        f"sample_keys={','.join(list(first.keys())[:8])}"
    )


# ============================================================
# TDCC
# ============================================================

def test_tdcc_distribution() -> str:
    url = (
        "https://openapi.tdcc.com.tw/v1/"
        "opendata/1-5"
    )

    data = load_json(url)

    rows = extract_rows(data)

    ensure(len(rows) > 100, f"unexpected record count: {len(rows)}")

    first = rows[0]

    if isinstance(first, dict):
        keys = ",".join(list(first.keys())[:8])
    else:
        keys = "array-row"

    return f"records={len(rows)}, sample_keys={keys}"


# ============================================================
# Monthly Revenue
# ============================================================

def test_twse_revenue() -> str:
    url = (
        "https://openapi.twse.com.tw/v1/"
        "opendata/t187ap05_L"
    )

    data = load_json(url)

    ensure(isinstance(data, list), "response is not a JSON array")
    ensure(len(data) > 500, f"unexpected record count: {len(data)}")

    first = data[0]

    for field in (
        "資料年月",
        "公司代號",
        "營業收入-當月營收",
        "營業收入-去年同月增減(%)",
    ):
        ensure(field in first, f"missing field: {field}")

    return (
        f"records={len(data)}, "
        f"month={first.get('資料年月')}"
    )


def test_tpex_revenue() -> str:
    url = (
        "https://mopsfin.twse.com.tw/"
        "opendata/t187ap05_O.csv"
    )

    rows = load_csv(url)

    ensure(len(rows) > 300, f"unexpected record count: {len(rows)}")

    first = rows[0]

    for field in (
        "資料年月",
        "公司代號",
        "營業收入-當月營收",
        "營業收入-去年同月增減(%)",
    ):
        ensure(field in first, f"missing field: {field}")

    return (
        f"records={len(rows)}, "
        f"month={first.get('資料年月')}"
    )


# ============================================================
# Quarterly Financial
#
# 先驗證「一般業」資料源是否可取得。
# 金融、金控、保險、證券期貨、異業之後再做完整 Schema Mapping。
# ============================================================

def test_twse_financial_general() -> str:
    url = (
        "https://openapi.twse.com.tw/v1/"
        "opendata/t187ap06_L_ci"
    )

    data = load_json(url)

    ensure(isinstance(data, list), "response is not a JSON array")
    ensure(len(data) > 100, f"unexpected record count: {len(data)}")

    first = data[0]

    return (
        f"records={len(data)}, "
        f"sample_keys={','.join(list(first.keys())[:8])}"
    )


def test_tpex_financial_general() -> str:
    url = (
        "https://mopsfin.twse.com.tw/"
        "opendata/t187ap06_O_ci.csv"
    )

    rows = load_csv(url)

    ensure(len(rows) > 100, f"unexpected record count: {len(rows)}")

    first = rows[0]

    return (
        f"records={len(rows)}, "
        f"sample_keys={','.join(list(first.keys())[:8])}"
    )


def print_summary() -> None:
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    pass_count = sum(r.status == "PASS" for r in RESULTS)
    warn_count = sum(r.status == "WARN" for r in RESULTS)
    fail_count = sum(r.status == "FAIL" for r in RESULTS)

    print(f"PASS : {pass_count}")
    print(f"WARN : {warn_count}")
    print(f"FAIL : {fail_count}")

    print()

    for result in RESULTS:
        print(
            f"{result.status:<4} | "
            f"{result.name:<38} | "
            f"{result.detail}"
        )

    print("=" * 70)


def main() -> None:
    print("=" * 70)
    print("StockWaveScanner V2 - Data Source Verification")
    print("=" * 70)
    print()

    # 已經人工驗證過，這些失敗視為真正 FAIL。
    run("TWSE Stock Master", test_twse_stock_master)
    run("TPEx Stock Master", test_tpex_stock_master)

    run("TWSE Market Index Current", test_twse_index_current)
    run("TWSE Market Index Historical", test_twse_index_history)

    run("TPEx Market Index Current", test_tpex_index_current)
    run("TPEx Market Index Historical", test_tpex_index_history)

    # 以下從這支程式開始一次驗證。
    # 現階段失敗先標 WARN，不中斷全部驗證。
    run(
        "TWSE Daily Price",
        test_twse_daily_price,
        optional=True,
    )

    run(
        "TPEx Daily Price",
        test_tpex_daily_price,
        optional=True,
    )

    run(
        "TWSE Institutional Historical",
        test_twse_institutional_history,
        optional=True,
    )

    run(
        "TPEx Institutional Current",
        test_tpex_institutional_current,
        optional=True,
    )

    run(
        "TDCC Shareholding Distribution",
        test_tdcc_distribution,
        optional=True,
    )

    run(
        "TWSE Monthly Revenue",
        test_twse_revenue,
        optional=True,
    )

    run(
        "TPEx Monthly Revenue",
        test_tpex_revenue,
        optional=True,
    )

    run(
        "TWSE Financial General",
        test_twse_financial_general,
        optional=True,
    )

    run(
        "TPEx Financial General",
        test_tpex_financial_general,
        optional=True,
    )

    print_summary()


if __name__ == "__main__":
    main()