import re

from crawler.http_client import (
    tpex_get,
)


URL = (
    "https://www.tpex.org.tw/"
    "zh-tw/product/etf/info/price.html"
)


def main():

    print(
        "================================"
    )

    print(
        "TPEx 全市場歷史日行情頁診斷"
    )

    print(
        "================================"
    )

    response = tpex_get(
        URL,
        timeout=30,
        headers={
            "User-Agent":
                "Mozilla/5.0 "
                "StockWaveScanner/1.0"
        },
    )

    response.raise_for_status()

    html = response.text

    print(
        f"HTTP Status："
        f"{response.status_code}"
    )

    print(
        f"HTML 長度："
        f"{len(html):,}"
    )

    print()

    # =================================
    # form
    # =================================

    forms = re.findall(
        r"<form[^>]*>",
        html,
        flags=re.IGNORECASE,
    )

    print(
        "Forms："
    )

    if forms:

        for item in forms:

            print(
                item[:1000]
            )

    else:

        print(
            "  沒找到 form"
        )

    print()

    # =================================
    # AJAX / API URL
    # =================================

    patterns = [
        r'https?://[^"\']+',
        r'/[^"\']+api[^"\']*',
        r'/[^"\']+ajax[^"\']*',
        r'/[^"\']+price[^"\']*',
        r'/[^"\']+daily[^"\']*',
    ]

    candidates = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            flags=re.IGNORECASE,
        )

        for value in matches:

            if value not in candidates:
                candidates.append(
                    value
                )

    print(
        "URL / API 候選："
    )

    for value in candidates[:100]:

        print(
            f"  {value[:500]}"
        )

    print()

    # =================================
    # 日期相關關鍵字
    # =================================

    keywords = [
        "date",
        "Date",
        "tradeDate",
        "d=",
        "response=json",
        "ajax",
        "api",
        "download",
        "csv",
        "se=",
        "t=",
        "o=",
    ]

    print(
        "關鍵字："
    )

    for keyword in keywords:

        print(
            f"  {keyword}: "
            f"{keyword in html}"
        )

    print()

    # =================================
    # script src
    # =================================

    scripts = re.findall(
        (
            r'<script[^>]+'
            r'src=["\']([^"\']+)["\']'
        ),
        html,
        flags=re.IGNORECASE,
    )

    print(
        "Script Sources："
    )

    for source in scripts:

        print(
            f"  {source}"
        )


if __name__ == "__main__":
    main()