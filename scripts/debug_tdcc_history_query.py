from __future__ import annotations

from bs4 import BeautifulSoup
import requests
import urllib3


HOME_URL = (
    "https://www.tdcc.com.tw/"
    "portal/zh/"
)

QUERY_URL = (
    "https://www.tdcc.com.tw/"
    "portal/zh/smWeb/qryStock"
)

TEST_STOCK_ID = "1294"

TEST_DATES = [
    "20260807",
    "20260731",
    "20260724",
]


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


def _is_embedded_403(
    response: requests.Response,
) -> bool:
    return (
        "HTTP 403 Forbidden"
        in (response.text or "")
    )


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
            "未取得 JSESSIONID"
        )


def _get_query_contract(
    session: requests.Session,
):
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
            "qryStock embedded 403"
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


def _parse_levels(
    rows: list[list[str]],
) -> dict[str, float]:
    result = {}

    for row in rows:
        if len(row) < 5:
            continue

        level = row[0].strip()

        if level not in {
            "1",
            "2",
            "15",
        }:
            continue

        pct = float(
            row[4]
            .replace("%", "")
            .replace(",", "")
            .strip()
        )

        result[level] = pct

    return result


def _inspect_post(
    response: requests.Response,
    sca_date: str,
) -> bool:
    print()
    print("-" * 72)

    print(
        "scaDate =",
        sca_date,
    )

    print(
        "status =",
        response.status_code,
    )

    print(
        "html chars =",
        len(response.text),
    )

    if _is_embedded_403(
        response
    ):
        print(
            "[FAIL] embedded 403"
        )
        return False

    if (
        "查無資料"
        in response.text
        or "查無此資料"
        in response.text
    ):
        print(
            "[FAIL] 查無資料"
        )
        return False

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    table = _find_result_table(
        soup
    )

    if table is None:
        print(
            "[FAIL] 找不到結果 table"
        )
        return False

    rows = _extract_rows(
        table
    )

    levels = _parse_levels(
        rows
    )

    print(
        "levels =",
        levels,
    )

    required = {
        "1",
        "2",
        "15",
    }

    if (
        required
        - set(levels)
    ):
        print(
            "[FAIL] level 不完整"
        )
        return False

    retail_pct = (
        levels["1"]
        + levels["2"]
    )

    large_pct = (
        levels["15"]
    )

    print(
        "retail_holder_pct =",
        retail_pct,
    )

    print(
        "large_holder_pct =",
        large_pct,
    )

    print(
        "[OK] query success"
    )

    return True


def main() -> None:
    urllib3.disable_warnings(
        urllib3.exceptions.InsecureRequestWarning
    )

    session = requests.Session()

    session.headers.update(
        BROWSER_HEADERS
    )

    print("=" * 72)
    print("TDCC Token Reuse Test")
    print("=" * 72)

    print(
        "stock_id =",
        TEST_STOCK_ID,
    )

    # ======================================
    # 只 bootstrap 一次
    # ======================================

    _bootstrap_session(
        session
    )

    contract = (
        _get_query_contract(
            session
        )
    )

    print(
        "firDate =",
        contract["fir_date"],
    )

    print(
        "available dates =",
        len(
            contract["dates"]
        ),
    )

    for target_date in TEST_DATES:
        if (
            target_date
            not in contract["dates"]
        ):
            raise RuntimeError(
                "日期不在 options："
                f"{target_date}"
            )

    token = contract["token"]
    uri = contract["uri"]
    fir_date = contract[
        "fir_date"
    ]

    print()
    print(
        "token =",
        token,
    )

    print()
    print(
        "開始使用同一 token "
        "連續 POST 3 次"
    )

    results = []

    for target_date in TEST_DATES:
        response = _post_query(
            session,
            stock_id=(
                TEST_STOCK_ID
            ),
            sca_date=(
                target_date
            ),
            token=token,
            uri=uri,
            fir_date=fir_date,
        )

        success = (
            _inspect_post(
                response,
                target_date,
            )
        )

        results.append(
            (
                target_date,
                success,
            )
        )

    print()
    print("=" * 72)
    print("TOKEN REUSE SUMMARY")
    print("=" * 72)

    for (
        target_date,
        success,
    ) in results:
        print(
            target_date,
            "=",
            (
                "SUCCESS"
                if success
                else "FAIL"
            ),
        )

    if all(
        success
        for _, success in results
    ):
        print()
        print(
            "[CONFIRMED] "
            "同一 SYNCHRONIZER_TOKEN "
            "可連續查詢多個 scaDate"
        )

        print()
        print(
            "全市場歷史回補可採："
        )

        print(
            "每個 Session："
        )

        print(
            "1 GET homepage"
        )

        print(
            "1 GET qryStock"
        )

        print(
            "N 個 historical POST"
        )

    else:
        print()
        print(
            "[CONFIRMED] token "
            "不能安全重複使用"
        )

        print()
        print(
            "正式 crawler 必須在 "
            "POST 前重新取得 token"
        )


if __name__ == "__main__":
    main()