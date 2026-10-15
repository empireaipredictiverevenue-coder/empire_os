"""Bounded Planning Data geographic discovery for Construction Signals.

Selects *sampled* brownfield record IDs in one official LPA boundary and
re-fetches their official entity details. No general crawler or outbound jobs.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping
from urllib.parse import urlencode

from empire_os.data_exchange_construction import (
    build_construction_preview, normalise_official_brownfield_entities,
)

SOURCE_HOST = "https://www.planning.data.gov.uk"
AUTHORITY = {
    "manchester": {"lpa_entity": 626027, "organisation_entity": 207},
    "liverpool": {"lpa_entity": 626048, "organisation_entity": 202},
}
MAX_DISCOVERY_ROWS = 5
MAX_OFFSET = 1000


def discover_official_brownfield_sample(
    *,
    authority: str,
    limit: int,
    offset: int,
    fetch_listing: Callable[[str], Any],
    fetch_entity: Callable[[str], Any],
    observed_at: datetime,
) -> dict[str, Any]:
    if authority not in AUTHORITY:
        raise ValueError("authority is not in approved pilot scope")
    if type(limit) is not int or not 1 <= limit <= MAX_DISCOVERY_ROWS:
        raise ValueError("limit must be within approved bounds")
    if type(offset) is not int or not 0 <= offset <= MAX_OFFSET:
        raise ValueError("offset out of approved bounds")
    selected = AUTHORITY[authority]
    params = [
        ("dataset", "brownfield-land"),
        ("geometry_entity", str(selected["lpa_entity"])),
        ("geometry_relation", "within"),
        ("limit", str(limit)),
        ("offset", str(offset)),
        ("field", "entity"),
        ("field", "dataset"),
    ]
    listing_url = SOURCE_HOST + "/entity.json?" + urlencode(params)
    result = fetch_listing(listing_url)
    if not isinstance(result, Mapping):
        raise ValueError("official discovery listing malformed")
    total = result.get("count")
    entities = result.get("entities")
    if (
        type(total) is not int or total < 0
        or not isinstance(entities, list)
        or not 1 <= len(entities) <= limit
        or total < offset + len(entities)
    ):
        raise ValueError("official discovery pagination unverified")
    ids: list[int] = []
    for entity in entities:
        if (
            not isinstance(entity, Mapping)
            or entity.get("dataset") != "brownfield-land"
            or type(entity.get("entity")) is not int
            or entity["entity"] <= 0
        ):
            raise ValueError("official discovery entity identity invalid")
        ids.append(entity["entity"])
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate official discovery entity")
    def verify_entity(url: str) -> Mapping[str, Any]:
        entity = fetch_entity(url)
        if (
            not isinstance(entity, Mapping)
            or entity.get("organisation-entity") != selected["organisation_entity"]
        ):
            raise ValueError("official organisation not in selected pilot area")
        return entity
    raw_rows = normalise_official_brownfield_entities(
        ids, fetch_json=verify_entity, observed_at=observed_at,
    )
    review = build_construction_preview(raw_rows, observed_at=observed_at)
    if review["dataset_record_count"] != len(ids) or review["rejected_counts"]:
        raise ValueError("official discovery sample failed source review")
    return {
        "schema_version": "empire.data_exchange.discovery.v1",
        "mode": "OBSERVE",
        "source": "gb_planning_data",
        "source_dataset": "brownfield-land",
        "pilot_authority": authority,
        "lpa_entity": selected["lpa_entity"],
        "listing_url": listing_url,
        "total_geographic_matches_reported": total,
        "sample_offset": offset,
        "sample_count": len(ids),
        "sample_is_complete": offset == 0 and len(ids) == total,
        "sample_coverage_status": "PARTIAL_SAMPLE" if offset + len(ids) < total or offset > 0 else "PAGE_RANGE_ONLY",
        "preview": review,
        "commercial_readiness": "HOLD_RIGHTS_AND_BUYER_VALIDATION",
        "customer_delivery_enabled": False,
        "data_resale_authorized": False,
        "outbound_enabled": False,
        "payment_execution": False,
        "production_writes": False,
        "execution_authority": "NONE",
    }
