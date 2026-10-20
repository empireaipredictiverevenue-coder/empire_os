"""Empire A2A Signal Miner — conservative cross-source commercial research.

Reuses EmpireOS community-intent and Revenue GPS read-only summaries to identify
evidence-backed research priorities. It never turns an inferred signal into a
verified buyer, sale, permission to send, or data resale entitlement.

No network, social scraping, CRM writes, database access, messages or payments.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Mapping
import json
import math
import re

SCHEMA = "empire.a2a.signal_mining.review.v1"
AGENT_ID = "empire.a2a.commercial_signal_miner.v1"
COMMUNITY_SCHEMA = "empire.community_intent.v2"
GPS_SCHEMA = "empire.market_sweep_revenue_gps.v1"

CAPABILITIES = (
    ("intelligence.source.review", "Evaluate existing licensed or permitted source summaries"),
    ("intelligence.buyer_signal.rank", "Rank B2B buyer research priorities, not verified buyers"),
    ("intelligence.market_gap.match", "Cross-reference market research and buyer evidence"),
    ("intelligence.money_opportunity.review", "Form unpriced opportunity hypotheses, no revenue claims"),
    ("campaign.microsegment.draft", "Draft tightly scoped internal campaign experiments"),
    ("finance.payment_request.plan", "Prepare a request for existing finance owner, never issue a payment link"),
    ("a2a.commerce.intent.handoff", "Propose governed specialist handoff without dispatch"),
)
DATA_OFFERS = {
    "general_contractor": {
        "product": "nyc_permit_project_verification",
        "audience": "commercial construction firms, specialist contractors and project intelligence buyers",
        "pain": "Verify recent projects and identify relevant commercial activity",
        "channel": "owned_search_content",
    },
    "hvac": {
        "product": "founder_original_intelligence_reports",
        "audience": "US HVAC multi-location operators and verified lead/call buyers",
        "pain": "Identify underserved territories, demand gaps and measurable acquisition costs",
        "channel": "owned_search_content",
    },
    "roofing": {
        "product": "founder_original_intelligence_reports",
        "audience": "US roofing operators, verified appointment buyers and growth partners",
        "pain": "Find service-area demand gaps and understand seasonal opportunities",
        "channel": "owned_search_content",
    },
    "predictive_revenue_enterprise": {
        "product": "founder_original_intelligence_reports",
        "audience": "revenue operations leaders at B2B growth organisations",
        "pain": "Forecast uncertainty, demand attribution and sales leakage",
        "channel": "owned_b2b_content",
    },
}
OTHER_OFFERS = {
    "lead_generation": ("predictive_revenue_demand_engine", "US performance marketing buyers and local service operators", "qualified demand acquisition"),
    "revenue_growth": ("predictive_revenue", "revenue operations leaders and performance-focused founders", "pipeline and revenue forecasting"),
    "search_visibility": ("search_growth_command", "multi-location businesses and specialist agencies", "search visibility and AI discovery"),
    "sales_conversion": ("revenue_conversion_system", "B2B sales leaders and growing service businesses", "lead-to-appointment conversion"),
    "automation_ops": ("empire_automation_os", "operations managers and agencies", "manual workflow overhead"),
}
_SAFE_LABEL = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_SAFE_METRO = re.compile(r"^[A-Za-z0-9 .,/-]{3,80}$")
FORBIDDEN_KEYS = frozenset({
    "email", "phone", "person_name", "first_name", "last_name", "username",
    "user_id", "message", "raw_text", "contact", "cookies", "access_token",
    "session", "profile_id", "ip_address", "dm",
})


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def _valid_source(packet: Mapping[str, Any], kind: str, *, now: datetime) -> tuple[bool, str]:
    if not isinstance(packet, Mapping) or packet.get("schema_version") != (
        COMMUNITY_SCHEMA if kind == "community" else GPS_SCHEMA
    ):
        return False, "INVALID_SOURCE_SCHEMA"
    if packet.get("mode") != "OBSERVE" or str(packet.get("execution_authority")).lower() != "none":
        return False, "REJECT_NON_OBSERVE_SOURCE"
    if kind == "gps" and any(packet.get(k) is not False for k in (
        "outreach_enabled", "revenue_inferred", "buyer_intent_inferred", "commercial_intent_inferred"
    )):
        return False, "REJECT_EXCESS_AUTHORITY"
    if kind == "community" and packet.get("outreach_authority") != "none":
        return False, "REJECT_EXCESS_AUTHORITY"
    stamp = _time(packet.get("observed_at" if kind == "community" else "generated_at"))
    if stamp is None or stamp < now - timedelta(hours=48) or stamp > now + timedelta(minutes=5):
        return False, "SOURCE_STALE_OR_INVALID_TIMESTAMP"
    return True, "OBSERVED_SOURCE_FRESH_NOT_VERIFIED_BUYER"


def agent_card() -> dict[str, Any]:
    """Internally discoverable identity card, NOT externally registered credentials."""
    return {
        "schema_version": "empire.a2a.agent_capability_card.v1",
        "agent_id": AGENT_ID,
        "display_name": "Empire AI Commercial Signal Miner",
        "organisation": "Empire AI",
        "registration": {
            "internal_catalogue": "candidate_defined",
            "external_agent_network": "not_registered",
            "cryptographic_identity": "not_provisioned",
            "trusted_by_other_agents": False,
        },
        "capabilities": [
            {"name": name, "description": description,
             "authenticated_a2a_required": True,
             "approval_required_for_external_effects": True,
             "callable_endpoint_deployed": False}
            for name, description in CAPABILITIES
        ],
        "security": {
            "signature_and_replay_verification_required": True,
            "authority": "OBSERVE_ONLY",
            "outbound": False, "data_resale": False,
            "production_dispatch": False, "financial_execution": False,
        },
        "compatible_owner_boundaries": [
            "community_intent", "buyer_scout", "data_brokerage",
            "owned_campaigns", "predictive_revenue", "finance_os",
        ],
    }


def _segment_id(*parts: str) -> str:
    return sha256("|".join(parts).encode()).hexdigest()[:16]


def mine_signals(
    *,
    community: Mapping[str, Any],
    revenue_gps: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("current_time_timezone_required")
    now = now.astimezone(timezone.utc)
    c_ok, c_state = _valid_source(community, "community", now=now)
    g_ok, g_state = _valid_source(revenue_gps, "gps", now=now)
    sources = {
        "community_intent": {"available": c_ok, "state": c_state},
        "revenue_gps": {"available": g_ok, "state": g_state},
    }
    # A source's self-report of collection 'ok' is not independent source licensing.
    successes = ((community.get("source_status") or {}) if c_ok else {})
    sources["community_intent"]["collection_quality"] = {
        k: "LATEST_RETRIEVAL_OK" if isinstance(v, Mapping) and v.get("ok") is True else "LATEST_RETRIEVAL_NOT_VERIFIED"
        for k, v in successes.items()
    }
    candidates: list[dict[str, Any]] = []
    holds: list[str] = []
    if c_ok:
        briefs = community.get("pain_solution_briefs")
        if not isinstance(briefs, list) or len(briefs) > 100:
            holds.append("COMMUNITY_BRIEF_SHAPE_HOLD")
            briefs = []
        for brief in briefs:
            if not isinstance(brief, Mapping):
                continue
            pain = brief.get("pain_point")
            if pain not in OTHER_OFFERS:
                continue
            observed = brief.get("observed_mentions")
            high = brief.get("high_intent_mentions")
            if type(observed) is not int or type(high) is not int or not 0 <= high <= observed <= 10000:
                holds.append("BAD_COMMUNITY_INTENT_COUNTS")
                continue
            offer, audience, angle = OTHER_OFFERS[pain]
            platforms = brief.get("source_mix")
            platforms = platforms if isinstance(platforms, list) else []
            verified_platforms = sorted({
                p for p in platforms if isinstance(p, str) and p in successes
                and isinstance(successes[p], Mapping) and successes[p].get("ok") is True
            })
            # Ranking weight merely prioritises analyst time; does not represent purchase probability.
            priority = min(60, 5 + min(observed, 10) * 2 + min(high, 5) * 5 + len(verified_platforms) * 3)
            candidates.append({
                "segment_id": _segment_id("community", str(pain), str(offer)),
                "source_domain": "community_intent", "buyer_class": "B2B_BROAD",
                "niche": str(pain), "metro": "not_established",
                "pain_point": pain, "offer_hypothesis": offer,
                "recommended_audience": audience, "campaign_angle": angle,
                "supported_by_latest_successful_platforms": verified_platforms,
                "observed_mentions_unverified": observed, "high_intent_mentions_unverified": high,
                "research_priority_score_not_probability": priority,
                "evidence_status": "DISCUSSION_ONLY_NOT_VERIFIED_BUYER",
            })
    if g_ok:
        queue = revenue_gps.get("research_queue")
        if not isinstance(queue, list) or len(queue) > 100:
            holds.append("GPS_QUEUE_SHAPE_HOLD")
            queue = []
        seen = set()
        for entry in queue:
            if not isinstance(entry, Mapping):
                continue
            niche, metro, priority = entry.get("niche"), entry.get("metro"), entry.get("research_priority_score")
            if not (isinstance(niche, str) and _SAFE_LABEL.fullmatch(niche) and
                    isinstance(metro, str) and _SAFE_METRO.fullmatch(metro) and
                    isinstance(priority, (int, float)) and not isinstance(priority, bool) and
                    math.isfinite(priority) and 0 <= priority <= 100):
                holds.append("INVALID_GPS_RESEARCH_ROW")
                continue
            if (niche, metro) in seen:
                holds.append("DUPLICATE_GPS_MARKET")
                continue
            seen.add((niche, metro))
            if entry.get("external_execution_authorized") is not False or entry.get("mutation_authorized") is not False:
                holds.append("REJECT_UNSAFE_GPS_RESEARCH_ROW")
                continue
            offer = DATA_OFFERS.get(niche)
            if offer is None:
                continue
            candidates.append({
                "segment_id": _segment_id("gps", niche, metro),
                "source_domain": "revenue_gps",
                "buyer_class": "B2B_DATA_OR_INTELLIGENCE_BUYER",
                "niche": niche, "metro": metro,
                "pain_point": offer["pain"], "offer_hypothesis": offer["product"],
                "recommended_audience": offer["audience"],
                "campaign_angle": offer["pain"], "preferred_channel": offer["channel"],
                "research_priority_score_not_probability": round(float(priority), 2),
                "evidence_status": "GEO_MARKET_RESEARCH_NOT_BUYER_OR_LICENSE_PROOF",
            })
    candidates.sort(key=lambda x: (-x["research_priority_score_not_probability"], x["segment_id"]))
    # A campaign is a draft for *research*, not a deliverable to a specific person.
    campaign_briefs = []
    for rank, item in enumerate(candidates[:10], 1):
        campaign_briefs.append({
            "campaign_key": "a2a-signal-" + item["segment_id"],
            "rank_for_research": rank, "target_sector": item["niche"],
            "target_geography": item["metro"], "audience_hypothesis": item["recommended_audience"],
            "data_product_hypothesis": item["offer_hypothesis"],
            "value_proposition_hypothesis": item["campaign_angle"],
            "suggested_channels": ["owned_search_and_organic_content", "consented_b2b_partner_introductions"],
            "do_not_use": ["personal_social_profiles", "group_member_lists", "unconsented_custom_audiences"],
            "qualifying_questions": [
                "Does the business buy this kind of data or intelligence?",
                "What territories and fields must be covered?",
                "What legitimate licence and provenance are required?",
                "What is the measurable business use and approved budget?",
            ],
            "test_plan": {
                "phase": "DISCOVER_VERIFY_DRAFT_MEASURE",
                "first_metric": "independently_verified_buying_interest",
                "validation": "buyer written requirements and accepted licence terms",
            },
            "gates": [
                "SOURCE_RIGHTS_REVIEW", "INDEPENDENT_BUSINESS_VERIFICATION",
                "PRODUCT_DELIVERABILITY_PROOF", "CAMPAIGN_CONSENT_AND_REVIEW",
                "FOUNDER_APPROVAL_BEFORE_PUBLISH_OR_CONTACT",
            ],
            "outbound_sent": False, "live_campaign_started": False,
            "verified_buyer": False, "revenue_booked": False,
        })
    return {
        "schema_version": SCHEMA, "agent_id": AGENT_ID,
        "generated_at": now.isoformat(),
        "status": "RESEARCH_CANDIDATES" if candidates else "SOURCE_RESEARCH_HOLD",
        "source_status": sources, "holds": sorted(set(holds)),
        "buyer_signal_research_count": len(candidates),
        "market_candidate_count": sum(c["source_domain"] == "revenue_gps" for c in candidates),
        "campaign_brief_count": len(campaign_briefs),
        "prioritized_research_signals": candidates,
        "campaign_briefs": campaign_briefs,
        "verified_buyers_discovered": 0, "verified_money_opportunities": 0,
        "revenue_verified": False, "data_resale_rights_verified": False,
        "execution_authority": "NONE", "database_writes": False,
        "network_requests": False, "meta_scraping": False,
        "outbound_sent": False, "publishing_performed": False,
        "campaign_spend": 0, "bank_access": False, "payment_links_created": False,
        "hand_off_routes_not_connected": ["buyer_scout", "data_brokerage", "campaign_owner", "finance_os"],
        "agent_registration": agent_card()["registration"],
    }
