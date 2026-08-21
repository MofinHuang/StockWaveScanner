import sqlite3

from config import DATABASE_PATH


def get_connection():
    """
    StockWaveScanner 共用 SQLite connection。

    注意：
    journal_mode=WAL 不應在每次連線時重設，
    因為切換 journal mode 本身可能需要資料庫鎖。

    每條 connection 只設定：
    - sqlite3.Row
    - busy_timeout
    - foreign_keys
    """

    conn = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA busy_timeout=30000;"
    )

    conn.execute(
        "PRAGMA foreign_keys=ON;"
    )

    return conn