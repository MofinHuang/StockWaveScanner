from __future__ import annotations

import re
import sys

import requests
from bs4 import BeautifulSoup

import urllib3

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

BASE_URL = "https://www.fubon.com/financialholdings/news/"


NEWS_URLS = [
    "https://www.fubon.com/financialholdings/news/news_1260916_526196.htm",
    "https://www.fubon.com/financialholdings/news/news_1260814_701757.htm",
    "https://www.fubon.com/financialholdings/news/news_1260716_164206.htm",
    "https://www.fubon.com/financialholdings/news/news_1260611_143781.htm",
    "https://www.fubon.com/financialholdings/news/news_1260415_241492.htm",
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
        verify=False,
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

    text = fetch_text(url)

    date_match = re.search(
        r"2026年(\d{1,2})月"
        r".{0,30}?"
        r"自結合併稅前",
        text,
    )

    if not date_match:

        date_match = re.search(
            r"2026年(\d{1,2})月份"
            r".{0,30}?"
            r"稅後",
            text,
        )

    if not date_match:
        raise RuntimeError(
            f"Month not found: {url}"
        )

    month = date_match.group(1).zfill(2)

    monthly_match = re.search(
        r"2026年\d{1,2}月"
        r".{0,30}?"
        r"自結合併稅前"
        r"(?:淨利|淨損)"
        r"[\d,.]+億元"
        r"[、，,\s]*"
        r"稅後"
        r"(?P<type>淨利|淨損)"
        r"(?P<value>[\d,.]+)"
        r"億元",
        text,
    )

    if not monthly_match:

        monthly_match = re.search(
            r"2026年\d{1,2}月份"
            r".{0,30}?"
            r"稅後獲利"
            r"([\d,.]+)"
            r"億元",
            text,
        )

    ytd_match = re.search(
        r"累計今年前\d+月"
        r".{0,60}?"
        r"稅後淨利"
        r"([\d,.]+)"
        r"億元",
        text,
    )

    if not ytd_match:

        ytd_match = re.search(
            r"前\d+月"
            r".{0,50}?"
            r"稅後淨利"
            r"([\d,.]+)"
            r"億元",
            text,
        )

    eps_match = re.search(
        r"每股稅後盈餘"
        r"\(EPS\)"
        r".{0,10}?"
        r"(?:為)?"
        r"([\d,.]+)"
        r"元",
        text,
    )

    if not monthly_match:
        raise RuntimeError(
            f"Monthly profit not found: {url}"
        )

    if not ytd_match:
        raise RuntimeError(
            f"YTD profit not found: {url}"
        )

    if not eps_match:
        raise RuntimeError(
            f"EPS not found: {url}"
        )

    # 官網單位：億元
    # DB 統一：百萬元
    monthly_profit = round(
        parse_number(
            monthly_match.group("value")
        ) * 100,
        2,
    )

    if monthly_match.group("type") == "淨損":
        monthly_profit = -monthly_profit

    ytd_profit = round(
        parse_number(
            ytd_match.group(1)
        ) * 100,
        2,
    )

    eps = parse_number(
        eps_match.group(1)
    )

    return {
        "stock_id": "2881",
        "stock_name": "富邦金",
        "data_month": f"2026-{month}",
        "monthly_net_profit": monthly_profit,
        "ytd_net_profit": ytd_profit,
        "ytd_eps": eps,
        "source_url": url,
    }


def parse_fubon():

    rows = []

    for url in NEWS_URLS:

        row = parse_article(
            url
        )

        rows.append(
            row
        )

    rows.sort(
        key=lambda x: x["data_month"],
        reverse=True,
    )

    return rows


def main():

    configure_console()

    print("=" * 70)
    print(
        "StockWaveScanner V3 - "
        "Fubon Monthly Earnings Parser"
    )
    print("=" * 70)

    rows = parse_fubon()

    print()
    print(
        f"ROWS: {len(rows)}"
    )

    print()

    for row in rows:

        print(
            row["data_month"],
            f"Monthly={row['monthly_net_profit']}",
            f"YTD={row['ytd_net_profit']}",
            f"EPS={row['ytd_eps']}",
        )

    print()
    print("=" * 70)
    print("FUBON PARSER OK")
    print("=" * 70)

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )