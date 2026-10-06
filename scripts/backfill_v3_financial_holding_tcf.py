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


STOCK_ID = "5880"
STOCK_NAME = "合庫金"

TARGET_YEAR = 2025
TARGET_ROC_YEAR = "114"

#
# 2025-01 ~ 2025-11
# 大多於 2025 公告。
#
# 2025-12
# 通常於 2026-01 公告。
#
QUERY_ROC_YEARS = [
    "114",
    "115",
]

MOPS_URL = (
    "https://mopsov.twse.com.tw/"
    "mops/web/ajax_t05st01"
)

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

REQUEST_RETRIES = 5
REQUEST_DELAY_SECONDS = 1.0


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

            response = requests.request(
                method,
                url,
                **kwargs,
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

    response = request_with_retry(
        "POST",
        MOPS_URL,
        headers=get_headers(),
        data=payload,
        timeout=(
            10,
            60,
        ),
    )

    response.encoding = "utf-8"

    if not response.text.strip():

        raise RuntimeError(
            "MOPS returned "
            "empty HTML"
        )

    return response.text


def extract_detail_params(
    html,
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

        row_text = normalize_text(
            row.get_text(
                " ",
                strip=True,
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
            "自結合併盈餘"
            not in row_text
        ):

            continue

        if (
            "代子公司"
            in row_text
        ):

            continue

        #
        # 關鍵：
        #
        # 即使是 2026-01 公告，
        # 主旨仍應該寫：
        #
        # 114年12月份自結合併盈餘
        #
        # 所以只接受 TARGET_ROC_YEAR。
        #
        if (
            f"{TARGET_ROC_YEAR}年"
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
        # MOPS 有些列只有畫面日期，
        # 沒有 spoke_date / spoke_time attribute。
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

            print()
            print(
                "[WARN] Candidate row "
                "missing detail params:"
            )

            print(
                row_text[:1000]
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

        duplicate = any(
            existing[
                "spoke_date"
            ]
            == item[
                "spoke_date"
            ]
            and existing[
                "spoke_time"
            ]
            == item[
                "spoke_time"
            ]
            and existing[
                "seq_no"
            ]
            == item[
                "seq_no"
            ]
            for existing
            in results
        )

        if duplicate:

            continue

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

    value = params[
        "spoke_date"
    ]

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

    response = request_with_retry(
        "GET",
        MOPS_URL,
        headers=get_headers(),
        params=query,
        timeout=(
            10,
            60,
        ),
    )

    response.encoding = "utf-8"

    if not response.text.strip():

        raise RuntimeError(
            "MOPS detail returned "
            "empty HTML"
        )

    return response.text


def parse_detail(
    html,
    source_url,
    source_date,
):

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

    if (
        "5880"
        not in text
        and "合作金庫"
        not in text
        and "合庫金控"
        not in text
    ):

        return None

    if (
        "自結"
        not in text
        or "盈餘"
        not in text
    ):

        return None

    #
    # 114年8月份自結合併盈餘
    #
    month_match = re.search(
        rf"{re.escape(TARGET_ROC_YEAR)}"
        r"\s*年"
        r"\s*"
        r"(?P<month>\d{1,2})"
        r"\s*月份"
        r".{0,30}?"
        r"自結",
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
        1 <= month <= 12
    ):

        raise RuntimeError(
            "Invalid TCF month: "
            f"{month}"
        )

    data_month = (
        f"{TARGET_YEAR}-"
        f"{month:02d}"
    )

    #
    # 固定抓金控合併列。
    #
    # 預期欄位：
    #
    # 合庫金控(合併)
    # 月稅前
    # 月稅後
    # 累計稅前
    # 累計稅後
    # EPS
    #
    row_patterns = [
        re.compile(
            r"合庫金控"
            r"\s*"
            r"\(合併\)"
            r"\s*"
            r"(?P<monthly_pre>-?[\d,.]+)"
            r"\s+"
            r"(?P<monthly_after>-?[\d,.]+)"
            r"\s+"
            r"(?P<ytd_pre>-?[\d,.]+)"
            r"\s+"
            r"(?P<ytd_after>-?[\d,.]+)"
            r"\s+"
            r"(?P<eps>-?[\d,.]+)"
        ),
        re.compile(
            r"合作金庫金融控股"
            r".{0,20}?"
            r"\(合併\)"
            r"\s*"
            r"(?P<monthly_pre>-?[\d,.]+)"
            r"\s+"
            r"(?P<monthly_after>-?[\d,.]+)"
            r"\s+"
            r"(?P<ytd_pre>-?[\d,.]+)"
            r"\s+"
            r"(?P<ytd_after>-?[\d,.]+)"
            r"\s+"
            r"(?P<eps>-?[\d,.]+)"
        ),
    ]

    match = None

    for pattern in (
        row_patterns
    ):

        match = pattern.search(
            text
        )

        if match:

            break

    if not match:

        print()
        print(
            "[DEBUG] "
            f"{data_month}"
        )

        print(
            text[:5000]
        )

        raise RuntimeError(
            "TCF holding row "
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
            "eps"
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


def collect_rows():

    params_list = []

    print()
    print(
        "[TARGET] "
        f"{TARGET_YEAR} "
        f"{STOCK_NAME}"
    )

    for query_roc_year in (
        QUERY_ROC_YEARS
    ):

        query_ad_year = (
            roc_to_ad_year(
                query_roc_year
            )
        )

        print()
        print(
            "[SEARCH] "
            f"{TARGET_YEAR} data "
            f"in {query_ad_year} "
            "announcements"
        )

        html = fetch_mops_list(
            query_roc_year
        )

        year_params = (
            extract_detail_params(
                html,
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
        "[INFO] "
        "Detail candidates: "
        f"{len(params_list)}"
    )

    if not params_list:

        raise RuntimeError(
            "TCF 2025 MOPS "
            "detail params not found"
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

        detail_html = fetch_detail(
            params
        )

        row = parse_detail(
            detail_html,
            source_url,
            source_date,
        )

        if row is None:

            print(
                "[WARN] Skip detail: "
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
            f"{row['ytd_eps']} "
            f"SourceDate="
            f"{row['source_date']}"
        )

        rows.append(
            row
        )

    #
    # 如果同月份曾重複公告，
    # 依 source_date / URL 順序保留最後取得的一筆。
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
            "TCF 2025 "
            "missing months: "
            f"{', '.join(missing)}"
        )

    if unexpected:

        raise RuntimeError(
            "TCF 2025 "
            "unexpected months: "
            f"{', '.join(unexpected)}"
        )

    if len(
        rows
    ) != 12:

        raise RuntimeError(
            "TCF 2025 "
            "row count invalid: "
            f"{len(rows)}"
        )

    rows.sort(
        key=lambda x: x[
            "data_month"
        ]
    )

    #
    # MOPS 單位是億元，
    # 通常保留二位小數。
    #
    # 換算成百萬元後，
    # 允許 2 百萬元誤差。
    #
    tolerance = 2.0

    for index in range(
        1,
        len(rows),
    ):

        previous = rows[
            index - 1
        ]

        current = rows[
            index
        ]

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
                "TCF YTD "
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

        previous_ytd = lookup.get(
            previous_month
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
        "TCF Historical Backfill"
    )

    print(
        "=" * 70
    )

    print()
    print(
        "Target Year: 2025"
    )

    print(
        "Source: MOPS official"
    )

    print(
        "Database: Turso DEV only"
    )

    #
    # 先完整抓來源與驗證。
    # 未達 12/12 前絕不碰 Turso。
    #
    try:

        rows = collect_rows()

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

        conn = get_connection()

        sync_count = sync_rows(
            conn,
            rows,
        )

        yoy_count = (
            update_all_yoy(
                conn
            )
        )

        conn.commit()

        print()
        print(
            "[PASS] TCF "
            "backfill rows: "
            f"{sync_count}"
        )

        print(
            "[PASS] TCF "
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
            "TCF HISTORICAL "
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