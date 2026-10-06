from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import libsql
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


STOCK_ID = "2883"
STOCK_NAME = "凱基金"

TARGET_YEAR = 2025

BASE_URL = "https://www.kgi.com"

LIST_YEARS = [
    2025,
    2026,
]

MAX_PAGES = 10

REQUEST_RETRIES = 5

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


FALLBACK_ARTICLES = [
    {
        "data_month": "2025-09",
        "title": (
            "凱基金控9月份自結稅後獲利45.28億元 "
            "今年前三季稅後獲利190.50億元 "
            "每股盈餘1.09元"
        ),
        "source_date": "2025-10-09",
        "source_url": (
            "https://www.kgi.com/zh-tw/press/"
            "news-detail-content?"
            "dtlsrc=b9bc64216a7d444dbf7b384f649449e0"
            "&id=8b4529e665da477ab11214f0431004c0"
            "&secsrc=ce44e7f6813e4e76a4eacf65ef9388d8"
        ),
        "monthly_net_profit": 4528.0,
        "ytd_net_profit": 19050.0,
        "ytd_eps": 1.09,
    },
]


CHINESE_MONTH_MAP = {
    1: "一",
    2: "二",
    3: "三",
    4: "四",
    5: "五",
    6: "六",
    7: "七",
    8: "八",
    9: "九",
    10: "十",
    11: "十一",
    12: "十二",
}


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


def normalize_text(
    text,
):

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def parse_number(
    value,
):

    if value is None:

        return None

    value = str(
        value
    ).strip()

    if not value:

        return None

    return float(
        value.replace(
            ",",
            "",
        )
    )


def get_headers():

    return {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/154 Safari/537.36"
        ),
    }


def get_connection():

    load_dotenv(
        ENV_FILE
    )

    url = os.getenv(
        "TURSO_DEV_DATABASE_URL",
        "",
    ).strip()

    token = os.getenv(
        "TURSO_DEV_AUTH_TOKEN",
        "",
    ).strip()

    if not url:

        raise RuntimeError(
            "TURSO_DEV_DATABASE_URL missing"
        )

    if not token:

        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN missing"
        )

    lower_url = (
        url.lower()
    )

    if (
        "stockwave-dev"
        not in lower_url
    ):

        raise RuntimeError(
            "SAFETY STOP: "
            "DEV database required"
        )

    if (
        "stockwave-prod"
        in lower_url
    ):

        raise RuntimeError(
            "SAFETY STOP: "
            "PROD database detected"
        )

    return libsql.connect(
        database=url,
        auth_token=token,
    )


def fetch_html(
    url,
):

    last_exception = None

    for attempt in range(
        1,
        REQUEST_RETRIES + 1,
    ):

        try:

            response = requests.get(
                url,
                headers=get_headers(),
                timeout=(
                    10,
                    60,
                ),
            )

            response.raise_for_status()

            response.encoding = (
                response.apparent_encoding
                or "utf-8"
            )

            if not response.text.strip():

                raise RuntimeError(
                    "KGI source returned "
                    f"empty HTML: {url}"
                )

            return response.text

        except (
            requests.exceptions.HTTPError
        ) as exc:

            last_exception = exc

            status_code = (
                exc.response.status_code
                if exc.response
                is not None
                else None
            )

            if status_code not in {
                500,
                502,
                503,
                504,
            }:

                raise

            print(
                "[WARN] KGI HTTP error: "
                f"{status_code} "
                f"attempt="
                f"{attempt}/"
                f"{REQUEST_RETRIES}"
            )

        except (
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError,
        ) as exc:

            last_exception = exc

            print(
                "[WARN] KGI connection error: "
                f"{type(exc).__name__} "
                f"attempt="
                f"{attempt}/"
                f"{REQUEST_RETRIES}"
            )

        if attempt >= REQUEST_RETRIES:

            break

        import time

        wait_seconds = (
            attempt * 3
        )

        print(
            "[WAIT] Retry after "
            f"{wait_seconds} seconds"
        )

        time.sleep(
            wait_seconds
        )

    if last_exception:

        raise last_exception

    raise RuntimeError(
        "KGI request failed"
    )


def build_list_url(
    year,
    page,
):

    url = (
        f"{BASE_URL}/zh-tw/press"
        f"?category=all"
        f"&year={year}"
    )

    if page > 0:

        url += (
            f"&p={page}"
        )

    return url


def extract_date_from_title(
    title,
):

    match = re.search(
        r"(?P<year>20\d{2})"
        r"\."
        r"(?P<month>\d{1,2})"
        r"\."
        r"(?P<day>\d{1,2})",
        title,
    )

    if not match:

        return None

    try:

        value = datetime(
            int(
                match.group(
                    "year"
                )
            ),
            int(
                match.group(
                    "month"
                )
            ),
            int(
                match.group(
                    "day"
                )
            ),
        )

    except ValueError:

        return None

    return value.strftime(
        "%Y-%m-%d"
    )


def source_date_to_data_month(
    source_date,
):

    value = datetime.strptime(
        source_date,
        "%Y-%m-%d",
    )

    if value.month == 1:

        data_year = (
            value.year - 1
        )

        data_month = 12

    else:

        data_year = (
            value.year
        )

        data_month = (
            value.month - 1
        )

    return (
        f"{data_year}-"
        f"{data_month:02d}"
    )


def find_candidate_articles():

    result = {}

    for list_year in (
        LIST_YEARS
    ):

        print()
        print(
            "=" * 70
        )

        print(
            "[SEARCH] KGI "
            f"{list_year} news center"
        )

        print(
            "=" * 70
        )

        for page in range(
            MAX_PAGES
        ):

            url = build_list_url(
                list_year,
                page,
            )

            print(
                "[FETCH] List page: "
                f"{url}"
            )

            html = fetch_html(
                url
            )

            soup = BeautifulSoup(
                html,
                "html.parser",
            )

            page_found = 0

            for anchor in soup.find_all(
                "a",
                href=True,
            ):

                title = normalize_text(
                    anchor.get_text(
                        " ",
                        strip=True,
                    )
                )

                if not title:

                    continue

                if (
                    "凱基金控"
                    not in title
                ):

                    continue

                if (
                    "自結"
                    not in title
                ):

                    continue

                if (
                    "稅後"
                    not in title
                ):

                    continue

                source_date = (
                    extract_date_from_title(
                        title
                    )
                )

                if source_date is None:

                    continue

                data_month = (
                    source_date_to_data_month(
                        source_date
                    )
                )

                if not data_month.startswith(
                    f"{TARGET_YEAR}-"
                ):

                    continue

                href = (
                    anchor.get(
                        "href",
                        "",
                    ).strip()
                )

                if not href:

                    continue

                detail_url = urljoin(
                    BASE_URL,
                    href,
                )

                result[
                    data_month
                ] = {
                    "data_month": (
                        data_month
                    ),
                    "title": title,
                    "source_date": (
                        source_date
                    ),
                    "source_url": (
                        detail_url
                    ),
                }

                page_found += 1

                print(
                    "[FOUND] "
                    f"{data_month} "
                    f"{title}"
                )

            print(
                "[INFO] "
                f"Page candidates: "
                f"{page_found}"
            )

    for article in (
        FALLBACK_ARTICLES
    ):

        data_month = (
            article[
                "data_month"
            ]
        )

        if (
            data_month
            not in result
        ):

            result[
                data_month
            ] = article.copy()

            print(
                "[FALLBACK] "
                f"{data_month} "
                f"{article['source_url']}"
            )

    rows = list(
        result.values()
    )

    rows.sort(
        key=lambda x: x[
            "data_month"
        ]
    )

    print()
    print(
        "[INFO] 2025 candidate "
        f"months: {len(rows)}"
    )

    return rows


def extract_monthly_from_title(
    title,
):

    patterns = [
        re.compile(
            r"凱基金控"
            r".{0,40}?"
            r"自結"
            r".{0,20}?"
            r"稅後"
            r"(?P<type>"
            r"獲利|淨利|虧損|淨損"
            r")"
            r"\s*"
            r"(?P<value>[\d,.]+)"
            r"\s*億元"
        ),
    ]

    for pattern in patterns:

        match = pattern.search(
            title
        )

        if not match:

            continue

        value = parse_number(
            match.group(
                "value"
            )
        )

        profit_type = (
            match.group(
                "type"
            )
        )

        if profit_type in {
            "虧損",
            "淨損",
        }:

            value = -abs(
                value
            )

        return value

    return None


def extract_ytd_from_title(
    title,
    month,
):

    if month == 1:

        return None

    chinese_month = (
        CHINESE_MONTH_MAP[
            month
        ]
    )

    patterns = []

    #
    # 12 月全年
    #
    if month == 12:

        patterns.extend(
            [
                re.compile(
                    r"全年"
                    r"\s*稅後"
                    r"(?:獲利|淨利)"
                    r"\s*"
                    r"(?P<value>[\d,.]+)"
                    r"\s*億元"
                ),
                re.compile(
                    r"2025"
                    r"\s*全年"
                    r".{0,20}?"
                    r"稅後"
                    r"(?:獲利|淨利)"
                    r"\s*"
                    r"(?P<value>[\d,.]+)"
                    r"\s*億元"
                ),
            ]
        )

    #
    # 第一季
    #
    if month == 3:

        patterns.append(
            re.compile(
                r"(?:今年)?"
                r"\s*第一季"
                r"\s*稅後"
                r"(?:獲利|淨利)"
                r"\s*"
                r"(?P<value>[\d,.]+)"
                r"\s*億元"
            )
        )

    #
    # 上半年
    #
    if month == 6:

        patterns.append(
            re.compile(
                r"(?:今年)?"
                r"\s*上半年"
                r".{0,20}?"
                r"稅後"
                r"(?:獲利|淨利)"
                r"\s*"
                r"(?P<value>[\d,.]+)"
                r"\s*億元"
            )
        )

    #
    # 前三季
    #
    if month == 9:

        patterns.append(
            re.compile(
                r"(?:今年)?"
                r"\s*前三季"
                r"\s*稅後"
                r"(?:獲利|淨利)"
                r"\s*"
                r"(?P<value>[\d,.]+)"
                r"\s*億元"
            )
        )

    #
    # 中文月份：
    #
    # 今年前二月
    # 今年前七月
    # 今年前十一月
    #
    patterns.append(
        re.compile(
            rf"(?:今年)?"
            rf"\s*前"
            rf"\s*{chinese_month}"
            rf"\s*月"
            rf"\s*稅後"
            rf"(?:獲利|淨利)"
            rf"\s*"
            rf"(?P<value>[\d,.]+)"
            rf"\s*億元"
        )
    )

    #
    # 阿拉伯數字：
    #
    # 今年前8月
    # 今年前11月
    #
    patterns.append(
        re.compile(
            rf"(?:今年)?"
            rf"\s*前"
            rf"\s*{month}"
            rf"\s*月"
            rf"\s*稅後"
            rf"(?:獲利|淨利)"
            rf"\s*"
            rf"(?P<value>[\d,.]+)"
            rf"\s*億元"
        )
    )

    #
    # 累計格式
    #
    patterns.append(
        re.compile(
            rf"(?:今年)?"
            rf"\s*前"
            rf"\s*{chinese_month}"
            rf"\s*月"
            rf"\s*累計"
            rf"\s*稅後"
            rf"(?:獲利|淨利)"
            rf"\s*"
            rf"(?P<value>[\d,.]+)"
            rf"\s*億元"
        )
    )

    patterns.append(
        re.compile(
            rf"(?:今年)?"
            rf"\s*前"
            rf"\s*{month}"
            rf"\s*月"
            rf"\s*累計"
            rf"\s*稅後"
            rf"(?:獲利|淨利)"
            rf"\s*"
            rf"(?P<value>[\d,.]+)"
            rf"\s*億元"
        )
    )

    for pattern in patterns:

        match = pattern.search(
            title
        )

        if match:

            return parse_number(
                match.group(
                    "value"
                )
            )

    return None


def extract_eps_from_title(
    title,
):

    patterns = [
        re.compile(
            r"每股盈餘"
            r"\s*"
            r"(?P<value>[\d,.]+)"
            r"\s*元"
        ),
        re.compile(
            r"每股獲利"
            r"\s*"
            r"(?:為)?"
            r"\s*"
            r"(?P<value>[\d,.]+)"
            r"\s*元"
        ),
    ]

    for pattern in patterns:

        match = pattern.search(
            title
        )

        if match:

            return parse_number(
                match.group(
                    "value"
                )
            )

    return None


def parse_article(
    article,
):

    if (
        "monthly_net_profit"
        in article
    ):

        print()
        print(
            "[PARSE] "
            f"{article['data_month']} "
            "(official fallback)"
        )

        return {
            "stock_id": STOCK_ID,
            "stock_name": STOCK_NAME,
            "data_month": (
                article[
                    "data_month"
                ]
            ),
            "monthly_net_profit": (
                article[
                    "monthly_net_profit"
                ]
            ),
            "ytd_net_profit": (
                article[
                    "ytd_net_profit"
                ]
            ),
            "ytd_eps": (
                article[
                    "ytd_eps"
                ]
            ),
            "source_date": (
                article[
                    "source_date"
                ]
            ),
            "source_url": (
                article[
                    "source_url"
                ]
            ),
        }

    data_month = (
        article[
            "data_month"
        ]
    )

    title = (
        article[
            "title"
        ]
    )

    _, month_text = (
        data_month.split(
            "-"
        )
    )

    month = int(
        month_text
    )

    print()
    print(
        f"[PARSE] "
        f"{data_month}"
    )

    print(
        f"[TITLE] "
        f"{title}"
    )

    monthly_profit = (
        extract_monthly_from_title(
            title
        )
    )

    if monthly_profit is None:

        raise RuntimeError(
            "KGI monthly profit "
            "not found in title: "
            f"{data_month}"
        )

    ytd_profit = (
        extract_ytd_from_title(
            title,
            month,
        )
    )

    if (
        month == 1
        and ytd_profit is None
    ):

        ytd_profit = (
            monthly_profit
        )

    if ytd_profit is None:

        raise RuntimeError(
            "KGI YTD profit "
            "not found in title: "
            f"{data_month}"
        )

    eps = (
        extract_eps_from_title(
            title
        )
    )

    if eps is None:

        raise RuntimeError(
            "KGI EPS "
            "not found in title: "
            f"{data_month}"
        )

    return {
        "stock_id": STOCK_ID,
        "stock_name": STOCK_NAME,
        "data_month": (
            data_month
        ),
        "monthly_net_profit": round(
            monthly_profit * 100,
            2,
        ),
        "ytd_net_profit": round(
            ytd_profit * 100,
            2,
        ),
        "ytd_eps": eps,
        "source_date": (
            article[
                "source_date"
            ]
        ),
        "source_url": (
            article[
                "source_url"
            ]
        ),
    }


def validate_rows(
    rows,
):

    expected = {
        f"{TARGET_YEAR}-{month:02d}"
        for month in range(
            1,
            13,
        )
    }

    actual = {
        row[
            "data_month"
        ]
        for row in rows
    }

    missing = sorted(
        expected
        - actual
    )

    if missing:

        raise RuntimeError(
            "KGI 2025 "
            "missing months: "
            f"{', '.join(missing)}"
        )

    if len(
        rows
    ) != 12:

        raise RuntimeError(
            "KGI 2025 "
            "row count invalid: "
            f"{len(rows)}"
        )

    rows.sort(
        key=lambda x: x[
            "data_month"
        ]
    )

    tolerance = 20.0

    for index in range(
        1,
        len(rows),
    ):

        previous = (
            rows[
                index - 1
            ]
        )

        current = (
            rows[
                index
            ]
        )

        expected_ytd = round(
            previous[
                "ytd_net_profit"
            ]
            + current[
                "monthly_net_profit"
            ],
            2,
        )

        actual_ytd = round(
            current[
                "ytd_net_profit"
            ],
            2,
        )

        difference = abs(
            expected_ytd
            - actual_ytd
        )

        if (
            difference
            > tolerance
        ):

            raise RuntimeError(
                "KGI YTD "
                "reconciliation failed: "
                f"{current['data_month']} "
                f"Expected="
                f"{expected_ytd} "
                f"Actual="
                f"{actual_ytd} "
                f"Diff="
                f"{difference}"
            )


def collect_rows():

    articles = (
        find_candidate_articles()
    )

    rows = []

    for article in articles:

        row = parse_article(
            article
        )

        print(
            "[RESULT] "
            f"{row['data_month']} "
            f"Monthly="
            f"{row['monthly_net_profit']} "
            f"YTD="
            f"{row['ytd_net_profit']} "
            f"EPS="
            f"{row['ytd_eps']} "
            f"SourceDate="
            f"{row['source_date']}"
        )

        rows.append(
            row
        )

    rows.sort(
        key=lambda x: x[
            "data_month"
        ]
    )

    validate_rows(
        rows
    )

    print()
    print(
        "[PASS] "
        "2025 coverage: "
        "12/12"
    )

    return rows


def sync_rows(
    conn,
    rows,
):

    sql = """
    INSERT INTO financial_holding_monthly (
        stock_id,
        data_month,
        monthly_net_profit,
        ytd_net_profit,
        ytd_eps,
        previous_year_ytd_net_profit,
        ytd_profit_yoy_pct,
        source_date,
        source_url,
        data_status,
        created_at,
        updated_at
    )
    VALUES (
        ?,
        ?,
        ?,
        ?,
        ?,
        NULL,
        NULL,
        ?,
        ?,
        'STORED',
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    )
    ON CONFLICT(stock_id, data_month)
    DO UPDATE SET
        monthly_net_profit =
            excluded.monthly_net_profit,
        ytd_net_profit =
            excluded.ytd_net_profit,
        ytd_eps =
            excluded.ytd_eps,
        source_date =
            excluded.source_date,
        source_url =
            excluded.source_url,
        data_status =
            excluded.data_status,
        updated_at =
            CURRENT_TIMESTAMP
    """

    for row in rows:

        conn.execute(
            sql,
            (
                row[
                    "stock_id"
                ],
                row[
                    "data_month"
                ],
                row[
                    "monthly_net_profit"
                ],
                row[
                    "ytd_net_profit"
                ],
                row[
                    "ytd_eps"
                ],
                row[
                    "source_date"
                ],
                row[
                    "source_url"
                ],
            ),
        )

    return len(
        rows
    )


def update_all_yoy(
    conn,
):

    rows = (
        conn.execute(
            """
            SELECT
                stock_id,
                data_month,
                ytd_net_profit
            FROM financial_holding_monthly
            WHERE stock_id = ?
              AND ytd_net_profit IS NOT NULL
            ORDER BY data_month
            """,
            (
                STOCK_ID,
            ),
        ).fetchall()
    )

    lookup = {
        row[1]: row[2]
        for row in rows
    }

    update_count = 0

    for row in rows:

        stock_id = (
            row[0]
        )

        data_month = (
            row[1]
        )

        current_ytd = (
            row[2]
        )

        year, month = (
            data_month.split(
                "-"
            )
        )

        previous_month = (
            f"{int(year) - 1}-"
            f"{month}"
        )

        previous_ytd = (
            lookup.get(
                previous_month
            )
        )

        if previous_ytd is None:

            continue

        if previous_ytd == 0:

            yoy_pct = None

        else:

            yoy_pct = round(
                (
                    current_ytd
                    / previous_ytd
                    - 1
                )
                * 100,
                2,
            )

        conn.execute(
            """
            UPDATE financial_holding_monthly
            SET
                previous_year_ytd_net_profit = ?,
                ytd_profit_yoy_pct = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE stock_id = ?
              AND data_month = ?
            """,
            (
                previous_ytd,
                yoy_pct,
                stock_id,
                data_month,
            ),
        )

        update_count += 1

    return update_count


def verify(
    conn,
):

    return (
        conn.execute(
            """
            SELECT
                data_month,
                monthly_net_profit,
                ytd_net_profit,
                ytd_eps,
                previous_year_ytd_net_profit,
                ytd_profit_yoy_pct,
                source_date
            FROM financial_holding_monthly
            WHERE stock_id = ?
              AND data_month >= '2025-01'
            ORDER BY data_month
            """,
            (
                STOCK_ID,
            ),
        ).fetchall()
    )


def main():

    configure_console()

    print(
        "=" * 70
    )

    print(
        "StockWaveScanner V3 - "
        "KGI Historical Backfill"
    )

    print(
        "=" * 70
    )

    print()
    print(
        "Target Year: 2025"
    )

    print(
        "Source: KGI official "
        "news center"
    )

    print(
        "Database: Turso DEV only"
    )

    try:

        rows = (
            collect_rows()
        )

    except Exception as exc:

        print()
        print(
            "ERROR"
        )

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return 1

    print()
    print(
        "=" * 70
    )

    print(
        "[PASS] Historical source "
        "validation completed"
    )

    print(
        "[PASS] Total collected rows: "
        f"{len(rows)}"
    )

    print(
        "=" * 70
    )

    conn = None

    try:

        print()
        print(
            "[CONNECT] Turso DEV"
        )

        conn = (
            get_connection()
        )

        sync_count = (
            sync_rows(
                conn,
                rows,
            )
        )

        yoy_count = (
            update_all_yoy(
                conn
            )
        )

        conn.commit()

        print()
        print(
            "[PASS] KGI "
            "backfill rows: "
            f"{sync_count}"
        )

        print(
            "[PASS] KGI "
            "YoY rows: "
            f"{yoy_count}"
        )

        print()
        print(
            "=" * 70
        )

        print(
            "TURSO DEV VERIFY"
        )

        print(
            "=" * 70
        )

        for row in verify(
            conn
        ):

            prev_text = (
                row[4]
                if row[4]
                is not None
                else "N/A"
            )

            yoy_text = (
                f"{row[5]:.2f}%"
                if row[5]
                is not None
                else "N/A"
            )

            source_date_text = (
                row[6]
                if row[6]
                is not None
                else "N/A"
            )

            print(
                f"{row[0]} "
                f"Monthly="
                f"{row[1]} "
                f"YTD="
                f"{row[2]} "
                f"EPS="
                f"{row[3]} "
                f"PrevYTD="
                f"{prev_text} "
                f"YoY="
                f"{yoy_text} "
                f"SourceDate="
                f"{source_date_text}"
            )

        print()
        print(
            "=" * 70
        )

        print(
            "KGI HISTORICAL "
            "BACKFILL OK"
        )

        print(
            "=" * 70
        )

        return 0

    except Exception as exc:

        if conn is not None:

            conn.rollback()

        print()
        print(
            "ERROR"
        )

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return 1

    finally:

        if conn is not None:

            conn.close()


if __name__ == "__main__":

    sys.exit(
        main()
    )