import re

from crawler.http_client import (
    tpex_get,
)


URL = (
    "https://www.tpex.org.tw/"
    "rsrc/js/tables.js"
)


def main():

    print(
        "================================"
    )

    print(
        "TPEx tables.js 診斷"
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

    js = response.text

    print(
        f"HTTP Status："
        f"{response.status_code}"
    )

    print(
        f"JS 長度："
        f"{len(js):,}"
    )

    print()

    # =================================
    # 找 URL / endpoint
    # =================================

    url_patterns = [
        r'https?://[^"\']+',
        r'["\'](/[^"\']+\.php[^"\']*)["\']',
        r'["\'](/[^"\']+/api/[^"\']*)["\']',
        r'["\'](/[^"\']+/ajax[^"\']*)["\']',
        r'["\'](/[^"\']+result[^"\']*)["\']',
    ]

    candidates = []

    for pattern in url_patterns:

        matches = re.findall(
            pattern,
            js,
            flags=re.IGNORECASE,
        )

        for value in matches:

            if isinstance(
                value,
                tuple,
            ):
                value = "".join(
                    value
                )

            if value not in candidates:

                candidates.append(
                    value
                )

    print(
        "Endpoint 候選："
    )

    if candidates:

        for value in candidates[:100]:

            print(
                f"  {value}"
            )

    else:

        print(
            "  沒找到明確 URL"
        )

    print()

    # =================================
    # 搜尋 AJAX / fetch 關鍵字附近內容
    # =================================

    keywords = [
        "$.ajax",
        "$.get",
        "$.post",
        "fetch(",
        "axios",
        "url:",
        "data:",
        "scaDate",
        "tradeDate",
        "date",
        "tables-form",
        "api",
        "csv",
    ]

    print(
        "================================"
    )

    print(
        "關鍵字附近程式碼"
    )

    print(
        "================================"
    )

    for keyword in keywords:

        positions = [
            match.start()
            for match in re.finditer(
                re.escape(keyword),
                js,
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
                len(js),
                position + 1200,
            )

            print(
                "--------------------------------"
            )

            print(
                js[start:end]
            )


if __name__ == "__main__":
    main()