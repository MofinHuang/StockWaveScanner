from __future__ import annotations

import re
import sys

import requests
from lxml import html


URL = "https://www.cathayholdings.com/holdings/ir/financial_information/monthly"


def configure_console():

    for stream in (sys.stdout, sys.stderr):

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

    if not value or value == "-":
        return None

    return float(
        value.replace(",", "")
    )


def fetch_html():

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

    return response.text


def parse_cathay():

    html_text = fetch_html()

    root = html.fromstring(
        html_text
    )

    text = "\n".join(
        line.strip()
        for line in root.text_content().splitlines()
        if line.strip()
    )

    pattern = re.compile(
        r"國泰金控暨主要子公司"
        r"(?P<year>\d{4})年"
        r"(?P<month>\d{1,2})月份自結盈餘"
        r".*?"
        r"國泰金控"
        r".*?"
        r"月份稅後淨利\(億台幣\):\s*"
        r"(?P<monthly>[\d,.]+)"
        r".*?"
        r"累計稅後淨利\(億台幣\):\s*"
        r"(?P<ytd>[\d,.]+)"
        r".*?"
        r"累計EPS\(NT\$\):\s*"
        r"(?P<eps>[\d,.]+)",
        flags=re.DOTALL,
    )

    rows = []

    for match in pattern.finditer(text):

        year = match.group("year")
        month = match.group("month").zfill(2)

        # 官網單位為億元
        # DB 統一存百萬元
        monthly_profit = round(
            parse_number(
                match.group("monthly")
            ) * 100,
            2,
        )

        ytd_profit = round(
            parse_number(
                match.group("ytd")
            ) * 100,
            2,
        )

        eps = parse_number(
            match.group("eps")
        )

        rows.append(
            {
                "stock_id": "2882",
                "stock_name": "國泰金",
                "data_month": f"{year}-{month}",
                "monthly_net_profit": monthly_profit,
                "ytd_net_profit": ytd_profit,
                "ytd_eps": eps,
                "source_url": URL,
            }
        )

    if not rows:
        raise RuntimeError(
            "No Cathay FHC monthly rows found"
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
        "Cathay Monthly Earnings Parser"
    )
    print("=" * 70)

    rows = parse_cathay()

    print()
    print(
        f"ROWS: {len(rows)}"
    )

    print()

    for row in rows[:12]:

        print(
            row["data_month"],
            f"Monthly={row['monthly_net_profit']}",
            f"YTD={row['ytd_net_profit']}",
            f"EPS={row['ytd_eps']}",
        )

    print()
    print("=" * 70)
    print("CATHAY PARSER OK")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )