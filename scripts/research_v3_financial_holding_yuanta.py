from __future__ import annotations

import sys

import requests
from lxml import html


URL = "https://www.yuanta.com/TW/IR/Financials/Monthly-Earnings"


def configure_console():

    for stream in (sys.stdout, sys.stderr):

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


def clean_text(value: str) -> str:

    return " ".join(
        value.split()
    )


def main():

    configure_console()

    print("=" * 70)
    print("StockWaveScanner V3 - Yuanta Monthly Earnings Parser Research")
    print("=" * 70)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/154 Safari/537.36"
        )
    }

    response = requests.get(
        URL,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()
    response.encoding = "utf-8"

    root = html.fromstring(
        response.text
    )

    targets = [
        "稅後盈餘",
        "累積稅後盈餘",
        "49,941",
    ]

    for target in targets:

        print()
        print("=" * 70)
        print(f"TARGET: {target}")
        print("=" * 70)

        nodes = root.xpath(
            f"//*[contains(text(), '{target}')]"
        )

        print(
            f"MATCH COUNT: {len(nodes)}"
        )

        for index, node in enumerate(nodes[:10]):

            print()
            print(
                f"--- MATCH {index + 1} ---"
            )

            print(
                f"TAG   : {node.tag}"
            )

            print(
                f"CLASS : {node.get('class')}"
            )

            own_text = clean_text(
                node.text_content()
            )

            print(
                f"TEXT  : {own_text[:500]}"
            )

            parent = node.getparent()

            if parent is not None:

                print()
                print("PARENT:")

                print(
                    clean_text(
                        parent.text_content()
                    )[:1500]
                )

            grandparent = (
                parent.getparent()
                if parent is not None
                else None
            )

            if grandparent is not None:

                print()
                print("GRANDPARENT:")

                print(
                    clean_text(
                        grandparent.text_content()
                    )[:3000]
                )

    print()
    print("=" * 70)
    print("RESEARCH FINISHED")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )