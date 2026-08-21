import re

from crawler.http_client import (
    tpex_get,
    tpex_post,
)


PAGE_URL = (
    "https://www.tpex.org.tw/"
    "zh-tw/mainboard/trading/"
    "major-institutional/detail/day.html"
)

API_URL = (
    "https://www.tpex.org.tw/"
    "www/zh-tw/insti/dailyTrade"
)

TARGET_DATE = "2026/08/14"


def extract_sect_options(
    html: str,
):
    select_match = re.search(
        (
            r'<select[^>]+'
            r'name=["\']sect["\']'
            r'[^>]*>'
            r'(.*?)'
            r'</select>'
        ),
        html,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if not select_match:
        raise ValueError(
            "找不到 sect select"
        )

    select_html = (
        select_match.group(1)
    )

    options = re.findall(
        (
            r'<option([^>]*)>'
            r'(.*?)'
            r'</option>'
        ),
        select_html,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    result = []

    for attrs, label in options:

        value_match = re.search(
            r'value=["\']([^"\']*)["\']',
            attrs,
            flags=re.IGNORECASE,
        )

        if not value_match:
            continue

        value = (
            value_match
            .group(1)
            .strip()
        )

        clean_label = re.sub(
            r"<[^>]+>",
            "",
            label,
        ).strip()

        selected = (
            "selected"
            in attrs.lower()
        )

        result.append(
            {
                "value":
                    value,

                "label":
                    clean_label,

                "selected":
                    selected,
            }
        )

    return result


def query_sect(
    sect_value: str,
):
    response = tpex_post(
        API_URL,
        data={
            "type":
                "Daily",

            "sect":
                sect_value,

            "date":
                TARGET_DATE,

            "response":
                "json",
        },
        timeout=30,
        headers={
            "User-Agent":
                "Mozilla/5.0 "
                "StockWaveScanner/1.0",

            "Referer":
                PAGE_URL,
        },
    )

    response.raise_for_status()

    return response.json()


def main():

    print(
        "================================"
    )

    print(
        "TPEx 三大法人 sect 診斷"
    )

    print(
        "================================"
    )

    page_response = tpex_get(
        PAGE_URL,
        timeout=30,
        headers={
            "User-Agent":
                "Mozilla/5.0 "
                "StockWaveScanner/1.0"
        },
    )

    page_response.raise_for_status()

    options = extract_sect_options(
        page_response.text
    )

    print()

    print(
        "sect options："
    )

    for option in options:

        print(
            f"  value="
            f"{option['value']!r} "
            f"selected="
            f"{option['selected']} "
            f"label="
            f"{option['label']!r}"
        )

    print()

    print(
        "================================"
    )

    print(
        f"查詢日期：{TARGET_DATE}"
    )

    print(
        "================================"
    )

    found = []

    for option in options:

        value = option[
            "value"
        ]

        if not value:
            continue

        try:

            payload = query_sect(
                value
            )

            tables = payload.get(
                "tables",
                []
            )

            row_count = 0

            fields = None

            first_row = None

            if tables:

                table = tables[0]

                fields = table.get(
                    "fields"
                )

                rows = table.get(
                    "data",
                    [],
                )

                row_count = len(
                    rows
                )

                if rows:
                    first_row = rows[0]

            print(
                f"sect={value!r:<8} "
                f"rows={row_count:>6,} "
                f"label="
                f"{option['label']!r}"
            )

            if row_count > 0:

                found.append(
                    {
                        "value":
                            value,

                        "label":
                            option[
                                "label"
                            ],

                        "rows":
                            row_count,

                        "fields":
                            fields,

                        "first_row":
                            first_row,
                    }
                )

        except Exception as ex:

            print(
                f"sect={value!r:<8} "
                f"[ERROR] "
                f"{type(ex).__name__}: "
                f"{ex}"
            )

    print()

    print(
        "================================"
    )

    print(
        "有資料的 sect"
    )

    print(
        "================================"
    )

    if not found:

        print(
            "[ERROR] "
            "所有 sect 都是 0 筆"
        )

        return

    for item in found:

        print()

        print(
            f"sect："
            f"{item['value']!r}"
        )

        print(
            f"label："
            f"{item['label']!r}"
        )

        print(
            f"rows："
            f"{item['rows']:,}"
        )

        print(
            "fields："
        )

        for index, field in enumerate(
            item["fields"],
        ):

            print(
                f"  [{index:02d}] "
                f"{field}"
            )

        print(
            "第一筆："
        )

        for index, value in enumerate(
            item["first_row"],
        ):

            print(
                f"  [{index:02d}] "
                f"{value}"
            )


if __name__ == "__main__":
    main()