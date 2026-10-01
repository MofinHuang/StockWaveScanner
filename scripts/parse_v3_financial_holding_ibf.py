from __future__ import annotations

import re
import sys

import requests
from bs4 import BeautifulSoup


SOURCE_URL = "https://www.ibf.com.tw/performance_reports"

STOCK_ID = "2889"
STOCK_NAME = "國票金"


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


def get_headers():

    return {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/154 Safari/537.36"
        )
    }


def fetch_html():

    print(
        f"[FETCH] {SOURCE_URL}"
    )

    response = requests.get(
        SOURCE_URL,
        headers=get_headers(),
        timeout=30,
    )

    response.raise_for_status()

    response.encoding = (
        response.apparent_encoding
        or "utf-8"
    )

    if not response.text.strip():

        raise RuntimeError(
            "IBF source returned empty HTML"
        )

    return response.text


def normalize_text(text):

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def roc_to_ad_year(
    roc_year,
):

    return int(
        roc_year
    ) + 1911


def parse_money_to_million(
    billion_text,
    ten_thousand_text,
):

    #
    # 官方格式：
    #
    # 7億7,245萬元
    # 1億8,923萬元
    # 6億142萬元
    # 8,455萬元
    #
    # DB 單位：
    # 百萬元
    #

    billion = 0.0
    ten_thousand = 0.0

    if billion_text:

        billion = float(
            billion_text.replace(
                ",",
                "",
            )
        )

    if ten_thousand_text:

        ten_thousand = float(
            ten_thousand_text.replace(
                ",",
                "",
            )
        )

    #
    # 1 億 = 100 百萬元
    # 1 萬 = 0.01 百萬元
    #
    result = (
        billion * 100
        + ten_thousand * 0.01
    )

    return round(
        result,
        3,
    )


def find_monthly_profit(
    body,
):

    pattern = re.compile(
        r"自結"
        r"\s*稅後"
        r"(?:盈餘|虧損)"
        r"\s*"
        r"(?P<negative>-)?"
        r"(?:(?P<billion>[\d,]+)"
        r"\s*億)?"
        r"(?P<ten_thousand>[\d,]+)?"
        r"\s*萬元"
    )

    match = pattern.search(
        body
    )

    if not match:

        return None

    value = parse_money_to_million(
        match.group(
            "billion"
        ),
        match.group(
            "ten_thousand"
        ),
    )

    if match.group(
        "negative"
    ):

        value *= -1

    return value


def find_ytd_profit(
    body,
    month,
    monthly_profit,
):

    #
    # 1 月官方沒有寫「累計」。
    # 因此：
    #
    # January YTD = January Monthly
    #
    if month == 1:

        return monthly_profit

    pattern = re.compile(
        r"累計"
        r"\s*1"
        r"\s*至"
        r"\s*"
        rf"{month}"
        r"\s*月份"
        r"\s*稅後"
        r"(?:盈餘|虧損)"
        r"\s*"
        r"(?P<negative>-)?"
        r"(?:(?P<billion>[\d,]+)"
        r"\s*億)?"
        r"(?P<ten_thousand>[\d,]+)?"
        r"\s*萬元"
    )

    match = pattern.search(
        body
    )

    if not match:

        return None

    value = parse_money_to_million(
        match.group(
            "billion"
        ),
        match.group(
            "ten_thousand"
        ),
    )

    if match.group(
        "negative"
    ):

        value *= -1

    return value


def find_ytd_eps(
    body,
):

    pattern = re.compile(
        r"每股"
        r"\s*稅後"
        r"(?:盈餘|盈虧)"
        r"\s*"
        r"(?P<value>-?[\d,.]+)"
        r"\s*元"
    )

    match = pattern.search(
        body
    )

    if not match:

        return None

    return float(
        match.group(
            "value"
        ).replace(
            ",",
            "",
        )
    )


def parse_ibf():

    html = fetch_html()

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    text = normalize_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    #
    # 每一段資料從：
    #
    # 115年8月份業績報告
    #
    # 到下一個：
    #
    # 115年7月份業績報告
    #
    # 之前為止。
    #

    heading_pattern = re.compile(
        r"(?P<roc_year>\d{3})"
        r"\s*年"
        r"\s*"
        r"(?P<month>\d{1,2})"
        r"\s*月份"
        r"\s*業績報告"
    )

    matches = list(
        heading_pattern.finditer(
            text
        )
    )

    if not matches:

        raise RuntimeError(
            "IBF performance report headings not found"
        )

    rows = []

    for index, match in enumerate(
        matches
    ):

        roc_year = int(
            match.group(
                "roc_year"
            )
        )

        month = int(
            match.group(
                "month"
            )
        )

        year = roc_to_ad_year(
            roc_year
        )

        #
        # Incremental Parser 目前只處理 2026。
        #
        # Historical Backfill 與 Daily Incremental 分開，
        # 避免舊年度不同頁面格式造成錯誤資料進入正式同步。
        #
        if year != 2026:

            continue

        if not (
            1 <= month <= 12
        ):

            continue

        start = match.end()

        if index + 1 < len(
            matches
        ):

            end = matches[
                index + 1
            ].start()

        else:

            end = len(
                text
            )

        body = text[
            start:end
        ]

        #
        # 只取文章第一段「本公司」。
        #
        # 避免誤抓：
        #
        # 國際票券
        # 國票證券
        # 國票創投
        #
        company_match = re.search(
            r"本公司"
            r".*?"
            r"(?:二、主要子公司|公司\s*\|)",
            body,
        )

        if company_match:

            company_body = (
                company_match.group(
                    0
                )
            )

        else:

            company_body = body[
                :1000
            ]

        monthly_profit = (
            find_monthly_profit(
                company_body
            )
        )

        if monthly_profit is None:

            print()
            print(
                f"[DEBUG] "
                f"{year}-{month:02d}"
            )

            print(
                company_body[:1500]
            )

            raise RuntimeError(
                "IBF monthly profit not found: "
                f"{year}-{month:02d}"
            )

        ytd_profit = find_ytd_profit(
            company_body,
            month,
            monthly_profit,
        )

        if ytd_profit is None:

            print()
            print(
                f"[DEBUG] "
                f"{year}-{month:02d}"
            )

            print(
                company_body[:1500]
            )

            raise RuntimeError(
                "IBF YTD profit not found: "
                f"{year}-{month:02d}"
            )

        ytd_eps = find_ytd_eps(
            company_body
        )

        if ytd_eps is None:

            print()
            print(
                f"[DEBUG] "
                f"{year}-{month:02d}"
            )

            print(
                company_body[:1500]
            )

            raise RuntimeError(
                "IBF YTD EPS not found: "
                f"{year}-{month:02d}"
            )

        data_month = (
            f"{year}-{month:02d}"
        )

        rows.append(
            {
                "stock_id": STOCK_ID,
                "stock_name": STOCK_NAME,
                "data_month": data_month,
                "monthly_net_profit": (
                    monthly_profit
                ),
                "ytd_net_profit": (
                    ytd_profit
                ),
                "ytd_eps": ytd_eps,
                "source_url": SOURCE_URL,
            }
        )

    #
    # 去除可能重複月份
    #
    unique_rows = {}

    for row in rows:

        unique_rows[
            row["data_month"]
        ] = row

    rows = list(
        unique_rows.values()
    )

    rows.sort(
        key=lambda x: x[
            "data_month"
        ]
    )

    if not rows:

        raise RuntimeError(
            "IBF parser returned no rows"
        )

    #
    # 驗證同年度 YTD 是否可由前月 YTD + 當月損益合理銜接。
    #
    for index in range(1, len(rows)):

        previous = rows[index - 1]
        current = rows[index]

        previous_year = previous["data_month"][:4]
        current_year = current["data_month"][:4]

        if previous_year != current_year:
            continue

        expected_ytd = round(
            previous["ytd_net_profit"]
            + current["monthly_net_profit"],
            2,
        )

        actual_ytd = round(
            current["ytd_net_profit"],
            2,
        )

        #
        # 官方億元 / 萬元轉換可能有極小四捨五入差。
        #
        if abs(expected_ytd - actual_ytd) > 0.1:

            raise RuntimeError(
                "IBF YTD reconciliation failed: "
                f"{current['data_month']} "
                f"Expected={expected_ytd} "
                f"Actual={actual_ytd}"
            )

    return rows


def main():

    configure_console()

    print("=" * 70)

    print(
        "StockWaveScanner V3 - "
        "IBF Financial Holding Monthly Earnings Parser"
    )

    print("=" * 70)

    rows = parse_ibf()

    print()
    print(
        f"ROWS: {len(rows)}"
    )

    print()

    for row in rows:

        print(
            row["data_month"],
            (
                "Monthly="
                f"{row['monthly_net_profit']}"
            ),
            (
                "YTD="
                f"{row['ytd_net_profit']}"
            ),
            (
                "EPS="
                f"{row['ytd_eps']}"
            ),
        )

    print()
    print("=" * 70)

    print(
        "IBF FINANCIAL HOLDING PARSER OK"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )