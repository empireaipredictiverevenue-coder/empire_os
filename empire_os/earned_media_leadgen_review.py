"""Earned Media -> B2B lead discovery -> evidence-qualified commercial review.

Read-only composition of existing first-party research and Revenue Distribution.
Ranks source observations, never predicts buyers or fabricates contact permission.
Not a lead scraper, CRM writer, message sender, proposal issuer, quote or forecast.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

from empire_os.earned_media_advisory_bridge import SCHEMA as BRIDGE_SCHEMA
from empire_os.earned_media_advisory_bridge import _json, _read, SourceHeld

SCHEMA = "empire.earned_media.lead_generation_review.v1"
DEMAND_DOC = "docs/commercial/SAAS_DIRECT_BUYER_REQUESTS_20261024.md"
DIST_SNAPSHOT = "runtime/revenue_distribution/latest.json"

# Evidence-bounded original requests. Distinct job links from existing
# founder-authored research; they are NOT fresh listings, qualified buyers,
# or proof Empire AI can fulfil a software-implementation contract.
REQUESTS = (
    {
        "key": "revops_hubspot_canada",
        "label": "HubSpot B2B RevOps consultancy request",
        "url": "https://www.upwork.com/freelance-jobs/apply/HubSpot-RevOps-Consultant-Needed-Revenue-Operations-Setup-for-B2B-Sales-Team_~022113313008957668345/",
        "topic": "sales_marketing_lifecycle_forecast",
        "original_source_tier": "DIRECT_SERVICE_REQUEST_INDEXED",
        "sample": "One-page MQL/SQL, deal-stage and attribution definition checklist",
        "offer": "consultancy_ai_revenue_opportunity_assessment",
        "blockers": ("LISTING_AVAILABILITY_UNVERIFIED", "MARKETPLACE_ACCOUNT_AND_CONNECTS_NOT_CLEARED",
                     "HUBSPOT_DELIVERY_CREDENTIALS_NOT_VERIFIED", "BUYER_IDENTITY_UNKNOWN",
                     "PERMISSION_TO_CONTACT_NOT_ESTABLISHED"),
    },
    {
        "key": "erp_hubspot_us",
        "label": "US ERP-to-HubSpot forecast and automation request",
        "url": "https://www.upwork.com/freelance-jobs/apply/HubSpot-RevOps-Grow-Automation-Specialist_~022097530147436142669/",
        "topic": "erp_bi_sales_decision_support",
        "original_source_tier": "DIRECT_SERVICE_REQUEST_INDEXED",
        "sample": "One-page revenue-data lineage and forecast measurement checklist",
        "offer": "consultancy_ai_revenue_opportunity_assessment",
        "blockers": ("LISTING_AVAILABILITY_UNVERIFIED", "MARKETPLACE_ACCOUNT_AND_CONNECTS_NOT_CLEARED",
                     "ERP_HUBSPOT_GROW_DELIVERY_CREDENTIALS_NOT_VERIFIED", "BUYER_IDENTITY_UNKNOWN",
                     "PERMISSION_TO_CONTACT_NOT_ESTABLISHED"),
    },
    {
        "key": "revops_au_brokered",
        "label": "Australian operations dashboard request (brokered)",
        "url": "https://flexstack.online/job/revenue-operations-revops-kpi-dashboard-specialist-monthly-executive-reporting",
        "topic": "operations_kpi_decision_support",
        "original_source_tier": "BROKERED_LISTING_UNVERIFIED",
        "sample": "Example profit/CAC/LTV dashboard measurement questions, internal only",
        "offer": "consultancy_ai_revenue_opportunity_assessment",
        "blockers": ("ORIGINAL_HOST_AND_BUYER_UNVERIFIED", "FRESH_LISTING_NOT_VERIFIED",
                     "NO_DIRECT_CONTACT_AUTHORITY", "DELIVERY_SCOPE_UNVERIFIED"),
    },
)

# Precise policy from existing founder-approved consultancy file; amounts are
# starting-price *policies*, not bids, orders, pipeline value or actual revenue.
STARTING_PRICES_GBP_MINOR = {
    "consultancy_ai_revenue_opportunity_assessment": 250000,
    "consultancy_predictive_revenue_strategy_blueprint": 750000,
    "consultancy_strategic_ai_revenue_advisory": 300000,
}


def _key(lane: str, raw: str) -> str:
    return "leadreview_" + sha256((lane + "|" + raw).encode()).hexdigest()[:24]


def _uuid(value: Any) -> bool:
    try:
        return isinstance(value, str) and str(UUID(value)) == value.lower()
    except (ValueError, TypeError, AttributeError):
        return False


def _packet_ok(packet: Mapping[str, Any]) -> bool:
    return (packet.get("schema_version") == BRIDGE_SCHEMA
            and packet.get("mode") == "OBSERVE"
            and packet.get("execution_authority") == "none"
            and packet.get("smart_crm_writes") is False
            and packet.get("new_outbound_authorized") is False)


def _hold(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE", "execution_authority": "none",
        "status": "HELD_SOURCE_OR_PACKET_INTEGRITY",
        "reason_code": reason, "opportunities": [],
        "counts": {"source_signal": 0, "researched_account": 0,
                   "qualified_buyer": 0, "total": 0},
        "empiredb_writes": False, "crm_writes": False,
        "outbound_authorized": False, "outbound_sent": False,
        "paid_traffic_authorized": False, "quote_authorized": False,
        "realised_revenue_gbp_minor": None,
        "recognised_revenue_state": "NOT_QUERIED",
    }


def review_lead_generation(
    packet: Mapping[str, Any],
    *,
    repo_root: str | Path,
    distribution_root: str | Path,
) -> dict[str, Any]:
    """Read bounded real research artefacts, reconcile hashes and rank review only."""
    if not _packet_ok(packet):
        return _hold("ORIGINAL_BRIDGE_PACKET_UNTRUSTED")
    sources = packet.get("sources")
    if not isinstance(sources, Mapping):
        return _hold("ORIGINAL_BRIDGE_SOURCES_MISSING")
    dist_source = sources.get("distribution_snapshot")
    pricing_source = sources.get("consultancy_pricing")
    if (not isinstance(dist_source, Mapping)
            or dist_source.get("state") != "EVIDENCE_FILE_READ"
            or not isinstance(pricing_source, Mapping)
            or pricing_source.get("state") != "EVIDENCE_FILE_READ"):
        return _hold("PRICING_OR_DISTRIBUTION_SOURCE_UNVERIFIED")
    try:
        demand, demand_hash = _read(Path(repo_root), DEMAND_DOC, max_bytes=45000)
        dist, dist_hash = _json(Path(distribution_root), DIST_SNAPSHOT)
    except (OSError, SourceHeld, ValueError):
        return _hold("RESEARCH_OR_DISTRIBUTION_DOCUMENT_UNAVAILABLE")
    if dist_hash != dist_source.get("sha256"):
        return _hold("REVENUE_DISTRIBUTION_CHANGED_SINCE_BRIDGE_REVIEW")
    if (dist.get("mode") != "OBSERVE" or dist.get("execution_authority") != "none"
            or dist.get("proposal_only") is not True
            or not isinstance(dist.get("human_review_queue"), list)
            or len(dist["human_review_queue"]) > 200):
        return _hold("REVENUE_DISTRIBUTION_AUTHORITY_OR_SHAPE_INVALID")

    # All three source URL appearances must be independently present in the
    # vetted document. No NLP extracts contacts or treats a page as still open.
    if any(spec["url"].encode() not in demand for spec in REQUESTS):
        return _hold("ORIGINAL_B2B_REQUEST_REFERENCES_CHANGED")

    opportunities: list[dict[str, Any]] = []
    for spec in REQUESTS:
        direct = spec["original_source_tier"] == "DIRECT_SERVICE_REQUEST_INDEXED"
        opportunities.append({
            "opportunity_id": _key("public_request", spec["url"]),
            "lead_stage": "SOURCE_SIGNAL_ONLY", "channel": "PUBLIC_PROCUREMENT_REQUEST",
            "label": spec["label"], "source_url": spec["url"],
            "source_document": DEMAND_DOC, "source_observed_on": "2026-10-24",
            "fresh_listing_verified": False,
            "verified_buyer_identity": False, "verified_buyer_contact": False,
            "verified_procurement_intent": False,
            "public_request_observed_in_research": True,
            "priority_score": 70 if direct else 40,
            "priority_score_type": "RULE_BASED_RESEARCH_REVIEW_NOT_CONVERSION_PROBABILITY",
            "why_review": ("Public source requests external RevOps service work"
                           if direct else "Brokered dashboard request needs original-source verification"),
            "recommended_offer_code": spec["offer"],
            "recommended_offer_state": "FIT_HYPOTHESIS_NO_QUOTE",
            "value_first_free_sample_outline": spec["sample"],
            "next_action": ("Verify real listing and marketplace eligibility before proposing a limited audit"
                            if direct else "Verify original publisher, buyer and availability; do not contact"),
            "blockers": list(spec["blockers"]),
            "existing_canonical_prospect_id": None,
            "outbound_authorized": False, "quote_authorized": False,
            "expected_revenue": None, "verified_revenue": False,
        })

    seen: set[str] = set()
    duplicate_or_unsafe = 0
    for row in dist["human_review_queue"]:
        if not isinstance(row, Mapping):
            duplicate_or_unsafe += 1
            continue
        identity = row.get("canonical_prospect_id")
        company = row.get("company")
        if (not isinstance(company, str)
                or not company.strip() or len(company) > 140
                or row.get("execution_authority") != "none"
                or row.get("outreach_authorized") is not False
                or row.get("commercial_authority_verified") is not False
                or row.get("commercial_role") != "RESEARCH_PROSPECT_NOT_VERIFIED_BUYER"):
            duplicate_or_unsafe += 1
            continue
        canonical_bound = _uuid(identity)
        # Preserve useful uncatalogued company observations as explicit
        # UNBOUND research, never fabricate a canonical prospect identifier.
        normalized_domain = str(row.get("domain") or "").strip().lower()
        unique_key = (("id:" + identity) if canonical_bound else
                      ("name:" + company.strip().casefold() + "|domain:" + normalized_domain))
        if unique_key in seen:
            duplicate_or_unsafe += 1
            continue
        seen.add(unique_key)
        why_now = row.get("why_now_evidence")
        why = [x[:220] for x in why_now[:3]
               if isinstance(x, str) and x.strip()] if isinstance(why_now, list) else []
        fit = row.get("product_match_state") == "INFERRED_RESEARCH_FIT"
        evidence_ready = bool(why)
        priority = min(45, 10 + (15 if evidence_ready else 0)
                       + (5 if fit else 0)
                       + (5 if row.get("person_verified") is True else 0)
                       + (5 if row.get("email_verified") is True else 0))
        # A research company, even with a known verified email, is not a buyer.
        opportunities.append({
            "opportunity_id": _key("canonical_research" if canonical_bound else "unbound_research",
                                   identity if canonical_bound else unique_key),
            "lead_stage": ("RESEARCHED_ACCOUNT_NOT_BUYER" if canonical_bound
                           else "RESEARCHED_ACCOUNT_UNBOUND"),
            "channel": "CANONICAL_REVENUE_DISTRIBUTION_RESEARCH",
            "label": company.strip(), "source_url": None,
            "source_document": DIST_SNAPSHOT,
            "source_observed_on": dist.get("generated_at"),
            "fresh_listing_verified": False,
            "verified_buyer_identity": False,
            "verified_buyer_contact": False,
            "verified_procurement_intent": False,
            "public_request_observed_in_research": False,
            "priority_score": priority if canonical_bound else min(25, priority),
            "priority_score_type": "RULE_BASED_RESEARCH_REVIEW_NOT_CONVERSION_PROBABILITY",
            "why_review": why,
            "recommended_offer_code": None,
            "recommended_offer_state": "NEEDS_BUYER_PROBLEM_BEFORE_OFFER",
            "value_first_free_sample_outline": (
                "Prepare a short, original company-specific insight from independently verified facts"
            ),
            "next_action": (
                "Recheck genuine commercial need, exact prior contact, current suppression and contact purpose"
                " before founder-reviewed value-first outreach"
            ),
            "blockers": sorted(set(
                [b for b in row.get("readiness_blockers", [])[:20]
                 if isinstance(b, str) and len(b) <= 120]
                if isinstance(row.get("readiness_blockers"), list) else []
            ) | {"BUYER_DEMAND_NOT_VERIFIED", "FRESH_SOURCE_AND_SUPPRESSION_CHECK_REQUIRED"}
              | (set() if canonical_bound else {"CANONICAL_PROSPECT_ID_MISSING"})),
            "existing_canonical_prospect_id": identity if canonical_bound else None,
            "canonical_identity_state": ("CANONICAL_ID_PRESENT_NOT_BUYER_VERIFIED" if canonical_bound
                                         else "NO_CANONICAL_PROSPECT_ID"),
            "outbound_authorized": False, "quote_authorized": False,
            "expected_revenue": None, "verified_revenue": False,
        })

    opportunities.sort(key=lambda x: (-x["priority_score"], x["opportunity_id"]))
    counts = {
        "source_signal": sum(x["lead_stage"] == "SOURCE_SIGNAL_ONLY" for x in opportunities),
        "researched_account": sum(x["lead_stage"].startswith("RESEARCHED_ACCOUNT")
                                  for x in opportunities),
        "canonical_researched_account": sum(x["lead_stage"] == "RESEARCHED_ACCOUNT_NOT_BUYER"
                                            for x in opportunities),
        "unbound_researched_account": sum(x["lead_stage"] == "RESEARCHED_ACCOUNT_UNBOUND"
                                          for x in opportunities),
        "qualified_buyer": 0,
        "total": len(opportunities),
    }
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "status": "RESEARCH_PRIORITY_QUEUE_NOT_BUYER_PIPELINE",
        "execution_authority": "none",
        "sources": {
            "demand_document": {"reference": DEMAND_DOC, "sha256": demand_hash,
                                "observed_on": "2026-10-24", "freshness": "HISTORICAL"},
            "canonical_revenue_distribution": {"reference": DIST_SNAPSHOT,
                                              "sha256": dist_hash,
                                              "freshness": "HISTORICAL"},
        },
        "counts": counts, "skipped_duplicate_or_unsafe_company_rows": duplicate_or_unsafe,
        "opportunities": opportunities,
        "offer_price_policy_gbp_minor": STARTING_PRICES_GBP_MINOR,
        "offer_price_warning": "FOUNDER_APPROVED_STARTING_PRICES_ONLY_NO_QUOTE",
        "conditional_unit_economics_examples": [
            {
                "hypothesis": "four_paid_opportunity_assessments",
                "conditions": "4 separately approved, contracted, delivered and actually paid £2,500 assessments",
                "gross_contract_amount_gbp_minor_if_all_conditions_met": 1000000,
                "not_a_forecast": True,
                "actual_sales_verified": 0,
                "costs_verified": False,
                "delivery_capacity_verified": False,
            },
            {
                "hypothesis": "one_blueprint_and_one_assessment",
                "conditions": "1 paid £7,500 blueprint and 1 paid £2,500 assessment with separately accepted terms",
                "gross_contract_amount_gbp_minor_if_all_conditions_met": 1000000,
                "not_a_forecast": True,
                "actual_sales_verified": 0,
                "costs_verified": False,
                "delivery_capacity_verified": False,
            },
            {
                "hypothesis": "four_monthly_advisory_clients",
                "conditions": "4 separately approved and paying £3,000/month advisory clients in the same billing month",
                "gross_monthly_billings_gbp_minor_if_all_conditions_met": 1200000,
                "not_a_forecast": True,
                "actual_sales_verified": 0,
                "costs_verified": False,
                "delivery_capacity_verified": False,
            },
        ],
        "acquisition_conversion_contract": [
            {
                "stage": "SOURCE_DISCOVERY",
                "evidence": "source URL and original observed date",
                "verified_here": True,
                "next_gate": "FRESH_SOURCE_AND_RIGHTS_CHECK",
            },
            {
                "stage": "ATTRIBUTABLE_ATTENTION",
                "evidence": "independent published PR/guest article URL plus first-party referral measurement",
                "verified_here": False,
                "next_gate": "REAL_VISIT_AND_CONSENTED_ATTRIBUTION",
            },
            {
                "stage": "BUYER_QUALIFICATION",
                "evidence": "first-party opted-in enquiry, authenticated company, identified budget/problem",
                "verified_here": False,
                "next_gate": "CANONICAL_TENANT_SCOPED_CRM_VERIFICATION",
            },
            {
                "stage": "SIGNED_ENGAGEMENT",
                "evidence": "scoped client SOW, actual acceptance and lawful terms",
                "verified_here": False,
                "next_gate": "FOUNDER_LEGAL_DELIVERY_APPROVAL",
            },
            {
                "stage": "REALISED_REVENUE",
                "evidence": "fulfilled milestone, verified settlement and refunds/clawbacks in existing EmpireDB",
                "verified_here": False,
                "next_gate": "CANONICAL_SETTLEMENT_RECONCILIATION",
            },
        ],
        "conversion_probability": None, "pipeline_value_gbp_minor": None,
        "expected_revenue_gbp_minor": None,
        "realised_revenue_gbp_minor": None,
        "recognised_revenue_state": "NOT_QUERIED",
        "qualified_buyers_verified": 0, "matched_to_crm_and_consent": 0,
        "proposals_sent_by_this_review": 0,
        "empiredb_writes": False, "crm_writes": False,
        "outbound_authorized": False, "outbound_sent": False,
        "paid_traffic_authorized": False, "quote_authorized": False,
        "next_iteration": "VERIFY_FRESH_PURCHASE_SIGNAL_AND_ORIGINAL_SOURCE_THEN_CANONICAL_CRM_REVIEW",
    }
