from __future__ import annotations

from pprint import pprint

from crawler.http_client import tpex_post


URL = "https://www.tpex.org.tw/www/zh-tw/insti/qfiiStat"

REFERER = (
    "https://www.tpex.org.tw/zh-tw/mainboard/"
    "trading/major-institutional/foreign/day.html"
)

TEST_DATE = "2026/08/14"


def fetch_qfii_stat(
    search_type: str | None,
) -> dict:
    data = {
        "type": "Daily",
        "date": TEST_DATE,
    }

    if search_type is not None:
        data["searchType"] = search_type

    response = tpex_post(
        URL,
        data=data,
        headers={
            "Referer": REFERER,
        },
    )

    print()
    print("=" * 80)

    if search_type is None:
        print("searchType = <NOT SENT>")
    elif search_type == "":
        print("searchType = <EMPTY>")
    else:
        print(f"searchType = {search_type}")

    print(
        f"HTTP status = "
        f"{response.status_code}"
    )

    print(
        "Content-Type = "
        f"{response.headers.get('Content-Type')}"
    )

    print("=" * 80)

    response.raise_for_status()

    content_type = (
        response.headers.get(
            "Content-Type",
            "",
        )
    )

    if "json" not in content_type.lower():
        print(
            "[ERROR] Response 不是 JSON"
        )

        print()
        print(
            response.text[:2000]
        )

        raise RuntimeError(
            "TPEx qfiiStat response "
            "Content-Type 不是 JSON"
        )

    payload = response.json()

    if payload.get("stat") != "ok":
        raise RuntimeError(
            "TPEx qfiiStat stat != ok: "
            f"{payload.get('stat')!r}"
        )

    return payload


def is_4digit_stock_id(
    value: object,
) -> bool:
    stock_id = str(value).strip()

    return (
        len(stock_id) == 4
        and stock_id.isdigit()
    )


def get_table(
    payload: dict,
) -> dict:
    tables = payload.get(
        "tables"
    ) or []

    if len(tables) != 1:
        raise RuntimeError(
            "預期 tables = 1，"
            f"實際為 {len(tables)}"
        )

    return tables[0]


def get_stock_rows(
    payload: dict,
) -> list[list]:
    table = get_table(payload)

    rows = table.get(
        "data"
    ) or []

    result = []

    for row in rows:
        if len(row) < 12:
            continue

        # [00] 排行
        # [01] 代號
        stock_id = row[1]

        if not is_4digit_stock_id(
            stock_id
        ):
            continue

        result.append(row)

    return result


def get_stock_ids(
    payload: dict,
) -> set[str]:
    return {
        str(row[1]).strip()
        for row in get_stock_rows(
            payload
        )
    }


def parse_number(
    value: object,
) -> int:
    text = str(value).strip()

    if text in {
        "",
        "-",
        "--",
    }:
        raise ValueError(
            f"無法解析數字: {value!r}"
        )

    return int(
        text.replace(
            ",",
            "",
        )
    )


def inspect_payload(
    payload: dict,
) -> None:
    print()
    print("Top-level keys:")
    print(
        list(
            payload.keys()
        )
    )

    print()
    print("stat:")
    pprint(
        payload.get("stat")
    )

    print()
    print("date:")
    pprint(
        payload.get("date")
    )

    table = get_table(
        payload
    )

    print()
    print("title:")
    pprint(
        table.get("title")
    )

    fields = (
        table.get("fields")
        or []
    )

    print()
    print(
        f"fields count = "
        f"{len(fields)}"
    )

    for index, field in enumerate(
        fields
    ):
        print(
            f"  [{index:02d}] "
            f"{field}"
        )

    rows = (
        table.get("data")
        or []
    )

    stock_rows = get_stock_rows(
        payload
    )

    print()
    print(
        f"all rows count = "
        f"{len(rows)}"
    )

    print(
        f"4-digit stock rows = "
        f"{len(stock_rows)}"
    )

    print()
    print(
        "last 10 "
        "4-digit stock rows:"
    )

    for row in stock_rows[-10:]:
        print(row)

    if stock_rows:
        nets = [
            parse_number(row[5])
            for row in stock_rows
        ]

        print()
        print(
            "foreign_net range:"
        )

        print(
            "max =",
            max(nets),
        )

        print(
            "min =",
            min(nets),
        )

        print(
            "last row net =",
            parse_number(
                stock_rows[-1][5]
            ),
        )

    for row in stock_rows[:10]:
        print(row)

    print()
    print(
        "foreign-only "
        "[03:05] parsed sample:"
    )

    for row in stock_rows[:10]:
        stock_id = str(
            row[1]
        ).strip()

        stock_name = str(
            row[2]
        ).strip()

        foreign_buy_lot = (
            parse_number(row[3])
        )

        foreign_sell_lot = (
            parse_number(row[4])
        )

        foreign_net_lot = (
            parse_number(row[5])
        )

        print(
            stock_id,
            stock_name,
            {
                "foreign_buy_lot":
                    foreign_buy_lot,
                "foreign_sell_lot":
                    foreign_sell_lot,
                "foreign_net_lot":
                    foreign_net_lot,
                "foreign_buy_shares":
                    foreign_buy_lot * 1000,
                "foreign_sell_shares":
                    foreign_sell_lot * 1000,
                "foreign_net_shares":
                    foreign_net_lot * 1000,
            },
        )


def compare_results(
    results: dict[str, dict],
) -> None:
    print()
    print("=" * 80)
    print("COVERAGE COMPARISON")
    print("=" * 80)

    id_sets: dict[
        str,
        set[str],
    ] = {}

    for label, payload in (
        results.items()
    ):
        ids = get_stock_ids(
            payload
        )

        id_sets[label] = ids

        table = get_table(
            payload
        )

        all_rows = (
            table.get("data")
            or []
        )

        print(
            f"{label:10s} "
            f"all_rows="
            f"{len(all_rows):4d} "
            f"4digit="
            f"{len(ids):4d}"
        )

    buy_ids = id_sets.get(
        "buy",
        set(),
    )

    sell_ids = id_sets.get(
        "sell",
        set(),
    )

    union_ids = (
        buy_ids
        | sell_ids
    )

    intersection_ids = (
        buy_ids
        & sell_ids
    )

    print()
    print(
        "buy ∪ sell "
        f"4-digit count = "
        f"{len(union_ids)}"
    )

    print(
        "buy ∩ sell "
        f"4-digit count = "
        f"{len(intersection_ids)}"
    )

    print(
        "buy only = "
        f"{len(buy_ids - sell_ids)}"
    )

    print(
        "sell only = "
        f"{len(sell_ids - buy_ids)}"
    )

    for label in (
        "empty",
        "not_sent",
    ):
        ids = id_sets.get(
            label
        )

        if ids is None:
            continue

        print()
        print(
            f"{label} vs "
            "buy∪sell:"
        )

        print(
            "  extra = "
            f"{len(ids - union_ids)}"
        )

        print(
            "  missing = "
            f"{len(union_ids - ids)}"
        )

        print(
            "  same = "
            f"{ids == union_ids}"
        )
        
    print()
    print("=" * 80)
    print("TRUNCATION CHECK")
    print("=" * 80)

    for label in (
        "buy",
        "sell",
    ):
        payload = results.get(
            label
        )

        if payload is None:
            continue

        rows = get_stock_rows(
            payload
        )

        if not rows:
            continue

        last_row = rows[-1]

        print()
        print(
            f"{label}:"
        )

        print(
            "last stock =",
            last_row[1],
            last_row[2],
        )

        print(
            "last foreign_net_lot =",
            parse_number(
                last_row[5]
            ),
        )

        print(
            "last rank =",
            last_row[0],
        )        


def main() -> None:
    tests = [
        (
            "buy",
            "buy",
        ),
        (
            "sell",
            "sell",
        ),
        (
            "empty",
            "",
        ),
        (
            "not_sent",
            None,
        ),
    ]

    results = {}

    for label, search_type in tests:
        try:
            payload = fetch_qfii_stat(
                search_type
            )

            results[label] = payload

            inspect_payload(
                payload
            )

        except Exception as exc:
            print()
            print(
                f"[ERROR] "
                f"{label}: "
                f"{exc}"
            )

    compare_results(
        results
    )

    print()
    print("=" * 80)
    print("EXPECTED COLUMN MAPPING")
    print("=" * 80)

    print(
        "[01] stock_id"
    )

    print(
        "[02] stock_name"
    )

    print(
        "[03] 外資及陸資"
        "（不含自營商）買進"
    )

    print(
        "[04] 外資及陸資"
        "（不含自營商）賣出"
    )

    print(
        "[05] 外資及陸資"
        "（不含自營商）"
        "買賣超(張數)"
    )

    print()
    print(
        "DB normalization:"
    )

    print(
        "foreign_buy  = "
        "row[3] * 1000"
    )

    print(
        "foreign_sell = "
        "row[4] * 1000"
    )

    print(
        "foreign_net  = "
        "row[5] * 1000"
    )


if __name__ == "__main__":
    main()