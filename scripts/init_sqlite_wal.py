import sqlite3

from config import DATABASE_PATH


def main():

    print(
        "================================"
    )

    print(
        "SQLite WAL 初始化"
    )

    print(
        "================================"
    )

    conn = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )

    try:

        conn.execute(
            "PRAGMA busy_timeout=30000;"
        )

        row = conn.execute(
            "PRAGMA journal_mode=WAL;"
        ).fetchone()

        journal_mode = (
            row[0]
            if row
            else "UNKNOWN"
        )

        print(
            f"journal_mode："
            f"{journal_mode}"
        )

        print(
            "[OK] SQLite WAL 初始化完成"
        )

    finally:

        conn.close()


if __name__ == "__main__":
    main()