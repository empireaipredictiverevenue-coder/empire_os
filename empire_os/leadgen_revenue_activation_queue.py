"""Private read-only Lead Generation revenue activation work queue.

Joins *aggregate niches only*, never identities: existing buyer-qualification
actions (real B2B research), canonical EmpireDB Exchange selected inventory and
preflighted official source research. Strictly no auto-contact, offer, sale,
buying-intent claim, new leads, or database write.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import datetime, timezone
import re
from urllib.parse import urlsplit
from typing import Any

from empire_os.lead_exchange_live_inventory import build_lead_exchange_live_inventory
from scripts.build_buyer_qualification_actions import EVIDENCE_TASKS

SCHEMA = "empire.leadgen_revenue_activation_queue.v1"
BUYER_SCHEMA = "empire.buyer_qualification_actions.v1"
SOURCE_SCHEMA = "empire.official_source_canonical_preflight.v1"
DOM_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
BLOCKED_DOMAINS = (".example", ".test", ".invalid", ".localhost", ".internal", ".local")
NICHE_ALIASES = {
    "roofing": "roofing", "solar": "solar", "hvac": "hvac",
    "plumbing": "plumbing", "restoration": "restoration",
    "dental": "dental", "insurance": "insurance", "legal": "legal",
}
MAX_TARGETS = 100
MAX_VISIBLE = 25
AGE_HOURS = 6


def _validated_first_party_urls(domain: str, raw: Any) -> list[str]:
    """Keep only small, clean verified-origin B2B research references."""
    if not isinstance(raw, list):
        return []
    links = []
    for candidate in raw[:12]:
        if not isinstance(candidate, str) or len(candidate) > 900:
            continue
        try:
            parsed = urlsplit(candidate)
            hostname = (parsed.hostname or "").lower().rstrip(".")
            if (parsed.scheme != "https" or parsed.username or parsed.password
                    or parsed.port is not None or parsed.fragment
                    or not (hostname == domain or hostname == "www." + domain)
                    or not parsed.path.startswith("/")):
                continue
        except ValueError:
            continue
        if candidate not in links:
            links.append(candidate)
        if len(links) == 5:
            break
    return links


def _valid_ts(value: Any, now: datetime) -> bool:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return False
        age = (now - stamp).total_seconds()
        return -300 <= age <= AGE_HOURS * 3600
    except (TypeError, ValueError, OverflowError):
        return False


def _hold(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY_PRIVATE_LEADGEN",
        "state": "HOLD",
        "reason": reason,
        "qualified_buyers": 0, "verified_buyer_capacity": 0,
        "immediately_sellable_inventory": 0,
        "ready_for_outbound": 0, "buyer_outreach_authorized": False,
        "prospect_insert_authorized": False,
        "canonical_empiredb_writes": False,
        "public_inventory_claim_allowed": False,
        "execution_authority": "none",
    }


def build_leadgen_revenue_queue(
    *,
    exchange: Mapping,
    buyer_actions: Mapping,
    source_preflight: Mapping | None = None,
    max_visible: int = 15,
    now: datetime | None = None,
) -> dict[str, Any]:
    """One actionable *research* plan backed by current verified snapshots."""
    if type(max_visible) is not int or not 1 <= max_visible <= MAX_VISIBLE:
        raise ValueError("bounded_visible_target_count_required")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("timezone_aware_current_time_required")

    inv = build_lead_exchange_live_inventory(exchange, now=current)
    if inv["state"] != "FRESH_CANONICAL_SNAPSHOT":
        return _hold("canonical_exchange_not_fresh_or_valid")
    if not isinstance(buyer_actions, Mapping):
        return _hold("buyer_qualification_actions_missing")
    required = {
        "schema_version": BUYER_SCHEMA,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "outbound_enabled": False,
        "outbound_sent": False,
        "human_review_required": True,
        "buyer_conversation_verified": False,
        "contact_verified_for_outbound_count": 0,
    }
    if any(buyer_actions.get(k) != v for k, v in required.items()):
        return _hold("buyer_qualification_actions_contract_mismatch")
    if not _valid_ts(buyer_actions.get("generated_at"), current):
        return _hold("buyer_qualification_actions_stale")
    targets = buyer_actions.get("targets")
    if (not isinstance(targets, list) or len(targets) > MAX_TARGETS
            or buyer_actions.get("shortlisted_count") != len(targets)):
        return _hold("buyer_qualification_target_count_inconsistent")

    market_counts = Counter()
    for group in inv["markets"]:
        name = group["niche"].lower().strip()
        if name in NICHE_ALIASES:
            market_counts[name] += group["selected_inventory_records"]
    gap_summary = Counter()
    sector_target_count = Counter()
    rows = []
    seen = set()
    for item in targets:
        if not isinstance(item, Mapping):
            return _hold("buyer_target_not_mapping")
        domain = item.get("domain")
        if (not isinstance(domain, str) or not DOM_RE.fullmatch(domain)
                or len(domain) > 253 or domain in seen
                or domain.endswith(BLOCKED_DOMAINS)):
            return _hold("invalid_or_duplicate_buyer_company_domain")
        seen.add(domain)
        if (item.get("tier") not in {
                "EVIDENCE_RECOVERY", "FOUNDER_REVIEW_ONLY",
                "DUE_DILIGENCE_PENDING", "AUTOMATED_EVIDENCE_HOLD",
                "MANUAL_EVIDENCE_HOLD",
            } or item.get("outbound_authorized") is not False
                or item.get("canonical_contact_or_reply_verified") is not False
                or item.get("commercial_terms_verified") is not False):
            return _hold("buyer_review_authority_conflict")
        score = item.get("founder_priority")
        if type(score) is not int or not 0 <= score <= 100:
            return _hold("untrusted_research_priority_score")
        gaps = item.get("missing_evidence")
        if not isinstance(gaps, list) or len(gaps) > 12:
            return _hold("unbounded_buyer_evidence_requirements")
        if not all(isinstance(g, str) and g in EVIDENCE_TASKS for g in gaps):
            return _hold("unregistered_buyer_evidence_requirement")
        gaps = list(dict.fromkeys(gaps))
        gap_summary.update(gaps)
        verticals = item.get("verticals")
        if not isinstance(verticals, list) or len(verticals) > 10:
            return _hold("unbounded_buyer_verticals")
        exact_niches = sorted({NICHE_ALIASES[v] for v in verticals
                               if isinstance(v, str) and v in NICHE_ALIASES})
        for n in exact_niches:
            sector_target_count[n] += 1
        # Overlap is only a vertical-tag coincidence: no geography, terms,
        # consent, delivery type, pricing, buyer acceptance or route match.
        market_overlap = {n: market_counts[n] for n in exact_niches
                          if market_counts[n]}
        due = item.get("first_party_due_diligence")
        due = due if isinstance(due, Mapping) else {}
        research_links = _validated_first_party_urls(
            domain, item.get("existing_first_party_source_urls")
        )
        rows.append({
            "domain": domain,
            "tier": item["tier"],
            "founder_research_priority_not_buyer_intent": score,
            "observed_vertical_tags": exact_niches,
            "unverified_vertical_only_supply_overlap": market_overlap,
            "territory_or_buyer_capacity_match_verified": False,
            "first_party_site_review_current": due.get("freshness") == "CURRENT",
            "first_party_buyer_role_corroborated_not_capacity": (
                item.get("site_corroborated_buyer_role") is True
            ),
            "missing_evidence": gaps,
            "evidence_checklist": [
                {"evidence_key": g, "required_proof": EVIDENCE_TASKS[g],
                 "verified": False}
                for g in gaps
            ],
            "first_party_research_links_for_manual_review": research_links,
            "next_action": EVIDENCE_TASKS[gaps[0]] if gaps else (
                "Independent buyer terms, territory, capacity and contact-path confirmation"
            ),
            "action_type": "MANUAL_B2B_BUYER_RESEARCH",
            "buyer_committed": False,
            "purchase_intent_verified": False,
            "outbound_authorized": False,
        })
    if buyer_actions.get("trusted_founder_review_count") != sum(
        1 for row in rows if row["tier"] == "FOUNDER_REVIEW_ONLY"
    ):
        return _hold("founder_review_count_not_reconciled")

    # Known first-party research can inform priority order; no implied
    # absolute buying intent. Preserve manual holds at bottom.
    tiers = {
        "FOUNDER_REVIEW_ONLY": 0,
        "DUE_DILIGENCE_PENDING": 1,
        "EVIDENCE_RECOVERY": 2,
        "AUTOMATED_EVIDENCE_HOLD": 3,
        "MANUAL_EVIDENCE_HOLD": 4,
    }
    rows.sort(key=lambda row: (
        tiers[row["tier"]],
        -int(row["first_party_site_review_current"]),
        -int(row["first_party_buyer_role_corroborated_not_capacity"]),
        -row["founder_research_priority_not_buyer_intent"],
        row["domain"],
    ))
    source = {
        "source_rows_observed": None,
        "businesses_prepared_for_review_not_ingested": None,
        "source_rows_held": None,
    }
    if source_preflight is not None:
        if (not isinstance(source_preflight, Mapping)
                or source_preflight.get("schema_version") != SOURCE_SCHEMA
                or source_preflight.get("mode") != "OFFICIAL_TO_CANONICAL_REVIEW_ONLY"
                or source_preflight.get("canonical_empiredb_writes") is not False
                or source_preflight.get("outbound_authorized") is not False
                or source_preflight.get("verified_net_new_empiredb_prospects") != 0
                or source_preflight.get("exchange_inventory_added") != 0):
            return _hold("untrusted_source_research_preflight")
        observed = source_preflight.get("source_rows_observed")
        prepared = source_preflight.get("company_source_rows_prepared_not_ingested")
        held = source_preflight.get("held_source_rows")
        if (any(type(x) is not int or not 0 <= x <= 100 for x in (
                observed, prepared, held)) or observed != prepared + held):
            return _hold("source_preflight_totals_inconsistent")
        source = {
            "source_rows_observed": observed,
            "businesses_prepared_for_review_not_ingested": prepared,
            "source_rows_held": held,
        }
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY_PRIVATE_LEADGEN",
        "state": "FOUNDER_RESEARCH_QUEUE_READY",
        "generated_at": current.isoformat(),
        "buyer_research_observed_at": buyer_actions["generated_at"],
        "canonical_exchange_observed_at": exchange["observed_at"],
        "research_target_count": len(rows),
        "buyer_research_review_ready_count": buyer_actions["trusted_founder_review_count"],
        "qualified_buyers": 0,
        "verified_buyer_capacity": 0,
        "immediately_sellable_inventory": 0,
        "canonical_selected_inventory_records": inv["selected_inventory_records"],
        "canonical_evidence_hold_records": inv["evidence_hold_records"],
        "canonical_capacity_waitlist_records": inv["buyer_capacity_waitlist_records"],
        "observed_supply_by_vertical_not_buyer_mapped": dict(sorted(market_counts.items())),
        "buyer_research_targets_by_vertical": dict(sorted(sector_target_count.items())),
        "buyer_evidence_gap_counts": dict(sorted(gap_summary.items())),
        "source_research": source,
        "founder_research_queue": rows[:max_visible],
        "queue_rows_hidden_for_preview_limit": len(rows) - min(len(rows), max_visible),
        "next_revenue_priority": "Find independently verified buyers willing to purchase niche/territory inventory, then obtain signed capacity and commercial terms",
        "territory_matching_performed": False,
        "ready_for_outbound": 0,
        "buyer_outreach_authorized": False,
        "prospect_insert_authorized": False,
        "canonical_empiredb_writes": False,
        "public_inventory_claim_allowed": False,
        "execution_authority": "none",
    }
