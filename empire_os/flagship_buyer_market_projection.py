"""One privacy-preserving exact-market coverage classification.

Runs INSIDE the already-authorised buyer capacity worker, after the same
EmpireDB projection was successfully read for its existing snapshot.
Never performs a second DB query, creates a new database actor, publishes
buyer identities, identifies paying intent or bypasses tenant authority.

This output may be in a world-readable ops snapshot: no raw buyer IDs,
company names, phone numbers, cities, market contacts or rare count values.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from empire_os.revenue_buyer_evidence_handoff import review_one_commercial_evidence_request
from empire_os.revenue_market_buyer_linkage import (
    MarketBuyerLinkageHold, review_existing_buyer_market_linkage,
)

SCHEMA = "empire.predictive_revenue.authorized_market_coverage.v1"
MAX_CANONICAL_ROWS = 10000

BUCKETS = (
    ("ZERO", 0),
    ("ONE_TO_FOUR", 4),
    ("FIVE_TO_NINETEEN", 19),
    ("TWENTY_PLUS", None),
)


def _bucket(count: int) -> str:
    if count == 0:
        return "ZERO"
    if count <= 4:
        return "ONE_TO_FOUR"
    if count <= 19:
        return "FIVE_TO_NINETEEN"
    return "TWENTY_PLUS"


def held_authorized_market_coverage(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "EXACT_MARKET_COVERAGE_HELD",
        "hold_code": reason,
        "opaque_opportunity_ref": None,
        "record_count_bucket": "UNKNOWN",
        "exact_market_record_count": None,
        "full_buyer_projection_confirmed": False,
        "market_attribute_coverage_complete": False,
        "market_no_match_claim_authorized": False,
        "next_internal_evidence_action": "REVIEW_AUTHORIZED_BUYER_PROJECTION_AVAILABILITY",
        "first_party_buyer_request_verified": False,
        "written_terms_or_allocation_verified": False,
        "tenant_level_buyer_detail_exposed": False,
        "buyer_or_revenue_verified": False,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "none",
    }


def summarize_authorized_market_coverage(
    repo_root: Path,
    buyer_rows: Iterable[Mapping[str, Any]],
    *, as_of: datetime,
) -> dict[str, Any]:
    """Aggregate within the existing trusted buyer snapshot service only."""
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("aware coverage date required")
    at = as_of.astimezone(timezone.utc)
    rows = list(buyer_rows)
    if len(rows) >= MAX_CANONICAL_ROWS or any(
        not isinstance(row, Mapping) for row in rows
    ):
        return held_authorized_market_coverage("INCOMPLETE_OR_INVALID_EXISTING_BUYER_PROJECTION")
    try:
        prepared = review_one_commercial_evidence_request(
            repo_root, as_of=at,
        )
    except (ValueError, OSError, TypeError, KeyError):
        return held_authorized_market_coverage("CANONICAL_MARKET_EVIDENCE_UNAVAILABLE")
    if prepared.get("status") != "ONE_INTERNAL_EVIDENCE_REQUEST_PREPARED":
        return held_authorized_market_coverage("CANONICAL_MARKET_EVIDENCE_UNAVAILABLE")
    try:
        preview = review_existing_buyer_market_linkage(
            repo_root, prepared=prepared,
            buyer_rows=rows, as_of=at, max_return=1,
        )
    except (MarketBuyerLinkageHold, ValueError, KeyError, TypeError, AttributeError):
        return held_authorized_market_coverage("MARKET_JOIN_NOT_AUTHENTICATED")
    if (preview.get("source_buyer_record_count") != len(rows)
            or preview.get("execution_authority") != "none"
            or preview.get("market_match_is_buyer_intent") is not False
            or preview.get("database_writes") is not False
            or preview.get("outbound_sent") is not False):
        return held_authorized_market_coverage("UNTRUSTED_MARKET_PROJECTION_OUTPUT")
    count = preview.get("same_niche_and_exact_metro_record_count")
    if type(count) is not int or count < 0 or count > len(rows):
        return held_authorized_market_coverage("INVALID_EXACT_MARKET_MATCH_COUNT")
    missing = preview.get("missing_or_unusable_market_record_count")
    scoped = preview.get("tenant_scoped_records_held")
    if (type(missing) is not int or missing < 0 or
            type(scoped) is not int or scoped < 0 or
            missing + scoped + count > len(rows)):
        return held_authorized_market_coverage("INCONSISTENT_MARKET_ATTRIBUTE_COVERAGE")
    attributes_complete = (missing + scoped == 0)
    if not attributes_complete and count == 0:
        status = "NO_MATCH_OBSERVED_MARKET_COVERAGE_UNKNOWN"
    elif not attributes_complete:
        status = "PARTIAL_MARKET_OVERLAP_OBSERVED_COVERAGE_INCOMPLETE"
    elif count:
        status = "SAME_MARKET_BUYER_RECORDS_EXIST_UNVERIFIED"
    else:
        status = "NO_SAME_MARKET_RECORDS_IN_COMPLETE_PROJECTION"
    # No arbitrary market string or raw buyer detail is persisted. Counts
    # below 20 intentionally obscured in the broad operations snapshot.
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": status,
        "hold_code": None,
        "opaque_opportunity_ref": preview["opportunity_ref"],
        "record_count_bucket": _bucket(count) if count else (
            "ZERO" if attributes_complete else "UNKNOWN"
        ),
        "exact_market_record_count": None,
        "full_buyer_projection_confirmed": True,
        "market_attribute_coverage_complete": attributes_complete,
        "market_no_match_claim_authorized": attributes_complete and count == 0,
        "next_internal_evidence_action": (
            "COMPLETE_MISSING_BUYER_NICHE_AND_METRO_PROVENANCE"
            if not attributes_complete else
            "VERIFY_FIRST_PARTY_BUYING_BRIEF_AND_PRICE_TERMS"
            if count else "RESEARCH_AUTHORIZED_ALTERNATIVE_BUYER_CAPACITY"
        ),
        "first_party_buyer_request_verified": False,
        "written_terms_or_allocation_verified": False,
        "tenant_level_buyer_detail_exposed": False,
        "buyer_or_revenue_verified": False,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "none",
    }


def review_authorized_market_coverage_snapshot(
    repo_root: Path, *, as_of: datetime,
) -> dict[str, Any]:
    """Validate only the safe projection emitted by the existing root worker."""
    from datetime import timedelta
    import json

    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("aware market coverage review time required")
    now = as_of.astimezone(timezone.utc)
    target = Path(repo_root).resolve() / (
        "runtime/buyer_capacity_readiness/latest.json"
    )
    untrusted = held_authorized_market_coverage("CANONICAL_CAPACITY_PROJECTION_NOT_READY")
    if (target.is_symlink() or target.parent.is_symlink()
            or not target.is_file()):
        return untrusted
    try:
        if not 0 < target.stat().st_size <= 100000:
            return untrusted
        source = json.loads(target.read_text(encoding="utf-8"))
        if (not isinstance(source, dict)
                or source.get("schema_version") != "empire.buyer_capacity_readiness.v1"
                or source.get("mode") != "OBSERVE"
                or source.get("execution_authority") != "none"):
            return untrusted
        stamp = datetime.fromisoformat(source["observed_at"].replace("Z", "+00:00"))
        if stamp.utcoffset() is None or not (
            timedelta(0) <= now - stamp.astimezone(timezone.utc)
            <= timedelta(hours=6)
        ):
            return held_authorized_market_coverage("CAPACITY_SNAPSHOT_NOT_FRESH")
        child = source.get("flagship_exact_market_coverage")
        expected = set(held_authorized_market_coverage("TEST"))
        if (not isinstance(child, dict) or set(child) != expected
                or child.get("schema_version") != SCHEMA
                or child.get("mode") != "OBSERVE"
                or child.get("execution_authority") != "none"
                or any(child.get(field) is not False for field in (
                    "first_party_buyer_request_verified",
                    "written_terms_or_allocation_verified",
                    "tenant_level_buyer_detail_exposed",
                    "buyer_or_revenue_verified",
                    "outbound_sent",
                    "database_writes",
                ))):
            return untrusted
        bucket = child.get("record_count_bucket")
        if bucket not in ("UNKNOWN", "ZERO", "ONE_TO_FOUR",
                          "FIVE_TO_NINETEEN", "TWENTY_PLUS"):
            return untrusted
        if child.get("exact_market_record_count") is not None:
            return untrusted
        if child.get("status") not in (
            "EXACT_MARKET_COVERAGE_HELD",
            "NO_MATCH_OBSERVED_MARKET_COVERAGE_UNKNOWN",
            "PARTIAL_MARKET_OVERLAP_OBSERVED_COVERAGE_INCOMPLETE",
            "SAME_MARKET_BUYER_RECORDS_EXIST_UNVERIFIED",
            "NO_SAME_MARKET_RECORDS_IN_COMPLETE_PROJECTION",
        ):
            return untrusted
        for field in (
            "full_buyer_projection_confirmed",
            "market_attribute_coverage_complete",
            "market_no_match_claim_authorized",
        ):
            if type(child.get(field)) is not bool:
                return untrusted
        if child["market_no_match_claim_authorized"] and (
            bucket != "ZERO" or
            child["status"] != "NO_SAME_MARKET_RECORDS_IN_COMPLETE_PROJECTION" or
            child["market_attribute_coverage_complete"] is not True or
            child["full_buyer_projection_confirmed"] is not True
        ):
            return untrusted
        if (bucket == "ZERO") != child["market_no_match_claim_authorized"]:
            return untrusted
        ref = child.get("opaque_opportunity_ref")
        if ref is not None and (
            not isinstance(ref, str) or len(ref) != 27
            or not ref.startswith("oppref_")
            or any(letter not in "0123456789abcdef" for letter in ref[7:])
        ):
            return untrusted
        action = child.get("next_internal_evidence_action")
        if action not in {
            "REVIEW_AUTHORIZED_BUYER_PROJECTION_AVAILABILITY",
            "COMPLETE_MISSING_BUYER_NICHE_AND_METRO_PROVENANCE",
            "VERIFY_FIRST_PARTY_BUYING_BRIEF_AND_PRICE_TERMS",
            "RESEARCH_AUTHORIZED_ALTERNATIVE_BUYER_CAPACITY",
        }:
            return untrusted
        if child["status"] == "EXACT_MARKET_COVERAGE_HELD":
            if (bucket != "UNKNOWN" or ref is not None or
                    child.get("hold_code") not in {
                        "CANONICAL_CAPACITY_PROJECTION_NOT_READY",
                        "CAPACITY_SNAPSHOT_NOT_FRESH",
                        "CANONICAL_MARKET_EVIDENCE_UNAVAILABLE",
                        "INCOMPLETE_OR_INVALID_EXISTING_BUYER_PROJECTION",
                        "MARKET_JOIN_NOT_AUTHENTICATED",
                        "UNTRUSTED_MARKET_PROJECTION_OUTPUT",
                        "INVALID_EXACT_MARKET_MATCH_COUNT",
                        "INCONSISTENT_MARKET_ATTRIBUTE_COVERAGE",
                        "OPTIONAL_FLAGSHIP_MARKET_PREVIEW_HELD",
                    }):
                return untrusted
        else:
            if ref is None or child.get("hold_code") is not None:
                return untrusted
            if child["status"] == "NO_MATCH_OBSERVED_MARKET_COVERAGE_UNKNOWN" and (
                bucket != "UNKNOWN" or child["market_attribute_coverage_complete"]
            ):
                return untrusted
            if child["status"] == "PARTIAL_MARKET_OVERLAP_OBSERVED_COVERAGE_INCOMPLETE" and (
                bucket not in ("ONE_TO_FOUR", "FIVE_TO_NINETEEN", "TWENTY_PLUS")
                or child["market_attribute_coverage_complete"]
            ):
                return untrusted
            if child["status"] == "SAME_MARKET_BUYER_RECORDS_EXIST_UNVERIFIED" and (
                bucket not in ("ONE_TO_FOUR", "FIVE_TO_NINETEEN", "TWENTY_PLUS")
                or not child["market_attribute_coverage_complete"]
            ):
                return untrusted
            if child["status"] == "NO_SAME_MARKET_RECORDS_IN_COMPLETE_PROJECTION" and (
                bucket != "ZERO" or not child["market_no_match_claim_authorized"]
            ):
                return untrusted
        return {
            **child, "source_snapshot_time": stamp.isoformat(),
            "source_classification_is_customer_proof": False,
        }
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        return untrusted
