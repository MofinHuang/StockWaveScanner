from datetime import datetime

from db.database import get_connection


def has_price_month(
    stock_id: str,
    market: str,
    year: int,
    month: int,
) -> bool:

    start_date = f"{year:04d}-{month:02d}-01"

    if month == 12:
        end_date = f"{year + 1:04d}-01-01"
    else:
        end_date = f"{year:04d}-{month + 1:02d}-01"

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM daily_prices

        WHERE stock_id = ?
          AND market = ?
          AND trade_date >= ?
          AND trade_date < ?
        """,
        (
            stock_id,
            market,
            start_date,
            end_date,
        ),
    )

    count = cursor.fetchone()[0]

    conn.close()

    return count > 0


def get_crawl_log(
    source: str,
    request_key: str,
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            source,
            request_key,
            status,
            record_count,
            error_message,
            started_at,
            finished_at

        FROM crawl_logs

        WHERE source = ?
          AND request_key = ?
        """,
        (
            source,
            request_key,
        ),
    )

    row = cursor.fetchone()

    conn.close()

    if row is None:
        return None

    return dict(row)


def crawl_success_exists(
    source: str,
    request_key: str,
) -> bool:

    log = get_crawl_log(
        source,
        request_key,
    )

    if log is None:
        return False

    return log["status"] == "SUCCESS"


def start_crawl_log(
    source: str,
    request_key: str,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO crawl_logs
        (
            source,
            request_key,
            status,
            record_count,
            error_message,
            started_at,
            finished_at
        )
        VALUES
        (
            ?,
            ?,
            'RUNNING',
            0,
            NULL,
            ?,
            NULL
        )

        ON CONFLICT(source, request_key)
        DO UPDATE SET
            status = 'RUNNING',
            record_count = 0,
            error_message = NULL,
            started_at = excluded.started_at,
            finished_at = NULL
        """,
        (
            source,
            request_key,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()

    # 部分較新的同步器會保留這個回傳值，
    # 以判斷 ERROR 時是否需要更新同一筆 crawl log。
    # 舊呼叫端忽略回傳值，因此維持向後相容。
    return request_key


def finish_crawl_success(
    source: str,
    request_key: str,
    record_count: int,
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE crawl_logs

        SET
            status = 'SUCCESS',
            record_count = ?,
            error_message = NULL,
            finished_at = ?

        WHERE source = ?
          AND request_key = ?
        """,
        (
            record_count,
            datetime.now().isoformat(),
            source,
            request_key,
        ),
    )

    conn.commit()
    conn.close()


def finish_crawl_error(
    source: str,
    request_key: str,
    error_message: str,
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE crawl_logs

        SET
            status = 'ERROR',
            error_message = ?,
            finished_at = ?

        WHERE source = ?
          AND request_key = ?
        """,
        (
            error_message,
            datetime.now().isoformat(),
            source,
            request_key,
        ),
    )

    conn.commit()
    conn.close()
    
    
def get_institutional_trades(
    stock_id: str,
    market: str,
    limit: int = 120,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            trade_date,
            foreign_buy,
            foreign_sell,
            foreign_net
        FROM institutional_trades
        WHERE stock_id = ?
          AND market = ?
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        (
            stock_id,
            market,
            limit,
        ),
    )

    rows = cursor.fetchall()
    conn.close()

    return [
        dict(row)
        for row in rows
    ]
    
    
def upsert_stock(
    stock_id: str,
    market: str,
    stock_name: str,
    is_active: int = 1,
):
    """
    新增或更新股票主檔。

    主鍵：
        (stock_id, market)

    已存在時更新：
        stock_name
        is_active
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO stocks
        (
            stock_id,
            market,
            stock_name,
            is_active
        )
        VALUES
        (
            ?, ?, ?, ?
        )

        ON CONFLICT(
            stock_id,
            market
        )
        DO UPDATE SET
            stock_name =
                excluded.stock_name,

            is_active =
                excluded.is_active
        """,
        (
            stock_id,
            market,
            stock_name,
            is_active,
        ),
    )

    conn.commit()
    conn.close()
    
    
def deactivate_market_stocks(
    market: str,
):
    """
    同步股票主檔前，
    先將該市場現有股票標記 inactive。

    後續官方目前仍存在的股票
    會再由 upsert_stock() 設回 active。

    這樣下市 / 下櫃股票不會被刪除，
    歷史資料也能保留。
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE stocks

        SET is_active = 0

        WHERE market = ?
        """,
        (
            market,
        ),
    )

    conn.commit()
    conn.close()    
    
    
def upsert_tdcc_holding(
    stock_id: str,
    data_date: str,
    large_holder_pct: float,
    retail_holder_pct: float,
    source: str = "TDCC_SHAREHOLDING",
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO tdcc_holdings
        (
            stock_id,
            data_date,
            large_holder_pct,
            retail_holder_pct,
            source,
            downloaded_at
        )
        VALUES
        (
            ?, ?, ?, ?, ?, ?
        )

        ON CONFLICT(
            stock_id,
            data_date
        )
        DO UPDATE SET
            large_holder_pct =
                excluded.large_holder_pct,

            retail_holder_pct =
                excluded.retail_holder_pct,

            source =
                excluded.source,

            downloaded_at =
                excluded.downloaded_at
        """,
        (
            stock_id,
            data_date,
            large_holder_pct,
            retail_holder_pct,
            source,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()    