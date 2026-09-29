from __future__ import annotations

import io
import re
import sys

import requests
import urllib3
from pypdf import PdfReader


urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


PDF_URLS = [
    "https://www.hnfhc.com.tw/uploads/operating/20250108170941493381.pdf",
    "https://www.hnfhc.com.tw/uploads/operating/20241206164654526808.pdf",
    "https://www.hnfhc.com.tw/uploads/operating/20240410162854892142.pdf",
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


def fetch_pdf_text(url):

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

    if not response.content.startswith(
        b"%PDF"
    ):
        raise RuntimeError(
            f"Response is not PDF: {url}"
        )

    reader = PdfReader(
        io.BytesIO(
            response.content
        )
    )

    pages = []

    for page in reader.pages:

        text = page.extract_text()

        if text:
            pages.append(
                text
            )

    if not pages:
        raise RuntimeError(
            f"No PDF text extracted: {url}"
        )

    return "\n".join(
        pages
    )


def normalize_text(text):

    text = text.replace(
        "\u3000",
        " ",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def find_date(text):

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

    raise RuntimeError(
        "Hua Nan report date not found"
    )


def find_sentence_values(text):

    monthly_match = re.search(
        r"本月"
        r".{0,80}?"
        r"合併稅後淨利"
        r"(?:為)?"
        r"\s*"
        r"(?P<value>-?[\d,.]+)"
        r"\s*億元",
        text,
    )

    if not monthly_match:

        monthly_match = re.search(
            r"華南金控"
            r".{0,80}?"
            r"合併稅後淨利"
            r"(?:為)?"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*億元",
            text,
        )

    ytd_match = re.search(
        r"(?:累計|全年累計)"
        r".{0,100}?"
        r"合併稅後淨利"
        r"(?:為)?"
        r"\s*"
        r"(?P<value>-?[\d,.]+)"
        r"\s*億元",
        text,
    )

    eps_match = re.search(
        r"每股稅後盈餘"
        r"(?:為)?"
        r"\s*"
        r"(?P<value>-?[\d,.]+)"
        r"\s*元",
        text,
    )

    if (
        monthly_match
        and ytd_match
        and eps_match
    ):

        return (
            parse_number(
                monthly_match.group(
                    "value"
                )
            ),
            parse_number(
                ytd_match.group(
                    "value"
                )
            ),
            parse_number(
                eps_match.group(
                    "value"
                )
            ),
        )

    return None


def find_table_values(text):

    pattern = re.compile(
        r"華南金控"
        r"\s+"
        r"(?P<monthly_pre>-?[\d,.]+)"
        r"\s+"
        r"(?P<monthly>-?[\d,.]+)"
        r"\s+"
        r"(?P<ytd_pre>-?[\d,.]+)"
        r"\s+"
        r"(?P<ytd>-?[\d,.]+)"
        r"\s+"
        r"(?P<eps_pre>-?[\d,.]+)"
        r"\s+"
        r"(?P<eps>-?[\d,.]+)"
    )

    match = pattern.search(
        text
    )

    if not match:
        return None

    return (
        parse_number(
            match.group(
                "monthly"
            )
        ),
        parse_number(
            match.group(
                "ytd"
            )
        ),
        parse_number(
            match.group(
                "eps"
            )
        ),
    )


def parse_article(url):

    raw_text = fetch_pdf_text(
        url
    )

    text = normalize_text(
        raw_text
    )

    year, month = find_date(
        text
    )

    values = find_sentence_values(
        text
    )

    if values is None:

        values = find_table_values(
            text
        )

    if values is None:

        print()
        print(
            "[DEBUG] Hua Nan text preview:"
        )

        print(
            text[:5000]
        )

        raise RuntimeError(
            f"Hua Nan earnings data not found: {url}"
        )

    (
        monthly_profit_100m,
        ytd_profit_100m,
        eps,
    ) = values

    # 官網：億元
    # DB：百萬元

    monthly_profit = round(
        monthly_profit_100m
        * 100,
        2,
    )

    ytd_profit = round(
        ytd_profit_100m
        * 100,
        2,
    )

    return {
        "stock_id": "2880",
        "stock_name": "華南金",
        "data_month": (
            f"{year}-{month}"
        ),
        "monthly_net_profit": (
            monthly_profit
        ),
        "ytd_net_profit": (
            ytd_profit
        ),
        "ytd_eps": eps,
        "source_url": url,
    }


def parse_huanan():

    rows = []

    seen = set()

    for url in PDF_URLS:

        row = parse_article(
            url
        )

        data_month = row[
            "data_month"
        ]

        if data_month in seen:
            continue

        seen.add(
            data_month
        )

        rows.append(
            row
        )

    if not rows:

        raise RuntimeError(
            "No Hua Nan monthly rows found"
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
        "Hua Nan Monthly Earnings Parser"
    )

    print(
        "=" * 70
    )

    rows = parse_huanan()

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

    print(
        "=" * 70
    )

    print(
        "HUA NAN PARSER OK"
    )

    print(
        "=" * 70
    )

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )