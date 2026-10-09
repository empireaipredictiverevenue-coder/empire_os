"""Revenue Strike contractor review using existing EmpireOS evidence and governance.

This is a research/qualification projection. It NEVER infers a buyer, permits
outbound, writes CRM, sells a lead, accepts claims fees or starts contracts.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import date
from hashlib import sha256
import json
from urllib.parse import urlparse

from empire_os.claims_exchange.adapters import normalized_domain
from empire_os.claims_exchange.controls import parse_date, reject_sensitive_input, safe_https_source
from empire_os.claims_exchange.dossier import build_dossiers
from empire_os.storm_contractor_independent_evidence import (
    review_independent_evidence, review_official_state_dataset,
)

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
                            signals: Mapping, *, as_of: date,
                            independent_evidence: Mapping | None = None,
                            state_registry_evidence: Mapping | None = None) -> dict:
    for source in (cohort, sites, signals):
        reject_sensitive_input(source)
    dossiers = build_dossiers(cohort, sites, as_of=as_of)
    independent = review_independent_evidence(
        independent_evidence,
        cohort_names={row["original_domain"]: row["company_name"]
                      for row in dossiers["dossiers"]},
        as_of=as_of,
    )
    state_research = review_official_state_dataset(
        state_registry_evidence,
        approved_bbb_names={
            domain: record["directory_business_name"]
            for domain, record in independent.items()
            if record["state"] == "THIRD_PARTY_PROFILE_DOMAIN_MATCH"
        },
        as_of=as_of,
    )
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
        independent_record = independent.get(domain)
        independent_state = (
            independent_record["state"] if independent_record
            else "NO_THIRD_PARTY_PROFILE_LINK"
        )
        if independent_state == "INDEPENDENT_SOURCE_IDENTITY_CONFLICT_HOLD" and stage != "IDENTITY_CHANGE_HOLD":
            stage = "IDENTITY_EVIDENCE_CONFLICT_HOLD"
        official_state = state_research.get(domain)
        if (official_state
                and official_state["status"] == "STATE_CODE_REVIEW_HOLD"
                and stage == "CORROBORATION_PENDING"):
            stage = "OFFICIAL_STATE_CODE_REVIEW_HOLD"
        site_ready = stage == "CORROBORATION_PENDING"
        score = (30 if site_ready else 0) + (8 if r["public_contact_source_observed"] else 0)
        if site_ready:
            score += sum(SCORE[k] for k in kinds)
            if independent_state == "THIRD_PARTY_PROFILE_DOMAIN_MATCH":
                score += 24  # prioritise a stronger business-identity research route
            if (official_state and official_state["status"] ==
                    "OFFICIAL_DATASET_NAME_MATCH_PENDING_LIVE_STATUS"):
                score += 16  # public registry name match, NOT a verified legal link
        score = min(score, 75) if site_ready else 0  # no promotion under identity holds
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
        if stage == "IDENTITY_EVIDENCE_CONFLICT_HOLD":
            tasks.append("RESOLVE_THIRD_PARTY_IDENTITY_CONFLICT_DO_NOT_CONTACT")
        if stage == "OFFICIAL_STATE_CODE_REVIEW_HOLD":
            tasks.append("RECHECK_CURRENT_TEXAS_FRANCHISE_RIGHT_TO_TRANSACT_NO_CONTACT")
        if official_state is not None:
            tasks.append("CONFIRM_ENTITY_IN_LIVE_TEXAS_COMPTROLLER_SEARCH_AND_SOS")
        if independent_state == "THIRD_PARTY_PROFILE_DOMAIN_MATCH":
            tasks.append("CONFIRM_OFFICIAL_REGISTRATION_AND_DOMAIN_CONTROL_BEFORE_OUTREACH")
            if independent_record and independent_record.get("business_management_research"):
                tasks.append("VERIFY_DIRECTORY_LISTED_PRINCIPAL_IS_CURRENT_AUTHORISED_BUYER")
        tasks = sorted(set(tasks))
        packets.append({
            "entity_id": r["entity_id"],
            "company_name": r["company_name"],
            "company_domain": domain,
            "market": "Dallas-Fort Worth, TX",
            "role": "potential_b2b_contractor_customer",
            "origin": "existing_revenue_strike_dfw_cohort",
            "qualification": stage,
            "independent_business_research": independent_record or {
                "state": "NO_THIRD_PARTY_PROFILE_LINK",
                "state_registry_identity_verified": False,
                "domain_ownership_verified": False,
                "marketing_buyer_intent_verified": False,
                "outbound_authorized": False,
            },
            "official_state_entity_research": official_state or {
                "status": "NO_OFFICIAL_STATE_ENTITY_MATCH_ATTACHED",
                "live_official_account_status_verified": False,
                "website_entity_control_verified": False,
                "outbound_authorized": False,
            },
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
        "third_party_identity_conflict_holds": sum(p["qualification"]=="IDENTITY_EVIDENCE_CONFLICT_HOLD" for p in packets),
        "third_party_directory_domain_matches": sum(
            p["independent_business_research"]["state"] == "THIRD_PARTY_PROFILE_DOMAIN_MATCH"
            for p in packets),
        "no_third_party_profile_link": sum(
            p["independent_business_research"]["state"] == "NO_THIRD_PARTY_PROFILE_LINK"
            for p in packets),
        "official_state_dataset_name_matches": len(state_research),
        "official_state_code_review_holds": sum(
            p["qualification"] == "OFFICIAL_STATE_CODE_REVIEW_HOLD" for p in packets),
        "official_live_account_status_verified": 0,
        "verified_company_legal_registrations": 0,
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



def attach_existing_canonical_contact_history(
    review: Mapping, *, prior_contact_domains: set[str],
    suppressed_emails: set[str],
) -> dict:
    """Re-use EmpireOS's existing read-only buyer-contact-history guard.

    A domain-only comparison can find a hold, but CANNOT clear an actual
    recipient. Never use this as consent, an outbound eligibility result or
    an action gate.
    """
    if review.get("schema") != SCHEMA or review.get("outbound_authorized") is not False:
        raise ValueError("CONTACT_HISTORY_REQUIRES_GOVERNED_REVIEW")
    if not isinstance(prior_contact_domains, set) or not isinstance(suppressed_emails, set):
        raise ValueError("UNVERIFIED_CANONICAL_HISTORY_INPUT")
    for group in (prior_contact_domains, suppressed_emails):
        if len(group) > 100000 or any(not isinstance(x, str) for x in group):
            raise ValueError("CANONICAL_HISTORY_INPUT_UNBOUNDED")
    from empire_os.claims_exchange.adapters import normalized_domain
    prior = {normalized_domain(d) for d in prior_contact_domains if normalized_domain(d)}
    suppressed = {
        normalized_domain(s.partition("@")[2]) for s in suppressed_emails
        if "@" in s and normalized_domain(s.partition("@")[2])
    }
    checked = deepcopy(review)
    previous = suppressed_count = 0
    for p in checked["packets"]:
        domain = p["company_domain"]
        has_prior = domain in prior
        has_suppression = domain in suppressed
        previous += int(has_prior)
        suppressed_count += int(has_suppression)
        p["domain_contact_history_checked"] = True
        p["previous_contact_domain_hold"] = has_prior
        p["domain_has_suppressed_contact"] = has_suppression
        p["recipient_level_suppression_verified"] = False
        p["suppression_verified_clear"] = False
        p["canonical_contact_history_checked"] = False
        p["founder_review_ready"] = False
        p["outbound_authorized"] = False
        p["contact_history_state"] = (
            "SUPPRESSED_DOMAIN_CONTACT_HOLD" if has_suppression
            else "PRIOR_OUTBOUND_DOMAIN_REVIEW_HOLD" if has_prior
            else "NO_DOMAIN_MATCH_RECIPIENT_STILL_UNVERIFIED"
        )
        tasks = set(p["review_tasks"])
        tasks.add("VERIFY_EXACT_CONTACT_AND_CONSENT_BEFORE_ANY_SEND")
        if has_prior:
            tasks.add("RECONCILE_PREVIOUS_CONTACT_NO_DUPLICATE_OUTREACH")
        if has_suppression:
            tasks.add("DO_NOT_CONTACT_SUPPRESSION_REQUIRES_MANUAL_REVIEW")
        p["review_tasks"] = sorted(tasks)
    checked["summary"]["prior_outbound_domain_review_holds"] = previous
    checked["summary"]["suppressed_domain_contact_holds"] = suppressed_count
    checked["canonical_domain_history_observed"] = True
    checked["individual_recipient_suppression_cleared"] = False
    checked["outbound_authorized"] = False
    checked["execution_authority"] = "none"
    checked["review_digest"] = sha256(json.dumps({
        "as_of": checked["as_of"], "summary": checked["summary"],
        "packets": checked["packets"],
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return checked
