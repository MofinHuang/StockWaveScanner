from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import libsql
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


STOCK_ID = "2880"
STOCK_NAME = "華南金"

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

MOPS_URL = (
    "https://mopsov.twse.com.tw/"
    "mops/web/ajax_t05st01"
)

#
# 歷史補資料年份
#
# 113 = 2024
# 114 = 2025
#
# 2026 維持由原本既有 Parser / Sync 負責。
#
TARGET_ROC_YEARS = [
    "113",
    "114",
]

EXPECTED_MONTHS = 12

REQUEST_RETRIES = 5
REQUEST_DELAY_SECONDS = 1.5


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
        "Content-Type": (
            "application/"
            "x-www-form-urlencoded"
        ),
        "Referer": (
            "https://mopsov.twse.com.tw/"
            "mops/web/t05sr01_1"
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


def request_with_retry(
    method,
    url,
    **kwargs,
):

    last_exception = None

    for attempt in range(
        1,
        REQUEST_RETRIES + 1,
    ):

        try:

            response = (
                requests.request(
                    method,
                    url,
                    **kwargs,
                )
            )

            response.raise_for_status()

            return response

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
                "[WARN] MOPS HTTP error: "
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
                "[WARN] MOPS connection error: "
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
        "MOPS request failed"
    )


def fetch_mops_list(
    query_roc_year,
):

    query_ad_year = (
        roc_to_ad_year(
            query_roc_year
        )
    )

    print(
        "[FETCH] "
        f"MOPS announcement year "
        f"{query_ad_year}"
    )

    payload = {
        "firstin": "1",
        "TYPEK": "sii",
        "co_id": STOCK_ID,
        "year": query_roc_year,
        "month": "",
        "b_date": "",
        "e_date": "",
    }

    response = (
        request_with_retry(
            "POST",
            MOPS_URL,
            headers=get_headers(),
            data=payload,
            timeout=(
                10,
                60,
            ),
        )
    )

    response.encoding = "utf-8"

    if (
        not response.text.strip()
    ):

        raise RuntimeError(
            "MOPS returned "
            "empty HTML: "
            f"{query_ad_year}"
        )

    return response.text


def extract_detail_params(
    html,
    target_roc_year,
    query_roc_year,
):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    results = []

    for row in soup.find_all(
        "tr"
    ):

        row_text = (
            normalize_text(
                row.get_text(
                    " ",
                    strip=True,
                )
            )
        )

        if not row_text:

            continue

        if (
            STOCK_ID
            not in row_text
        ):

            continue

        if (
            "自結盈餘"
            not in row_text
        ):

            continue

        if (
            "代子公司"
            in row_text
        ):

            continue

        #
        # MOPS 查詢年度是「公告年度」，
        # 但真正資料年度可能是上一年。
        #
        # 例如：
        #
        # 2024-12 獲利
        # 於 2025-01 公告
        #
        # 所以查 2025 公告時，
        # 仍只保留主旨中的「113年12月份」。
        #
        if (
            f"{target_roc_year}年"
            not in row_text
        ):

            continue

        row_html = (
            str(row).replace(
                "&amp;",
                "&",
            )
        )

        spoke_date = None
        spoke_time = None
        seq_no = None

        date_patterns = [
            (
                r"spoke_date\s*=\s*"
                r"['\"]?(\d{8})"
            ),
            (
                r"spoke_date\.value\s*=\s*"
                r"['\"](\d{8})"
            ),
            (
                r"spoke_date['\"]?\s*"
                r"[:,=]\s*['\"]?"
                r"(\d{8})"
            ),
        ]

        for pattern in (
            date_patterns
        ):

            match = re.search(
                pattern,
                row_html,
                re.I,
            )

            if match:

                spoke_date = (
                    match.group(1)
                )

                break

        time_patterns = [
            (
                r"spoke_time\s*=\s*"
                r"['\"]?(\d{6})"
            ),
            (
                r"spoke_time\.value\s*=\s*"
                r"['\"](\d{6})"
            ),
            (
                r"spoke_time['\"]?\s*"
                r"[:,=]\s*['\"]?"
                r"(\d{6})"
            ),
        ]

        for pattern in (
            time_patterns
        ):

            match = re.search(
                pattern,
                row_html,
                re.I,
            )

            if match:

                spoke_time = (
                    match.group(1)
                )

                break

        seq_patterns = [
            (
                r"seq_no\s*=\s*"
                r"['\"]?(\d+)"
            ),
            (
                r"seq_no\.value\s*=\s*"
                r"['\"](\d+)"
            ),
            (
                r"seq_no['\"]?\s*"
                r"[:,=]\s*['\"]?"
                r"(\d+)"
            ),
        ]

        for pattern in (
            seq_patterns
        ):

            match = re.search(
                pattern,
                row_html,
                re.I,
            )

            if match:

                seq_no = (
                    match.group(1)
                )

                break

        #
        # 如果 HTML attribute
        # 沒有公告日期 / 時間，
        # 從畫面文字取得。
        #
        roc_match = re.search(
            r"(?P<year>\d{3})/"
            r"(?P<month>\d{2})/"
            r"(?P<day>\d{2})"
            r"\s+"
            r"(?P<hour>\d{2}):"
            r"(?P<minute>\d{2}):"
            r"(?P<second>\d{2})",
            row_text,
        )

        if roc_match:

            if spoke_date is None:

                ad_year = (
                    int(
                        roc_match.group(
                            "year"
                        )
                    )
                    + 1911
                )

                spoke_date = (
                    f"{ad_year}"
                    f"{roc_match.group('month')}"
                    f"{roc_match.group('day')}"
                )

            if spoke_time is None:

                spoke_time = (
                    f"{roc_match.group('hour')}"
                    f"{roc_match.group('minute')}"
                    f"{roc_match.group('second')}"
                )

        if (
            spoke_date is None
            or spoke_time is None
            or seq_no is None
        ):

            print(
                "[WARN] Skip candidate "
                "without detail params: "
                f"{row_text[:200]}"
            )

            continue

        item = {
            "spoke_date": (
                spoke_date
            ),
            "spoke_time": (
                spoke_time
            ),
            "seq_no": (
                seq_no
            ),
            "query_roc_year": (
                query_roc_year
            ),
        }

        if (
            item
            not in results
        ):

            results.append(
                item
            )

            print(
                "[FOUND] "
                f"{spoke_date} "
                f"{spoke_time} "
                f"seq={seq_no}"
            )

    return results


def build_source_url(
    params,
):

    query = {
        "firstin": "1",
        "TYPEK": "all",
        "step": "2",
        "co_id": STOCK_ID,
        "year": params[
            "query_roc_year"
        ],
        "month": "all",
        "spoke_date": params[
            "spoke_date"
        ],
        "spoke_time": params[
            "spoke_time"
        ],
        "seq_no": params[
            "seq_no"
        ],
        "off": "1",
    }

    return (
        MOPS_URL
        + "?"
        + urlencode(
            query
        )
    )


def source_date_from_params(
    params,
):

    value = (
        params[
            "spoke_date"
        ]
    )

    if (
        not value
        or len(value) != 8
    ):

        return None

    return (
        f"{value[0:4]}-"
        f"{value[4:6]}-"
        f"{value[6:8]}"
    )


def fetch_detail(
    params,
):

    query = {
        "firstin": "1",
        "TYPEK": "all",
        "step": "2",
        "co_id": STOCK_ID,
        "year": params[
            "query_roc_year"
        ],
        "month": "all",
        "spoke_date": params[
            "spoke_date"
        ],
        "spoke_time": params[
            "spoke_time"
        ],
        "seq_no": params[
            "seq_no"
        ],
        "off": "1",
    }

    response = (
        request_with_retry(
            "GET",
            MOPS_URL,
            headers=get_headers(),
            params=query,
            timeout=(
                10,
                60,
            ),
        )
    )

    response.encoding = (
        "utf-8"
    )

    if (
        not response.text.strip()
    ):

        raise RuntimeError(
            "MOPS detail returned "
            "empty HTML: "
            f"{params['spoke_date']}"
        )

    return response.text


def parse_detail(
    html,
    target_roc_year,
    source_url,
    source_date,
):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    text = (
        normalize_text(
            soup.get_text(
                " ",
                strip=True,
            )
        )
    )

    if (
        "華南金融控股"
        not in text
        and "華南金控"
        not in text
    ):

        return None

    if (
        "自結盈餘"
        not in text
    ):

        return None

    month_match = re.search(
        rf"{re.escape(target_roc_year)}"
        r"\s*年"
        r"\s*"
        r"(?P<month>\d{1,2})"
        r"\s*月份"
        r"\s*自結盈餘",
        text,
    )

    if not month_match:

        return None

    month = int(
        month_match.group(
            "month"
        )
    )

    if not (
        1
        <= month
        <= 12
    ):

        raise RuntimeError(
            f"Invalid month: "
            f"{month}"
        )

    ad_year = (
        roc_to_ad_year(
            target_roc_year
        )
    )

    data_month = (
        f"{ad_year}-"
        f"{month:02d}"
    )

    #
    # 華南金控 MOPS 資料列：
    #
    # 自結合併稅前淨利
    # 自結合併稅後淨利
    # 累計合併稅前淨利
    # 累計合併稅後淨利
    # 累計合併每股稅前
    # 累計合併每股稅後
    #
    row_pattern = re.compile(
        r"華南金控"
        r"\s+"
        r"(?P<monthly_pre>-?[\d,.]+)"
        r"\s+"
        r"(?P<monthly_after>-?[\d,.]+)"
        r"\s+"
        r"(?P<ytd_pre>-?[\d,.]+)"
        r"\s+"
        r"(?P<ytd_after>-?[\d,.]+)"
        r"\s+"
        r"(?P<eps_pre>-?[\d,.]+)"
        r"\s+"
        r"(?P<eps_after>-?[\d,.]+)"
    )

    match = (
        row_pattern.search(
            text
        )
    )

    if not match:

        print()
        print(
            f"[DEBUG] "
            f"{data_month}"
        )

        print(
            text[:4000]
        )

        raise RuntimeError(
            "Hua Nan holding row "
            "not found: "
            f"{data_month}"
        )

    monthly_after = float(
        match.group(
            "monthly_after"
        ).replace(
            ",",
            "",
        )
    )

    ytd_after = float(
        match.group(
            "ytd_after"
        ).replace(
            ",",
            "",
        )
    )

    eps = float(
        match.group(
            "eps_after"
        ).replace(
            ",",
            "",
        )
    )

    #
    # MOPS 單位：億元
    # DB 單位：百萬元
    #
    monthly_net_profit = round(
        monthly_after * 100,
        3,
    )

    ytd_net_profit = round(
        ytd_after * 100,
        3,
    )

    return {
        "stock_id": STOCK_ID,
        "stock_name": STOCK_NAME,
        "data_month": (
            data_month
        ),
        "monthly_net_profit": (
            monthly_net_profit
        ),
        "ytd_net_profit": (
            ytd_net_profit
        ),
        "ytd_eps": (
            eps
        ),
        "source_date": (
            source_date
        ),
        "source_url": (
            source_url
        ),
    }


def validate_year(
    rows,
    ad_year,
):

    expected = {
        (
            f"{ad_year}-"
            f"{month:02d}"
        )
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
            f"Hua Nan "
            f"{ad_year} "
            f"missing months: "
            f"{', '.join(missing)}"
        )

    if unexpected:

        raise RuntimeError(
            f"Hua Nan "
            f"{ad_year} "
            f"unexpected months: "
            f"{', '.join(unexpected)}"
        )

    if (
        len(rows)
        != EXPECTED_MONTHS
    ):

        raise RuntimeError(
            f"Hua Nan "
            f"{ad_year} "
            "row count invalid: "
            f"{len(rows)}"
        )

    sorted_rows = sorted(
        rows,
        key=lambda x: x[
            "data_month"
        ],
    )

    #
    # 驗證：
    #
    # 上月累計 +
    # 本月單月獲利
    # ≈
    # 本月累計獲利
    #
    for index in range(
        1,
        len(sorted_rows),
    ):

        previous = (
            sorted_rows[
                index - 1
            ]
        )

        current = (
            sorted_rows[
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

        if abs(
            expected_ytd
            - actual_ytd
        ) > 1.0:

            raise RuntimeError(
                "Hua Nan YTD "
                "reconciliation failed: "
                f"{current['data_month']} "
                f"Expected="
                f"{expected_ytd} "
                f"Actual="
                f"{actual_ytd}"
            )


def collect_year(
    target_roc_year,
):

    ad_year = (
        roc_to_ad_year(
            target_roc_year
        )
    )

    #
    # 一個資料年度必須查：
    #
    # 1. 當年度公告
    # 2. 下一年度公告
    #
    # 因為 12 月份自結盈餘
    # 通常於隔年 1 月公告。
    #
    query_roc_years = [
        target_roc_year,
        str(
            int(
                target_roc_year
            )
            + 1
        ),
    ]

    params_list = []

    print()
    print(
        f"[TARGET] "
        f"{ad_year} "
        f"{STOCK_NAME}"
    )

    for query_roc_year in (
        query_roc_years
    ):

        query_ad_year = (
            roc_to_ad_year(
                query_roc_year
            )
        )

        print()
        print(
            f"[SEARCH] "
            f"{ad_year} data "
            f"in {query_ad_year} "
            f"announcements"
        )

        html = (
            fetch_mops_list(
                query_roc_year
            )
        )

        year_params = (
            extract_detail_params(
                html,
                target_roc_year,
                query_roc_year,
            )
        )

        for params in (
            year_params
        ):

            duplicate = any(
                existing[
                    "spoke_date"
                ]
                == params[
                    "spoke_date"
                ]
                and existing[
                    "spoke_time"
                ]
                == params[
                    "spoke_time"
                ]
                and existing[
                    "seq_no"
                ]
                == params[
                    "seq_no"
                ]
                for existing
                in params_list
            )

            if not duplicate:

                params_list.append(
                    params
                )

    print()
    print(
        f"[INFO] "
        f"{ad_year} "
        f"detail candidates: "
        f"{len(params_list)}"
    )

    if not params_list:

        raise RuntimeError(
            f"Hua Nan "
            f"{ad_year} "
            "MOPS detail params "
            "not found"
        )

    rows = []

    for index, params in enumerate(
        params_list,
        start=1,
    ):

        if index > 1:

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

        source_url = (
            build_source_url(
                params
            )
        )

        source_date = (
            source_date_from_params(
                params
            )
        )

        detail_html = (
            fetch_detail(
                params
            )
        )

        row = parse_detail(
            detail_html,
            target_roc_year,
            source_url,
            source_date,
        )

        if row is None:

            print(
                "[WARN] Detail skipped: "
                f"{params['spoke_date']} "
                f"{params['spoke_time']}"
            )

            continue

        print(
            "[PARSE] "
            f"{row['data_month']} "
            f"Monthly="
            f"{row['monthly_net_profit']} "
            f"YTD="
            f"{row['ytd_net_profit']} "
            f"EPS="
            f"{row['ytd_eps']}"
        )

        rows.append(
            row
        )

    #
    # 同一月份若因公告重複，
    # 僅保留最後取得的一筆。
    #
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

    validate_year(
        rows,
        ad_year,
    )

    print()
    print(
        f"[PASS] "
        f"{ad_year} "
        f"coverage: "
        f"{len(rows)}/12"
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

    return len(rows)


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
                  >= '2024-01'
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
        "Hua Nan Historical Backfill"
    )

    print(
        "=" * 70
    )

    print()
    print(
        "Target Years: "
        "2024, 2025"
    )

    print(
        "Database: "
        "Turso DEV only"
    )

    #
    # 先把 2024 / 2025
    # 全部抓完並驗證。
    #
    # 任何一年失敗都不碰 Turso。
    #
    all_rows = []

    try:

        for target_roc_year in (
            TARGET_ROC_YEARS
        ):

            ad_year = (
                roc_to_ad_year(
                    target_roc_year
                )
            )

            print()
            print(
                "-" * 70
            )

            print(
                f"[COLLECT] "
                f"{ad_year} "
                f"{STOCK_NAME}"
            )

            print(
                "-" * 70
            )

            year_rows = (
                collect_year(
                    target_roc_year
                )
            )

            all_rows.extend(
                year_rows
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
        f"{len(all_rows)}"
    )

    print(
        "=" * 70
    )

    conn = None

    try:

        print()
        print(
            "[CONNECT] "
            "Turso DEV"
        )

        conn = (
            get_connection()
        )

        sync_count = (
            sync_rows(
                conn,
                all_rows,
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
            "[PASS] Hua Nan "
            "backfill rows: "
            f"{sync_count}"
        )

        print(
            "[PASS] Hua Nan "
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

        for row in (
            verify(
                conn
            )
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
            "HUA NAN HISTORICAL "
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