from __future__ import annotations

import re
import sys

import requests
from bs4 import BeautifulSoup


NEWS_URLS = [
    (
        "https://www.esunfhc.com/zh-tw/"
        "news-center/news-center/news/detail"
        "?id=F38712D2C0244A0ABE12801BAF82A204"
        "&p=2B4822BDE7BF44D3BFB4B81E00E842A6"
    ),
]


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


def fetch_text(url):

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/154 Safari/537.36"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()
    response.encoding = "utf-8"

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    return " ".join(
        soup.stripped_strings
    )


def parse_article(url):

    text = fetch_text(
        url
    )

    # 目前這篇官方新聞明確提供：
    # 截至 7 月累計自結稅後淨利 202.1 億
    # EPS 1.25 元

    match = re.search(
        r"截至"
        r"(?P<month>\d{1,2})月"
        r".{0,100}?"
        r"自結稅後淨利"
        r"(?P<ytd>[\d,.]+)"
        r"億元"
        r".{0,80}?"
        r"EPS"
        r"\s*"
        r"(?P<eps>[\d,.]+)"
        r"元",
        text,
        flags=re.IGNORECASE,
    )

    if not match:

        raise RuntimeError(
            f"E.SUN earnings data not found: {url}"
        )

    month = match.group(
        "month"
    ).zfill(2)

    ytd_profit = round(
        parse_number(
            match.group(
                "ytd"
            )
        )
        * 100,
        2,
    )

    eps = parse_number(
        match.group(
            "eps"
        )
    )

    return {
        "stock_id": "2884",
        "stock_name": "玉山金",
        "data_month": (
            f"2025-{month}"
        ),

        # 官網這篇新聞只有累計值，
        # 不人工反推單月獲利
        "monthly_net_profit": None,

        "ytd_net_profit": (
            ytd_profit
        ),

        "ytd_eps": eps,
        "source_url": url,
    }


def parse_esun():

    rows = []

    for url in NEWS_URLS:

        row = parse_article(
            url
        )

        rows.append(
            row
        )

    if not rows:

        raise RuntimeError(
            "No E.SUN monthly rows found"
        )

    rows.sort(
        key=lambda x: x[
            "data_month"
        ],
        reverse=True,
    )

    return rows


def main():

    configure_console()

    print("=" * 70)

    print(
        "StockWaveScanner V3 - "
        "E.SUN Monthly Earnings Parser"
    )

    print("=" * 70)

    rows = parse_esun()

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
        "E.SUN PARSER OK"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )