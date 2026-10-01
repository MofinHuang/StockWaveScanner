from __future__ import annotations

import re
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.kgi.com"
LIST_URL = (
    "https://www.kgi.com/zh-tw/press"
    "?category=pressrelease"
    "&year=2026"
)

STOCK_ID = "2883"
STOCK_NAME = "凱基金"

MAX_PAGES = 10


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


def parse_number(value):

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    return float(
        value.replace(",", "")
    )


def get_headers():

    return {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/154 Safari/537.36"
        )
    }


def fetch_html(url):

    response = requests.get(
        url,
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
            f"KGI source returned empty HTML: {url}"
        )

    return response.text


def normalize_text(text):

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def find_monthly_article_links():

    result = {}

    title_pattern = re.compile(
        r"凱基金控"
        r"\s*"
        r"(?P<year>20\d{2})"
        r"\s*年"
        r"\s*"
        r"(?P<month>\d{1,2})"
        r"\s*月"
        r".{0,20}?"
        r"自結"
    )

    for page in range(MAX_PAGES):

        if page == 0:
            url = LIST_URL
        else:
            url = (
                LIST_URL
                + f"&p={page}"
            )

        print(
            f"[FETCH] List page: {url}"
        )

        html = fetch_html(url)

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        page_found = 0

        for anchor in soup.find_all(
            "a",
            href=True,
        ):

            title = normalize_text(
                anchor.get_text(
                    " ",
                    strip=True,
                )
            )

            if not title:
                continue

            match = title_pattern.search(
                title
            )

            if not match:
                continue

            year = int(
                match.group("year")
            )

            month = int(
                match.group("month")
            )

            if year != 2026:
                continue

            if not (
                1 <= month <= 12
            ):
                continue

            href = anchor.get(
                "href",
                "",
            ).strip()

            if not href:
                continue

            detail_url = urljoin(
                BASE_URL,
                href,
            )

            data_month = (
                f"{year}-{month:02d}"
            )

            result[data_month] = {
                "data_month": data_month,
                "title": title,
                "source_url": detail_url,
            }

            page_found += 1

        print(
            f"[INFO] Page candidates: "
            f"{page_found}"
        )

    rows = list(
        result.values()
    )

    rows.sort(
        key=lambda x: x["data_month"]
    )

    if not rows:

        raise RuntimeError(
            "KGI monthly earnings articles not found"
        )

    return rows


def fetch_article_text(url):

    html = fetch_html(url)

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

    if not text:

        raise RuntimeError(
            f"KGI article returned empty text: {url}"
        )

    return text


def find_monthly_profit(
    text,
    year,
    month,
):

    patterns = [
        re.compile(
            rf"{year}"
            rf"\s*年"
            rf"\s*{month}"
            rf"\s*月"
            rf".{{0,30}}?"
            rf"自結"
            rf".{{0,80}}?"
            rf"單月稅後"
            rf"(?:淨利|獲利)?"
            rf"(?:為|達)?"
            rf"\s*"
            rf"(?P<value>-?[\d,.]+)"
            rf"\s*億元"
        ),
        re.compile(
            r"單月稅後"
            r"(?:淨利|獲利)?"
            r"(?:為|達)?"
            r"\s*"
            r"(?:新台幣)?"
            r"(?:（以下同）)?"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*億元"
        ),
        re.compile(
            rf"{month}"
            rf"\s*月"
            rf".{{0,30}}?"
            rf"稅後"
            rf"(?:淨利|獲利)"
            rf"(?:為|達)?"
            rf"\s*"
            rf"(?P<value>-?[\d,.]+)"
            rf"\s*億元"
        ),
    ]

    for pattern in patterns:

        match = pattern.search(
            text
        )

        if match:

            return parse_number(
                match.group(
                    "value"
                )
            )

    return None


def find_ytd_profit(
    text,
    month,
):

    #
    # 凱基金官方新聞稿有多種累計描述方式。
    #
    # 重要：
    # 同一篇文章後段會出現：
    #
    # - 凱基銀行累計稅後獲利
    # - 凱基證券累計稅後獲利
    # - 凱基人壽累計稅後獲利
    #
    # 因此必須優先抓「金控本身」在文章開頭使用的格式。
    #

    chinese_month_map = {
        1: "一",
        2: "二",
        3: "三",
        4: "四",
        5: "五",
        6: "六",
        7: "七",
        8: "八",
        9: "九",
        10: "十",
        11: "十一",
        12: "十二",
    }

    chinese_month = chinese_month_map.get(
        month
    )

    patterns = []

    #
    # Priority 1
    #
    # 2026-03：
    # 年度累計稅後獲利116.9億元
    #
    # 2026-05：
    # 年度累計稅後獲利223.3億元
    #
    # 這是目前最明確的金控層級寫法，
    # 必須放在「前X月」之前。
    #
    patterns.append(
        re.compile(
            r"年度"
            r"\s*累計"
            r"\s*稅後"
            r"(?:淨利|獲利)?"
            r"(?:為|達)?"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*億元"
        )
    )

    #
    # Priority 2
    #
    # 2026-06：
    # 今年上半年累計稅後獲利284.4億元
    #
    if month == 6:

        patterns.append(
            re.compile(
                r"(?:今年)?"
                r"\s*上半年"
                r"\s*累計"
                r"\s*稅後"
                r"(?:淨利|獲利)?"
                r"(?:為|達)?"
                r"\s*"
                r"(?P<value>-?[\d,.]+)"
                r"\s*億元"
            )
        )

    #
    # Priority 3
    #
    # 2026-07：
    # 今年前七月累計稅後獲利305.29億元
    #
    # 2026-08：
    # 今年前八月累計稅後獲利362.9億元
    #
    if chinese_month:

        patterns.append(
            re.compile(
                rf"(?:今年)?"
                rf"\s*前"
                rf"\s*{chinese_month}"
                rf"\s*月"
                rf"\s*累計"
                rf"\s*稅後"
                rf"(?:淨利|獲利)?"
                rf"(?:為|達)?"
                rf"\s*"
                rf"(?P<value>-?[\d,.]+)"
                rf"\s*億元"
            )
        )

    #
    # Priority 4
    #
    # 阿拉伯數字格式：
    #
    # 前7月累計稅後獲利
    # 前7個月累計稅後獲利
    #
    patterns.append(
        re.compile(
            rf"(?:今年)?"
            rf"\s*前"
            rf"\s*{month}"
            rf"\s*(?:個)?月"
            rf"\s*累計"
            rf"\s*稅後"
            rf"(?:淨利|獲利)?"
            rf"(?:為|達)?"
            rf"\s*"
            rf"(?P<value>-?[\d,.]+)"
            rf"\s*億元"
        )
    )

    #
    # Priority 5
    #
    # 最後才使用較寬鬆的一般型。
    #
    patterns.append(
        re.compile(
            r"今年"
            r"\s*累計"
            r"\s*稅後"
            r"(?:淨利|獲利)?"
            r"(?:為|達)?"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*億元"
        )
    )

    for pattern in patterns:

        match = pattern.search(
            text
        )

        if match:

            return parse_number(
                match.group(
                    "value"
                )
            )

    return None


def find_ytd_eps(
    text,
):

    patterns = [
        re.compile(
            r"每股盈餘"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*元"
        ),
        re.compile(
            r"每股獲利"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*元"
        ),
        re.compile(
            r"EPS"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*元"
        ),
    ]

    for pattern in patterns:

        match = pattern.search(
            text
        )

        if match:

            return parse_number(
                match.group(
                    "value"
                )
            )

    return None


def parse_article(
    article,
):

    data_month = article[
        "data_month"
    ]

    year_text, month_text = (
        data_month.split("-")
    )

    year = int(
        year_text
    )

    month = int(
        month_text
    )

    url = article[
        "source_url"
    ]

    print()
    print(
        f"[PARSE] {data_month}"
    )

    print(
        f"[SOURCE] {url}"
    )

    text = fetch_article_text(
        url
    )

    monthly_profit = (
        find_monthly_profit(
            text,
            year,
            month,
        )
    )

    if monthly_profit is None:

        print()
        print(
            "[DEBUG] Article preview:"
        )

        print(
            text[:4000]
        )

        raise RuntimeError(
            f"KGI monthly profit not found: "
            f"{data_month}"
        )

    ytd_profit = find_ytd_profit(
        text,
        month,
    )

    #
    # 1 月沒有「累計」問題，
    # YTD 即為當月獲利。
    #
    if (
        month == 1
        and ytd_profit is None
    ):
        ytd_profit = (
            monthly_profit
        )

    if ytd_profit is None:

        print()
        print(
            "[DEBUG] Article preview:"
        )

        print(
            text[:4000]
        )

        raise RuntimeError(
            f"KGI YTD profit not found: "
            f"{data_month}"
        )

    ytd_eps = find_ytd_eps(
        text
    )

    if ytd_eps is None:

        print()
        print(
            "[DEBUG] Article preview:"
        )

        print(
            text[:4000]
        )

        raise RuntimeError(
            f"KGI YTD EPS not found: "
            f"{data_month}"
        )

    #
    # 官方單位：億元
    # DB 單位：百萬元
    #
    monthly_profit_million = round(
        monthly_profit * 100,
        2,
    )

    ytd_profit_million = round(
        ytd_profit * 100,
        2,
    )

    return {
        "stock_id": STOCK_ID,
        "stock_name": STOCK_NAME,
        "data_month": data_month,
        "monthly_net_profit": (
            monthly_profit_million
        ),
        "ytd_net_profit": (
            ytd_profit_million
        ),
        "ytd_eps": ytd_eps,
        "source_url": url,
    }


def parse_kgi():

    articles = (
        find_monthly_article_links()
    )

    rows = []

    for article in articles:

        try:

            row = parse_article(
                article
            )

            rows.append(
                row
            )

        except Exception as exc:

            print()
            print(
                f"[WARN] Skip "
                f"{article['data_month']}: "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

    rows.sort(
        key=lambda x: x["data_month"]
    )

    if not rows:

        raise RuntimeError(
            "KGI parser returned no valid rows"
        )

    return rows


def main():

    configure_console()

    print("=" * 70)

    print(
        "StockWaveScanner V3 - "
        "KGI Financial Holding Monthly Earnings Parser"
    )

    print("=" * 70)

    rows = parse_kgi()

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
        "KGI FINANCIAL HOLDING PARSER OK"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )