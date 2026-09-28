from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import libsql
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

YOUTUBE_FEED_URL = (
    "https://www.youtube.com/feeds/videos.xml"
    "?channel_id={channel_id}"
)

ATOM_NS = "http://www.w3.org/2005/Atom"
YT_NS = "http://www.youtube.com/xml/schemas/2015"
MEDIA_NS = "http://search.yahoo.com/mrss/"


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


def fetch_text(
    url: str,
) -> str:

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "StockWaveScanner/3.0"
            )
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:

        raw = response.read()

    return raw.decode(
        "utf-8",
        errors="replace",
    )


def text_or_none(
    element,
    path: str,
    namespaces: dict,
) -> str | None:

    node = element.find(
        path,
        namespaces,
    )

    if node is None:
        return None

    value = (
        node.text
        or ""
    ).strip()

    return (
        value
        if value
        else None
    )


def build_content_hash(
    analyst_id: str,
    title: str,
    published_at: str | None,
) -> str:

    raw = (
        f"{analyst_id}|"
        f"{title}|"
        f"{published_at or ''}"
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def get_youtube_sources(
    conn,
) -> list[tuple]:

    return conn.execute(
        """
        SELECT
            source_id,
            analyst_id,
            source_name,
            source_account_id

        FROM analyst_source

        WHERE source_type = 'YOUTUBE'
          AND is_enabled = 1
          AND is_official = 1
          AND source_account_id IS NOT NULL
          AND TRIM(source_account_id) <> ''

        ORDER BY
            analyst_id,
            source_priority,
            source_id
        """
    ).fetchall()


def parse_feed(
    xml_text: str,
) -> list[dict]:

    root = ET.fromstring(
        xml_text
    )

    namespaces = {
        "atom": ATOM_NS,
        "yt": YT_NS,
        "media": MEDIA_NS,
    }

    results: list[dict] = []

    entries = root.findall(
        "atom:entry",
        namespaces,
    )

    for entry in entries:

        video_id = text_or_none(
            entry,
            "yt:videoId",
            namespaces,
        )

        channel_id = text_or_none(
            entry,
            "yt:channelId",
            namespaces,
        )

        title = text_or_none(
            entry,
            "atom:title",
            namespaces,
        )

        published_at = text_or_none(
            entry,
            "atom:published",
            namespaces,
        )

        author = text_or_none(
            entry,
            "atom:author/atom:name",
            namespaces,
        )

        description = text_or_none(
            entry,
            "media:group/media:description",
            namespaces,
        )

        link_node = entry.find(
            "atom:link[@rel='alternate']",
            namespaces,
        )

        source_url = None

        if link_node is not None:
            source_url = (
                link_node.attrib.get(
                    "href",
                    ""
                )
                .strip()
            )

        if not source_url and video_id:
            source_url = (
                "https://www.youtube.com/watch?v="
                f"{video_id}"
            )

        if not video_id:
            continue

        if not title:
            continue

        if not source_url:
            continue

        results.append(
            {
                "video_id": video_id,
                "channel_id": channel_id,
                "title": title,
                "published_at": published_at,
                "author": author,
                "description": description,
                "source_url": source_url,
            }
        )

    return results


def upsert_comment(
    conn,
    source_id: str,
    analyst_id: str,
    item: dict,
) -> tuple[bool, str]:

    video_id = item["video_id"]

    comment_id = (
        "YT_"
        f"{analyst_id}_"
        f"{video_id}"
    )

    content_hash = build_content_hash(
        analyst_id=analyst_id,
        title=item["title"],
        published_at=item["published_at"],
    )

    existing = conn.execute(
        """
        SELECT comment_id

        FROM analyst_comment

        WHERE source_id = ?
          AND external_content_id = ?
        """,
        (
            source_id,
            video_id,
        ),
    ).fetchone()

    is_new = (
        existing is None
    )

    conn.execute(
        """
        INSERT INTO analyst_comment (
            comment_id,
            analyst_id,
            source_id,
            external_content_id,
            source_type,
            source_url,
            source_title,
            source_published_at,
            source_author,
            summary_text,
            summary_type,
            content_hash,
            canonical_content_key,
            copyright_mode,
            attribution_required,
            review_status,
            publish_status,
            created_at,
            updated_at
        )
        VALUES (
            ?,
            ?,
            ?,
            ?,
            'YOUTUBE',
            ?,
            ?,
            ?,
            ?,
            NULL,
            'SYSTEM_SUMMARY',
            ?,
            NULL,
            'SUMMARY_ONLY',
            1,
            'AUTO',
            'READY',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )

        ON CONFLICT(comment_id)
        DO UPDATE SET
            source_url = excluded.source_url,
            source_title = excluded.source_title,
            source_published_at = excluded.source_published_at,
            source_author = excluded.source_author,
            content_hash = excluded.content_hash,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            comment_id,
            analyst_id,
            source_id,
            video_id,
            item["source_url"],
            item["title"],
            item["published_at"],
            item["author"],
            content_hash,
        ),
    )

    return (
        is_new,
        comment_id,
    )


def sync_source(
    conn,
    source_id: str,
    analyst_id: str,
    source_name: str,
    channel_id: str,
) -> tuple[int, int]:

    feed_url = YOUTUBE_FEED_URL.format(
        channel_id=channel_id
    )

    print()
    print(
        f"[SYNC] {analyst_id} | {source_name}"
    )

    print(
        f"       channel={channel_id}"
    )

    xml_text = fetch_text(
        feed_url
    )

    items = parse_feed(
        xml_text
    )

    inserted = 0
    updated = 0

    for item in items:

        is_new, comment_id = (
            upsert_comment(
                conn=conn,
                source_id=source_id,
                analyst_id=analyst_id,
                item=item,
            )
        )

        if is_new:
            inserted += 1
            status = "NEW"
        else:
            updated += 1
            status = "EXISTS"

        print(
            f"       [{status}] "
            f"{item['published_at']} "
            f"| {comment_id} "
            f"| {item['title']}"
        )

    return (
        inserted,
        updated,
    )


def print_summary(
    conn,
) -> None:

    print()
    print("=" * 70)
    print("V3 ANALYST YOUTUBE SUMMARY")
    print("=" * 70)

    rows = conn.execute(
        """
        SELECT
            m.analyst_id,
            m.analyst_name,
            COUNT(c.comment_id)

        FROM analyst_master m

        LEFT JOIN analyst_comment c
          ON c.analyst_id = m.analyst_id
         AND c.source_type = 'YOUTUBE'

        GROUP BY
            m.analyst_id,
            m.analyst_name

        ORDER BY
            m.sort_order,
            m.analyst_id
        """
    ).fetchall()

    for row in rows:

        print(
            f"{row[0]:<6} "
            f"| {row[1]:<8} "
            f"| youtube_comments={row[2]}"
        )


def main() -> int:

    configure_console()

    print("=" * 70)
    print("StockWaveScanner V3 - Analyst YouTube Sync")
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
            print(
                "[PASS] Turso DEV connection"
            )

            sources = get_youtube_sources(
                conn
            )

            if not sources:
                raise RuntimeError(
                    "No enabled official YouTube sources found"
                )

            print()
            print(
                f"YouTube sources: {len(sources)}"
            )

            total_inserted = 0
            total_updated = 0

            conn.execute(
                "BEGIN"
            )

            try:

                for row in sources:

                    (
                        source_id,
                        analyst_id,
                        source_name,
                        channel_id,
                    ) = row

                    inserted, updated = (
                        sync_source(
                            conn=conn,
                            source_id=source_id,
                            analyst_id=analyst_id,
                            source_name=source_name,
                            channel_id=channel_id,
                        )
                    )

                    total_inserted += inserted
                    total_updated += updated

                conn.commit()

            except BaseException:

                try:
                    conn.rollback()
                except Exception:
                    pass

                raise

            print()
            print(
                f"[PASS] New comments     : {total_inserted}"
            )

            print(
                f"[PASS] Existing updated: {total_updated}"
            )

            print_summary(
                conn
            )

        finally:

            conn.close()

        print()
        print("=" * 70)
        print("V3 ANALYST YOUTUBE SYNC OK")
        print("=" * 70)

        print()
        print(
            "Metadata only."
        )

        print(
            "No transcript was downloaded."
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