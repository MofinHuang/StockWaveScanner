from __future__ import annotations

from collections import Counter

from crawler.http_client import (
    tdcc_get,
)


URL = (
    "https://openapi.tdcc.com.tw/"
    "v1/opendata/1-5"
)


def normalize_key(
    value: object,
) -> str:
    return (
        str(value)
        .replace("\ufeff", "")
        .strip()
    )


def normalize_row(
    row: dict,
) -> dict:
    return {
        normalize_key(key): value
        for key, value in row.items()
    }


def get_first_value(
    row: dict,
    candidates: list[str],
):
    for key in candidates:
        if key in row:
            return row[key]

    return None


def main() -> None:
    response = tdcc_get(
        URL
    )

    print("=" * 72)
    print("TDCC Market Open Data")
    print("=" * 72)

    print(
        "HTTP status =",
        response.status_code,
    )

    print(
        "Content-Type =",
        response.headers.get(
            "Content-Type"
        ),
    )

    response.raise_for_status()

    content_type = (
        response.headers.get(
            "Content-Type",
            "",
        )
    )

    if "json" not in content_type.lower():
        raise RuntimeError(
            "TDCC OpenAPI response "
            "不是 JSON"
        )

    payload = response.json()

    if not isinstance(
        payload,
        list,
    ):
        raise RuntimeError(
            "TDCC OpenAPI top-level "
            "不是 list"
        )

    print(
        "rows =",
        len(payload),
    )

    if not payload:
        raise RuntimeError(
            "TDCC OpenAPI rows = 0"
        )

    rows = [
        normalize_row(row)
        for row in payload
        if isinstance(row, dict)
    ]

    print()
    print("First row keys:")

    for key in rows[0].keys():
        print(
            " ",
            repr(key),
        )

    print()
    print("First 5 rows:")

    for row in rows[:5]:
        print(row)

    stock_id_candidates = [
        "證券代號",
        "股票代號",
        "證券代碼",
    ]

    date_candidates = [
        "資料日期",
        "日期",
    ]

    level_candidates = [
        "持股分級",
        "持股分級級別",
        "級別",
    ]

    pct_candidates = [
        "占集保庫存數比例%",
        "占集保庫存數比例",
        "占集保庫存比例%",
        "占集保庫存比例",
    ]

    stock_ids = []

    dates = []

    levels = []

    for row in rows:
        stock_id = get_first_value(
            row,
            stock_id_candidates,
        )

        data_date = get_first_value(
            row,
            date_candidates,
        )

        level = get_first_value(
            row,
            level_candidates,
        )

        if stock_id is not None:
            stock_ids.append(
                str(stock_id).strip()
            )

        if data_date is not None:
            dates.append(
                str(data_date).strip()
            )

        if level is not None:
            levels.append(
                str(level).strip()
            )

    unique_stock_ids = sorted(
        {
            value
            for value in stock_ids
            if (
                len(value) == 4
                and value.isdigit()
            )
        }
    )

    print()
    print("=" * 72)
    print("COVERAGE")
    print("=" * 72)

    print(
        "unique 4-digit stocks =",
        len(unique_stock_ids),
    )

    print(
        "unique dates =",
        sorted(
            set(dates)
        )[:20],
    )

    print(
        "date count =",
        len(
            set(dates)
        ),
    )

    print()
    print("Level counts:")

    for level, count in sorted(
        Counter(levels).items(),
        key=lambda item: item[0],
    ):
        print(
            f"  level={level!r}"
            f" count={count}"
        )

    print()
    print("=" * 72)
    print("SAMPLE STOCK")
    print("=" * 72)

    if not unique_stock_ids:
        print(
            "[WARN] 找不到 4 碼股票"
        )
        return

    sample_stock_id = (
        unique_stock_ids[0]
    )

    print(
        "sample stock_id =",
        sample_stock_id,
    )

    sample_rows = []

    for row in rows:
        stock_id = get_first_value(
            row,
            stock_id_candidates,
        )

        if (
            stock_id is not None
            and str(stock_id).strip()
            == sample_stock_id
        ):
            sample_rows.append(
                row
            )

    for row in sample_rows:
        print(row)

    print()
    print("=" * 72)
    print("STRATEGY FIELD CHECK")
    print("=" * 72)

    found_pct = any(
        get_first_value(
            row,
            pct_candidates,
        )
        is not None
        for row in rows[:100]
    )

    print(
        "percentage field found =",
        found_pct,
    )

    print()
    print(
        "目標確認："
    )

    print(
        "1. 是否一次包含全市場多檔股票"
    )

    print(
        "2. 是否只有單一最新資料日"
    )

    print(
        "3. levels 是否包含 1、2、15"
    )

    print(
        "4. 是否可直接取得比例欄位"
    )


if __name__ == "__main__":
    main()