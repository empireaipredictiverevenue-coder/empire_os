"""NYC construction data-product commercial proof gates (read-only).

Consumes existing owner-issued provenance, internal catalogue and market summary;
does not query the DOB API, assert reuse rights, discover people, or sell anything.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Mapping
import re

SCHEMA = "empire.a2a.nyc_permit_evidence_preflight.v1"
PRODUCT = "nyc_permit_project_verification"
_DATASETS = {
    "dob_now_filings": "w9ak-ipjd",
    "dob_now_initial_permits": "rbx6-tga4",
    "dcp_pluto": "64uk-42ks",
    "oti_building_footprints": "5zhs-2jue",
}
_HASH = re.compile(r"^[0-9a-f]{64}$")


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else None


def inspect_nyc_pilot(
    *,
    report: Mapping[str, Any],
    report_sha256: str,
    provenance: Mapping[str, Any],
    catalogue: Mapping[str, Any],
    revenue_gps: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return strict, claim-limited status and next-owner research tasks."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("aware_time_required")
    now = now.astimezone(timezone.utc)
    if not all(isinstance(x, Mapping) for x in (report, provenance, catalogue, revenue_gps)):
        raise ValueError("invalid_evidence_document_type")
    if not isinstance(report_sha256, str) or not _HASH.fullmatch(report_sha256):
        raise ValueError("invalid_digest")
    if report.get("schema") != "empire.permit_property_three_agency_evidence.v1":
        raise ValueError("unsupported_nyc_permit_source_schema")
    if provenance.get("schema") != "empire.original_derived_three_agency_receipt.v1":
        raise ValueError("unsupported_provenance_schema")
    if catalogue.get("schema_version") != "empire.data_brokerage.internal_product_catalog.v1":
        raise ValueError("unsupported_product_catalogue_schema")
    if revenue_gps.get("schema_version") != "empire.market_sweep_revenue_gps.v1":
        raise ValueError("unsupported_revenue_gps_schema")

    digest_matches = provenance.get("derived_evidence_sha256") == report_sha256
    report_count = report.get("permit_event_count")
    if type(report_count) is not int or not 0 <= report_count <= 100000:
        raise ValueError("invalid_permit_event_count")
    joins = report.get("event_level_join_status_counts")
    landuse = report.get("event_level_landuse_category_counts")
    if not isinstance(joins, Mapping) or not isinstance(landuse, Mapping):
        raise ValueError("missing_aggregated_permit_counts")
    for counts in (joins, landuse):
        if any(type(v) is not int or v < 0 for v in counts.values()):
            raise ValueError("invalid_aggregate_counts")
        if sum(counts.values()) != report_count:
            raise ValueError("inconsistent_aggregate_event_counts")
    # Distinguish event counts from physical properties and contactable buyers.
    source_caveats = {
        "report_is_observe_only": report.get("mode") == "OBSERVE"
            and str(report.get("execution_authority")).lower() == "none",
        "all_expected_source_datasets_present": report.get("source_datasets") == _DATASETS,
        "derived_file_sha256_matches_provenance": digest_matches,
        "source_responses_not_signed_by_nyc": True,
        "no_buyer_or_property_owner_verified": provenance.get("no_buyer_or_property_owner_verified") is True,
        "source_rights_review_required": provenance.get("source_rights_review_required") is True,
        "customer_facing_distributable": report.get("customer_facing_distributable") is True,
        "third_party_resale_licensed": False,
    }
    statuses: list[str] = []
    if not all(source_caveats[k] for k in (
        "report_is_observe_only", "all_expected_source_datasets_present",
        "derived_file_sha256_matches_provenance", "no_buyer_or_property_owner_verified",
        "source_rights_review_required",
    )):
        statuses.append("SOURCE_INTEGRITY_OR_CONTRACT_REVIEW")
    timestamp = _aware(provenance.get("captured_at_utc"))
    provenance_fresh = timestamp is not None and now - timedelta(days=7) <= timestamp <= now + timedelta(minutes=5)
    if not provenance_fresh:
        statuses.append("PROVENANCE_STALE_OR_UNVERIFIED_TIME")
    if report.get("source_rights_not_granted_by_derived_evidence") is not True:
        statuses.append("REPORT_RIGHTS_ASSERTION_CONFLICT")

    rows = catalogue.get("products")
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("untrusted_product_catalogue")
    products = [p for p in rows if isinstance(p, Mapping) and p.get("product_id") == PRODUCT]
    if len(products) != 1:
        statuses.append("NYC_PRODUCT_NOT_RESOLVED_UNIQUELY")
        product = {}
    else:
        product = products[0]
    catalogue_rights_cleared = (
        catalogue.get("product_publication_authorized") is True
        and catalogue.get("third_party_resale_authorized") is True
        and product.get("raw_third_party_resale_cleared") is True
        and product.get("customer_data_export_ready") is True
        and product.get("customer_claim_release_ready") is True
        and product.get("fulfilment_verified") is True
    )
    # This is intentionally always held even if all caller fields claim True.
    # Only the Data Brokerage owner can authenticate independent licences
    # through an external signed review, not the miner's input snapshot.
    statuses.append("DATASET_SPECIFIC_RIGHTS_AND_PRODUCT_DELIVERY_NOT_ATTESTED_BY_OWNER")
    source_status = {
        "event_count_from_existing_report": report_count,
        "event_join_counts": dict(sorted(joins.items())),
        "event_landuse_counts": dict(sorted(landuse.items())),
        "four_source_datasets": dict(sorted(_DATASETS.items())),
        "source_caveats": source_caveats,
        "digest_matches": digest_matches,
        "provenance_recent_enough_for_research": provenance_fresh,
        "reported_catalogue_flags_all_true": catalogue_rights_cleared,
        "independent_legal_reuse_attestation_present": False,
        "saleable_dataset_verified": False,
        "distinct_verified_buildings": None,
    }

    if (revenue_gps.get("mode") != "OBSERVE"
            or str(revenue_gps.get("execution_authority")).lower() != "none"
            or revenue_gps.get("buyer_intent_inferred") is not False
            or revenue_gps.get("revenue_inferred") is not False):
        raise ValueError("untrusted_market_signal_snapshot")
    markets = revenue_gps.get("markets")
    if not isinstance(markets, list) or len(markets) > 250:
        raise ValueError("untrusted_market_list")
    targets = [m for m in markets if isinstance(m, Mapping)
               and m.get("niche") == "general_contractor" and m.get("metro") == "nyc"]
    if len(targets) != 1:
        statuses.append("NYC_BUYER_MARKET_NOT_RESOLVED_UNIQUELY")
        market = {}
    else:
        market = targets[0]
    numeric_fields = ("approved_buyer_count", "commercial_demand_evidence_count", "commercial_terms_count", "commercial_reply_count")
    for k in numeric_fields:
        value = market.get(k)
        if type(value) is not int or not 0 <= value <= 100000:
            statuses.append("MARKET_COMMERCIAL_COUNT_UNVERIFIED")
            break
    verified_buyer_count = market.get("approved_buyer_count") if not statuses.count("MARKET_COMMERCIAL_COUNT_UNVERIFIED") else None
    if not verified_buyer_count:
        statuses.append("NO_APPROVED_NYC_BUYERS_IN_SOURCE_SNAPSHOT")
    if not market.get("commercial_terms_count"):
        statuses.append("NO_VERIFIED_NYC_PURCHASE_TERMS_IN_SOURCE_SNAPSHOT")
    market_state = {
        "matched_market": len(targets) == 1,
        "research_priority_score_not_purchase_probability": market.get("research_priority_score"),
        "approved_buyers_reported_by_source": verified_buyer_count,
        "commercial_demand_events_reported_by_source": market.get("commercial_demand_evidence_count"),
        "written_terms_reported_by_source": market.get("commercial_terms_count"),
        "separately_verified_buyer_in_this_preflight": False,
        "market_snapshot_is_purchase_authority": False,
    }
    workflow = [
        {"owner": "data_brokerage", "request": "VERIFY_NYC_SOURCE_FIELD_LICENSING_AND_DELIVERABILITY",
         "acceptance": "Independent, dataset-specific legal/use-field attestation; source-specific permitted customer deliverable; no broad resale assumptions"},
        {"owner": "buyer_scout", "request": "VERIFY_NYC_B2B_DECISION_MAKERS_AND_WRITTEN_BUYING_INTENT",
         "acceptance": "Independently evidenced company, relevant role, source-permitted contact, exact buying need; no inferred buyers"},
        {"owner": "commercial_terms", "request": "GET_SIGNED_PRICE_USAGE_SCOPE_AND_BUYER_ACCEPTANCE",
         "acceptance": "Buyer-approved field list, geographic scope, licence terms, price, refunds and settlement method"},
        {"owner": "owned_campaigns", "request": "PREPARE_FOUNDER_REVIEWABLE_NYC_EXPERIMENT",
         "acceptance": "Rights-reviewed examples, one narrowly scoped audience, first-party opt-in tracking and approved creative; publish nothing"},
    ]
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "product_id": PRODUCT, "city": "New York City",
        "generated_at": now.isoformat(),
        "source": source_status, "market": market_state,
        "hold_reasons": sorted(set(statuses)),
        "source_verified_only_to_existing_derived_receipt": digest_matches,
        "rights_cleared": False, "verified_customer_or_buyer": False,
        "commercial_pilot_ready": False, "campaign_launch_authorized": False,
        "offer_fulfillable_verified": False, "data_licence_to_resell_verified": False,
        "proposed_owner_handoffs_not_dispatched": workflow,
        "next_action": "VERIFY_DATA_RIGHTS_AND_BUYER_CONTRACTS_BEFORE_ANY_LIVE_CAMPAIGN",
        "database_writes": False, "outbound_sent": False,
        "website_changed": False, "network_calls": False, "spend": 0,
        "execution_authority": "NONE",
    }
