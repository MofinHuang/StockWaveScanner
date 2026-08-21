import re

from crawler.http_client import (
    tpex_get,
)


URL = (
    "https://www.tpex.org.tw/"
    "zh-tw/mainboard/trading/info/pricing.html"
)


def main():

    print(
        "================================"
    )

    print(
        "TPEx 上櫃股票行情頁診斷"
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
    # tables.init(...)
    # =================================

    matches = list(
        re.finditer(
            r"tables\.init\s*\(",
            html,
            flags=re.IGNORECASE,
        )
    )

    print(
        f"tables.init 出現："
        f"{len(matches)} 次"
    )

    print()

    for index, match in enumerate(
        matches,
        start=1,
    ):

        start = max(
            0,
            match.start() - 500,
        )

        end = min(
            len(html),
            match.start() + 6000,
        )

        print(
            "================================"
        )

        print(
            f"tables.init #{index}"
        )

        print(
            "================================"
        )

        print(
            html[start:end]
        )

        print()

    # =================================
    # action 關鍵字
    # =================================

    keywords = [
        "action:",
        '"action"',
        "'action'",
        "pricing",
        "daily",
        "date",
        "tables-form",
        "autoLoad",
        "autoChange",
    ]

    print(
        "================================"
    )

    print(
        "關鍵字附近 HTML"
    )

    print(
        "================================"
    )

    for keyword in keywords:

        positions = [
            match.start()
            for match in re.finditer(
                re.escape(keyword),
                html,
                flags=re.IGNORECASE,
            )
        ]

        print()

        print(
            f"[{keyword}] "
            f"出現 {len(positions)} 次"
        )

        for position in positions[:5]:

            start = max(
                0,
                position - 500,
            )

            end = min(
                len(html),
                position + 1500,
            )

            print(
                "--------------------------------"
            )

            print(
                html[start:end]
            )

    # =================================
    # form 欄位
    # =================================

    print()

    print(
        "================================"
    )

    print(
        "tables-form 欄位"
    )

    print(
        "================================"
    )

    form_match = re.search(
        (
            r'<form[^>]+'
            r'id=["\']tables-form["\']'
            r'[^>]*>.*?</form>'
        ),
        html,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if not form_match:

        print(
            "[ERROR] 找不到 tables-form"
        )

        return

    form_html = (
        form_match.group(0)
    )

    fields = re.findall(
        (
            r'<(?:input|select)[^>]+'
            r'name=["\']([^"\']+)["\']'
        ),
        form_html,
        flags=re.IGNORECASE,
    )

    print(
        "欄位名稱："
    )

    for field in fields:

        print(
            f"  {field}"
        )


if __name__ == "__main__":
    main()