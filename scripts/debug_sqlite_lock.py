import sqlite3

from config import DATABASE_PATH


def main():

    print(
        "================================"
    )
    print(
        "SQLite Lock 診斷"
    )
    print(
        "================================"
    )

    # =================================
    # 1. 一般讀取測試
    # =================================

    print()
    print(
        "[1] READ 測試"
    )

    conn = sqlite3.connect(
        DATABASE_PATH,
        timeout=5,
    )

    try:

        journal_mode = conn.execute(
            "PRAGMA journal_mode;"
        ).fetchone()[0]

        print(
            f"journal_mode：{journal_mode}"
        )

        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM crawl_logs
            """
        ).fetchone()[0]

        print(
            f"[OK] READ 成功，"
            f"crawl_logs={count}"
        )

    except Exception as ex:

        print(
            f"[ERROR] READ 失敗：{ex}"
        )

    finally:

        conn.close()

    # =================================
    # 2. Write lock 測試
    #
    # BEGIN IMMEDIATE 只取得寫入權，
    # 隨即 ROLLBACK，不修改任何資料。
    # =================================

    print()
    print(
        "[2] WRITE LOCK 測試"
    )

    conn = sqlite3.connect(
        DATABASE_PATH,
        timeout=5,
    )

    try:

        conn.execute(
            "PRAGMA busy_timeout=5000;"
        )

        conn.execute(
            "BEGIN IMMEDIATE;"
        )

        print(
            "[OK] 成功取得 SQLite write lock"
        )

        conn.rollback()

    except Exception as ex:

        print(
            f"[ERROR] 無法取得 write lock：{ex}"
        )

    finally:

        conn.close()

    # =================================
    # 3. DB integrity
    # =================================

    print()
    print(
        "[3] quick_check"
    )

    conn = sqlite3.connect(
        DATABASE_PATH,
        timeout=5,
    )

    try:

        result = conn.execute(
            "PRAGMA quick_check;"
        ).fetchone()[0]

        print(
            f"quick_check：{result}"
        )

    except Exception as ex:

        print(
            f"[ERROR] quick_check：{ex}"
        )

    finally:

        conn.close()


if __name__ == "__main__":
    main()