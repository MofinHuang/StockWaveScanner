import os
import sys
from pathlib import Path

import libsql
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent

load_dotenv(
    BASE_DIR / ".env"
)


def test_connection(
    environment_name: str,
    database_url: str,
    auth_token: str,
):
    if not database_url:
        raise RuntimeError(
            f"{environment_name}: 找不到 Database URL"
        )

    if not auth_token:
        raise RuntimeError(
            f"{environment_name}: 找不到 Auth Token"
        )

    print(
        f"Connecting to "
        f"{environment_name} ..."
    )

    conn = None

    try:
        conn = libsql.connect(
            database=database_url,
            auth_token=auth_token,
        )

        row = conn.execute(
            "SELECT 1"
        ).fetchone()

        if (
            row is None
            or row[0] != 1
        ):
            raise RuntimeError(
                f"{environment_name}: "
                f"SELECT 1 驗證失敗"
            )

        print(
            f"{environment_name}: CONNECTION OK"
        )
        print(
            f"{environment_name}: SELECT 1 = 1"
        )

    finally:
        if conn is not None:
            conn.close()

    print()


def main():
    print(
        f"Python: "
        f"{sys.version.split()[0]}"
    )
    print()

    test_connection(
        environment_name="DEV",
        database_url=os.getenv(
            "TURSO_DEV_DATABASE_URL"
        ),
        auth_token=os.getenv(
            "TURSO_DEV_AUTH_TOKEN"
        ),
    )

    test_connection(
        environment_name="PROD",
        database_url=os.getenv(
            "TURSO_PROD_DATABASE_URL"
        ),
        auth_token=os.getenv(
            "TURSO_PROD_AUTH_TOKEN"
        ),
    )

    print(
        "================================"
    )
    print(
        "TURSO DEV / PROD CONNECTION OK"
    )
    print(
        "================================"
    )


if __name__ == "__main__":
    main()