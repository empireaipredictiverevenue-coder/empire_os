"""Privacy-preserving market enrichment workload for existing buyer records.

Reuses the existing authorised buyer-capacity reader, niche taxonomy and
Buyer Acquisition Team responsibilities. Counts describe unknown/invalid
source fields, NEVER classified buyers, real demand, buying consent, payout,
deliverability, or permission to mutate EmpireDB / send email.

One market record is never inferred from an unrelated email, listing,
external IP, public permit, or another buyer's description.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from empire_os.niche_taxonomy import niche_family
from empire_os.revenue_market_buyer_linkage import _normalize, SAFE_NICHE, SAFE_METRO

SCHEMA = "empire.predictive_revenue.buyer_enrichment_triage.v1"
MAX_RECORDS = 10000
# Never export rare exact counts of customer records into a shared
# operational response.
BUCKETS = ("ZERO", "ONE_TO_FOUR", "FIVE_TO_NINETEEN", "TWENTY_PLUS")
STATES = (
    "BOTH_MARKET_FIELDS_PRESENT",
    "NICHE_ONLY_MISSING",
    "METRO_ONLY_MISSING",
    "BOTH_MARKET_FIELDS_MISSING",
    "INVALID_MARKET_FIELD_FORMAT",
    "TENANT_SCOPE_HELD",
)
OWNERS = {
    "VERIFY_FOUNDER_SCOPE": ("business_development", "review_tenant_scope"),
    "VERIFY_BUYER_VERTICAL": ("buyer_qualifier", "buyer_vertical_source_check"),
    "VERIFY_BUYER_SERVICE_AREA": ("buyer_qualifier", "buyer_service_area_source_check"),
    "VERIFY_VERTICAL_AND_SERVICE_AREA": ("buyer_qualifier", "buyer_buybox_source_recovery"),
    "VERIFY_INVALID_MARKET_SOURCE_FORMAT": ("buyer_qualifier", "buyer_market_schema_review"),
    "VERIFY_FIRST_PARTY_BUYING_TERMS": ("buyer_conversation_intake", "verify_buyer_terms_original"),
}

def _bucket(n: int) -> str:
    if n == 0:
        return "ZERO"
    if n < 5:
        return "ONE_TO_FOUR"
    if n < 20:
        return "FIVE_TO_NINETEEN"
    return "TWENTY_PLUS"


def _market_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _unsupported_market_type(value: Any) -> bool:
    return value is not None and (not isinstance(value, str))


def _market_state(row: Mapping[str, Any]) -> str:
    # Canonical public.buyers uses org_id, not tenant_id. Never treat an
    # unprojected org_id as proof that a global founder may inspect it.
    if row.get("org_id") is not None or row.get("tenant_id") not in (None, ""):
        return "TENANT_SCOPE_HELD"
    niche_text = _market_text(row.get("niche"))
    metro_text = _market_text(row.get("metro"))
    if (_unsupported_market_type(row.get("niche")) or
            _unsupported_market_type(row.get("metro"))):
        return "INVALID_MARKET_FIELD_FORMAT"
    if niche_text and _normalize(row["niche"], SAFE_NICHE) is None:
        return "INVALID_MARKET_FIELD_FORMAT"
    if metro_text and _normalize(row["metro"], SAFE_METRO) is None:
        return "INVALID_MARKET_FIELD_FORMAT"
    if niche_text and metro_text:
        return "BOTH_MARKET_FIELDS_PRESENT"
    if niche_text:
        return "METRO_ONLY_MISSING"
    if metro_text:
        return "NICHE_ONLY_MISSING"
    return "BOTH_MARKET_FIELDS_MISSING"


def summarize_buyer_enrichment_triage(
    buyers: Iterable[Mapping[str, Any]], *,
    as_of: datetime,
) -> dict[str, Any]:
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("time-aware buyer enrichment review required")
    rows = list(buyers)
    if len(rows) >= MAX_RECORDS or any(
        not isinstance(row, Mapping) for row in rows
    ):
        raise ValueError("canonical buyer projection invalid or truncated")
    if any("org_id" not in row for row in rows):
        raise ValueError("canonical buyer projection missing organisation scope")
    # Single partition invariant: every input row appears in ONE state.
    states = Counter(_market_state(row) for row in rows)
    if sum(states.values()) != len(rows):
        raise ValueError("buyer market completeness partition invalid")
    complete = states["BOTH_MARKET_FIELDS_PRESENT"]
    unknown = len(rows) - complete
    # Source-niche labels are used ONLY for a cohort-level, aggregate
    # research workstream. Never join to city or infer demand from labels.
    # Explicitly ignore names, contacts, payout/cap, URLs and tenant rows.
    family_counts: Counter[str] = Counter()
    for row in rows:
        if _market_state(row) == "BOTH_MARKET_FIELDS_PRESENT":
            normalized = _normalize(row.get("niche"), SAFE_NICHE)
            if normalized is not None:
                family = niche_family(normalized)
                if family in ("roofing", "solar", "hvac", "legal", "insurance",
                              "restoration", "plumbing", "medical claims"):
                    family_counts[family] += 1

    actions = [
        # Cannot research another tenant's information from this global desk.
        ("TENANT_SCOPE_HELD", "VERIFY_FOUNDER_SCOPE", 100),
        ("INVALID_MARKET_FIELD_FORMAT", "VERIFY_INVALID_MARKET_SOURCE_FORMAT", 96),
        ("BOTH_MARKET_FIELDS_MISSING", "VERIFY_VERTICAL_AND_SERVICE_AREA", 94),
        ("NICHE_ONLY_MISSING", "VERIFY_BUYER_VERTICAL", 92),
        ("METRO_ONLY_MISSING", "VERIFY_BUYER_SERVICE_AREA", 90),
        # An existing market label is not buyer purchase intent.
        ("BOTH_MARKET_FIELDS_PRESENT", "VERIFY_FIRST_PARTY_BUYING_TERMS", 74),
    ]
    workload = [
        {
            "source_state": state,
            "observed_record_bucket": _bucket(states[state]),
            "requires_work": states[state] > 0,
            "owner": OWNERS[action][0],
            "existing_workflow": OWNERS[action][1],
            "next_internal_action": action,
            "priority": priority,
            "first_party_source_required": True,
            "automatic_enrichment_authorized": False,
            "commercial_buyer_proof_established": False,
        }
        for state, action, priority in actions
    ]
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "MARKET_COVERAGE_ENRICHMENT_WORKLOAD_REVIEW",
        "observed_at": as_of.astimezone(timezone.utc).isoformat(),
        "source_records_observed": len(rows),
        "market_fields_complete": complete,
        "market_fields_incomplete_or_held": unknown,
        "same_record_market_fields_not_commercial_proof": True,
        "coverage_percent_of_observed_records": (
            round(100 * complete / len(rows), 1) if rows else None
        ),
        "source_market_state_buckets": {
            state: _bucket(states[state]) for state in STATES
        },
        "observed_vertical_family_buckets": {
            niche: _bucket(family_counts[niche]) for niche in (
                "roofing", "solar", "hvac", "legal", "insurance",
                "restoration", "plumbing", "medical claims"
            )
        },
        "workload": workload,
        "current_exact_match_count_verified": False,
        "independent_first_party_buying_intent_verified": False,
        "canonical_buyer_rows_mutated": False,
        "commercial_terms_activated": False,
        "external_outbound_authorized": False,
        "paid_research_authorized": False,
        "contacts_or_buyer_names_exported": False,
        "tenant_scoped_records_exported": False,
        "execution_authority": "none",
    }


def held_buyer_enrichment_triage(reason: str) -> dict[str, Any]:
    """Safe public operational hold; never includes originating error text."""
    if reason not in {
        "BUYER_ENRICHMENT_UNAVAILABLE",
        "BUYER_MARKET_FIELDS_UNTRUSTED",
        "CAPACITY_PROJECTION_NOT_CURRENT",
    }:
        reason = "BUYER_ENRICHMENT_UNAVAILABLE"
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "BUYER_MARKET_ENRICHMENT_HELD",
        "hold_code": reason,
        "source_records_observed": None,
        "market_fields_complete": None,
        "market_fields_incomplete_or_held": None,
        "coverage_percent_of_observed_records": None,
        "source_market_state_buckets": {},
        "observed_vertical_family_buckets": {},
        "workload": [],
        "canonical_buyer_rows_mutated": False,
        "independent_first_party_buying_intent_verified": False,
        "contacts_or_buyer_names_exported": False,
        "tenant_scoped_records_exported": False,
        "external_outbound_authorized": False,
        "execution_authority": "none",
    }


def review_enrichment_triage_snapshot(
    repo_root: Any, *, as_of: datetime,
) -> dict[str, Any]:
    """Read back ONLY the existing safe root-worker aggregate.

    Snapshot is internal operational evidence, never independently signed
    original company market provenance. Without the owner deployment the
    preview remains UNKNOWN (not a fabricated 950-row verification).
    """
    from datetime import timedelta
    from pathlib import Path
    import json
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("time-aware enrichment readback required")
    hold = held_buyer_enrichment_triage("CAPACITY_PROJECTION_NOT_CURRENT")
    path = Path(repo_root).resolve() / (
        "runtime/buyer_capacity_readiness/latest.json"
    )
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        return hold
    try:
        if not 0 < path.stat().st_size <= 100000:
            return hold
        original = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(original, dict)
                or original.get("schema_version") != "empire.buyer_capacity_readiness.v1"
                or original.get("mode") != "OBSERVE"
                or original.get("execution_authority") != "none"):
            return hold
        timestamp = datetime.fromisoformat(original["observed_at"].replace("Z", "+00:00"))
        if timestamp.utcoffset() is None or not (
            timedelta(0) <= as_of.astimezone(timezone.utc) -
            timestamp.astimezone(timezone.utc) <= timedelta(hours=6)
        ):
            return hold
        result = original.get("flagship_buyer_enrichment_triage")
        if not isinstance(result, dict):
            return hold
        expected = set(summarize_buyer_enrichment_triage([], as_of=as_of))
        if (set(result) != expected
                or result.get("schema_version") != SCHEMA
                or result.get("mode") != "OBSERVE"
                or result.get("status") != "MARKET_COVERAGE_ENRICHMENT_WORKLOAD_REVIEW"
                or result.get("execution_authority") != "none"):
            return hold
        if any(result.get(field) is not False for field in (
            "current_exact_match_count_verified",
            "independent_first_party_buying_intent_verified",
            "canonical_buyer_rows_mutated", "commercial_terms_activated",
            "external_outbound_authorized", "paid_research_authorized",
            "contacts_or_buyer_names_exported", "tenant_scoped_records_exported",
        )) or result.get("same_record_market_fields_not_commercial_proof") is not True:
            return hold
        total = original.get("buyers_seen")
        complete = result.get("market_fields_complete")
        incomplete = result.get("market_fields_incomplete_or_held")
        if (any(type(item) is not int or not 0 <= item <= MAX_RECORDS
                for item in (total, complete, incomplete))
                or result.get("source_records_observed") != total
                or complete + incomplete != total
                or type(original.get("market_defined")) is not int
                or not complete <= original["market_defined"] <= total):
            return hold
        expected_percent = round(100 * complete / total, 1) if total else None
        if result.get("coverage_percent_of_observed_records") != expected_percent:
            return hold
        try:
            child_time = datetime.fromisoformat(result["observed_at"])
        except (ValueError, TypeError):
            return hold
        if child_time.tzinfo is None or child_time != timestamp:
            return hold
        buckets = result.get("source_market_state_buckets")
        families = result.get("observed_vertical_family_buckets")
        if (not isinstance(buckets, dict) or set(buckets) != set(STATES)
                or not isinstance(families, dict)
                or set(families) != {
                    "roofing", "solar", "hvac", "legal", "insurance",
                    "restoration", "plumbing", "medical claims"
                }
                or any(bucket not in BUCKETS for bucket in
                       [*buckets.values(), *families.values()])):
            return hold
        def lo(state: str) -> int:
            return {"ZERO": 0, "ONE_TO_FOUR": 1,
                    "FIVE_TO_NINETEEN": 5, "TWENTY_PLUS": 20}[state]
        def hi(state: str) -> int:
            return {"ZERO": 0, "ONE_TO_FOUR": 4,
                    "FIVE_TO_NINETEEN": 19,
                    "TWENTY_PLUS": MAX_RECORDS}[state]
        if (sum(lo(bucket) for bucket in buckets.values()) > total
                or sum(hi(bucket) for bucket in buckets.values()) < total
                or lo(buckets["BOTH_MARKET_FIELDS_PRESENT"]) > complete
                or hi(buckets["BOTH_MARKET_FIELDS_PRESENT"]) < complete
                or sum(lo(bucket) for bucket in families.values()) > complete):
            return hold
        workload = result.get("workload")
        if not isinstance(workload, list) or len(workload) != len(STATES):
            return hold
        source_by_action = {
            "VERIFY_FOUNDER_SCOPE": ("TENANT_SCOPE_HELD", 100),
            "VERIFY_INVALID_MARKET_SOURCE_FORMAT": ("INVALID_MARKET_FIELD_FORMAT", 96),
            "VERIFY_VERTICAL_AND_SERVICE_AREA": ("BOTH_MARKET_FIELDS_MISSING", 94),
            "VERIFY_BUYER_VERTICAL": ("NICHE_ONLY_MISSING", 92),
            "VERIFY_BUYER_SERVICE_AREA": ("METRO_ONLY_MISSING", 90),
            "VERIFY_FIRST_PARTY_BUYING_TERMS": ("BOTH_MARKET_FIELDS_PRESENT", 74),
        }
        for row, (action, (state, priority)) in zip(
            workload, source_by_action.items()
        ):
            if not isinstance(row, dict) or set(row) != {
                "source_state", "observed_record_bucket",
                "requires_work", "owner", "existing_workflow",
                "next_internal_action", "priority",
                "first_party_source_required",
                "automatic_enrichment_authorized",
                "commercial_buyer_proof_established",
            }:
                return hold
            owner, flow = OWNERS[action]
            if (row.get("source_state") != state
                    or row.get("observed_record_bucket") != buckets[state]
                    or row.get("requires_work") is not (buckets[state] != "ZERO")
                    or row.get("owner") != owner
                    or row.get("existing_workflow") != flow
                    or row.get("next_internal_action") != action
                    or row.get("priority") != priority
                    or row.get("first_party_source_required") is not True
                    or row.get("automatic_enrichment_authorized") is not False
                    or row.get("commercial_buyer_proof_established") is not False):
                return hold
        return {
            **result,
            "snapshot_generated_by_existing_service_at": timestamp.isoformat(),
            "original_market_source_independently_authenticated": False,
        }
    except (OSError, ValueError, TypeError, KeyError, OverflowError,
            UnicodeError, AttributeError):
        return hold
