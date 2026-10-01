from __future__ import annotations

import re
import sys
import time

import requests
from bs4 import BeautifulSoup


STOCK_ID = "2880"
STOCK_NAME = "華南金"

ROC_YEAR = "115"

MOPS_URL = (
    "https://mopsov.twse.com.tw/"
    "mops/web/ajax_t05st01"
)


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


def normalize_text(text):

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def fetch_mops_list():

    print(
        "[FETCH] MOPS material information"
    )

    payload = {
        "firstin": "1",
        "TYPEK": "sii",
        "co_id": STOCK_ID,
        "year": ROC_YEAR,
        "month": "",
        "b_date": "",
        "e_date": "",
    }

    response = requests.post(
        MOPS_URL,
        headers=get_headers(),
        data=payload,
        timeout=30,
    )

    response.raise_for_status()

    response.encoding = "utf-8"

    if not response.text.strip():

        raise RuntimeError(
            "MOPS returned empty HTML"
        )

    return response.text


def extract_detail_params(
    html,
):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    results = []

    for row in soup.find_all("tr"):

        row_text = normalize_text(
            row.get_text(
                " ",
                strip=True,
            )
        )

        if not row_text:
            continue

        if STOCK_ID not in row_text:
            continue

        #
        # 華南金主旨格式：
        #
        # 公告本公司115年8月份自結盈餘
        #
        if "自結盈餘" not in row_text:
            continue

        if "代子公司" in row_text:
            continue

        row_html = str(row).replace(
            "&amp;",
            "&",
        )

        spoke_date = None
        spoke_time = None
        seq_no = None

        date_patterns = [
            r"spoke_date\s*=\s*['\"]?(\d{8})",
            r"spoke_date\.value\s*=\s*['\"](\d{8})",
            r"spoke_date['\"]?\s*[:,=]\s*['\"]?(\d{8})",
        ]

        for pattern in date_patterns:

            match = re.search(
                pattern,
                row_html,
                re.I,
            )

            if match:

                spoke_date = match.group(1)
                break

        time_patterns = [
            r"spoke_time\s*=\s*['\"]?(\d{6})",
            r"spoke_time\.value\s*=\s*['\"](\d{6})",
            r"spoke_time['\"]?\s*[:,=]\s*['\"]?(\d{6})",
        ]

        for pattern in time_patterns:

            match = re.search(
                pattern,
                row_html,
                re.I,
            )

            if match:

                spoke_time = match.group(1)
                break

        seq_patterns = [
            r"seq_no\s*=\s*['\"]?(\d+)",
            r"seq_no\.value\s*=\s*['\"](\d+)",
            r"seq_no['\"]?\s*[:,=]\s*['\"]?(\d+)",
        ]

        for pattern in seq_patterns:

            match = re.search(
                pattern,
                row_html,
                re.I,
            )

            if match:

                seq_no = match.group(1)
                break

        #
        # 日期 / 時間若 HTML attribute 沒帶，
        # 直接從畫面文字取。
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
                "[DEBUG] Candidate row "
                "missing detail params:"
            )

            print(
                row_text
            )

            print()
            print(
                "[DEBUG] Candidate row HTML:"
            )

            print(
                row_html[:3000]
            )

            continue

        item = {
            "spoke_date": spoke_date,
            "spoke_time": spoke_time,
            "seq_no": seq_no,
        }

        if item not in results:

            print(
                "[FOUND] "
                f"{spoke_date} "
                f"{spoke_time} "
                f"seq={seq_no}"
            )

            results.append(
                item
            )

    return results


def fetch_detail(
    params,
):

    query = {
        "firstin": "1",
        "TYPEK": "all",
        "step": "2",
        "co_id": STOCK_ID,
        "year": ROC_YEAR,
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

    max_retries = 3

    for attempt in range(
        1,
        max_retries + 1,
    ):

        try:

            response = requests.get(
                MOPS_URL,
                headers=get_headers(),
                params=query,
                timeout=(
                    10,
                    60,
                ),
            )

            response.raise_for_status()

            response.encoding = "utf-8"

            if not response.text.strip():

                raise RuntimeError(
                    "MOPS detail returned empty HTML"
                )

            return response.text

        except requests.exceptions.ReadTimeout:

            print(
                "[WARN] MOPS detail timeout: "
                f"{params['spoke_date']} "
                f"{params['spoke_time']} "
                f"attempt={attempt}/{max_retries}"
            )

            if attempt >= max_retries:

                raise

            time.sleep(
                attempt * 2
            )


def parse_detail(
    html,
    source_url,
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
        "華南金融控股"
        not in text
        and "華南金控"
        not in text
    ):

        return None

    if "自結盈餘" not in text:

        return None

    #
    # 公告本公司115年8月份自結盈餘
    #
    month_match = re.search(
        r"115"
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

    data_month = (
        f"2026-{month:02d}"
    )

    #
    # 優先抓 MOPS 表格中的「華南金控」資料列。
    #
    # 欄位順序：
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

    match = row_pattern.search(
        text
    )

    if not match:

        print()
        print(
            f"[DEBUG] {data_month}"
        )

        print(
            text[:4000]
        )

        raise RuntimeError(
            "Hua Nan holding row not found: "
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
    # 官方：億元
    # DB：百萬元
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
        "data_month": data_month,
        "monthly_net_profit": (
            monthly_net_profit
        ),
        "ytd_net_profit": (
            ytd_net_profit
        ),
        "ytd_eps": eps,
        "source_url": source_url,
    }


def parse_huanan_mops():

    html = fetch_mops_list()

    params_list = extract_detail_params(
        html
    )

    if not params_list:

        print()
        print(
            "[DEBUG] MOPS list preview:"
        )

        print(
            normalize_text(
                BeautifulSoup(
                    html,
                    "html.parser",
                ).get_text(
                    " ",
                    strip=True,
                )
            )[:4000]
        )

        raise RuntimeError(
            "Hua Nan MOPS detail params not found"
        )

    print(
        f"[INFO] Detail candidates: "
        f"{len(params_list)}"
    )

    rows = []

    for params in params_list:

        source_url = (
            MOPS_URL
            + "?"
            + "firstin=1"
            + "&TYPEK=all"
            + "&step=2"
            + f"&co_id={STOCK_ID}"
            + f"&year={ROC_YEAR}"
            + "&month=all"
            + "&spoke_date="
            + params["spoke_date"]
            + "&spoke_time="
            + params["spoke_time"]
            + "&seq_no="
            + params["seq_no"]
            + "&off=1"
        )

        time.sleep(1)

        detail_html = fetch_detail(
            params
        )

        row = parse_detail(
            detail_html,
            source_url,
        )

        if row is None:

            continue

        print(
            f"[PARSE] "
            f"{row['data_month']}"
        )

        rows.append(
            row
        )

    unique_rows = {}

    for row in rows:

        unique_rows[
            row["data_month"]
        ] = row

    rows = list(
        unique_rows.values()
    )

    rows.sort(
        key=lambda x: x[
            "data_month"
        ]
    )

    if not rows:

        raise RuntimeError(
            "Hua Nan MOPS parser returned no rows"
        )

    #
    # YTD reconciliation
    #
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

        if abs(
            expected_ytd
            - actual_ytd
        ) > 1.0:

            raise RuntimeError(
                "Hua Nan YTD reconciliation failed: "
                f"{current['data_month']} "
                f"Expected={expected_ytd} "
                f"Actual={actual_ytd}"
            )

    return rows


def main():

    configure_console()

    print("=" * 70)

    print(
        "StockWaveScanner V3 - "
        "Hua Nan Financial Holding "
        "MOPS Monthly Earnings Parser"
    )

    print("=" * 70)

    rows = parse_huanan_mops()

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
        "HUA NAN MOPS PARSER OK"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )