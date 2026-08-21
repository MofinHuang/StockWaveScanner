import json

from crawler.http_client import (
    tpex_get,
)


URL = (
    "https://www.tpex.org.tw/"
    "openapi/v1/mopsfin_t187ap03_O"
)


def main():

    print(
        "================================"
    )

    print(
        "TPEx 股票主檔 Raw 診斷"
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

    print(
        f"HTTP Status："
        f"{response.status_code}"
    )

    rows = response.json()

    print(
        f"Raw 筆數："
        f"{len(rows):,}"
    )

    print()

    if not rows:

        print(
            "[EMPTY] TPEx API 真正回傳空資料"
        )

        return

    first = rows[0]

    print(
        "第一筆完整資料："
    )

    print(
        json.dumps(
            first,
            ensure_ascii=False,
            indent=2,
        )
    )

    print()

    print(
        "第一筆欄位名稱："
    )

    for key in first.keys():

        print(
            f"  {repr(key)}"
        )

    # =================================
    # 額外找 6488
    # =================================

    print()

    print(
        "搜尋 6488："
    )

    found = []

    for row in rows:

        row_text = json.dumps(
            row,
            ensure_ascii=False,
        )

        if "6488" in row_text:

            found.append(
                row
            )

    print(
        f"找到：{len(found)} 筆"
    )

    if found:

        print(
            json.dumps(
                found[0],
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()