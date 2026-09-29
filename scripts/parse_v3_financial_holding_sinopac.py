from __future__ import annotations

import re
import sys

import requests
from bs4 import BeautifulSoup


URL = (
    "https://www.sinopac.com/"
    "investors/20211210153454773946/"
    "20211210153454804513.html"
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

    value = value.replace(
        ",",
        "",
    )

    if value in {
        "-",
        "--",
        "N/A",
    }:
        return None

    return float(value)


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
    response.encoding = "utf-8"

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    return " ".join(
        soup.stripped_strings
    )


def parse_sinopac():

    text = fetch_text()

    date_match = re.search(
        r"(?P<year>20\d{2})年"
        r"(?P<month>\d{1,2})月"
        r"自結損益摘要",
        text,
    )

    if not date_match:

        raise RuntimeError(
            "SinoPac report date not found"
        )

    year = date_match.group(
        "year"
    )

    month = date_match.group(
        "month"
    ).zfill(2)

    monthly_match = re.search(
        r"稅後純益"
        r"\(佰萬元\)"
        r"\s*"
        r"(?P<monthly>-?[\d,]+(?:\.\d+)?)"
        r"\s*"
        r"(?P<ytd>-?[\d,]+(?:\.\d+)?)",
        text,
    )

    eps_match = re.search(
        r"每股稅後純益"
        r"\(元\)"
        r"\s*"
        r"(?P<monthly_eps>-?[\d,.]+)"
        r"\s*"
        r"(?P<ytd_eps>-?[\d,.]+)",
        text,
    )

    if not monthly_match:

        raise RuntimeError(
            "SinoPac profit data not found"
        )

    if not eps_match:

        raise RuntimeError(
            "SinoPac EPS data not found"
        )

    monthly_profit = parse_number(
        monthly_match.group(
            "monthly"
        )
    )

    ytd_profit = parse_number(
        monthly_match.group(
            "ytd"
        )
    )

    ytd_eps = parse_number(
        eps_match.group(
            "ytd_eps"
        )
    )

    return [
        {
            "stock_id": "2890",
            "stock_name": "永豐金",
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
        "SinoPac Monthly Earnings Parser"
    )

    print("=" * 70)

    rows = parse_sinopac()

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
        "SINOPAC PARSER OK"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )