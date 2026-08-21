from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from crawler.http_client import tpex_post


TPEX_QFII_URL = (
    "https://www.tpex.org.tw/"
    "www/zh-tw/insti/qfiiStat"
)

TPEX_QFII_REFERER = (
    "https://www.tpex.org.tw/"
    "zh-tw/mainboard/trading/"
    "major-institutional/foreign/day.html"
)

SOURCE = "TPEX_QFII_STAT"

EXPECTED_TITLE = "外資及陸資買賣超彙總表"

EXPECTED_FIELDS = [
    "排行",
    "代號",
    "名稱",
    "買進",
    "賣出",
    "買賣超(張數)",
    "買進",
    "賣出",
    "買賣超(張數)",
    "買進",
    "賣出",
    "買賣超(張數)",
]

# 2025-01-10 起 TPEx qfiiStat 顯示「張數」。
# DB institutional_trades 統一存 shares。
LOT_TO_SHARES = 1000


@dataclass(frozen=True)
class TpexForeignRecord:
    stock_id: str
    market: str
    trade_date: str
    foreign_buy: int
    foreign_sell: int
    foreign_net: int
    source: str
    downloaded_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "stock_id": self.stock_id,
            "market": self.market,
            "trade_date": self.trade_date,
            "foreign_buy": self.foreign_buy,
            "foreign_sell": self.foreign_sell,
            "foreign_net": self.foreign_net,
            "source": self.source,
            "downloaded_at": self.downloaded_at,
        }


@dataclass(frozen=True)
class TpexForeignFetchResult:
    trade_date: str
    buy_payload: dict[str, Any]
    sell_payload: dict[str, Any]
    records: list[TpexForeignRecord]


def _format_request_date(
    trade_date: str | date,
) -> str:
    """
    轉成 TPEx POST 所需 YYYY/MM/DD。
    """
    if isinstance(trade_date, date):
        return trade_date.strftime("%Y/%m/%d")

    text = str(trade_date).strip()

    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d",
    ):
        try:
            parsed = datetime.strptime(
                text,
                fmt,
            )
            return parsed.strftime(
                "%Y/%m/%d"
            )
        except ValueError:
            continue

    raise ValueError(
        "trade_date 必須為 "
        "YYYY-MM-DD、YYYY/MM/DD "
        "或 YYYYMMDD，"
        f"實際收到：{trade_date!r}"
    )


def _normalize_response_date(
    value: Any,
) -> str:
    """
    TPEx response date:
        20260814
    正規化為：
        2026-08-14
    """
    text = str(value).strip()

    try:
        parsed = datetime.strptime(
            text,
            "%Y%m%d",
        )
    except ValueError as exc:
        raise RuntimeError(
            "TPEx qfiiStat 回傳 "
            "無法識別的 date："
            f"{value!r}"
        ) from exc

    return parsed.strftime(
        "%Y-%m-%d"
    )


def _parse_lot_number(
    value: Any,
) -> int:
    """
    API 欄位目前為整數張數，
    例如：
        '6,253'
        '-11,752'
        '0'
    """
    text = str(value).strip()

    if text == "":
        raise ValueError(
            "TPEx qfiiStat 數值欄位為空"
        )

    cleaned = (
        text
        .replace(",", "")
        .replace("＋", "+")
        .replace("－", "-")
    )

    try:
        return int(cleaned)
    except ValueError as exc:
        raise ValueError(
            "TPEx qfiiStat "
            "無法解析張數："
            f"{value!r}"
        ) from exc


def _is_4digit_stock_id(
    value: Any,
) -> bool:
    stock_id = str(value).strip()

    return (
        len(stock_id) == 4
        and stock_id.isdigit()
    )


def _validate_payload(
    payload: dict[str, Any],
    expected_date: str,
    search_type: str,
) -> dict[str, Any]:
    """
    嚴格驗證 API 結構。

    不只看 HTTP 200，
    還確認：
    - stat == ok
    - date 正確
    - tables == 1
    - title 正確
    - fields 與已驗證 schema 一致
    """
    stat = payload.get("stat")

    if stat != "ok":
        raise RuntimeError(
            "TPEx qfiiStat "
            f"searchType={search_type} "
            f"stat != ok：{stat!r}"
        )

    response_date = (
        _normalize_response_date(
            payload.get("date")
        )
    )

    if response_date != expected_date:
        raise RuntimeError(
            "TPEx qfiiStat 日期不符："
            f"request={expected_date}, "
            f"response={response_date}"
        )

    tables = payload.get(
        "tables"
    )

    if not isinstance(
        tables,
        list,
    ):
        raise RuntimeError(
            "TPEx qfiiStat tables "
            "不是 list"
        )

    if len(tables) != 1:
        raise RuntimeError(
            "TPEx qfiiStat "
            "預期 tables=1，"
            f"實際={len(tables)}"
        )

    table = tables[0]

    title = table.get(
        "title"
    )

    if title != EXPECTED_TITLE:
        raise RuntimeError(
            "TPEx qfiiStat "
            "table title 改變："
            f"{title!r}"
        )

    fields = table.get(
        "fields"
    )

    if fields != EXPECTED_FIELDS:
        raise RuntimeError(
            "TPEx qfiiStat "
            "fields schema 改變。\n"
            f"expected={EXPECTED_FIELDS!r}\n"
            f"actual={fields!r}"
        )

    data = table.get(
        "data"
    )

    if not isinstance(
        data,
        list,
    ):
        raise RuntimeError(
            "TPEx qfiiStat "
            "table.data 不是 list"
        )

    return table


def _fetch_payload(
    trade_date: str | date,
    search_type: str,
) -> dict[str, Any]:
    if search_type not in {
        "buy",
        "sell",
    }:
        raise ValueError(
            "search_type 只能是 "
            "'buy' 或 'sell'"
        )

    request_date = (
        _format_request_date(
            trade_date
        )
    )

    response = tpex_post(
        TPEX_QFII_URL,
        data={
            "type": "Daily",
            "date": request_date,
            "searchType": search_type,
        },
        headers={
            "Referer": TPEX_QFII_REFERER,
        },
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
            "TPEx qfiiStat "
            "response 不是 JSON。"
            f" Content-Type="
            f"{content_type!r}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "TPEx qfiiStat "
            "JSON decode failed"
        ) from exc

    expected_date = (
        datetime.strptime(
            request_date,
            "%Y/%m/%d",
        )
        .strftime("%Y-%m-%d")
    )

    _validate_payload(
        payload=payload,
        expected_date=expected_date,
        search_type=search_type,
    )

    return payload


def fetch_tpex_foreign_buy(
    trade_date: str | date,
) -> dict[str, Any]:
    return _fetch_payload(
        trade_date=trade_date,
        search_type="buy",
    )


def fetch_tpex_foreign_sell(
    trade_date: str | date,
) -> dict[str, Any]:
    return _fetch_payload(
        trade_date=trade_date,
        search_type="sell",
    )


def _parse_payload_records(
    payload: dict[str, Any],
    search_type: str,
    downloaded_at: str,
) -> dict[str, TpexForeignRecord]:
    """
    qfiiStat schema：

    [00] 排行
    [01] 代號
    [02] 名稱

    外資及陸資（不含自營商）
    [03] 買進
    [04] 賣出
    [05] 買賣超(張數)

    外資自營商
    [06] 買進
    [07] 賣出
    [08] 買賣超(張數)

    外資及陸資合計
    [09] 買進
    [10] 賣出
    [11] 買賣超(張數)

    Foreign /20 策略只使用第一組，
    不含外資自營商。
    """
    response_date = (
        _normalize_response_date(
            payload.get("date")
        )
    )

    table = _validate_payload(
        payload=payload,
        expected_date=response_date,
        search_type=search_type,
    )

    rows = table["data"]

    records: dict[
        str,
        TpexForeignRecord,
    ] = {}

    for row in rows:
        if not isinstance(
            row,
            list,
        ):
            raise RuntimeError(
                "TPEx qfiiStat row "
                "不是 list"
            )

        if len(row) != 12:
            raise RuntimeError(
                "TPEx qfiiStat "
                "row 欄位數改變："
                f"{len(row)}"
            )

        stock_id = str(
            row[1]
        ).strip()

        # 排除 ETF / ETN / 權證 /
        # 其他非 4 碼普通股票商品。
        if not _is_4digit_stock_id(
            stock_id
        ):
            continue

        foreign_buy_lot = (
            _parse_lot_number(
                row[3]
            )
        )

        foreign_sell_lot = (
            _parse_lot_number(
                row[4]
            )
        )

        foreign_net_lot = (
            _parse_lot_number(
                row[5]
            )
        )

        record = TpexForeignRecord(
            stock_id=stock_id,
            market="TPEx",
            trade_date=response_date,
            foreign_buy=(
                foreign_buy_lot
                * LOT_TO_SHARES
            ),
            foreign_sell=(
                foreign_sell_lot
                * LOT_TO_SHARES
            ),
            foreign_net=(
                foreign_net_lot
                * LOT_TO_SHARES
            ),
            source=SOURCE,
            downloaded_at=downloaded_at,
        )

        if stock_id in records:
            raise RuntimeError(
                "TPEx qfiiStat "
                f"searchType={search_type} "
                "出現重複 stock_id："
                f"{stock_id}"
            )

        records[stock_id] = record

    return records


def parse_tpex_foreign_payloads(
    buy_payload: dict[str, Any],
    sell_payload: dict[str, Any],
    downloaded_at: str | None = None,
) -> list[TpexForeignRecord]:
    """
    合併 buy / sell。

    已在 2026-08-14 驗證：
    - buy 包含正買賣超 + 尾端部分 zero
    - sell 包含負買賣超 + 尾端部分 zero
    - 4 碼股票 intersection = 0

    若未來同一 stock_id 同時出現在兩邊，
    視為 API 行為改變，直接報錯，
    不靜默覆蓋。
    """
    buy_date = (
        _normalize_response_date(
            buy_payload.get("date")
        )
    )

    sell_date = (
        _normalize_response_date(
            sell_payload.get("date")
        )
    )

    if buy_date != sell_date:
        raise RuntimeError(
            "TPEx qfiiStat "
            "buy/sell 日期不同："
            f"buy={buy_date}, "
            f"sell={sell_date}"
        )

    if downloaded_at is None:
        downloaded_at = (
            datetime.now()
            .astimezone()
            .isoformat(
                timespec="seconds"
            )
        )

    buy_records = (
        _parse_payload_records(
            payload=buy_payload,
            search_type="buy",
            downloaded_at=downloaded_at,
        )
    )

    sell_records = (
        _parse_payload_records(
            payload=sell_payload,
            search_type="sell",
            downloaded_at=downloaded_at,
        )
    )

    intersection = (
        set(buy_records)
        & set(sell_records)
    )

    if intersection:
        sample = sorted(
            intersection
        )[:10]

        raise RuntimeError(
            "TPEx qfiiStat "
            "buy/sell 出現重疊股票，"
            "API 行為可能已改變。"
            f" sample={sample}"
        )

    merged = {
        **buy_records,
        **sell_records,
    }

    return sorted(
        merged.values(),
        key=lambda item: item.stock_id,
    )


def fetch_tpex_market_foreign(
    trade_date: str | date,
) -> TpexForeignFetchResult:
    """
    正式 crawler 入口。

    注意：
    未出現在 buy/sell 的股票不要自行補：
        buy=0
        sell=0
        net=0

    因為官方 qfiiStat 並沒有提供
    那些股票實際的 buy/sell 數值。

    normalized table 僅保存官方
    qfiiStat 實際提供且可追溯的紀錄。
    """
    buy_payload = (
        fetch_tpex_foreign_buy(
            trade_date
        )
    )

    sell_payload = (
        fetch_tpex_foreign_sell(
            trade_date
        )
    )

    records = (
        parse_tpex_foreign_payloads(
            buy_payload=buy_payload,
            sell_payload=sell_payload,
        )
    )

    normalized_date = (
        _normalize_response_date(
            buy_payload.get("date")
        )
    )

    return TpexForeignFetchResult(
        trade_date=normalized_date,
        buy_payload=buy_payload,
        sell_payload=sell_payload,
        records=records,
    )