"""Read-only revenue sniper over EXISTING Empire buyer scanner evidence.

Consumes bounded local Empire buyer_acquisition_scout.v1 snapshot; does not
launch a crawler, invoke any sniper agent, write EmpireDB, send outreach,
purchase traffic, execute a trade, activate seats or claim verified buyer intent.
Existing scout and source providers remain authoritative for observations.

This is a research ranking, NOT a sale, contact, verified buyer or lead score.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlsplit
import ipaddress
import re

SCOUT_SCHEMA = "empire.buyer_acquisition_scout.v1"
RESULT_SCHEMA = "empire.revenue_scanner_sniper_review.v1"
MAX_CANDIDATES = 100
MAX_QUERIES = 100
STALE_AFTER_HOURS = 24
REGULATED_LANES = frozenset({"insurance", "legal_services", "legal_mass_tort"})
APPROVED_LANES = frozenset({
    "predictive_revenue_enterprise", "home_service_growth",
    "permit_home_services", "insurance", "legal_services", "legal_mass_tort",
})
SOURCE_CLASSES = frozenset({
    "public_research_seed", "canonical_prospect_seed",
    "search_fabric", "intent_signal_seed",
})
# No individuals, patients, homeowners, claimants or vulnerable-case targeting.
B2B_BUSINESS_TYPES = frozenset({
    "direct_buyer", "agency", "white_label_agency",
    "publisher_affiliate_partner", "insurance_broker", "insurance_carrier",
    "managed_repair_network", "third_party_administrator", "law_firm",
    "unknown",
})


def _hostname(value) -> str:
    if not isinstance(value, str) or not value or len(value) > 255:
        return ""
    candidate = value if "://" in value else "https://" + value
    try:
        u = urlsplit(candidate)
        host = (u.hostname or "").lower().rstrip(".")
        if u.scheme != "https" or u.username or u.password or u.port is not None:
            return ""
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", host):
            return ""
        if "." not in host or host.endswith((".local", ".internal", ".localhost")):
            return ""
        ipaddress.ip_address(host)
    except ValueError:
        # Here, ValueError from ipaddress means a DNS hostname rather than IP.
        return host if re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", host) else ""
    return ""


def _fresh_enough(text, now: datetime) -> bool:
    try:
        observed = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            return False
        lag = (now - observed).total_seconds() / 3600
        return -1 <= lag <= STALE_AFTER_HOURS
    except (ValueError, TypeError, OverflowError):
        return False


def _priority(candidate: Mapping, *, lane: str) -> tuple[int, list[str]]:
    """Stable transparent RESEARCH priority only; never a readiness score."""
    points = 0
    facts = []
    if candidate.get("discovery_source") == "canonical_prospect_seed":
        points += 2
        facts.append("canonical_seed_reference_observed_not_verified")
    if candidate.get("decision_maker_state") == "OBSERVED_ROLE_MATCH":
        points += 2
        facts.append("first_party_role_match_observed")
    if candidate.get("economic_capacity_state") == "OBSERVED_PROXY":
        points += 1
        facts.append("economic_capacity_proxy_only")
    trigger = candidate.get("observed_buying_triggers")
    if isinstance(trigger, list) and trigger:
        points += 1
        facts.append("buying_trigger_research_observed_not_buyer_confirmation")
    if candidate.get("intent_band") == "high":
        points += 1
        facts.append("intent_research_band_high_unconfirmed")
    fit = candidate.get("continuous_lane_fit_score")
    if type(fit) is int and 70 <= fit <= 100 and lane in APPROVED_LANES:
        points += 1
        facts.append("high_internal_lane_fit_heuristic")
    return points, facts


def _safe_result(
    candidate: Mapping, *, now: datetime, snapshot_fresh: bool,
) -> dict:
    reasons = []
    lane = candidate.get("continuous_commercial_lane")
    if lane not in APPROVED_LANES:
        reasons.append("unclassified_commercial_lane")
    source = candidate.get("discovery_source")
    if source not in SOURCE_CLASSES:
        reasons.append("unknown_research_source")
    host = _hostname(candidate.get("domain") or "")
    if not host:
        reasons.append("invalid_or_unverified_source_domain")
    if candidate.get("candidate_state") != "RESEARCH_EVIDENCE_ONLY":
        reasons.append("unexpected_candidate_state")
    if candidate.get("outreach_authorized") is not False:
        reasons.append("outreach_flag_must_be_false")
    if candidate.get("buyer_type") not in B2B_BUSINESS_TYPES:
        reasons.append("target_must_be_b2b_company")
    if not snapshot_fresh:
        reasons.append("source_snapshot_stale_or_future")
    if candidate.get("canonical_identity_verified") is not True:
        reasons.append("canonical_business_identity_not_verified")
    if candidate.get("budget_verified") is not True:
        reasons.append("buyer_budget_not_verified")
    if candidate.get("commercial_terms_verified") is not True:
        reasons.append("commercial_terms_not_verified")
    if candidate.get("direct_buyer_score", 0) == 0:
        reasons.append("direct_buyer_relationship_not_proven")

    if lane in REGULATED_LANES:
        # The existing scanner has no independent law/insurance-specific
        # review certificate. Keep regulated candidates on specialist hold.
        reasons.append("regulated_firm_only_jurisdiction_review_required")
        if lane in {"legal_services", "legal_mass_tort"}:
            if candidate.get("buyer_type") != "law_firm":
                reasons.append("law_firm_identity_not_proven")

    points, facts = _priority(candidate, lane=str(lane or ""))
    blocking = (
        not host
        or source not in SOURCE_CLASSES
        or lane not in APPROVED_LANES
        or candidate.get("candidate_state") != "RESEARCH_EVIDENCE_ONLY"
        or candidate.get("outreach_authorized") is not False
        or candidate.get("buyer_type") not in B2B_BUSINESS_TYPES
        or not snapshot_fresh
    )
    rank = "SOURCE_HOLD" if blocking else (
        "REGULATED_HOLD" if lane in REGULATED_LANES else (
            "PRIORITY_RESEARCH" if points >= 3 else "RESEARCH_REVIEW"
        )
    )
    next_action = (
        "validate legal/insurance B2B firm status, source rights and local jurisdiction"
        if lane in REGULATED_LANES
        else "verify company identity, actual budget, buyer authority and signed offer"
    )
    identity = sha256((host + "|" + str(lane)).encode()).hexdigest()[:16]
    return {
        "candidate_key": identity,
        "domain": host,  # Public corporate domain, not emails/people.
        "lane": lane if lane in APPROVED_LANES else None,
        "source": source if source in SOURCE_CLASSES else None,
        "research_rank": rank,
        "research_priority_points": points,
        "priority_basis": facts,
        "blocking_reasons": sorted(set(reasons)),
        "next_action": next_action,
        "canonical_buyer_verified": False,
        "buyer_capacity_verified": False,
        "lead_sellable": False,
        "outbound_authorized": False,
        "sniper_execution_authorized": False,
    }


def review_existing_scout_snapshot(
    snapshot: Mapping, *, now: datetime | None = None,
) -> dict:
    """Pure review of already-captured scanner evidence, without side effects."""
    if not isinstance(snapshot, Mapping):
        raise TypeError("scout snapshot must be a mapping")
    candidates = snapshot.get("candidates")
    queries = snapshot.get("queries")
    if (snapshot.get("schema_version") != SCOUT_SCHEMA
            or snapshot.get("mode") != "OBSERVE"
            or snapshot.get("database_write_performed") is not False
            or snapshot.get("outbound_sent") is not False
            or snapshot.get("execution_authority") != "none"
            or not isinstance(candidates, list)
            or len(candidates) > MAX_CANDIDATES
            or not isinstance(queries, list) or len(queries) > MAX_QUERIES):
        raise ValueError("untrusted_or_unbounded_scout_snapshot")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone aware")
    fresh = _fresh_enough(snapshot.get("generated_at"), current)
    rows = []
    seen: dict[str, dict] = {}
    duplicates = 0
    for raw in candidates:
        if not isinstance(raw, Mapping):
            raise ValueError("candidate_not_mapping")
        row = _safe_result(raw, now=current, snapshot_fresh=fresh)
        prior = seen.get(row["candidate_key"])
        if prior is not None:
            # Never discard contradictory records or keep the highest-scored
            # duplicate as if it were a genuine independently verified buyer.
            duplicates += 1
            prior["research_rank"] = "SOURCE_HOLD"
            prior["blocking_reasons"] = sorted(set(
                prior["blocking_reasons"] + ["duplicate_company_lane_requires_reconciliation"]
                + row["blocking_reasons"]
            ))
            continue
        seen[row["candidate_key"]] = row
        rows.append(row)

    # Strongest research priority first, but without implying a valid buyer.
    rows.sort(key=lambda r: (
        r["research_rank"] not in {"PRIORITY_RESEARCH", "RESEARCH_REVIEW"},
        -r["research_priority_points"], r["candidate_key"]
    ))
    counts = Counter(r["research_rank"] for r in rows)
    raw_failures = snapshot.get("probe_failure_counts") or {}
    diag = {
        str(k)[:80]: v for k, v in raw_failures.items()
        if isinstance(k, str) and type(v) is int and v >= 0
    } if isinstance(raw_failures, Mapping) else {}
    return {
        "schema_version": RESULT_SCHEMA,
        "mode": "READ_ONLY_EXISTING_SCANNER_SNAPSHOT",
        "scout_observed_at": snapshot.get("generated_at"),
        "source_snapshot_fresh_under_24h": fresh,
        "scanner_rows_observed": len(candidates),
        "distinct_business_lane_keys": len(rows),
        "duplicate_company_lane_observations": duplicates,
        "research_rank_counts": dict(sorted(counts.items())),
        "source_failure_counts": dict(sorted(diag.items())),
        "research_candidates": rows,
        "sniper_runner_mode": "REVIEW_ONLY_NO_LIVE_LAUNCH",
        "existing_scout_timer_reused": True,
        "commercially_verified_buyers": 0,
        "live_outreach": False,
        "financial_execution": False,
        "canonical_database_writes": False,
        "execution_authority": "none",
        "buyer_capacity_verified": False,
        "note": "Priority heuristic ranks manual research only; all commercial claims require independent receipts",
    }
