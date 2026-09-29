from __future__ import annotations

import re
import sys

import requests
from bs4 import BeautifulSoup


URL = (
    "https://www.tsholdings.com.tw/"
    "tsh/relations/finance/revenue/"
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

    value = (
        value
        .replace(",", "")
        .replace("+", "")
        .replace("%", "")
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

    text = " ".join(
        soup.stripped_strings
    )

    return text


def parse_taishin():

    text = fetch_text()

    # 只取「台新新光金控」區塊，
    # 避免把台新銀行等子公司資料一起抓進來。
    start_marker = "台新新光金控"
    end_marker = "台新國際商業銀行"

    start_pos = text.find(
        start_marker
    )

    if start_pos < 0:
        raise RuntimeError(
            "Taishin FHC section not found"
        )

    end_pos = text.find(
        end_marker,
        start_pos,
    )

    if end_pos < 0:
        section = text[start_pos:]
    else:
        section = text[
            start_pos:end_pos
        ]

    pattern = re.compile(
        r"(?P<year>20\d{2})"
        r"[-/]"
        r"(?P<month>\d{1,2})"
        r"\s+"
        r"(?P<monthly>-?[\d,]+(?:\.\d+)?)"
        r"\s+"
        r"(?P<monthly_yoy>"
        r"[+-]?[\d,.]+%"
        r"|--"
        r"|N/A"
        r")"
        r"\s+"
        r"(?P<ytd>-?[\d,]+(?:\.\d+)?)"
        r"\s+"
        r"(?P<ytd_yoy>"
        r"[+-]?[\d,.]+%"
        r"|--"
        r"|N/A"
        r")"
        r"\s+"
        r"(?P<eps>-?[\d,.]+)",
        flags=re.IGNORECASE,
    )

    rows = []

    seen = set()

    for match in pattern.finditer(
        section
    ):

        year = match.group(
            "year"
        )

        month = match.group(
            "month"
        ).zfill(2)

        data_month = (
            f"{year}-{month}"
        )

        if data_month in seen:
            continue

        seen.add(
            data_month
        )

        monthly_profit = parse_number(
            match.group(
                "monthly"
            )
        )

        ytd_profit = parse_number(
            match.group(
                "ytd"
            )
        )

        eps = parse_number(
            match.group(
                "eps"
            )
        )

        rows.append(
            {
                "stock_id": "2887",
                "stock_name": "台新新光金",
                "data_month": data_month,
                "monthly_net_profit": (
                    monthly_profit
                ),
                "ytd_net_profit": (
                    ytd_profit
                ),
                "ytd_eps": eps,
                "source_url": URL,
            }
        )

    if not rows:

        raise RuntimeError(
            "No Taishin FHC monthly rows found"
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

    print(
        "=" * 70
    )

    print(
        "StockWaveScanner V3 - "
        "Taishin Shin Kong Monthly "
        "Earnings Parser"
    )

    print(
        "=" * 70
    )

    rows = parse_taishin()

    print()

    print(
        f"ROWS: {len(rows)}"
    )

    print()

    for row in rows[:12]:

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

    print(
        "=" * 70
    )

    print(
        "TAISHIN SHIN KONG "
        "PARSER OK"
    )

    print(
        "=" * 70
    )

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )