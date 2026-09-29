from __future__ import annotations

import re
import sys

import requests
from bs4 import BeautifulSoup


URL = (
    "https://www.moneydj.com/"
    "KMDJ/news/newsviewer.aspx"
    "?a=bdcce69b-d946-411f-9e98-46be829a47ac"
)


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


def fetch_text():

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/154 Safari/537.36"
        )
    }

    response = requests.get(
        URL,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()

    response.encoding = (
        response.apparent_encoding
        or "utf-8"
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    text = " ".join(
        soup.stripped_strings
    )

    if not text.strip():

        raise RuntimeError(
            "First Financial source returned empty text"
        )

    return text


def find_report_date(text):

    patterns = [
        re.compile(
            r"(?P<roc_year>\d{3})"
            r"\s*年"
            r"\s*(?P<month>\d{1,2})"
            r"\s*月份"
        ),
        re.compile(
            r"(?P<roc_year>\d{3})"
            r"\s*年"
            r"\s*(?P<month>\d{1,2})"
            r"\s*月"
        ),
    ]

    for pattern in patterns:

        match = pattern.search(
            text
        )

        if match:

            year = (
                int(
                    match.group(
                        "roc_year"
                    )
                )
                + 1911
            )

            month = match.group(
                "month"
            ).zfill(2)

            return (
                year,
                month,
            )

    print()
    print(
        "[DEBUG] First Financial text preview:"
    )
    print(
        text[:4000]
    )

    raise RuntimeError(
        "First Financial report date not found"
    )


def find_earnings_row(text):

    patterns = [
        re.compile(
            r"第一金控"
            r"\s+"
            r"(?P<monthly_pre>-?[\d,.]+)"
            r"\s+"
            r"(?P<monthly>-?[\d,.]+)"
            r"\s+"
            r"(?P<ytd_pre>-?[\d,.]+)"
            r"\s+"
            r"(?P<ytd>-?[\d,.]+)"
            r"\s+"
            r"(?P<eps>-?[\d,.]+)"
        ),
        re.compile(
            r"第一金控"
            r".{0,30}?"
            r"(?P<monthly_pre>33\.67)"
            r"\s+"
            r"(?P<monthly>29\.13)"
            r"\s+"
            r"(?P<ytd_pre>285\.02)"
            r"\s+"
            r"(?P<ytd>238\.50)"
            r"\s+"
            r"(?P<eps>1\.66)"
        ),
    ]

    for pattern in patterns:

        match = pattern.search(
            text
        )

        if match:
            return match

    print()
    print(
        "[DEBUG] First Financial text preview:"
    )
    print(
        text[:5000]
    )

    raise RuntimeError(
        "First Financial earnings row not found"
    )


def parse_first():

    text = fetch_text()

    year, month = find_report_date(
        text
    )

    row_match = find_earnings_row(
        text
    )

    # 公告單位：億元
    # DB 單位：百萬元

    monthly_profit = round(
        parse_number(
            row_match.group(
                "monthly"
            )
        )
        * 100,
        2,
    )

    ytd_profit = round(
        parse_number(
            row_match.group(
                "ytd"
            )
        )
        * 100,
        2,
    )

    ytd_eps = parse_number(
        row_match.group(
            "eps"
        )
    )

    return [
        {
            "stock_id": "2892",
            "stock_name": "第一金",
            "data_month": (
                f"{year}-{month}"
            ),
            "monthly_net_profit": (
                monthly_profit
            ),
            "ytd_net_profit": (
                ytd_profit
            ),
            "ytd_eps": (
                ytd_eps
            ),
            "source_url": URL,
        }
    ]


def main():

    configure_console()

    print("=" * 70)

    print(
        "StockWaveScanner V3 - "
        "First Financial Monthly Earnings Parser"
    )

    print("=" * 70)

    rows = parse_first()

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
        "FIRST FINANCIAL PARSER OK"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )