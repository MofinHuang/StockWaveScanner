import re

from crawler.http_client import (
    tdcc_get,
)


URL = (
    "https://www.tdcc.com.tw/"
    "portal/zh/smWeb/qryStock"
)


def main():

    print(
        "================================"
    )

    print(
        "TDCC 歷史查詢表單診斷"
    )

    print(
        "================================"
    )

    response = tdcc_get(
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

    print()

    # =================================
    # 找 form1 開頭
    # =================================

    form_match = re.search(
        r'<form[^>]+id=["\']form1["\'][^>]*>',
        html,
        flags=re.IGNORECASE,
    )

    print(
        "form1："
    )

    if form_match:

        print(
            form_match.group(0)
        )

    else:

        print(
            "[ERROR] 找不到 form1"
        )

    print()

    # =================================
    # 擷取 form1 整段
    # =================================

    form_block_match = re.search(
        (
            r'(<form[^>]+'
            r'id=["\']form1["\']'
            r'[^>]*>.*?</form>)'
        ),
        html,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if not form_block_match:

        print(
            "[ERROR] 無法取得 form1 內容"
        )

        return

    form_html = (
        form_block_match.group(1)
    )

    # =================================
    # 列出所有有 name 的 input
    # =================================

    inputs = re.findall(
        r'<input[^>]*>',
        form_html,
        flags=re.IGNORECASE,
    )

    print(
        "Form Inputs："
    )

    for item in inputs:

        name_match = re.search(
            r'name=["\']([^"\']+)["\']',
            item,
            flags=re.IGNORECASE,
        )

        if not name_match:
            continue

        name = name_match.group(1)

        value_match = re.search(
            r'value=["\']([^"\']*)["\']',
            item,
            flags=re.IGNORECASE,
        )

        input_type_match = re.search(
            r'type=["\']([^"\']+)["\']',
            item,
            flags=re.IGNORECASE,
        )

        value = (
            value_match.group(1)
            if value_match
            else ""
        )

        input_type = (
            input_type_match.group(1)
            if input_type_match
            else ""
        )

        checked = (
            "checked"
            if re.search(
                r'\bchecked\b',
                item,
                flags=re.IGNORECASE,
            )
            else ""
        )

        print(
            f"  name={name!r} "
            f"type={input_type!r} "
            f"value={value!r} "
            f"{checked}"
        )

    print()

    # =================================
    # Select 欄位
    # =================================

    selects = re.findall(
        r'<select[^>]*>',
        form_html,
        flags=re.IGNORECASE,
    )

    print(
        "Form Selects："
    )

    for item in selects:

        name_match = re.search(
            r'name=["\']([^"\']+)["\']',
            item,
            flags=re.IGNORECASE,
        )

        if name_match:

            print(
                f"  name="
                f"{name_match.group(1)!r}"
            )


if __name__ == "__main__":
    main()