from __future__ import annotations

import re
import sys
import time

import requests
from bs4 import BeautifulSoup


STOCK_ID = "5880"
STOCK_NAME = "合庫金"

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


def find_candidate_links(html):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    candidates = []

    for tag in soup.find_all(
        ["input", "button", "a"]
    ):

        text = normalize_text(
            tag.get_text(
                " ",
                strip=True,
            )
        )

        onclick = (
            tag.get("onclick")
            or ""
        )

        value = (
            tag.get("value")
            or ""
        )

        combined = " ".join(
            [
                text,
                onclick,
                value,
            ]
        )

        if (
            "自結"
            not in combined
            and "盈餘"
            not in combined
        ):
            continue

        candidates.append(
            combined
        )

    #
    # MOPS 有時候主旨不直接掛在 button，
    # 因此也保留整頁 HTML，
    # 後面直接搜尋 detail 參數。
    #

    return candidates


def extract_detail_params(
    html,
):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    results = []

    #
    # 只處理「自結合併盈餘」的重大訊息，
    # 不需要把 5880 全部重大訊息都抓進來。
    #
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

        if "自結合併盈餘" not in row_text:
            continue

        #
        # 不抓「代子公司...」類型，
        # 只保留合庫金本公司公告。
        #
        if "代子公司" in row_text:
            continue

        row_html = str(row)

        #
        # 把 row 裡所有 attribute / onclick /
        # href / hidden input 一起攤平搜尋。
        #
        search_text = row_html.replace(
            "&amp;",
            "&",
        )

        #
        # spoke_date
        #
        spoke_date = None

        date_patterns = [
            r"spoke_date\s*=\s*['\"]?(\d{8})",
            r"spoke_date\.value\s*=\s*['\"](\d{8})",
            r"spoke_date['\"]?\s*[:,=]\s*['\"]?(\d{8})",
        ]

        for pattern in date_patterns:

            match = re.search(
                pattern,
                search_text,
                re.I,
            )

            if match:

                spoke_date = match.group(1)
                break

        #
        # spoke_time
        #
        spoke_time = None

        time_patterns = [
            r"spoke_time\s*=\s*['\"]?(\d{6})",
            r"spoke_time\.value\s*=\s*['\"](\d{6})",
            r"spoke_time['\"]?\s*[:,=]\s*['\"]?(\d{6})",
        ]

        for pattern in time_patterns:

            match = re.search(
                pattern,
                search_text,
                re.I,
            )

            if match:

                spoke_time = match.group(1)
                break

        #
        # seq_no
        #
        seq_no = None

        seq_patterns = [
            r"seq_no\s*=\s*['\"]?(\d+)",
            r"seq_no\.value\s*=\s*['\"](\d+)",
            r"seq_no['\"]?\s*[:,=]\s*['\"]?(\d+)",
        ]

        for pattern in seq_patterns:

            match = re.search(
                pattern,
                search_text,
                re.I,
            )

            if match:

                seq_no = match.group(1)
                break

        #
        # MOPS 部分清單列只把日期 / 時間顯示在文字，
        # 沒放 spoke_date / spoke_time attribute。
        #
        # 例如：
        #
        # 115/08/14 15:xx:xx
        #
        # 這時直接由畫面日期轉西元。
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

        #
        # seq_no 是 Detail 必要參數，
        # 不能猜。
        #
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

            #
            # MOPS 對連續 Request 有時反應較慢，
            # Retry 前稍微等待。
            #
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
        "5880"
        not in text
        and "合作金庫"
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
    # 取得公告月份：
    #
    # 115年8月份自結合併盈餘
    #
    month_match = re.search(
        r"115"
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

    data_month = (
        f"2026-{month:02d}"
    )

    #
    # 固定抓「合庫金控(合併)」那一列，
    # 避免誤抓合庫銀行 / 證券 / 人壽。
    #
    row_pattern = re.compile(
        r"合庫金控"
        r"\s*\(合併\)"
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
            "TCF holding row not found: "
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
    # MOPS 單位為億元。
    # DB 單位為百萬元。
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


def parse_tcf():

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
            "TCF MOPS detail params not found"
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

        #
        # 避免短時間連續呼叫 MOPS Detail。
        #
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

    #
    # 同月份若因 MOPS 重複公告，
    # 保留最後一筆。
    #
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
            "TCF parser returned no rows"
        )

    return rows


def main():

    configure_console()

    print("=" * 70)

    print(
        "StockWaveScanner V3 - "
        "TCF Financial Holding Monthly Earnings Parser"
    )

    print("=" * 70)

    rows = parse_tcf()

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
        "TCF FINANCIAL HOLDING PARSER OK"
    )

    print("=" * 70)

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )