from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

OUTPUT_FILE = (
    ROOT
    / "docs"
    / "data"
    / "latest"
    / "analysts.json"
)

TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def configure_console() -> None:
    for stream in (
        sys.stdout,
        sys.stderr,
    ):
        reconfigure = getattr(
            stream,
            "reconfigure",
            None,
        )

        if callable(reconfigure):
            try:
                reconfigure(
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception:
                pass


def load_dev_credentials() -> tuple[str, str]:
    load_dotenv(
        ENV_FILE
    )

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

    return (
        url,
        token,
    )


def parse_datetime(
    value: str | None,
) -> datetime | None:

    if not value:
        return None

    value = value.strip()

    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None


def to_taipei_iso(
    value: str | None,
) -> str | None:

    dt = parse_datetime(
        value
    )

    if dt is None:
        return value

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    return (
        dt.astimezone(
            TAIPEI_TZ
        )
        .isoformat(
            timespec="seconds"
        )
    )


def get_analysts(
    conn,
) -> list[dict]:

    rows = conn.execute(
        """
        SELECT
            analyst_id,
            analyst_name,
            display_name,
            organization_name,
            sort_order

        FROM analyst_master

        WHERE active = 1

        ORDER BY
            sort_order,
            analyst_id
        """
    ).fetchall()

    result = []

    for row in rows:

        analyst_id = row[0]

        sources = get_sources(
            conn,
            analyst_id,
        )

        comments = get_comments(
            conn,
            analyst_id,
        )

        result.append(
            {
                "analyst_id": analyst_id,
                "analyst_name": row[1],
                "display_name": row[2],
                "organization_name": row[3],
                "sort_order": row[4],
                "sources": sources,
                "comment_count": len(
                    comments
                ),
                "comments": comments,
            }
        )

    return result


def get_sources(
    conn,
    analyst_id: str,
) -> list[dict]:

    rows = conn.execute(
        """
        SELECT
            source_id,
            source_type,
            source_name,
            source_url,
            source_account_id,
            source_priority,
            is_official

        FROM analyst_source

        WHERE analyst_id = ?
          AND is_enabled = 1

        ORDER BY
            source_priority,
            source_id
        """,
        (
            analyst_id,
        ),
    ).fetchall()

    result = []

    for row in rows:

        result.append(
            {
                "source_id": row[0],
                "source_type": row[1],
                "source_name": row[2],
                "source_url": row[3],
                "source_account_id": row[4],
                "source_priority": row[5],
                "is_official": bool(
                    row[6]
                ),
            }
        )

    return result


def get_comments(
    conn,
    analyst_id: str,
) -> list[dict]:

    rows = conn.execute(
        """
        SELECT
            c.comment_id,
            c.source_id,
            c.external_content_id,
            c.source_type,
            c.source_url,
            c.source_title,
            c.source_published_at,
            c.source_author,
            c.summary_text,
            c.summary_type,
            c.review_status,
            c.publish_status,
            s.source_name

        FROM analyst_comment c

        INNER JOIN analyst_source s
            ON s.source_id = c.source_id

        WHERE c.analyst_id = ?
          AND c.publish_status = 'READY'

        ORDER BY
            c.source_published_at DESC,
            c.comment_id DESC
        """,
        (
            analyst_id,
        ),
    ).fetchall()

    result = []

    for row in rows:

        published_at_utc = row[6]

        result.append(
            {
                "comment_id": row[0],
                "source_id": row[1],
                "external_content_id": row[2],
                "source_type": row[3],
                "source_name": row[12],
                "source_url": row[4],
                "title": row[5],
                "published_at": (
                    published_at_utc
                ),
                "published_at_tw": (
                    to_taipei_iso(
                        published_at_utc
                    )
                ),
                "source_author": row[7],
                "summary": row[8],
                "summary_type": row[9],
                "review_status": row[10],
            }
        )

    return result


def build_payload(
    conn,
) -> dict:

    analysts = get_analysts(
        conn
    )

    total_comments = sum(
        item["comment_count"]
        for item in analysts
    )

    generated_at = (
        datetime.now(
            TAIPEI_TZ
        )
        .isoformat(
            timespec="seconds"
        )
    )

    return {
        "schema_version": "3.0",
        "generated_at": generated_at,
        "timezone": "Asia/Taipei",
        "environment": "DEV",
        "analyst_count": len(
            analysts
        ),
        "comment_count": total_comments,
        "analysts": analysts,
    }


def write_json(
    payload: dict,
) -> None:

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write(
            "\n"
        )


def main() -> int:

    configure_console()

    print("=" * 70)
    print(
        "StockWaveScanner V3 - Analyst Export"
    )
    print("=" * 70)

    try:

        url, token = (
            load_dev_credentials()
        )

        print()
        print(
            "Environment : DEV"
        )
        print(
            "Database    : stockwave-dev"
        )
        print(
            "PROD Access : DISABLED"
        )

        conn = libsql.connect(
            database=url,
            auth_token=token,
        )

        try:

            test = conn.execute(
                "SELECT 1"
            ).fetchone()

            if (
                not test
                or
                test[0] != 1
            ):
                raise RuntimeError(
                    "Turso DEV connection validation failed"
                )

            print()
            print(
                "[PASS] Turso DEV connection"
            )

            payload = build_payload(
                conn
            )

        finally:
            conn.close()

        write_json(
            payload
        )

        print()
        print(
            f"[PASS] Analysts : "
            f"{payload['analyst_count']}"
        )

        print(
            f"[PASS] Comments : "
            f"{payload['comment_count']}"
        )

        print(
            f"[PASS] Output   : "
            f"{OUTPUT_FILE.relative_to(ROOT)}"
        )

        print()
        print("=" * 70)
        print(
            "V3 ANALYST EXPORT OK"
        )
        print("=" * 70)

        print()
        print(
            "No transcript was exported."
        )

        print(
            "No AI summary was generated."
        )

        print(
            "No PROD database was accessed."
        )

        return 0

    except Exception as exc:

        print()
        print("=" * 70)
        print("ERROR")
        print("=" * 70)

        print(
            str(exc)
        )

        print()
        print(
            "No PROD database was accessed."
        )

        return 1


if __name__ == "__main__":

    sys.exit(
        main()
    )