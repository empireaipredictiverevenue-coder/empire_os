"""Evidence-bounded, original value-first sample previews for founder inspection.

A research record never implies a client brief, consent, verified commercial
demand, ability to deliver HubSpot implementation or an approved proposal.
"""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.earned_media_leadgen_review import REQUESTS, _key

SCHEMA = "empire.earned_media.value_first_sample_preview.v1"
VALID_STAGES = frozenset({
    "SOURCE_SIGNAL_ONLY", "RESEARCHED_ACCOUNT_NOT_BUYER", "RESEARCHED_ACCOUNT_UNBOUND",
})

PREVIEW_MODULES: dict[str, tuple[str, list[tuple[str, str]]]] = {
    _key("public_request", REQUESTS[0]["url"]): (
        "Revenue lifecycle and reporting audit — illustrative extract",
        [
            ("Demand handoff", "Where is a marketing-qualified lead defined? What evidence must sales accept before ownership changes?"),
            ("Stage integrity", "Write entry/exit rules for inquiry → qualified → sales accepted → opportunity → closed/won. Attach real timestamps."),
            ("Attribution", "Which first-party source field persists from initial consent through opportunity and won revenue? How are unknowns classified?"),
            ("Forecast", "Which open pipeline stages have reliable historic conversions? Compare projected versus actual recognised net revenue."),
            ("Two-week audit output", "Definition workshop, lifecycle map, exception report and proposed measurement contract — illustrative, not delivery commitment."),
        ],
    ),
    _key("public_request", REQUESTS[1]["url"]): (
        "ERP-to-CRM decision-support lineage — illustrative extract",
        [
            ("System map", "List what owns customer, product, invoice, order and collection truth across ERP, CRM and BI."),
            ("Join contract", "Document source IDs, currency, timezone, duplicates, cancellations and late arriving changes before attempting sync."),
            ("Commercial relevance", "Propose dashboards for dormant accounts, ageing orders, pipeline drift and rep/account growth, with evidence lineage."),
            ("Forecast hygiene", "Separate booked orders, outstanding invoices and bank-settled cash; report reconciliation gaps without estimating sales."),
            ("Delivery scope", "Data-model workshop and mapping template only; ERP/Grow/HubSpot credentials and integration capacity remain unverified."),
        ],
    ),
    _key("public_request", REQUESTS[2]["url"]): (
        "Operations KPI measurement questions — generic extract",
        [
            ("Profit", "How are gross margin, refunds, labour, overhead and cash receipts independently reconciled?"),
            ("Acquisition", "What source evidence links channel cost to qualified, accepted and paid customers without double counting?"),
            ("Capacity", "Which teams and territories have real fulfilment capacity versus merely apparent demand?"),
            ("Confidence", "Which KPI fields are verified, modelled, stale or unknown? Display their freshness in executive reporting."),
            ("Source limitation", "Original host, buyer and procurement request remain unverified; do not claim this is a commissioned audit."),
        ],
    ),
}


def preview_value_first_sample(
    lead_generation: Mapping[str, Any],
    *,
    opportunity_id: str,
) -> dict[str, Any]:
    if (lead_generation.get("schema_version") != "empire.earned_media.lead_generation_review.v1"
            or lead_generation.get("mode") != "OBSERVE"
            or lead_generation.get("execution_authority") != "none"
            or lead_generation.get("outbound_authorized") is not False
            or lead_generation.get("crm_writes") is not False
            or lead_generation.get("status") != "RESEARCH_PRIORITY_QUEUE_NOT_BUYER_PIPELINE"):
        raise ValueError("UNTRUSTED_LEAD_REVIEW")
    if not isinstance(opportunity_id, str) or len(opportunity_id) > 70:
        raise ValueError("INVALID_OPPORTUNITY_ID")
    items = lead_generation.get("opportunities")
    if not isinstance(items, list) or len(items) > 200:
        raise ValueError("INVALID_LEAD_REVIEW_ITEMS")
    matches = [x for x in items
               if isinstance(x, Mapping) and x.get("opportunity_id") == opportunity_id]
    if len(matches) != 1:
        raise LookupError("OPPORTUNITY_NOT_FOUND_OR_AMBIGUOUS")
    item = matches[0]
    stage = item.get("lead_stage")
    if (stage not in VALID_STAGES or item.get("outbound_authorized") is not False
            or item.get("quote_authorized") is not False
            or item.get("verified_buyer_identity") is not False
            or item.get("verified_procurement_intent") is not False):
        raise ValueError("PROSPECT_EVIDENCE_INVALID")
    if opportunity_id in PREVIEW_MODULES:
        title, sections = PREVIEW_MODULES[opportunity_id]
        # Public source-specific drafts are only valid for the exact request
        # identifiers in the reviewed packet, not an arbitrary injected ID.
        if stage != "SOURCE_SIGNAL_ONLY":
            raise ValueError("PUBLIC_SOURCE_MISMATCH")
    else:
        if not stage.startswith("RESEARCHED_ACCOUNT"):
            raise ValueError("SOURCE_SAMPLE_NOT_SUPPORTED")
        title = "Company research — hypothesis-only insight sheet"
        reasons = item.get("why_review")
        excerpts = [v[:200] for v in reasons[:2] if isinstance(v, str)] if isinstance(reasons, list) else []
        sections = [
            ("Existing research hypotheses", " | ".join(excerpts) if excerpts else "No specific public why-now evidence is supplied."),
            ("Independent verification", "Check a current first-party company statement and provenance before treating any hypothesis as fact."),
            ("Value first", "Offer a clearly described revenue leakage or forecasting audit checklist ONLY after current buying need is established."),
            ("Company context", "Do not assert budget, buying intent, contact permission, implementation capacity or revenue impact."),
        ]

    if len(sections) > 12 or not all(isinstance(x, tuple) and len(x) == 2 for x in sections):
        raise ValueError("UNSAFE_SAMPLE_STRUCTURE")
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "execution_authority": "none",
        "sample_type": "ORIGINAL_ILLUSTRATIVE_VALUE_FIRST_SAMPLE_NOT_CLIENT_WORK",
        "lead_id": opportunity_id,
        "label": item.get("label"),
        "lead_stage": stage,
        "source_document": item.get("source_document"),
        "source_observed_on": item.get("source_observed_on"),
        "title": title,
        "sections": [{"heading": k, "review_text": v} for k, v in sections],
        "safe_introduction": (
            "This is an original illustrative checklist demonstrating our approach; "
            "it is not a report based on access to a buyer's systems."
        ),
        "necessary_human_gates": [
            "VERIFY_CURRENT_ORIGINAL_DEMAND_SOURCE",
            "VERIFY_PLATFORM_OR_LAWFUL_CONTACT_ROUTE_AND_SUPPRESSION",
            "VERIFY_OPERATOR_DELIVERY_CAPABILITY_AND_SCOPE",
            "VERIFY_BUYER_IDENTITY_AND_EXPLICIT_INTEREST",
            "REVIEW_TENANT_SCOPED_CRM_AND_INDIVIDUAL_TERMS",
        ],
        "disallowed_claims": [
            "CLIENT_DATA_WAS_ACCESSED",
            "HUBSPOT_OR_ERP_DELIVERY_VERIFIED",
            "BUYER_BUDGET_OR_DEAL_SECURED",
            "REAL_RESULTS_OR_ROI_VERIFIED",
        ],
        "proposed_action": "FOUNDER_REVIEW_AND_SOURCE_VERIFICATION_ONLY",
        "message_drafted": False, "message_sent": False,
        "quote_issued": False, "proposal_authorized": False,
        "crm_write_authorized": False, "publication_authorized": False,
        "revenue_verified": False,
    }
