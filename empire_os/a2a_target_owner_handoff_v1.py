"""Cross-agent targeting handoff built from authenticated-shape owner snapshots.

This is a REVIEW INBOX, never a command executed against source collectors or
the canonical Buyer Scout. Does not promote prospects, send messages or write
into another owner's runtime. Company identity and geography must be explicit
before a target can be treated as a reviewed buyer match.

No names, domains, emails, phone numbers, company records or post text are
copied into the handoff. Exact market matches use only counters and digests.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Mapping
import math
import re

from empire_os.a2a_founder_targeting_cycle_v1 import SCHEMA as PROFILE_SCHEMA
from empire_os.a2a_commercial_signal_miner import AGENT_ID

SCHEMA = "empire.a2a.targeted_owner_research_handoff.v1"
OWNER_STATES = frozenset(("RESEARCH_EVIDENCE_ONLY", "OWNER_REVIEW_PENDING"))
SAFE_DIMENSION = re.compile(r"^[a-z0-9_ ,.-]{2,90}$")

def _utc(value: Any) -> datetime | None:
    try:
        obj = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return obj.astimezone(timezone.utc) if obj.tzinfo else None

def _source_status(value: str) -> str:
    return "AVAILABLE_FOR_OWNER_REVIEW" if value == "PERMITTED_NICHE_RESEARCH_AVAILABLE_FOR_OWNER_REVIEW" else "GAP_REQUIRES_SOURCE_OWNER"

def _queries(niche: str, metro: str, product: str) -> list[str]:
    category = {
        "leads_calls_appointments": ("inbound call buyer", "buy qualified appointments"),
        "business_data_intelligence": ("commercial business data buyer", "buy market intelligence"),
        "revenue_conversion_software": ("sales conversion software", "revenue operations CRM"),
    }[product]
    industry = {
        "general_contractor": "commercial construction",
        "hvac": "HVAC",
        "roofing": "roofing",
        "agency": "agency",
        "b2b": "B2B",
        "solar": "solar",
        "plumbing": "plumbing",
        "law": "law firms",
    }[niche]
    return [f"{metro} {industry} {category[0]}",
            f"{metro} {industry} {category[1]}",
            f"{metro} {industry} business operator service area"]

def make_owner_research_handoffs(
    targeting: Mapping[str, Any],
    buyer_scout: Mapping[str, Any],
    *, now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("AWARE_NOW_REQUIRED")
    now = now.astimezone(timezone.utc)
    if (not isinstance(targeting, Mapping)
            or targeting.get("schema_version") != PROFILE_SCHEMA
            or targeting.get("execution_authority") != "NONE"
            or targeting.get("external_messages_sent") != 0
            or targeting.get("owner_agent_tasks_dispatched") != 0
            or targeting.get("qualified_leads_found") != 0):
        raise ValueError("UNTRUSTED_TARGETING_CYCLE")
    profiles = targeting.get("profiles")
    if not isinstance(profiles, list) or not 1 <= len(profiles) <= 10:
        raise ValueError("INVALID_TARGET_COUNT")
    if (not isinstance(buyer_scout, Mapping)
            or buyer_scout.get("schema_version") != "empire.buyer_acquisition_scout.v1"
            or buyer_scout.get("mode") != "OBSERVE"
            or str(buyer_scout.get("execution_authority")).lower() != "none"
            or buyer_scout.get("outbound_sent") is not False
            or buyer_scout.get("database_write_performed") is not False):
        raise ValueError("UNTRUSTED_CANONICAL_BUYER_SCOUT")
    stamp = _utc(buyer_scout.get("generated_at"))
    if stamp is None or stamp < now - timedelta(hours=48) or stamp > now + timedelta(minutes=5):
        raise ValueError("SCOUT_SNAPSHOT_STALE")
    candidates = buyer_scout.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 1000:
        raise ValueError("INVALID_BUYER_RESEARCH_CANDIDATES")
    if buyer_scout.get("candidate_count") != len(candidates):
        raise ValueError("SCOUT_CANDIDATE_COUNT_MISMATCH")
    # No inferred source names, domain tokens, personal contacts or other raw
    # data leave this function. Existing Buyer Scout remains sole identity owner.
    exact_validated = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("INVALID_SCOUT_RECORD")
        if candidate.get("outreach_authorized") is not False:
            raise ValueError("CANDIDATE_EXCEEDS_SCOUT_AUTHORITY")
        exact_niche = candidate.get("canonical_seed_niche")
        exact_metro = candidate.get("canonical_seed_metro") or candidate.get("metro")
        if not isinstance(exact_niche, str) or not isinstance(exact_metro, str):
            continue
        niche = exact_niche.strip().casefold()
        metro = exact_metro.strip().casefold()
        if not SAFE_DIMENSION.fullmatch(niche) or not SAFE_DIMENSION.fullmatch(metro):
            continue
        if candidate.get("canonical_identity_verified") is not True:
            continue
        if candidate.get("budget_verified") is not True or candidate.get("commercial_terms_verified") is not True:
            continue
        # Even an owner-verified company is NOT automatically an approved lead;
        # exact market evidence is a research overlap requiring owner readback.
        exact_validated[(niche, metro)] = exact_validated.get((niche, metro), 0) + 1
    tickets = []
    seen = set()
    for record in profiles:
        if not isinstance(record, Mapping):
            raise ValueError("INVALID_TARGET_PROFILE")
        spec, review = record.get("specification"), record.get("source_review")
        if not isinstance(spec, Mapping) or not isinstance(review, Mapping):
            raise ValueError("INVALID_TARGET_REVIEW_PAYLOAD")
        target_id = spec.get("target_id")
        if not isinstance(target_id, str) or not re.fullmatch(r"[a-f0-9]{20}", target_id) or target_id in seen:
            raise ValueError("DUPLICATE_OR_INVALID_TARGET_ID")
        seen.add(target_id)
        if (spec.get("agent_id") != AGENT_ID
                or spec.get("research_ready") is not True
                or spec.get("external_contact_authorized") is not False
                or spec.get("campaign_authorized") is not False
                or spec.get("execution_authority") != "NONE"):
            raise ValueError("TARGET_NOT_ELIGIBLE_FOR_OWNER_RESEARCH")
        niche, metro, product = (spec.get(k) for k in ("niche", "metro", "product_type"))
        if not (isinstance(niche, str) and SAFE_DIMENSION.fullmatch(niche)
                and isinstance(metro, str) and SAFE_DIMENSION.fullmatch(metro)
                and isinstance(product, str)
                and product in ("leads_calls_appointments",
                                "business_data_intelligence", "revenue_conversion_software")):
            raise ValueError("UNTRUSTED_TARGET_DIMENSIONS")
        if review.get("target_id") != target_id or review.get("execution_authority") != "NONE":
            raise ValueError("RESEARCH_NOT_BOUND_TO_TARGET")
        if (review.get("contact_authorized") is not False
                or review.get("ad_campaign_created") is not False
                or review.get("sales_qualified_leads") != 0):
            raise ValueError("TARGET_RESEARCH_PRIVILEGE_ESCALATION")
        known_overlap = exact_validated.get((niche, metro), 0)
        sources = review.get("permitted_sources")
        if not isinstance(sources, list) or len(sources) > 12:
            raise ValueError("INVALID_PERMITTED_SOURCE_RESULTS")
        # Source identities are stable, public, pre-existing collector entries.
        source_ids = sorted({entry["source_id"] for entry in sources
                             if isinstance(entry, Mapping)
                             and isinstance(entry.get("source_id"), str)
                             and re.fullmatch(r"[a-z][a-z0-9_]{3,80}", entry["source_id"])})
        actions = (
            ("community_intent", "PERMITTED_SOURCE_TOPIC_REVIEW",
             "Review the existing source atlas; if no niche-specific source is available, propose a policy-cleared collector expansion"),
            ("buyer_scout", "CANONICAL_COMPANY_AND_BUYER_CAPACITY_REVIEW",
             "Use existing Buyer Scout records and permitted public business data to verify company, location, role, live buying need, budget, terms and duplicate outreach state"),
        )
        for owner, capability, instruction in actions:
            ticket_id = sha256((target_id + "|" + owner + "|" + capability).encode()).hexdigest()[:24]
            tickets.append({
                "ticket_id": ticket_id,
                "target_id": target_id,
                "review_owner": owner,
                "requested_capability": capability,
                "state": "PREPARED_NOT_DELIVERED",
                "idempotency_key": "a2a-target-review:" + ticket_id,
                "sector": niche,
                "market": metro,
                "product": product,
                "target_roles_not_contact_identities": list(spec.get("buyer_roles_to_verify") or [])[:8],
                "exclude": list(spec.get("negative_filters") or [])[:8],
                "existing_public_atlas_source_ids": source_ids,
                "source_research_gap": len(source_ids) == 0,
                "buyer_scout_snapshot_research_candidate_count": len(candidates),
                "exact_sector_market_evidence_ready_for_owner_validation": known_overlap,
                "canonical_overlap_status": (
                    "EXACT_SECTOR_MARKET_RESEARCH_OVERLAP_FOR_OWNER_REVIEW" if known_overlap
                    else "NO_EXACT_VERIFIED_OVERLAP_IN_SCOUT_SNAPSHOT"
                ),
                "suggested_research_queries_not_executed": _queries(niche, metro, product),
                "acceptance_criteria": instruction,
                "dataset_or_social_post_identity_not_promoted": True,
                "owner_approval_required": True,
                "may_call_external_api": False,
                "may_write_canonical_crm": False,
                "may_send_messages": False,
            })
    tickets.sort(key=lambda x: (x["target_id"], x["review_owner"]))
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "agent_id": AGENT_ID,
        "generated_at": now.isoformat(),
        "buyer_scout_source_timestamp": stamp.isoformat(),
        "profiles_reviewed": len(seen),
        "existing_scout_research_candidate_count": len(candidates),
        "prepared_handoff_ticket_count": len(tickets),
        "handoff_tickets": tickets,
        "owner_queue_published": False,
        "owner_response_received": False,
        "duplicate_buyer_outreach_prevented_by_non_dispatch": True,
        "externally_verified_new_buyers": 0,
        "buyer_record_writes": 0,
        "tasks_dispatched": 0, "messages_sent": 0,
        "execution_authority": "NONE",
        "next_gate": "BUYER_SCOUT_AND_COMMUNITY_SOURCE_OWNER_CONTRACT_ACCEPTANCE",
    }


def make_handoff_source_hold(*, reason: str, profile_count: int, now: datetime | None = None) -> dict[str, Any]:
    """Explicitly continue upstream observation while buyer-owner data is unusable."""
    if reason not in ("BUYER_SCOUT_SOURCE_UNAVAILABLE", "BUYER_SCOUT_SOURCE_UNTRUSTED"):
        raise ValueError("UNKNOWN_OWNER_HOLD_REASON")
    if type(profile_count) is not int or not 0 <= profile_count <= 10:
        raise ValueError("INVALID_SOURCE_HOLD_PROFILE_COUNT")
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        raise ValueError("SOURCE_HOLD_CLOCK_MUST_BE_AWARE")
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE", "agent_id": AGENT_ID,
        "generated_at": stamp.astimezone(timezone.utc).isoformat(),
        "source_state": reason,
        "profiles_reviewed": profile_count,
        "existing_scout_research_candidate_count": None,
        "prepared_handoff_ticket_count": 0,
        "handoff_tickets": [], "owner_queue_published": False,
        "owner_response_received": False,
        "externally_verified_new_buyers": 0, "buyer_record_writes": 0,
        "tasks_dispatched": 0, "messages_sent": 0,
        "execution_authority": "NONE",
        "next_gate": "REFRESH_OR_VERIFY_CANONICAL_BUYER_SCOUT_SOURCE",
    }
