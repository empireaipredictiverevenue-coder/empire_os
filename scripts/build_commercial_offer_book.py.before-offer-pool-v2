#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from empire_os.commercial_offer_book import (
    build_commercial_offer_book,
)
from empire_os.revenue_distribution_review import (
    REVIEW_SOURCES,
    build_human_review_queue,
)


ROOT = Path("/srv/empire_os")

CATALOG = (
    ROOT
    / "runtime/commercial_catalog/latest.json"
)

DISTRIBUTION = (
    ROOT
    / "runtime/revenue_distribution/latest.json"
)

OUTPUT = (
    ROOT
    / "runtime/predictive_revenue"
    / "commercial_offer_book"
    / "latest.json"
)


def read(path: Path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def main() -> int:
    if not CATALOG.exists():
        print("BUILD=BLOCKED")
        print("REASON=commercial_catalog_missing")
        return 2

    if not DISTRIBUTION.exists():
        print("BUILD=BLOCKED")
        print("REASON=revenue_distribution_missing")
        return 3

    catalog = read(CATALOG)
    distribution = read(DISTRIBUTION)

    review = {}

    for key, relative in REVIEW_SOURCES.items():
        path = ROOT / relative

        if not path.exists():
            review[key] = None
            continue

        try:
            review[key] = read(path)
        except Exception:
            review[key] = None

    opportunities = distribution.get(
        "opportunities"
    )

    opportunities = (
        opportunities
        if isinstance(opportunities, list)
        else []
    )

    full_review = build_human_review_queue(
        {
            "catalog": catalog,
        },
        review,
        opportunities,
        limit=None,
    )

    expanded_distribution = dict(
        distribution
    )

    expanded_distribution[
        "human_review_queue"
    ] = full_review.get(
        "human_review_queue"
    ) or []

    expanded_distribution[
        "review_candidate_count"
    ] = full_review.get(
        "review_candidate_count"
    )

    book = build_commercial_offer_book(
        catalog=catalog,
        revenue_distribution=
            expanded_distribution,
    )

    book[
        "canonical_review_candidate_count"
    ] = full_review.get(
        "review_candidate_count"
    )

    book[
        "excluded_suppression_count"
    ] = full_review.get(
        "excluded_suppression_count"
    )

    book[
        "canonical_review_blockers"
    ] = full_review.get(
        "review_blockers"
    ) or []

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = OUTPUT.with_suffix(
        ".json.tmp"
    )

    tmp.write_text(
        json.dumps(
            book,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(OUTPUT)

    print(
        "SCHEMA=",
        book["schema_version"],
    )

    print(
        "CANONICAL_REVIEW_CANDIDATES=",
        book.get(
            "canonical_review_candidate_count"
        ),
    )

    print(
        "READY_CATALOG_PRODUCTS=",
        book[
            "ready_catalog_product_count"
        ],
    )

    print(
        "REVIEW_TARGETS=",
        book["review_target_count"],
    )

    print(
        "OFFER_READY=",
        book["offer_ready_count"],
    )

    print(
        "EXCLUDED_SUPPRESSIONS=",
        book.get(
            "excluded_suppression_count"
        ),
    )

    print(
        "EXECUTION_AUTHORITY=",
        book["execution_authority"],
    )

    print("OUTPUT=", OUTPUT)

    print()
    print("=== OFFER READY ===")

    for row in book["offer_ready"]:
        products = ", ".join(
            (
                f'{p.get("product_code")}'
                f'=${(p.get("amount_cents") or 0)/100:.2f}'
                f' {p.get("currency")}'
                f'/{p.get("unit")}'
            )
            for p in row["products"]
        )

        print(
            row.get("company"),
            "|",
            row.get("domain"),
            "| person=",
            row.get("person_name"),
            "| email_verified=",
            row.get("email_verified"),
            "| context=",
            row.get("contact_mode"),
            "| demand=",
            row.get("demand_state"),
            "| products=",
            products,
        )

    print()
    print("=== STATE COUNTS ===")

    counts = {}

    for row in book["targets"]:
        state = row.get("state")
        counts[state] = (
            counts.get(state, 0) + 1
        )

    for key in sorted(counts):
        print(key, counts[key])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
