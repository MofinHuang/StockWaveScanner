import re

from crawler.http_client import (
    tpex_get,
)


URL = (
    "https://www.tpex.org.tw/"
    "zh-tw/mainboard/trading/"
    "major-institutional/foreign/day.html"
)


def main():

    print(
        "================================"
    )

    print(
        "TPEx 外資及陸資買賣明細頁診斷"
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
            match.start() + 5000,
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

    actions = re.findall(
        (
            r'action\s*:\s*'
            r'["\']([^"\']+)["\']'
        ),
        html,
        flags=re.IGNORECASE,
    )

    if actions:

        for action in actions:

            print(
                f"  {action}"
            )

    else:

        print(
            "  找不到 action"
        )

    # =================================
    # tables-form
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
            r'[^>]*>'
            r'.*?'
            r'</form>'
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
    # select options
    # =================================

    print()

    print(
        "================================"
    )

    print(
        "Select Options"
    )

    print(
        "================================"
    )

    selects = re.findall(
        (
            r'<select([^>]*)>'
            r'(.*?)'
            r'</select>'
        ),
        form_html,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    for attrs, body in selects:

        name_match = re.search(
            r'name=["\']([^"\']+)["\']',
            attrs,
            flags=re.IGNORECASE,
        )

        name = (
            name_match.group(1)
            if name_match
            else "UNKNOWN"
        )

        print()

        print(
            f"[select] {name}"
        )

        options = re.findall(
            (
                r'<option[^>]*'
                r'value=["\']([^"\']*)["\']'
                r'[^>]*>'
                r'(.*?)'
                r'</option>'
            ),
            body,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        for value, label in options:

            clean_label = re.sub(
                r"<[^>]+>",
                "",
                label,
            ).strip()

            print(
                f"  value={value!r} "
                f"label={clean_label!r}"
            )


if __name__ == "__main__":
    main()