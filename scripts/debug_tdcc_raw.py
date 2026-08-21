import json

from config import DATABASE_PATH

import sqlite3


TARGET_STOCK_IDS = {
    "2330",
    "2317",
    "2454",
    "6488",
    "6770",
}


def main():

    conn = sqlite3.connect(
        DATABASE_PATH
    )

    row = conn.execute(
        """
        SELECT
            request_key,
            content,
            downloaded_at

        FROM raw_responses

        WHERE source = ?

        ORDER BY downloaded_at DESC

        LIMIT 1
        """,
        (
            "TDCC_SHAREHOLDING",
        ),
    ).fetchone()

    conn.close()

    if row is None:
        print(
            "[ERROR] 找不到 TDCC Raw Response"
        )
        return

    request_key = row[0]
    raw_text = row[1]
    downloaded_at = row[2]

    print(
        "================================"
    )
    print(
        "TDCC Raw 診斷"
    )
    print(
        "================================"
    )

    print(
        f"request_key：{request_key}"
    )

    print(
        f"downloaded_at：{downloaded_at}"
    )

    rows = json.loads(
        raw_text
    )

    print(
        f"Raw 總筆數：{len(rows):,}"
    )

    print()

    if not rows:
        print(
            "[ERROR] Raw Response 為空"
        )
        return

    print(
        "第一筆實際欄位："
    )

    for key, value in rows[0].items():
        print(
            f"  {repr(key)} = {repr(value)}"
        )

    print()

    # =================================
    # 不使用目前 parser
    #
    # 直接從 Raw 搜尋目標股票
    # =================================

    found = []

    for raw_row in rows:

        normalized = {
            str(key).strip(): value
            for key, value
            in raw_row.items()
        }

        stock_id = str(
            normalized.get(
                "證券代號",
                "",
            )
        ).strip()

        if stock_id in TARGET_STOCK_IDS:

            found.append(
                {
                    "證券代號":
                        stock_id,

                    "資料日期":
                        normalized.get(
                            "資料日期"
                        ),

                    "持股分級":
                        normalized.get(
                            "持股分級"
                        ),

                    "人數":
                        normalized.get(
                            "人數"
                        ),

                    "股數":
                        normalized.get(
                            "股數"
                        ),

                    "占比":
                        normalized.get(
                            "占集保庫存數比例%"
                        ),
                }
            )

    print(
        "================================"
    )
    print(
        "Raw 中找到的測試股票"
    )
    print(
        "================================"
    )

    if not found:

        print(
            "[EMPTY] Raw 本身就找不到 "
            "2330 / 2317 / 2454 / 6488 / 6770"
        )

        return

    stock_counts = {}

    for item in found:

        stock_id = item[
            "證券代號"
        ]

        stock_counts[
            stock_id
        ] = (
            stock_counts.get(
                stock_id,
                0,
            )
            + 1
        )

    for stock_id in sorted(
        stock_counts
    ):

        print(
            f"{stock_id}: "
            f"{stock_counts[stock_id]} 筆"
        )

    print()

    print(
        "每檔第一筆 Raw："
    )

    shown = set()

    for item in found:

        stock_id = item[
            "證券代號"
        ]

        if stock_id in shown:
            continue

        shown.add(
            stock_id
        )

        print(
            repr(item)
        )


if __name__ == "__main__":
    main()