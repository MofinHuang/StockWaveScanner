from db.database import get_connection


def main():

    print("================================")
    print("初始化 tdcc_holdings")
    print("================================")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tdcc_holdings
        (
            stock_id TEXT NOT NULL,

            data_date TEXT NOT NULL,

            large_holder_pct REAL NOT NULL,
            retail_holder_pct REAL NOT NULL,

            source TEXT NOT NULL,
            downloaded_at TEXT NOT NULL,

            PRIMARY KEY
            (
                stock_id,
                data_date
            )
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_tdcc_holdings_stock_date
        ON tdcc_holdings
        (
            stock_id,
            data_date DESC
        )
        """
    )

    conn.commit()
    conn.close()

    print(
        "[OK] tdcc_holdings 已就緒"
    )


if __name__ == "__main__":
    main()