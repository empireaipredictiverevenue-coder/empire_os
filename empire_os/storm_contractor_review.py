"""Revenue Strike contractor review using existing EmpireOS evidence and governance.

This is a research/qualification projection. It NEVER infers a buyer, permits
outbound, writes CRM, sells a lead, accepts claims fees or starts contracts.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from hashlib import sha256
import json
from urllib.parse import urlparse

from empire_os.claims_exchange.adapters import normalized_domain
from empire_os.claims_exchange.controls import parse_date, reject_sensitive_input, safe_https_source
from empire_os.claims_exchange.dossier import build_dossiers

SCHEMA = "empire.revenue_strike.contractor_founder_review.v1"
SOURCE_SCHEMA = "empire.revenue_strike.dfw_public_signals.v1"
KNOWN_SIGNALS = frozenset({
    "public_sales_hiring", "claimed_capacity",
    "first_party_digital_customer_funnel", "public_business_contact",
})
SCORE = {
    "public_sales_hiring": 18,
    "claimed_capacity": 0,  # self-claimed; do not use as buyer capacity
    "first_party_digital_customer_funnel": 5,
    "public_business_contact": 0,
}


def _safe_signal_source(url: object, expected_domain: str) -> bool:
    if not safe_https_source(url):
        return False
    return normalized_domain(urlparse(url).hostname) == expected_domain


def build_contractor_review(cohort: Mapping, sites: Mapping,
                            signals: Mapping, *, as_of: date) -> dict:
    for source in (cohort, sites, signals):
        reject_sensitive_input(source)
    dossiers = build_dossiers(cohort, sites, as_of=as_of)
    if (not isinstance(signals, Mapping)
            or signals.get("schema") != SOURCE_SCHEMA
            or signals.get("market") != "Dallas-Fort Worth, TX"
            or not isinstance(signals.get("signals"), list)
            or len(signals["signals"]) > 100):
        raise ValueError("CONTRACTOR_SIGNALS_CONTRACT_UNSUPPORTED")
    by_domain: dict[str, list[dict]] = {}
    evidence_seen: set[tuple[str, str, str]] = set()
    for row in signals["signals"]:
        if not isinstance(row, Mapping):
            raise ValueError("SIGNAL_RECORD_INVALID")
        domain = normalized_domain(row.get("company_domain"))
        kind = row.get("kind")
        source_url = row.get("source_url")
        at = parse_date(row.get("observed_at"))
        if not domain or kind not in KNOWN_SIGNALS:
            raise ValueError("SIGNAL_KIND_OR_DOMAIN_UNTRUSTED")
        if not _safe_signal_source(source_url, domain):
            raise ValueError("NOT_FIRST_PARTY_SOURCE")
        if not at or at > as_of or (as_of-at).days > 30:
            raise ValueError("SIGNAL_STALE_OR_FUTURE")
        if row.get("verified_from_first_party_site") is not True:
            raise ValueError("SOURCE_NOT_REVIEWED")
        observed_fact = row.get("observed_fact")
        if not isinstance(observed_fact, str) or not 12 <= len(observed_fact) <= 350:
            raise ValueError("SIGNAL_FACT_NOT_BOUNDED")
        key = (domain, kind, source_url)
        if key in evidence_seen:
            continue
        evidence_seen.add(key)
        by_domain.setdefault(domain, []).append({
            "kind": kind, "source_url": source_url,
            "observed_at": at.isoformat(),
            "observation": observed_fact,
            "source_category": "company_self_report",
            "independently_verified_capacity": False,
            "commercial_buyer_intent_verified": False,
        })
    reviewed_domains = {p["original_domain"] for p in dossiers["dossiers"]}
    unknown = set(by_domain) - reviewed_domains
    if unknown:
        raise ValueError("SIGNAL_COMPANY_OUTSIDE_VERIFIED_COHORT")

    packets = []
    for r in dossiers["dossiers"]:
        domain = r["original_domain"]
        signals_for_company = sorted(by_domain.get(domain, []), key=lambda x: (x["kind"], x["source_url"]))
        kinds = {x["kind"] for x in signals_for_company}
        stage = r["qualification_stage"]
        site_ready = stage == "CORROBORATION_PENDING"
        score = (30 if site_ready else 0) + (8 if r["public_contact_source_observed"] else 0)
        if site_ready:
            score += sum(SCORE[k] for k in kinds)
        score = min(score, 75)  # strictly below qualification threshold
        tasks = list(r["research_tasks"])
        tasks += [
            "VERIFY_REGISTERED_COMPANY_AND_DOMAIN_CONTROL",
            "REVIEW_SUPPRESSION_AND_PRIOR_CONTACT_IN_CANONICAL_EMPIREDB",
            "IDENTIFY_REAL_MARKETING_OWNER_OR_AUTHORISED_BUSINESS_CONTACT",
            "CONFIRM_CURRENT_CAPACITY_BUDGET_AND_WILLINGNESS",
            "CHECK_EXACT_COMMERCIAL_OFFER_PRODUCT_AND_LEGAL_TERMS",
        ]
        if "public_sales_hiring" in kinds:
            tasks.append("QUALIFY_SALES_HIRING_RELEVANCE_NO_INTENT_INFERRED")
        if stage == "IDENTITY_CHANGE_HOLD":
            tasks.append("RESOLVE_OR_REJECT_REDIRECT_IDENTITY_NO_AUTO_MERGE")
        tasks = sorted(set(tasks))
        packets.append({
            "entity_id": r["entity_id"],
            "company_name": r["company_name"],
            "company_domain": domain,
            "market": "Dallas-Fort Worth, TX",
            "role": "potential_b2b_contractor_customer",
            "origin": "existing_revenue_strike_dfw_cohort",
            "qualification": stage,
            "research_priority_score": score,
            "source_evidence": signals_for_company,
            "site_review": r["site_evidence"],
            "review_tasks": tasks,
            "proposed_offer": {
                "marketing_registry_key": "storm_home_services_gtm",
                "offer_category": "fixed_fee_managed_growth_or_opportunity_intelligence",
                "pilot_fee_usd_hypothesis": 1500,
                "pilot_duration_days_hypothesis": 14,
                "binding_quote": False,
                "payable_claims_or_settlement_percentage": False,
                "buyer_capacity_verified": False,
                "market_demand_or_conversion_guaranteed": False,
            },
            "signing": {
                "provider": "documenso",
                "existing_deal_room": "/v1/deal-room",
                "contract_stage": "NOT_CREATED",
                "send_authorized": False,
            },
            "canonical_contact_history_checked": False,
            "suppression_verified_clear": False,
            "outbound_authorized": False,
            "founder_review_ready": False,
            "confirmed_commercial_buyer": False,
            "actual_revenue_usd": 0,
        })
    packets.sort(key=lambda p: (-p["research_priority_score"], p["company_name"].casefold()))
    summary = {
        "historical_contractor_companies": len(packets),
        "first_party_site_corroboration_pending": sum(p["qualification"]=="CORROBORATION_PENDING" for p in packets),
        "identity_change_holds": sum(p["qualification"]=="IDENTITY_CHANGE_HOLD" for p in packets),
        "independently_verified_purchase_intent": 0,
        "approved_outbound_count": 0,
        "verified_payments": 0,
        "realized_revenue_usd": 0,
    }
    digest = sha256(json.dumps({
        "as_of": as_of.isoformat(), "summary": summary, "packets": packets,
    },sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {
        "schema": SCHEMA,
        "as_of": as_of.isoformat(),
        "mode": "OBSERVE",
        "governance": {
            "manual_founder_approval_required": True,
            "independent_identity_and_legal_checks_required": True,
            "sender_owned_mailbox_required": True,
            "canonical_empiredb_suppression_read_required": True,
            "documenso_for_binding_contracts": True,
        },
        "summary": summary,
        "review_digest": digest,
        "packets": packets,
        "no_data_exfiltration": True,
        "outbound_sent": False,
        "outbound_authorized": False,
        "contract_sent": False,
        "execution_authority": "none",
    }
