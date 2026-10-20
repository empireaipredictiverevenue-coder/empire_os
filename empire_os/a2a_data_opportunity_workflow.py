"""Fail-closed A2A task plans for source -> buyer -> campaign -> payment.

Produces bounded, reviewable typed handoff envelopes. Does not dispatch them,
authenticate a peer, authorise an agent, create a lead, or execute payments.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from empire_os.a2a_data_campaign_experiments import SCHEMA as CAMPAIGN_SCHEMA
from empire_os.a2a_commercial_signal_miner import AGENT_ID

SCHEMA = "empire.a2a.data_opportunity_handoff_plan.v1"

STEPS = (
    ("rights_review", "data_brokerage_owner",
     "Verify source licence, field rights, retention, privacy and resale scope"),
    ("buyer_validation", "buyer_scout_owner",
     "Confirm legal entity, decision role, genuine use case and written buying capacity"),
    ("deliverability", "data_product_owner",
     "Verify original data product and evidence-backed sample availability"),
    ("campaign_draft", "owned_campaign_owner",
     "Prepare a compliant, first-party niche and geo-specific content test"),
    ("founder_release_gate", "founder",
     "Review actual audience, account access, creative, tracking, outreach and any spend"),
    ("commercial_terms", "commerce_intent_owner",
     "Document accepted offer, licence, value, terms and buyer acceptance before transaction"),
    ("payment_request", "finance_os_owner",
     "If authorised, prepare provider-hosted payment link or canonical governed BSC/USDT proposal"),
    ("reconciliation", "canonical_finance_owner",
     "Independently verify settled payment and refunds before revenue learning"),
)


def plan_handoffs(data_campaigns: Mapping[str, Any]) -> dict[str, Any]:
    if (not isinstance(data_campaigns, Mapping)
            or data_campaigns.get("schema_version") != CAMPAIGN_SCHEMA
            or data_campaigns.get("agent_id") != AGENT_ID
            or data_campaigns.get("execution_authority") != "NONE"
            or data_campaigns.get("campaigns_launched") != 0
            or data_campaigns.get("spend_authorised") is not False):
        raise ValueError("untrusted_campaign_packet")
    campaigns = data_campaigns.get("campaigns")
    if not isinstance(campaigns, list) or len(campaigns) > 10:
        raise ValueError("invalid_campaign_count")
    plans = []
    seen = set()
    for row in campaigns:
        if not isinstance(row, Mapping):
            raise ValueError("unstructured_campaign")
        cid = row.get("campaign_id")
        if not isinstance(cid, str) or not cid.startswith("research-only-") or cid in seen:
            raise ValueError("duplicate_or_invalid_campaign")
        seen.add(cid)
        if any(row.get(k) is not False for k in (
            "publishing_authorised", "outbound_authorised",
            "spend_authorised", "payment_created", "pipeline_created"
        )):
            raise ValueError("campaign_exceeds_research_authority")
        jobs = []
        for index, (name, owner, acceptance) in enumerate(STEPS, start=1):
            jobs.append({
                "step_id": sha256((cid + ":" + name).encode()).hexdigest()[:24],
                "sequence": index,
                "capability": name,
                "requested_owner": owner,
                "acceptance": acceptance,
                "state": "PLANNED_NOT_DISPATCHED",
                "dispatch_authorised": False,
                "requires_owner_acceptance": True,
                "requires_signed_agent_identity_before_any_remote_request": True,
                "depends_on_previous_verified_step": index > 1,
            })
        plans.append({
            "campaign_id": cid,
            "research_segment_id": row.get("source_research_segment_id"),
            "status": "BLOCKED_UNTIL_RIGHTS_AND_OWNER_REVIEW",
            "handoffs": jobs,
            "payment_link_url": None,
            "real_customer_count": None,
            "confirmed_buyer_count": 0,
            "financial_settlement_verified": False,
            "live_tasks_dispatched": 0,
        })
    return {
        "schema_version": SCHEMA, "agent_id": AGENT_ID,
        "mode": "OBSERVE", "handoff_plan_count": len(plans),
        "handoff_step_count": len(STEPS) * len(plans),
        "plans": plans,
        "registered_external_operators": False,
        "automated_negotiations_started": 0,
        "payments_executed": 0, "payment_links_issued": 0,
        "outbound_sent": False, "approval_overridden": False,
        "payment_rail_owner": "canonical_bsc_usdt_or_separately_approved_payment_service",
        "no_fiat_provider_assumed": True,
        "execution_authority": "NONE",
        "next_gate": "A2A_IDENTITY_AND_EXISTING_DOMAIN_OWNER_CONTRACT_APPROVAL",
    }
