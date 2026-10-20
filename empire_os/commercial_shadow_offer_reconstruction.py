"""Privacy-minimal *shadow* reconstruction of the EXISTING commercial offer book.

Uses the canonical owner's pure builder and human review projection IN MEMORY.
This code is not the producer, a refresh job, a publisher or an activation path.
No records, money, messages, source files, model weights or agent tasks change.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from empire_os.commercial_offer_book import (
    SCHEMA_VERSION as OFFER_SCHEMA,
    build_commercial_offer_book,
)
from empire_os.revenue_distribution_review import (
    REVIEW_SOURCES,
    build_human_review_queue,
)

SCHEMA = "empire.commercial_growth.shadow_offer_reconstruction.v1"
CATALOG_SCHEMA = "empire.commercial-product-catalog.v1"
DISTRIBUTION_SCHEMA = "empire.revenue_distribution.v1"
MAX_AGE_HOURS = 72
MAX_TARGETS = 5000


def _clock(value: Any, now: datetime) -> dict[str, Any]:
    if not isinstance(value, str) or not value or len(value) > 90:
        return {"state": "UNKNOWN_CLOCK", "age_hours": None}
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.utcoffset() is None:
            raise ValueError("naive source clock")
        age = (now - instant.astimezone(timezone.utc)).total_seconds() / 3600
    except (ValueError, OverflowError):
        return {"state": "INVALID_CLOCK", "age_hours": None}
    state = (
        "FUTURE_CLOCK" if age < -0.1
        else "STALE" if age > MAX_AGE_HOURS
        else "FRESH"
    )
    return {"state": state, "age_hours": round(age, 2)}


def _counts(book: Mapping[str, Any]) -> dict[str, Any]:
    records = book.get("targets")
    if not isinstance(records, list) or len(records) > MAX_TARGETS:
        raise ValueError("bounded canonical offer target list required")
    if any(not isinstance(row, Mapping) for row in records):
        raise ValueError("canonical offer target row must be mapping")
    states = dict(sorted(Counter(str(row.get("state") or "UNKNOWN") for row in records).items()))
    return {
        "target_count": len(records),
        "offer_ready_count": sum(
            row.get("state") == "OFFER_READY" and
            row.get("offer_package_ready") is True for row in records
        ),
        "state_counts": states,
        "missing_canonical_prospect_id_count": sum(
            not isinstance(row.get("canonical_prospect_id"), str)
            or not row["canonical_prospect_id"].strip() for row in records
        ),
        "verified_person_and_email_count": sum(
            row.get("person_verified") is True and row.get("email_verified") is True
            for row in records
        ),
        "source_claims_verified_buyer_demand_count": sum(
            row.get("buyer_demand_verified") is True for row in records
        ),
        "existing_thread_review_count": sum(
            row.get("contact_mode") == "EXISTING_THREAD_REVIEW" for row in records
        ),
    }


def review_shadow_offer_reconstruction(
    *,
    catalog: Mapping[str, Any],
    distribution: Mapping[str, Any],
    review_sources: Mapping[str, Any],
    previous_offer_book: Mapping[str, Any],
    now: datetime,
) -> dict[str, Any]:
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("trusted timezone-aware review clock required")
    now = now.astimezone(timezone.utc)
    if catalog.get("schema_version") != CATALOG_SCHEMA:
        raise ValueError("exact canonical catalog schema required")
    if distribution.get("schema_version") != DISTRIBUTION_SCHEMA:
        raise ValueError("exact canonical distribution schema required")
    if previous_offer_book.get("schema_version") != OFFER_SCHEMA:
        raise ValueError("exact canonical prior offer-book schema required")
    if (
        catalog.get("execution_authority") != "none"
        or distribution.get("execution_authority") != "none"
        or previous_offer_book.get("execution_authority") != "none"
    ):
        raise ValueError("source packet claims unsupported execution authority")
    if set(review_sources) != set(REVIEW_SOURCES):
        raise ValueError("exact existing owner review source names required")
    products = catalog.get("products")
    opportunities = distribution.get("opportunities")
    if (
        not isinstance(products, list) or len(products) > MAX_TARGETS
        or not isinstance(opportunities, list) or len(opportunities) > MAX_TARGETS
    ):
        raise ValueError("bounded canonical catalog and opportunity arrays required")

    source_clocks = {
        "catalog": _clock(catalog.get("generated_at"), now),
        "distribution": _clock(distribution.get("generated_at"), now),
        "previous_offer_book": _clock(previous_offer_book.get("generated_at"), now),
    }
    review_inputs = {}
    for label in REVIEW_SOURCES:
        value = review_sources[label]
        if value is not None and not isinstance(value, (Mapping, list)):
            raise ValueError("review input must be JSON mapping, array or unavailable")
        review_inputs[label] = value
        if isinstance(value, Mapping):
            stamp = value.get("generated_at") or value.get("observed_at")
        else:
            stamp = None
        source_clocks["owner_review_" + label] = _clock(stamp, now)

    # The existing owner specifies how missing sources influence review holds.
    generated = build_human_review_queue(
        {"catalog": catalog},
        review_inputs,
        opportunities,
        limit=None,
    )
    rows = generated.get("human_review_queue")
    if not isinstance(rows, list) or len(rows) > MAX_TARGETS:
        raise ValueError("bounded owner human review queue required")
    # No freshness laundering: the generated_at below is a shadow calculation
    # clock, not evidence that any upstream source was freshly observed.
    projected = build_commercial_offer_book(
        catalog=catalog,
        revenue_distribution={**distribution, "human_review_queue": rows},
        generated_at=now.isoformat(),
    )
    projected_counts = _counts(projected)
    previous_counts = _counts(previous_offer_book)
    current_blockers = list(
        label for label, data in source_clocks.items()
        if data["state"] != "FRESH"
        and label != "previous_offer_book"
    )
    refresh_required = bool(current_blockers)
    ready_catalog_count = projected.get("ready_catalog_product_count")
    if type(ready_catalog_count) is not int or ready_catalog_count < 0:
        raise ValueError("canonical ready catalog count required")

    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "SOURCE_FRESHNESS_HOLD" if refresh_required else "SHADOW_RECONSTRUCTION_ONLY",
        "result_is_shadow_not_current_commercial_authority": True,
        "recomputed_using_existing_owner_logic": True,
        "calculated_at": now.isoformat(),
        "upstream_freshness": source_clocks,
        "source_refresh_review_required": refresh_required,
        "owner_source_clocks_missing_or_stale": current_blockers,
        "historical_offer_book": previous_counts,
        "in_memory_reconstructed_offer_book": projected_counts,
        "reconstructed_ready_catalog_product_count": ready_catalog_count,
        "target_count_delta_not_a_new_leads_count": (
            projected_counts["target_count"] - previous_counts["target_count"]
        ),
        "readiness_gap_priority": [
            "VALIDATE_CURRENT_REVENUE_DISTRIBUTION_AND_REVIEW_SOURCE_PROVENANCE",
            "RECONCILE_FIRST_PARTY_CANONICAL_IDENTITIES_WITH_SOURCE_OWNER",
            "VERIFY_PERSON_CONTACT_AND_BUYER_DEMAND_IN_EXISTING_GOVERNED_PROCESS",
            "REVIEW_PRODUCT_TERMS_AND_FULFILLMENT_WITH_CATALOG_OWNER",
            "USE_CURRENT_ORIGINAL_BUYER_REPLY_AND_CAPACITY_PROOF_BEFORE_OUTBOUND",
        ],
        "execution_authority": "none",
        "outbound_authorized": False,
        "agent_tasks_created": False,
        "canonical_files_written": False,
        "database_writes": False,
        "payment_execution": False,
        "crm_mutations": False,
        "model_training": False,
        "website_changed": False,
    }
