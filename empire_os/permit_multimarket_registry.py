"""One EmpireOS Permit Intelligence engine: jurisdiction-scoped expansion plan.

NYC's five filing IDs and original source-owner gates remain untouched. All
other markets are SOURCE CANDIDATES, not active subscriptions, live scrapers,
qualified opportunities, CRM prospects, or redistribution-ready datasets.

Source pages were independently researched 2026-10-24. Every jurisdiction
needs its own schema, permitted access, source-terms review and acceptance tests.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
import json
import re

SCHEMA = "empire.permit_data.national_market_registry.v1"
NORMALIZED_SCHEMA = "empire.permit_data.multi_market_internal_observation.v1"
REGISTRY_VERSION = "2026-10-24.v1"

# Dataset category describes the source publisher's advertised coverage; it is
# NOT a promise that every row has reached a particular life-cycle stage.
MARKETS = {
    "nyc": {
        "name": "New York City", "state": "NY", "mode": "EXISTING_EXACT_FIVE_JOB_PILOT",
        "source_family": "NYC_DOB_NOW_TWO_DATASET_EXACT_FILING",
        "datasets": ("w9ak-ipjd", "rbx6-tga4"),
        "portal": "https://data.cityofnewyork.us",
        "coverage": "EXISTING_FILING_AND_APPROVED_PERMIT_CROSSCHECK",
        "license_review_status": "UNVERIFIED_FOR_CUSTOMER_DISTRIBUTION",
        "vertical_research": ("fire_protection", "sprinkler"),
        "schema_verified_for_live_ingest": True,  # NYC original narrow pilot only
    },
    "chicago": {
        "name": "Chicago", "state": "IL", "mode": "SOURCE_DISCOVERY_ONLY",
        "source_family": "SOCRATA",
        "datasets": ("ydr8-5enu",),
        "portal": "https://data.cityofchicago.org",
        "coverage": "ISSUED_PERMITS_EXCLUDES_LATER_VOIDED_OR_REVOKED",
        "license_review_status": "UNVERIFIED_FOR_CUSTOMER_DISTRIBUTION",
        "vertical_research": ("roofing", "hvac", "electrical", "general_construction"),
        "schema_verified_for_live_ingest": False,
    },
    "philadelphia": {
        "name": "Philadelphia", "state": "PA", "mode": "SOURCE_DISCOVERY_ONLY",
        "source_family": "CARTO_SQL",
        "datasets": ("permits",),
        "portal": "https://phl.carto.com",
        "coverage": "BUILDING_AND_ZONING_PERMITS_STATUS_NEEDS_AUDIT",
        "license_review_status": "UNVERIFIED_FOR_CUSTOMER_DISTRIBUTION",
        "vertical_research": ("roofing", "hvac", "fire_protection", "general_construction"),
        "schema_verified_for_live_ingest": False,
    },
    "san_francisco": {
        "name": "San Francisco", "state": "CA", "mode": "SOURCE_DISCOVERY_ONLY",
        "source_family": "SOCRATA",
        "datasets": ("i98e-djp9",),
        "portal": "https://data.sfgov.org",  # city publisher's API domain
        "coverage": "BUILDING_PERMIT_APPLICATIONS_WITH_ISSUANCE_DATES_WHEN_RECORDED",
        "license_review_status": "UNVERIFIED_FOR_CUSTOMER_DISTRIBUTION",
        "vertical_research": ("electrical", "hvac", "plumbing", "general_construction"),
        "schema_verified_for_live_ingest": False,
    },
    "seattle": {
        "name": "Seattle", "state": "WA", "mode": "SOURCE_DISCOVERY_ONLY",
        "source_family": "SOCRATA",
        "datasets": ("76t5-zqzr",),
        "portal": "https://data.seattle.gov",
        "coverage": "ISSUED_OR_IN_PROGRESS_PERMIT_RECORDS",
        "license_review_status": "UNVERIFIED_FOR_CUSTOMER_DISTRIBUTION",
        "vertical_research": ("roofing", "electrical", "hvac", "general_construction"),
        "schema_verified_for_live_ingest": False,
    },
    "austin": {
        "name": "Austin", "state": "TX", "mode": "SOURCE_DISCOVERY_ONLY",
        "source_family": "SOCRATA",
        "datasets": ("3syk-w9eu",),
        "portal": "https://data.austintexas.gov",
        "coverage": "ISSUED_CONSTRUCTION_PERMITS_ONLY",
        "license_review_status": "UNVERIFIED_FOR_CUSTOMER_DISTRIBUTION",
        "vertical_research": ("roofing", "hvac", "solar", "plumbing", "electrical"),
        "schema_verified_for_live_ingest": False,
    },
}

REFERENCE_URLS = {
    "chicago": "https://data.cityofchicago.org/Buildings/Building-Permits/ydr8-5enu",
    "philadelphia": "https://catalog.data.gov/dataset/licenses-and-inspections-building-and-zoning-permits",
    "san_francisco": "https://data.sf.gov/Housing-and-Buildings/Building-Permits/i98e-djp9",
    "seattle": "https://data.seattle.gov/Built-Environment/Building-Permits/76t5-zqzr",
    "austin": "https://data.austintexas.gov/Building-and-Development/Issued-Construction-Permits/3syk-w9eu",
}

ALLOWED_PHASES = frozenset({"APPLICATION", "IN_PROGRESS", "ISSUED", "UNKNOWN"})
IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9./_-]{0,119}$")


def digest(value: Mapping[str, Any]) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def market_plan(*, at: datetime) -> dict:
    if not isinstance(at, datetime) or at.utcoffset() is None:
        raise ValueError("multimarket_clock_requires_timezone")
    rows = []
    for key, source in MARKETS.items():
        rows.append({
            "market_id": key,
            "name": source["name"],
            "state": source["state"],
            "source_family": source["source_family"],
            "dataset_ids": list(source["datasets"]),
            "public_source_reference": REFERENCE_URLS.get(key),
            "publisher_coverage": source["coverage"],
            "original_nyc_pilot": key == "nyc",
            "source_schema_operational": source["schema_verified_for_live_ingest"],
            "market_stage": source["mode"],
            "trade_sectors_for_research_not_verified_inventory": list(source["vertical_research"]),
            "first_owner_step": "Verify dataset schema, source policy, rights and audience",
            "new_market_query_authorized": False,
            "source_field_distribution_approved": False,
            "qualified_buyers": 0,
            "verified_revenue_usd": "0.00",
        })
    packet = {
        "schema_version": SCHEMA,
        "registry_version": REGISTRY_VERSION,
        "reviewed_at_utc": at.astimezone(timezone.utc).isoformat(),
        "original_stack": "ONE_EMPIREOS_PERMIT_INTELLIGENCE",
        "original_nyc_exact_job_checkpoint_unchanged": True,
        "markets": rows,
        "distinct_us_markets": len(rows),
        "additional_market_candidates": len(rows) - 1,
        "new_markets_live": 0,
        "new_market_http_requests": 0,
        "aggregate_revenue_verified_usd": "0.00",
        "customer_distribution_approved": False,
        "marketing_outbound_sent": False,
        "original_empiredb_writes": 0,
        "original_smart_crm_writes": 0,
        "paid_traffic_used": False,
        "execution_authority": "none",
    }
    packet["private_market_registry_sha256"] = digest(packet)
    return packet


def normalize_offline_source_observation(*, market_id: str, dataset_id: str,
                                         source_row: Mapping[str, Any],
                                         reference_field: str, phase_field: str,
                                         phase_labels: Mapping[str, str],
                                         at: datetime) -> dict:
    """Offline, allowlisted minimal projection. Never stores raw addresses,
    people, phones, full permits, contacts or source raw rows.

    The field map is caller-supplied as a TEST-only provisional schema until
    separately verified against the matching city's current source dictionary.
    """
    if (market_id not in MARKETS or market_id == "nyc"):
        raise ValueError("use_original_nyc_exact_job_engine")
    market = MARKETS[market_id]
    if (market["mode"] != "SOURCE_DISCOVERY_ONLY"
        or dataset_id not in market["datasets"]):
        raise ValueError("unapproved_or_cross_market_dataset")
    if not isinstance(at, datetime) or at.utcoffset() is None:
        raise ValueError("observation_clock_invalid")
    if (not isinstance(source_row, Mapping) or not isinstance(phase_labels, Mapping)
        or len(source_row) > 100 or len(phase_labels) > 20
        or not isinstance(reference_field, str) or not isinstance(phase_field, str)
        or reference_field == phase_field or reference_field not in source_row
        or phase_field not in source_row):
        raise ValueError("untrusted_market_source_projection")
    ref = source_row[reference_field]
    raw_phase = source_row[phase_field]
    if (not isinstance(ref, str) or not IDENTITY.fullmatch(ref)
        or not isinstance(raw_phase, str) or len(raw_phase) > 80):
        raise ValueError("invalid_or_sensitive_permit_reference_or_state")
    mapped = phase_labels.get(raw_phase)
    if mapped not in ALLOWED_PHASES:
        mapped = "UNKNOWN"
    # Issued-only datasets must not yield a new application-stage trigger,
    # even if caller mistakes a raw source-status label for an application.
    if market["coverage"].startswith("ISSUED_") and mapped in {
        "APPLICATION", "IN_PROGRESS"}:
        mapped = "UNKNOWN"
    result = {
        "schema_version": NORMALIZED_SCHEMA,
        "market_id": market_id,
        "state": market["state"],
        "dataset_id": dataset_id,
        "observed_at_utc": at.astimezone(timezone.utc).isoformat(),
        "permit_identity_sha256": sha256(
            (market_id + ":" + dataset_id + ":" + ref).encode()).hexdigest(),
        "interpreted_source_phase": mapped,
        "source_record_publisher_signature_verified": False,
        "source_mapping_independently_verified": False,
        "permit_issued_independently_confirmed": False,
        "unawarded_contract_or_buying_signal_verified": False,
        "qualification_ready": False,
        "customer_delivery_authorized": False,
        "source_metadata_lookup_executed": False,
        "source_row_http_get_executed": False,
        "empiredb_writes": 0,
        "smart_crm_writes": 0,
        "execution_authority": "none",
    }
    result["private_source_observation_sha256"] = digest(result)
    return result


def render_market_plan(plan: Mapping[str, Any]) -> str:
    if (not isinstance(plan, Mapping) or plan.get("schema_version") != SCHEMA
        or plan.get("private_market_registry_sha256") != digest({
            k: v for k, v in plan.items() if k != "private_market_registry_sha256"})
        or plan.get("execution_authority") != "none"
        or plan.get("new_markets_live") != 0
        or plan.get("new_market_http_requests") != 0):
        raise ValueError("untrusted_multi_market_plan")
    lines = [
        "# EmpireOS Permit Intelligence — United States market expansion",
        "",
        "**Founder-private market research. Existing NYC five-job pilot is unchanged.**",
        "",
        "| City | Source | Coverage | Research trades | Release |",
        "|---|---|---|---|---|",
    ]
    for row in plan["markets"]:
        lines.append("| " + " | ".join((
            row["name"], ", ".join(row["dataset_ids"]),
            row["publisher_coverage"],
            ", ".join(row["trade_sectors_for_research_not_verified_inventory"]),
            "NYC existing pilot only" if row["original_nyc_pilot"]
            else "NO QUERY / NO SOURCE RIGHTS / NO CUSTOMER SEND",
        )) + " |")
    lines += [
        "", "## Commercial research sequence (not activated)",
        "",
        "1. Audit publisher dictionary and distribution/attribution policy for each city.",
        "2. Verify source observation freshness, permit phases and downstream contractor fit.",
        "3. Identify real contractors and manually verify relevant buyer workflows.",
        "4. Value-first outreach only after domain and exact recipient suppression, authenticated sender and founder approval.",
        "5. Authentic reply → rapport → buyer need → permission-based CTA → rights-cleared sample on request.",
        "6. Accepted pilot scope and payment → lawful fulfilment → evidence of realised revenue.",
        "", "**0 added live markets · 0 source GETs · 0 sends · $0 verified revenue.**", "",
    ]
    return "\n".join(lines)
