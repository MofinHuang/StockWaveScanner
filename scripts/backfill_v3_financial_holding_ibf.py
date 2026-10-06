from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import libsql
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


SOURCE_URL = (
    "https://www.ibf.com.tw/"
    "performance_reports"
)

STOCK_ID = "2889"
STOCK_NAME = "國票金"

TARGET_YEAR = 2025
TARGET_ROC_YEAR = 114

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

REQUEST_RETRIES = 5


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


def get_headers():

    return {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/154 Safari/537.36"
        ),
    }


def normalize_text(
    text,
):

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def roc_to_ad_year(
    roc_year,
):

    return (
        int(roc_year)
        + 1911
    )


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


def fetch_html():

    last_exception = None

    for attempt in range(
        1,
        REQUEST_RETRIES + 1,
    ):

        try:

            print(
                "[FETCH] "
                f"{SOURCE_URL} "
                f"attempt="
                f"{attempt}/"
                f"{REQUEST_RETRIES}"
            )

            response = requests.get(
                SOURCE_URL,
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
                    "IBF source returned "
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
                "[WARN] IBF HTTP error: "
                f"{status_code}"
            )

        except (
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError,
        ) as exc:

            last_exception = exc

            print(
                "[WARN] IBF connection error: "
                f"{type(exc).__name__}"
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
        "IBF request failed"
    )


def parse_money_to_million(
    billion_text,
    ten_thousand_text,
):

    billion = 0.0
    ten_thousand = 0.0

    if billion_text:

        billion = float(
            billion_text.replace(
                ",",
                "",
            )
        )

    if ten_thousand_text:

        ten_thousand = float(
            ten_thousand_text.replace(
                ",",
                "",
            )
        )

    #
    # 1 億 = 100 百萬元
    # 1 萬 = 0.01 百萬元
    #
    value = (
        billion * 100
        + ten_thousand * 0.01
    )

    return round(
        value,
        3,
    )


def find_monthly_profit(
    body,
):

    pattern = re.compile(
        r"自結"
        r"\s*稅後"
        r"(?P<type>盈餘|虧損)"
        r"\s*"
        r"(?P<negative>-)?"
        r"(?:(?P<billion>[\d,]+)"
        r"\s*億)?"
        r"(?P<ten_thousand>[\d,]+)?"
        r"\s*萬元"
    )

    match = pattern.search(
        body
    )

    if not match:

        return None

    value = (
        parse_money_to_million(
            match.group(
                "billion"
            ),
            match.group(
                "ten_thousand"
            ),
        )
    )

    if (
        match.group(
            "negative"
        )
        or match.group(
            "type"
        ) == "虧損"
    ):

        value = -abs(
            value
        )

    return value


def find_ytd_profit(
    body,
    month,
    monthly_profit,
):

    if month == 1:

        return monthly_profit

    patterns = [
        re.compile(
            r"累計"
            r"\s*1"
            r"\s*至"
            r"\s*"
            rf"{month}"
            r"\s*月份"
            r"\s*稅後"
            r"(?P<type>盈餘|虧損)"
            r"\s*"
            r"(?P<negative>-)?"
            r"(?:(?P<billion>[\d,]+)"
            r"\s*億)?"
            r"(?P<ten_thousand>[\d,]+)?"
            r"\s*萬元"
        ),
        re.compile(
            r"累計"
            r"\s*1"
            r"\s*~"
            r"\s*"
            rf"{month}"
            r"\s*月份"
            r"\s*稅後"
            r"(?P<type>盈餘|虧損)"
            r"\s*"
            r"(?P<negative>-)?"
            r"(?:(?P<billion>[\d,]+)"
            r"\s*億)?"
            r"(?P<ten_thousand>[\d,]+)?"
            r"\s*萬元"
        ),
    ]

    for pattern in patterns:

        match = pattern.search(
            body
        )

        if not match:

            continue

        value = (
            parse_money_to_million(
                match.group(
                    "billion"
                ),
                match.group(
                    "ten_thousand"
                ),
            )
        )

        if (
            match.group(
                "negative"
            )
            or match.group(
                "type"
            ) == "虧損"
        ):

            value = -abs(
                value
            )

        return value

    return None


def find_ytd_eps(
    body,
):

    patterns = [
        re.compile(
            r"每股"
            r"\s*稅後"
            r"(?:盈餘|盈虧)"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*元"
        ),
        re.compile(
            r"每股"
            r"\s*(?:盈餘|盈虧)"
            r"\s*"
            r"(?P<value>-?[\d,.]+)"
            r"\s*元"
        ),
    ]

    for pattern in patterns:

        match = pattern.search(
            body
        )

        if match:

            return float(
                match.group(
                    "value"
                ).replace(
                    ",",
                    "",
                )
            )

    return None


def extract_company_body(
    body,
):

    #
    # 一定只取「本公司」段落，
    # 避免誤抓：
    #
    # 國際票券
    # 國票證券
    # 國票創投
    #
    patterns = [
        re.compile(
            r"本公司"
            r".*?"
            r"(?=二、主要子公司)",
        ),
        re.compile(
            r"本公司"
            r".*?"
            r"(?=主要子公司)",
        ),
        re.compile(
            r"本公司"
            r".*?"
            r"(?=國際票券)",
        ),
    ]

    for pattern in patterns:

        match = pattern.search(
            body
        )

        if match:

            return match.group(
                0
            )

    #
    # 找不到明確結束標記時，
    # 最多只讀前 1500 字。
    #
    company_start = re.search(
        r"本公司",
        body,
    )

    if company_start:

        return body[
            company_start.start():
            company_start.start()
            + 1500
        ]

    return body[
        :1500
    ]


def parse_rows():

    html = fetch_html()

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    text = normalize_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    heading_pattern = re.compile(
        r"(?P<roc_year>\d{3})"
        r"\s*年"
        r"\s*"
        r"(?P<month>\d{1,2})"
        r"\s*月份"
        r"\s*業績報告"
    )

    matches = list(
        heading_pattern.finditer(
            text
        )
    )

    if not matches:

        raise RuntimeError(
            "IBF performance report "
            "headings not found"
        )

    print()
    print(
        "[INFO] Total headings: "
        f"{len(matches)}"
    )

    rows = []

    for index, match in enumerate(
        matches
    ):

        roc_year = int(
            match.group(
                "roc_year"
            )
        )

        month = int(
            match.group(
                "month"
            )
        )

        if (
            roc_year
            != TARGET_ROC_YEAR
        ):

            continue

        if not (
            1 <= month <= 12
        ):

            continue

        year = (
            roc_to_ad_year(
                roc_year
            )
        )

        start = (
            match.end()
        )

        if (
            index + 1
            < len(matches)
        ):

            end = (
                matches[
                    index + 1
                ].start()
            )

        else:

            end = len(
                text
            )

        body = text[
            start:end
        ]

        company_body = (
            extract_company_body(
                body
            )
        )

        data_month = (
            f"{year}-"
            f"{month:02d}"
        )

        print()
        print(
            "[PARSE] "
            f"{data_month}"
        )

        monthly_profit = (
            find_monthly_profit(
                company_body
            )
        )

        if monthly_profit is None:

            print()
            print(
                "[DEBUG] "
                f"{data_month}"
            )

            print(
                company_body[
                    :2000
                ]
            )

            raise RuntimeError(
                "IBF monthly profit "
                "not found: "
                f"{data_month}"
            )

        ytd_profit = (
            find_ytd_profit(
                company_body,
                month,
                monthly_profit,
            )
        )

        if ytd_profit is None:

            print()
            print(
                "[DEBUG] "
                f"{data_month}"
            )

            print(
                company_body[
                    :2000
                ]
            )

            raise RuntimeError(
                "IBF YTD profit "
                "not found: "
                f"{data_month}"
            )

        ytd_eps = (
            find_ytd_eps(
                company_body
            )
        )

        if ytd_eps is None:

            print()
            print(
                "[DEBUG] "
                f"{data_month}"
            )

            print(
                company_body[
                    :2000
                ]
            )

            raise RuntimeError(
                "IBF YTD EPS "
                "not found: "
                f"{data_month}"
            )

        row = {
            "stock_id": STOCK_ID,
            "stock_name": STOCK_NAME,
            "data_month": (
                data_month
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
            "source_date": None,
            "source_url": (
                SOURCE_URL
            ),
        }

        print(
            "[RESULT] "
            f"{data_month} "
            f"Monthly="
            f"{monthly_profit} "
            f"YTD="
            f"{ytd_profit} "
            f"EPS="
            f"{ytd_eps}"
        )

        rows.append(
            row
        )

    unique_rows = {}

    for row in rows:

        unique_rows[
            row[
                "data_month"
            ]
        ] = row

    rows = list(
        unique_rows.values()
    )

    rows.sort(
        key=lambda x: x[
            "data_month"
        ]
    )

    return rows


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
            "IBF 2025 missing months: "
            f"{', '.join(missing)}"
        )

    if unexpected:

        raise RuntimeError(
            "IBF 2025 unexpected months: "
            f"{', '.join(unexpected)}"
        )

    if len(
        rows
    ) != 12:

        raise RuntimeError(
            "IBF 2025 "
            "row count invalid: "
            f"{len(rows)}"
        )

    #
    # 國票官方資料精確到萬元，
    # 換算百萬元後理論上可以
    # 非常精準地對上 YTD。
    #
    tolerance = 0.1

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

        if difference > tolerance:

            raise RuntimeError(
                "IBF YTD "
                "reconciliation failed: "
                f"{current['data_month']} "
                f"Expected="
                f"{expected_ytd} "
                f"Actual="
                f"{actual_ytd} "
                f"Diff="
                f"{difference}"
            )

    print()
    print(
        "[PASS] "
        "2025 coverage: "
        "12/12"
    )


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
        NULL,
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
              AND ytd_net_profit
                  IS NOT NULL
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
        "IBF Historical Backfill"
    )

    print(
        "=" * 70
    )

    print()
    print(
        "Target Year: 2025"
    )

    print(
        "Source: IBF official "
        "performance reports"
    )

    print(
        "Database: Turso DEV only"
    )

    #
    # 先解析與驗證。
    # 12 個月全部正確以前，
    # 不寫 Turso。
    #
    try:

        rows = (
            parse_rows()
        )

        print()
        print(
            "[INFO] Parsed rows: "
            f"{len(rows)}"
        )

        validate_rows(
            rows
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
            "[PASS] IBF "
            "backfill rows: "
            f"{sync_count}"
        )

        print(
            "[PASS] IBF "
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
            "IBF HISTORICAL "
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