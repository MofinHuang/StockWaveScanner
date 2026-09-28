from __future__ import annotations

import os
import sys
from pathlib import Path

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)

        if callable(reconfigure):
            try:
                reconfigure(
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception:
                pass


def load_dev_credentials() -> tuple[str, str]:
    load_dotenv(ENV_FILE)

    url = os.getenv(
        "TURSO_DEV_DATABASE_URL",
        "",
    ).strip()

    token = os.getenv(
        "TURSO_DEV_AUTH_TOKEN",
        "",
    ).strip()

    if not url:
        raise RuntimeError(
            "TURSO_DEV_DATABASE_URL is missing from .env"
        )

    if not token:
        raise RuntimeError(
            "TURSO_DEV_AUTH_TOKEN is missing from .env"
        )

    lower_url = url.lower()

    if "stockwave-dev" not in lower_url:
        raise RuntimeError(
            "SAFETY STOP: database is not stockwave-dev"
        )

    if "stockwave-prod" in lower_url:
        raise RuntimeError(
            "SAFETY STOP: PROD database detected"
        )

    return url, token


def index_exists(
    conn,
    index_name: str,
) -> bool:

    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'index'
          AND name = ?
        """,
        (index_name,),
    ).fetchone()

    return row is not None


def main() -> int:

    configure_console()

    print("=" * 70)
    print("StockWaveScanner V3 - Fix Analyst Source Index")
    print("=" * 70)

    try:
        url, token = load_dev_credentials()

        print()
        print("Environment : DEV")
        print("Database    : stockwave-dev")
        print("PROD Access : DISABLED")

        conn = libsql.connect(
            database=url,
            auth_token=token,
        )

        try:
            test = conn.execute(
                "SELECT 1"
            ).fetchone()

            if not test or test[0] != 1:
                raise RuntimeError(
                    "Turso DEV connection validation failed"
                )

            print()
            print("[PASS] Turso DEV connection")

            conn.execute("BEGIN")

            try:
                conn.execute(
                    """
                    DROP INDEX IF EXISTS
                        idx_analyst_source_url_unique
                    """
                )

                conn.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS
                        idx_analyst_source_analyst_url_unique
                    ON analyst_source (
                        analyst_id,
                        source_url
                    )
                    """
                )

                conn.commit()

            except BaseException:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise

            if index_exists(
                conn,
                "idx_analyst_source_url_unique",
            ):
                raise RuntimeError(
                    "Old unique source_url index still exists"
                )

            if not index_exists(
                conn,
                "idx_analyst_source_analyst_url_unique",
            ):
                raise RuntimeError(
                    "New analyst + source_url unique index missing"
                )

            print()
            print(
                "[PASS] Removed global source_url unique index"
            )

            print(
                "[PASS] Added analyst_id + source_url unique index"
            )

        finally:
            conn.close()

        print()
        print("=" * 70)
        print("V3 ANALYST SOURCE INDEX FIX OK")
        print("=" * 70)
        print()
        print("No PROD database was accessed.")

        return 0

    except Exception as exc:

        print()
        print("=" * 70)
        print("ERROR")
        print("=" * 70)
        print(str(exc))
        print()
        print("No PROD database was accessed.")

        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )