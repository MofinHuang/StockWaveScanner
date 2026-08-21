import json

from crawler.http_client import (
    tpex_get,
)


CANDIDATE_URLS = [
    (
        "https://www.tpex.org.tw/"
        "zh-tw/afterTrading/dailyQuotes"
    ),
    (
        "https://www.tpex.org.tw/"
        "www/zh-tw/afterTrading/dailyQuotes"
    ),
]


TARGET_DATE = "2026/08/14"


def main():

    print(
        "================================"
    )

    print(
        "TPEx 單日全市場行情驗證"
    )

    print(
        "================================"
    )

    payload = {
        "date":
            TARGET_DATE,

        "response":
            "json",
    }

    for url in CANDIDATE_URLS:

        print()

        print(
            f"測試：{url}"
        )

        try:

            # 目前 http_client 尚未有 tpex_post，
            # 所以這支診斷先直接使用 requests
            # 會在下一步正式整合。
            import warnings
            import requests

            from urllib3.exceptions import (
                InsecureRequestWarning,
            )

            try:

                response = requests.post(
                    url,
                    data=payload,
                    timeout=30,
                    verify=True,
                    headers={
                        "User-Agent":
                            "Mozilla/5.0 "
                            "StockWaveScanner/1.0",

                        "Referer":
                            (
                                "https://www.tpex.org.tw/"
                                "zh-tw/mainboard/"
                                "trading/info/"
                                "pricing.html"
                            ),
                    },
                )

            except requests.exceptions.SSLError:

                print(
                    "[WARN] TPEx SSL fallback"
                )

                with warnings.catch_warnings():

                    warnings.simplefilter(
                        "ignore",
                        InsecureRequestWarning,
                    )

                    response = requests.post(
                        url,
                        data=payload,
                        timeout=30,
                        verify=False,
                        headers={
                            "User-Agent":
                                "Mozilla/5.0 "
                                "StockWaveScanner/1.0",

                            "Referer":
                                (
                                    "https://www.tpex.org.tw/"
                                    "zh-tw/mainboard/"
                                    "trading/info/"
                                    "pricing.html"
                                ),
                        },
                    )

            print(
                f"HTTP Status："
                f"{response.status_code}"
            )

            print(
                f"Content-Type："
                f"{response.headers.get('content-type')}"
            )

            print(
                f"Response 長度："
                f"{len(response.text):,}"
            )

            if (
                response.status_code
                != 200
            ):
                continue

            try:

                data = response.json()

            except Exception:

                print(
                    "不是 JSON"
                )

                print(
                    response.text[:1000]
                )

                continue

            print(
                "JSON 根層欄位："
                f"{list(data.keys())}"
            )

            print(
                f"stat："
                f"{data.get('stat')}"
            )

            print(
                f"date："
                f"{data.get('date')}"
            )

            tables = data.get(
                "tables",
                []
            )

            print(
                f"tables："
                f"{len(tables)}"
            )

            for index, table in enumerate(
                tables,
                start=1,
            ):

                print()

                print(
                    f"Table #{index}"
                )

                print(
                    "title："
                    f"{table.get('title')}"
                )

                print(
                    "fields："
                    f"{table.get('fields')}"
                )

                rows = table.get(
                    "data",
                    []
                )

                print(
                    f"data rows："
                    f"{len(rows):,}"
                )

                if rows:

                    print(
                        "第一筆："
                    )

                    print(
                        json.dumps(
                            rows[0],
                            ensure_ascii=False,
                            indent=2,
                        )
                    )

            # 找到真正成功 endpoint 後，
            # 不再繼續測其他候選。
            if (
                data.get("stat")
                == "ok"
                and tables
            ):

                print()

                print(
                    "[OK] 找到 TPEx "
                    "單日全市場行情 endpoint"
                )

                break

        except Exception as ex:

            print(
                f"[ERROR] "
                f"{type(ex).__name__}: "
                f"{ex}"
            )


if __name__ == "__main__":
    main()