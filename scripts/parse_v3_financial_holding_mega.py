from __future__ import annotations

import sys
from io import StringIO

import pandas as pd
import requests


URLS = [
    (
        "2025",
        "https://www.megaholdings.com.tw/"
        "tc/investors_in02.aspx"
        "?chk=f7223f64-a04a-4e15-ae2e-efbb55dbb14f"
        "&id=6543",
    ),
    (
        "2024",
        "https://www.megaholdings.com.tw/"
        "tc/investors_in02.aspx"
        "?chk=cadddb6a-0939-49ae-a48d-76f40b781a6d"
        "&id=6463",
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

    value = value.replace(
        ",",
        "",
    )

    if value.lower() in {
        "-",
        "--",
        "nan",
        "none",
    }:
        return None

    return float(value)


def fetch_html(url):

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

    return response.text


def normalize_dataframe(df):

    result = df.copy()

    # MultiIndex 欄位轉成簡單文字
    if isinstance(
        result.columns,
        pd.MultiIndex,
    ):

        result.columns = [
            " ".join(
                str(part).strip()
                for part in column
                if str(part).strip()
                and not str(part).startswith(
                    "Unnamed"
                )
            )
            for column in result.columns
        ]

    else:

        result.columns = [
            str(column).strip()
            for column in result.columns
        ]

    return result


def is_target_table(df):

    if df.empty:
        return False

    if len(df.columns) < 7:
        return False

    column_text = " ".join(
        str(column)
        for column in df.columns
    )

    body_text = " ".join(
        str(value)
        for value in df.head(3).values.flatten()
    )

    combined = (
        column_text
        + " "
        + body_text
    )

    keywords = [
        "月份",
        "合併稅後淨利",
        "EPS",
    ]

    return all(
        keyword in combined
        for keyword in keywords
    )


def parse_year(
    year,
    url,
):

    html_text = fetch_html(
        url
    )

    tables = pd.read_html(
        StringIO(
            html_text
        )
    )

    target = None

    for raw_df in tables:

        df = normalize_dataframe(
            raw_df
        )

        if is_target_table(
            df
        ):

            target = df
            break

    if target is None:

        print()
        print(
            f"[DEBUG] Tables found: "
            f"{len(tables)}"
        )

        for index, raw_df in enumerate(
            tables
        ):

            df = normalize_dataframe(
                raw_df
            )

            print()
            print(
                f"TABLE {index}"
            )

            print(
                f"COLUMNS: "
                f"{list(df.columns)}"
            )

            print(
                df.head(3).to_string(
                    index=False
                )
            )

        raise RuntimeError(
            f"Mega earnings table not found: "
            f"{year}"
        )

    rows = []

    for _, item in target.iterrows():

        values = list(
            item.values
        )

        if len(values) < 7:
            continue

        month_raw = str(
            values[0]
        ).strip()

        if month_raw.lower() == "nan":
            continue

        try:

            month_int = int(
                float(
                    month_raw
                )
            )

        except ValueError:

            continue

        if not (
            1 <= month_int <= 12
        ):
            continue

        month = (
            f"{month_int:02d}"
        )

        monthly_net_profit_thousand = (
            parse_number(
                values[3]
            )
        )

        ytd_net_profit_thousand = (
            parse_number(
                values[4]
            )
        )

        ytd_eps = parse_number(
            values[6]
        )

        if (
            monthly_net_profit_thousand
            is None
            or ytd_net_profit_thousand
            is None
        ):
            continue

        # 官網單位：仟元
        # DB 單位：百萬元

        monthly_net_profit = round(
            monthly_net_profit_thousand
            / 1000,
            3,
        )

        ytd_net_profit = round(
            ytd_net_profit_thousand
            / 1000,
            3,
        )

        rows.append(
            {
                "stock_id": "2886",
                "stock_name": "兆豐金",
                "data_month": (
                    f"{year}-{month}"
                ),
                "monthly_net_profit": (
                    monthly_net_profit
                ),
                "ytd_net_profit": (
                    ytd_net_profit
                ),
                "ytd_eps": ytd_eps,
                "source_url": url,
            }
        )

    if not rows:

        raise RuntimeError(
            f"No Mega rows parsed: "
            f"{year}"
        )

    return rows


def parse_mega():

    rows = []

    seen = set()

    for year, url in URLS:

        year_rows = parse_year(
            year,
            url,
        )

        for row in year_rows:

            key = row[
                "data_month"
            ]

            if key in seen:
                continue

            seen.add(
                key
            )

            rows.append(
                row
            )

    if not rows:

        raise RuntimeError(
            "No Mega monthly rows found"
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
        "Mega Monthly Earnings Parser"
    )

    print("=" * 70)

    rows = parse_mega()

    print()

    print(
        f"ROWS: {len(rows)}"
    )

    print()

    for row in rows[:15]:

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
        "MEGA PARSER OK"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )