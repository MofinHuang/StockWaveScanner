from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime

import libsql
import requests
import urllib3
from bs4 import BeautifulSoup
from dotenv import load_dotenv


urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


STOCK_ID = "2881"
STOCK_NAME = "富邦金"

TARGET_YEAR = 2025

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

REQUEST_RETRIES = 5
REQUEST_DELAY_SECONDS = 1.0


NEWS_URLS = [
    (
        "2025-01",
        "https://www.fubon.com/"
        "financialholdings/news/"
        "news_1250210_177261.htm",
    ),
    (
        "2025-02",
        "https://www.fubon.com/"
        "financialholdings/news/"
        "news_1250310_597128.htm",
    ),
    (
        "2025-03",
        "https://www.fubon.com/"
        "financialholdings/news/"
        "news_1250410_275866.htm",
    ),
    (
        "2025-04",
        "https://www.fubon.com/"
        "financialholdings/news/"
        "news_1250512_038109.htm",
    ),
    (
        "2025-05",
        "https://www.fubon.com/"
        "financialholdings/news/"
        "news_1250610_543998.htm",
    ),
    (
        "2025-06",
        "https://www.fubon.com/"
        "financialholdings/news/"
        "news_1250711_199937.htm",
    ),
    (
        "2025-07",
        "https://www.fubon.com/"
        "financialholdings/news/"
        "news_1250811_902045.htm",
    ),
    (
        "2025-08",
        "https://www.fubon.com/"
        "financialholdings/news/"
        "news_1250910_493137.htm",
    ),
    (
        "2025-09",
        "https://www.fubon.com/"
        "financialholdings/news/"
        "news_1251013_343392.htm",
    ),
    (
        "2025-10",
        "https://www.fubon.com/"
        "financialholdings/news/"
        "news_1251110_763926.htm",
    ),
    (
        "2025-11",
        "https://www.fubon.com/"
        "financialholdings/news/"
        "news_1251211_414995.htm",
    ),
    (
        "2025-12",
        "https://www.fubon.com/"
        "financialholdings/news/"
        "news_1260112_205991.htm",
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
                verify=False,
            )

            response.raise_for_status()

            response.encoding = (
                "utf-8"
            )

            if (
                not response.text.strip()
            ):

                raise RuntimeError(
                    "Fubon returned "
                    "empty HTML"
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
                "[WARN] Fubon HTTP error: "
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
                "[WARN] Fubon connection error: "
                f"{type(exc).__name__} "
                f"attempt="
                f"{attempt}/"
                f"{REQUEST_RETRIES}"
            )

        if (
            attempt
            >= REQUEST_RETRIES
        ):

            break

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
        "Fubon request failed"
    )


def extract_text(
    html,
):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    return normalize_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )


def extract_source_date(
    text,
):

    match = re.search(
        r"(?P<year>20\d{2})"
        r"[./年]"
        r"(?P<month>\d{1,2})"
        r"[./月]"
        r"(?P<day>\d{1,2})",
        text,
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


def parse_profit_value(
    match,
):

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
        "淨損",
        "虧損",
    }:

        value = -value

    return round(
        value * 100,
        2,
    )


def parse_monthly_profit(
    text,
    month,
):

    #
    # 12 月文章通常同時包含：
    #
    # 2025年全年稅後淨利 1,208.5 億
    # 單12月自結合併稅後淨利 1.4 億
    #
    # 因此 12 月一定先抓「單12月」，
    # 避免把全年值當成單月值。
    #
    if month == 12:

        december_patterns = [
            (
                r"單\s*12月"
                r".{0,80}?"
                r"自結合併"
                r".{0,30}?"
                r"稅後"
                r"(?P<type>"
                r"淨利|淨損|獲利|虧損"
                r")"
                r"\s*"
                r"(?P<value>[\d,.]+)"
                r"\s*億元"
            ),
            (
                r"單\s*12月"
                r".{0,80}?"
                r"稅後"
                r"(?P<type>"
                r"淨利|淨損|獲利|虧損"
                r")"
                r"\s*"
                r"(?P<value>[\d,.]+)"
                r"\s*億元"
            ),
            (
                r"2025年12月"
                r".{0,80}?"
                r"單月"
                r".{0,50}?"
                r"稅後"
                r"(?P<type>"
                r"淨利|淨損|獲利|虧損"
                r")"
                r"\s*"
                r"(?P<value>[\d,.]+)"
                r"\s*億元"
            ),
        ]

        for pattern in (
            december_patterns
        ):

            match = re.search(
                pattern,
                text,
            )

            if match:

                return (
                    parse_profit_value(
                        match
                    )
                )

        raise RuntimeError(
            "Monthly profit not found: "
            "2025-12"
        )

    #
    # 1～11 月一般格式。
    #
    patterns = [
        (
            rf"2025年{month}月"
            r".{0,80}?"
            r"自結合併"
            r".{0,50}?"
            r"稅後"
            r"(?P<type>"
            r"淨利|淨損|獲利|虧損"
            r")"
            r"\s*"
            r"(?P<value>[\d,.]+)"
            r"\s*億元"
        ),
        (
            rf"2025年{month}月份"
            r".{0,80}?"
            r"稅後"
            r"(?P<type>"
            r"淨利|淨損|獲利|虧損"
            r")"
            r"\s*"
            r"(?P<value>[\d,.]+)"
            r"\s*億元"
        ),
        (
            rf"單\s*{month}月"
            r".{0,50}?"
            r"稅後"
            r"(?P<type>"
            r"淨利|淨損|獲利|虧損"
            r")"
            r"\s*"
            r"(?P<value>[\d,.]+)"
            r"\s*億元"
        ),
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
        )

        if match:

            return (
                parse_profit_value(
                    match
                )
            )

    raise RuntimeError(
        "Monthly profit not found: "
        f"2025-{month:02d}"
    )


def parse_ytd_profit(
    text,
    month,
    monthly_profit,
):

    if month == 1:

        return monthly_profit

    #
    # 12 月優先抓全年。
    #
    if month == 12:

        patterns = [
            (
                r"2025年全年"
                r".{0,80}?"
                r"稅後"
                r"(?:淨利|獲利)"
                r"\s*"
                r"(?P<value>[\d,.]+)"
                r"\s*億元"
            ),
            (
                r"2025年"
                r".{0,80}?"
                r"全年"
                r".{0,80}?"
                r"稅後"
                r"(?:淨利|獲利)"
                r"\s*"
                r"(?P<value>[\d,.]+)"
                r"\s*億元"
            ),
            (
                r"累計全年"
                r".{0,80}?"
                r"稅後"
                r"(?:淨利|獲利)"
                r"\s*"
                r"(?P<value>[\d,.]+)"
                r"\s*億元"
            ),
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
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
            "YTD profit not found: "
            "2025-12"
        )

    patterns = [
        (
            rf"累計今年前{month}月"
            r".{0,100}?"
            r"稅後"
            r"(?:淨利|獲利)"
            r"\s*"
            r"(?P<value>[\d,.]+)"
            r"\s*億元"
        ),
        (
            rf"累計前{month}月"
            r".{0,100}?"
            r"稅後"
            r"(?:淨利|獲利)"
            r"\s*"
            r"(?P<value>[\d,.]+)"
            r"\s*億元"
        ),
        (
            rf"前{month}月"
            r".{0,100}?"
            r"稅後"
            r"(?:淨利|獲利)"
            r"\s*"
            r"(?P<value>[\d,.]+)"
            r"\s*億元"
        ),
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
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
        "YTD profit not found: "
        f"2025-{month:02d}"
    )


def parse_eps(
    text,
    month,
):

    patterns = [
        (
            r"每股稅後盈餘"
            r"\s*"
            r"\(EPS\)"
            r".{0,20}?"
            r"(?:為)?"
            r"\s*"
            r"(?P<value>[\d,.]+)"
            r"\s*元"
        ),
        (
            r"每股稅後盈餘"
            r".{0,20}?"
            r"(?P<value>[\d,.]+)"
            r"\s*元"
        ),
        (
            r"每股盈餘"
            r"\s*"
            r"\(EPS\)"
            r".{0,20}?"
            r"(?:為)?"
            r"\s*"
            r"(?P<value>[\d,.]+)"
            r"\s*元"
        ),
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
        )

        if match:

            return parse_number(
                match.group(
                    "value"
                )
            )

    raise RuntimeError(
        "EPS not found: "
        f"2025-{month:02d}"
    )


def parse_article(
    expected_data_month,
    url,
):

    html = fetch_html(
        url
    )

    text = extract_text(
        html
    )

    year_text, month_text = (
        expected_data_month.split(
            "-"
        )
    )

    year = int(
        year_text
    )

    month = int(
        month_text
    )

    if year != TARGET_YEAR:

        raise RuntimeError(
            "Unexpected target year: "
            f"{expected_data_month}"
        )

    month_pattern = re.compile(
        rf"{year}年"
        rf"{month}月"
    )

    month_pattern_2 = re.compile(
        rf"{year}年"
        rf"{month}月份"
    )

    if (
        not month_pattern.search(
            text
        )
        and not month_pattern_2.search(
            text
        )
    ):

        raise RuntimeError(
            "Article month validation "
            "failed: "
            f"{expected_data_month}"
        )

    monthly_profit = (
        parse_monthly_profit(
            text,
            month,
        )
    )

    ytd_profit = (
        parse_ytd_profit(
            text,
            month,
            monthly_profit,
        )
    )

    eps = parse_eps(
        text,
        month,
    )

    source_date = (
        extract_source_date(
            text
        )
    )

    return {
        "stock_id": STOCK_ID,
        "stock_name": STOCK_NAME,
        "data_month": (
            expected_data_month
        ),
        "monthly_net_profit": (
            monthly_profit
        ),
        "ytd_net_profit": (
            ytd_profit
        ),
        "ytd_eps": eps,
        "source_date": (
            source_date
        ),
        "source_url": url,
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

    unexpected = sorted(
        actual
        - expected
    )

    if missing:

        raise RuntimeError(
            "Fubon 2025 "
            "missing months: "
            f"{', '.join(missing)}"
        )

    if unexpected:

        raise RuntimeError(
            "Fubon 2025 "
            "unexpected months: "
            f"{', '.join(unexpected)}"
        )

    if (
        len(rows)
        != 12
    ):

        raise RuntimeError(
            "Fubon 2025 "
            "row count invalid: "
            f"{len(rows)}"
        )

    rows = sorted(
        rows,
        key=lambda x: x[
            "data_month"
        ],
    )

    #
    # 富邦官網以億元、小數一位呈現，
    # 因此換成百萬元後允許 20 百萬元誤差。
    #
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
                "Fubon YTD "
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

    rows = []

    for index, item in enumerate(
        NEWS_URLS,
        start=1,
    ):

        data_month = item[0]
        url = item[1]

        if index > 1:

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

        print(
            "[FETCH] "
            f"{data_month}"
        )

        row = parse_article(
            data_month,
            url,
        )

        print(
            "[PARSE] "
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
            FROM
                financial_holding_monthly
            WHERE stock_id = ?
              AND ytd_net_profit
                  IS NOT NULL
            ORDER BY
                data_month
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

        stock_id = row[0]
        data_month = row[1]
        current_ytd = row[2]

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

        if (
            previous_ytd
            is None
        ):

            continue

        if (
            previous_ytd
            == 0
        ):

            yoy_pct = None

        else:

            yoy_pct = round(
                (
                    (
                        current_ytd
                        / previous_ytd
                    )
                    - 1
                )
                * 100,
                2,
            )

        conn.execute(
            """
            UPDATE
                financial_holding_monthly
            SET
                previous_year_ytd_net_profit = ?,
                ytd_profit_yoy_pct = ?,
                updated_at =
                    CURRENT_TIMESTAMP
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
            FROM
                financial_holding_monthly
            WHERE stock_id = ?
              AND data_month
                  >= '2025-01'
            ORDER BY
                data_month
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
        "Fubon Historical Backfill"
    )

    print(
        "=" * 70
    )

    print()
    print(
        "Target Year: 2025"
    )

    print(
        "Database: Turso DEV only"
    )

    #
    # 先完整抓取與驗證。
    # 驗證成功前不寫 Turso。
    #
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
            "[PASS] Fubon "
            "backfill rows: "
            f"{sync_count}"
        )

        print(
            "[PASS] Fubon "
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
            "FUBON HISTORICAL "
            "BACKFILL OK"
        )

        print(
            "=" * 70
        )

        return 0

    except Exception as exc:

        if (
            conn
            is not None
        ):

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

        if (
            conn
            is not None
        ):

            conn.close()


if __name__ == "__main__":

    sys.exit(
        main()
    )