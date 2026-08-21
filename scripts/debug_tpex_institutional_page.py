import re

from crawler.http_client import (
    tpex_get,
)


URL = (
    "https://www.tpex.org.tw/"
    "zh-tw/mainboard/trading/"
    "major-institutional/detail/day.html"
)


def main():

    print(
        "================================"
    )

    print(
        "TPEx 三大法人頁診斷"
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
    # tables.init
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

        print()

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

    # =================================
    # action
    # =================================

    print()

    print(
        "================================"
    )

    print(
        "action 候選"
    )

    print(
        "================================"
    )

    action_matches = re.findall(
        r'action\s*:\s*["\']([^"\']+)["\']',
        html,
        flags=re.IGNORECASE,
    )

    if action_matches:

        for action in action_matches:

            print(
                f"  {action}"
            )

    else:

        print(
            "  找不到 action"
        )

    # =================================
    # form fields
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

    for field in fields:

        print(
            f"  {field}"
        )

    # =================================
    # 預設值
    # =================================

    print()

    print(
        "================================"
    )

    print(
        "欄位預設值"
    )

    print(
        "================================"
    )

    inputs = re.findall(
        r'<(?:input|select)[^>]+>',
        form_html,
        flags=re.IGNORECASE,
    )

    for item in inputs:

        if (
            "name=" in item
            or "data-" in item
        ):

            print(
                item[:1000]
            )


if __name__ == "__main__":
    main()