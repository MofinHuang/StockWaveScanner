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
    "https://www.ctbcholding.com/content/dam/twhoo/file/news/2026/20260611.pdf",
    "https://www.ctbcholding.com/content/dam/twhoo/file/news/2026/20260414.pdf",
    "https://www.ctbcholding.com/content/dam/twhoo/file/news/2026/20260109.pdf",
    "https://www.ctbcholding.com/content/dam/twhoo/file/news/2025/20250905.pdf",
    "https://www.ctbcholding.com/content/dam/twhoo/file/news/2025/20250807.pdf",
    "https://www.ctbcholding.com/content/dam/twhoo/file/news/2025/20250508-4.pdf",
    "https://www.ctbcholding.com/content/dam/twhoo/file/news/2025/20250207.pdf",
    "https://www.ctbcholding.com/content/dam/twhoo/file/news/2024/20241206.pdf",
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


def find_report_date(text, url):

    patterns = [
        re.compile(
            r"(?P<year>20\d{2})"
            r"\s*年"
            r"\s*(?P<month>\d{1,2})"
            r"\s*月份"
        ),
        re.compile(
            r"(?P<year>20\d{2})"
            r"\s*年"
            r"\s*(?P<month>\d{1,2})"
            r"\s*月"
            r".{0,20}?"
            r"自結盈餘"
        ),
    ]

    for pattern in patterns:

        match = pattern.search(
            text
        )

        if match:

            return (
                match.group(
                    "year"
                ),
                match.group(
                    "month"
                ).zfill(2),
            )

    raise RuntimeError(
        f"CTBC report date not found: {url}"
    )


def find_monthly_profit(text, url):

    patterns = [
        re.compile(
            r"單月"
            r"(?:合併)?"
            r"稅後盈餘"
            r"(?:為)?"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*億元"
        ),
        re.compile(
            r"(?P<month>\d{1,2})"
            r"\s*月份"
            r".{0,40}?"
            r"稅後盈餘"
            r"(?:為)?"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*億元"
        ),
    ]

    for pattern in patterns:

        match = pattern.search(
            text
        )

        if match:

            return round(
                parse_number(
                    match.group(
                        "value"
                    )
                )
                * 100,
                2,
            )

    raise RuntimeError(
        f"CTBC monthly profit not found: {url}"
    )


def find_ytd_profit(
    text,
    month,
    monthly_profit,
    url,
):

    patterns = [
        re.compile(
            r"累計"
            r"(?:前.{0,10}?月|全年)?"
            r"(?:合併)?"
            r"稅後盈餘"
            r"(?:為)?"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*億元"
        ),
        re.compile(
            r"累計"
            r"(?:前.{0,10}?月|全年)?"
            r"(?:合併)?"
            r"稅後"
            r"(?:淨利|獲利)"
            r"(?:為)?"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*億"
        ),
    ]

    for pattern in patterns:

        match = pattern.search(
            text
        )

        if match:

            return round(
                parse_number(
                    match.group(
                        "value"
                    )
                )
                * 100,
                2,
            )

    if month == "01":
        return monthly_profit

    raise RuntimeError(
        f"CTBC YTD profit not found: {url}"
    )


def find_eps(text, url):

    patterns = [
        re.compile(
            r"每股稅後盈餘"
            r"(?:（EPS）|\(EPS\)|EPS)?"
            r"(?:為)?"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*元",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"EPS"
            r"(?:為)?"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*元",
            flags=re.IGNORECASE,
        ),
    ]

    for pattern in patterns:

        match = pattern.search(
            text
        )

        if match:

            return parse_number(
                match.group(
                    "value"
                )
            )

    raise RuntimeError(
        f"CTBC EPS not found: {url}"
    )


def parse_article(url):

    text = normalize_text(
        fetch_pdf_text(
            url
        )
    )

    year, month = find_report_date(
        text,
        url,
    )

    monthly_profit = find_monthly_profit(
        text,
        url,
    )

    ytd_profit = find_ytd_profit(
        text,
        month,
        monthly_profit,
        url,
    )

    ytd_eps = find_eps(
        text,
        url,
    )

    return {
        "stock_id": "2891",
        "stock_name": "中信金",
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
        "source_url": url,
    }


def parse_ctbc():

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
            "No CTBC monthly rows found"
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
        "CTBC Monthly Earnings Parser"
    )

    print("=" * 70)

    rows = parse_ctbc()

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
        "CTBC PARSER OK"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )