"""Safe read-only join of the existing EmpireOS commercial relationship registry.

Company-domain overlap is a prior-conversation HOLD, never a suppression
clearance, purchaser qualification, contact approval, or CRM mutation.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
from copy import deepcopy
import json
import re

SCHEMA = "empire.commercial_relationship_registry.v1"
VALID_DOMAIN = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+$")


def relationship_context(review: Mapping, registry: Mapping | None,
                         *, now: datetime) -> dict:
    if (not isinstance(review, Mapping)
            or review.get("schema") != "empire.revenue_strike.contractor_founder_review.v1"
            or review.get("mode") != "OBSERVE"
            or review.get("outbound_authorized") is not False):
        raise ValueError("INVALID_CONTRACTOR_REVIEW_AUTHORITY")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("AWARE_TIME_REQUIRED")
    now = now.astimezone(timezone.utc)
    output = deepcopy(review)
    packets = output["packets"]
    if not isinstance(packets, list) or len(packets) > 500:
        raise ValueError("CONTRACTOR_REVIEW_UNBOUNDED")

    state = "UNAVAILABLE"
    indexed: dict[str, list[dict]] = {}
    if registry is not None:
        if not isinstance(registry, Mapping):
            raise ValueError("INVALID_EXISTING_RELATIONSHIP_REGISTRY")
        if (registry.get("schema_version") != SCHEMA
                or registry.get("mode") != "OBSERVE"
                or registry.get("outbound_authorized") is not False):
            raise ValueError("UNTRUSTED_EXISTING_RELATIONSHIP_REGISTRY")
        rows = registry.get("relationships")
        if not isinstance(rows, list) or len(rows) > 5000 or registry.get("relationship_count") != len(rows):
            raise ValueError("RELATIONSHIP_REGISTRY_COUNT_MISMATCH")
        stamp = registry.get("generated_at")
        try:
            stamp = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError("NAIVE_REGISTRY_TIMESTAMP")
            age = (now - stamp.astimezone(timezone.utc)).total_seconds()
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("REGISTRY_TIMESTAMP_UNVERIFIED") from exc
        fresh = -300 <= age <= 96 * 3600 and registry.get("gmail_snapshot_fresh") is True
        state = "FRESH" if fresh else "STALE"
        for record in rows:
            if not isinstance(record, Mapping):
                raise ValueError("MALFORMED_RELATIONSHIP")
            domains = record.get("identity_domains")
            if not isinstance(domains, list) or len(domains) > 12:
                raise ValueError("MALFORMED_RELATIONSHIP_DOMAINS")
            for domain in domains:
                if not isinstance(domain, str) or not VALID_DOMAIN.fullmatch(domain):
                    raise ValueError("UNTRUSTED_RELATIONSHIP_DOMAIN")
                indexed.setdefault(domain, []).append(record)

    related = ambiguous = 0
    for item in packets:
        if not isinstance(item, dict):
            raise ValueError("MALFORMED_CONTRACTOR_REVIEW_PACKET")
        domain = item.get("company_domain")
        if not isinstance(domain, str) or not VALID_DOMAIN.fullmatch(domain):
            raise ValueError("MALFORMED_CONTRACTOR_DOMAIN")
        matches = indexed.get(domain, []) if state == "FRESH" else []
        if state != "FRESH":
            status = "RELATIONSHIP_SOURCE_" + state
        elif len(matches) > 1:
            status = "AMBIGUOUS_RELATIONSHIP_HOLD"
            ambiguous += 1
        elif matches:
            status = "KNOWN_RELATIONSHIP_REVIEW_HOLD"
            related += 1
        else:
            status = "NO_EXACT_MATCH_NOT_A_SUPPRESSION_CLEARANCE"
        item["existing_commercial_relationship"] = {
            "status": status,
            "source": "existing_empire_commercial_relationship_registry",
            "exact_domain_match": len(matches) == 1 and state == "FRESH",
            "matched_relationship_count": len(matches) if state == "FRESH" else 0,
            "prior_contact_verified_absent": False,
            "crm_ownership_verified": False,
            "recipient_suppression_cleared": False,
            "outbound_authorized": False,
        }
        item["founder_review_ready"] = False
        item["outbound_authorized"] = False
        if status == "KNOWN_RELATIONSHIP_REVIEW_HOLD":
            item["review_tasks"] = sorted(set(item["review_tasks"]) | {
                "RECONCILE_EXISTING_COMMERCIAL_RELATIONSHIP_BEFORE_NEW_OUTREACH"})
        elif status == "AMBIGUOUS_RELATIONSHIP_HOLD":
            item["review_tasks"] = sorted(set(item["review_tasks"]) | {
                "RESOLVE_AMBIGUOUS_RELATIONSHIP_IDENTITY_NO_OUTBOUND"})
    output["summary"]["existing_relationship_domain_matches"] = related
    output["summary"]["ambiguous_relationship_domain_holds"] = ambiguous
    output["summary"]["relationship_registry_checked"] = state == "FRESH"
    output["existing_relationship_registry_state"] = state
    output["canonical_contact_history_checked"] = False
    output["suppression_verified_clear"] = False
    output["outbound_authorized"] = False
    output["execution_authority"] = "none"
    output["review_digest"] = sha256(json.dumps({
        "as_of": output["as_of"], "summary": output["summary"],
        "packets": packets, "registry_state": state,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return output
