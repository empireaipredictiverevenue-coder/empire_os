#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from empire_os.opportunity_radar import (
    refresh_opportunity_radar,
)
from empire_os.sell_now_book import (
    build_sell_now_book,
    write_sell_now_book,
)


ROOT = Path("/srv/empire_os")
CATALOG = ROOT / "runtime/commercial_catalog/latest.json"
OUTPUT = (
    ROOT
    / "runtime/predictive_revenue/sell_now/latest.json"
)


def main() -> int:
    if not CATALOG.exists():
        print("SELL_NOW=BLOCKED")
        print("REASON=commercial_catalog_missing")
        return 2

    catalog = json.loads(
        CATALOG.read_text(encoding="utf-8")
    )

    radar = refresh_opportunity_radar(ROOT)

    if not isinstance(radar, dict):
        print("SELL_NOW=BLOCKED")
        print("REASON=opportunity_radar_invalid")
        return 3

    book = build_sell_now_book(
        catalog=catalog,
        radar=radar,
    )

    write_sell_now_book(book, OUTPUT)

    print("SCHEMA=", book["schema_version"])
    print(
        "RADAR_CANDIDATES=",
        book["radar_candidate_count"],
    )
    print(
        "READY_PRODUCTS=",
        book["ready_product_count"],
    )
    print(
        "SELL_NOW_COUNT=",
        book["sell_now_count"],
    )
    print(
        "ACTUAL_REVENUE=",
        book["actual_revenue"],
    )
    print(
        "EXECUTION_AUTHORITY=",
        book["execution_authority"],
    )
    print("OUTPUT=", OUTPUT)

    print()
    print("=== TOP SELL_NOW ===")

    for row in book["sell_now"][:40]:
        opportunity = row["opportunity"]

        title = (
            opportunity.get("title")
            or opportunity.get("name")
            or opportunity.get("summary")
            or row["opportunity_id"]
        )

        print(
            row["fit_scope"].upper(),
            "|",
            str(title)[:100],
            "=>",
            row["product_code"],
            "|",
            row["product_name"],
            "|",
            row["billing_model"],
            "|",
            row["currency"],
            "|",
            row["fit_reason"],
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
