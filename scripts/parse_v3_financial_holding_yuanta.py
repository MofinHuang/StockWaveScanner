from __future__ import annotations

import json
import re
import sys

import requests


URL = "https://www.yuanta.com/TW/IR/Financials/Monthly-Earnings"


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

    if not value:
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


def extract_data(html_text: str):

    match = re.search(
        r"var\s+data\s*=\s*(\[.*?\]);",
        html_text,
        flags=re.DOTALL,
    )

    if not match:
        raise RuntimeError(
            "Yuanta var data not found"
        )

    raw_json = match.group(1)

    return json.loads(
        raw_json
    )


def parse_yuanta():

    html_text = fetch_html()

    source_data = extract_data(
        html_text
    )

    rows = []

    for year_group in source_data:

        year = str(
            year_group.get("year", "")
        ).strip()

        month_items = (
            year_group.get("data")
            or []
        )

        for month_group in month_items:

            month = str(
                month_group.get(
                    "month",
                    "",
                )
            ).zfill(2)

            companies = (
                month_group.get("data")
                or []
            )

            for company in companies:

                if (
                    company.get("title")
                    != "元大金控"
                ):
                    continue

                rows.append(
                    {
                        "stock_id": "2885",
                        "stock_name": "元大金",
                        "data_month": (
                            f"{year}-{month}"
                        ),
                        "monthly_net_profit": (
                            parse_number(
                                company.get(
                                    "netIncome"
                                )
                            )
                        ),
                        "ytd_net_profit": (
                            parse_number(
                                company.get(
                                    "accNetIncome"
                                )
                            )
                        ),
                        "ytd_eps": (
                            parse_number(
                                company.get(
                                    "accEPS"
                                )
                            )
                        ),
                        "source_url": URL,
                    }
                )

    if not rows:
        raise RuntimeError(
            "No Yuanta FHC monthly rows found"
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
        "Yuanta Monthly Earnings Parser"
    )
    print("=" * 70)

    rows = parse_yuanta()

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
    print("YUANTA PARSER OK")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )