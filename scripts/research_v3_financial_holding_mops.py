from __future__ import annotations

import sys
from io import StringIO

import pandas as pd
import requests


URL = "https://mops.twse.com.tw/mops/web/t120sb02_q10"

STOCKS = [
    "2880",
    "2881",
    "2882",
    "2883",
    "2884",
    "2885",
    "2886",
    "2887",
    "2889",
    "2890",
    "2891",
    "2892",
    "5880",
]


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


def fetch_stock(stock_id: str):

    payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "keyword4": "",
        "code1": "",
        "TYPEK2": "",
        "checkbtn": "",
        "queryName": "co_id",
        "inpuType": "co_id",
        "TYPEK": "all",
        "co_id": stock_id,
        "year": "115",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/154 Safari/537.36"
        ),
        "Referer": URL,
        "Content-Type": (
            "application/x-www-form-urlencoded"
        ),
    }

    response = requests.post(
        URL,
        data=payload,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()

    response.encoding = "utf-8"

    return response.text


def inspect_tables(stock_id: str, html: str):

    print()
    print("=" * 70)
    print(f"[{stock_id}]")
    print("=" * 70)

    if "FOR SECURITY REASONS" in html:
        print("SECURITY_BLOCK")
        return

    if "查無資料" in html:
        print("NO_DATA")
        return

    try:

        tables = pd.read_html(
            StringIO(html)
        )

    except ValueError:

        print("NO_TABLE")
        return

    print(
        f"TABLE COUNT: {len(tables)}"
    )

    for index, df in enumerate(tables):

        print()
        print(
            f"--- TABLE {index} "
            f"rows={len(df)} "
            f"cols={len(df.columns)} ---"
        )

        if df.empty:
            continue

        print(
            "COLUMNS:"
        )

        for column in df.columns:
            print(
                f"  {column}"
            )

        print()
        print(
            df.head(5).to_string(
                index=False
            )
        )


def main():

    configure_console()

    print("=" * 70)
    print(
        "StockWaveScanner V3 - "
        "Financial Holding MOPS Research"
    )
    print("=" * 70)

    print()
    print(
        "Research only - NO DATABASE WRITE"
    )

    for stock_id in STOCKS:

        try:

            html = fetch_stock(
                stock_id
            )

            inspect_tables(
                stock_id,
                html,
            )

        except Exception as exc:

            print()
            print("=" * 70)
            print(f"[{stock_id}]")
            print("=" * 70)

            print(
                f"ERROR: "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

    print()
    print("=" * 70)
    print("RESEARCH FINISHED")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )