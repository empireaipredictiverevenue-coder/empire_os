"""Governed commercial-readiness synthesis for the *existing* Jev intent portfolio.

Calls EmpireOS's already-owned Buyer Capacity and Relationship Registry
executive readers. Aggregate counts can explain missing commercial evidence,
but cannot establish a particular buyer's buy-box, consent or suppression
state. No per-person matching, mail read, CRM writes or execution authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.executive_buyer_capacity_review import review_buyer_capacity
from empire_os.executive_relationship_registry_review import summarize_relationship_registry

SCHEMA="empire.jev.commercial_action_readiness.v1"
INPUT_SCHEMA="empire.jev.commercial_signal_portfolio.v1"
LANES=frozenset(("REVIEW_IDENTITY","REVIEW_EVIDENCE","REVIEW_BUYER_CAPACITY",
                "MONITOR","DISCARD"))
MAX_PORTFOLIO=60


def _is_int(value:Any)->bool:
    return type(value) is int and 0<=value<=MAX_PORTFOLIO


def review_portfolio_commercial_readiness(
    portfolio:Mapping[str,Any], *, buyer_capacity:Mapping[str,Any]|None,
    relationships:Mapping[str,Any]|None, as_of:datetime,
)->dict[str,Any]:
    if (not isinstance(as_of,datetime) or as_of.tzinfo is None
        or as_of.utcoffset() is None):
        raise ValueError("timezone-aware commercial review clock required")
    if (not isinstance(portfolio,Mapping)
        or portfolio.get("schema_version")!=INPUT_SCHEMA
        or portfolio.get("mode")!="OBSERVE"
        or portfolio.get("status")!="EXECUTIVE_INTENT_PORTFOLIO_REVIEW_ONLY"
        or portfolio.get("execution_authority")!="none"
        or portfolio.get("canonical_prospects_created")!=0
        or portfolio.get("identity_promotions")!=0
        or portfolio.get("outreach_sent")!=0
        or portfolio.get("lead_sales_verified")!=0
        or portfolio.get("actual_revenue") is not False
        or portfolio.get("database_writes") is not False
        or portfolio.get("buyer_capacity_verified") is not False):
        raise ValueError("untrusted commercial portfolio authority")
    items=portfolio.get("items")
    counts=portfolio.get("lane_counts")
    if (not isinstance(items,list) or len(items)>MAX_PORTFOLIO
        or not isinstance(counts,Mapping)
        or not set(counts).issubset(LANES)
        or any(not _is_int(n) for n in counts.values())
        or sum(counts.values())!=len(items)
        or portfolio.get("review_item_count")!=len(items)):
        raise ValueError("invalid bounded portfolio queue totals")
    actual={lane:0 for lane in LANES}
    seen=set()
    for item in items:
        if not isinstance(item,Mapping):
            raise ValueError("untrusted portfolio item")
        lane=item.get("deterministic_review_lane")
        event=item.get("signal_event_sha256")
        if (lane not in LANES
            or not isinstance(event,str) or len(event)!=64
            or any(ch not in "0123456789abcdef" for ch in event)
            or event in seen
            or item.get("identity_verified") is not False
            or item.get("verified_buyer_capacity") is not False
            or item.get("commercial_demand_verified") is not False
            or item.get("source_reference_sha256") is None):
            raise ValueError("source identity or authority untrusted")
        seen.add(event)
        actual[lane]+=1
    if any(actual[lane]!=counts.get(lane,0) for lane in LANES):
        raise ValueError("commercial lane counts mismatch")
    buyer=review_buyer_capacity(buyer_capacity,as_of=as_of)
    registry=summarize_relationship_registry(relationships,as_of=as_of)
    if (buyer.get("execution_authority")!="none"
        or buyer.get("lead_delivery_authorized") is not False
        or buyer.get("payment_execution") is not False
        or buyer.get("specific_buybox_verified") is not False
        or registry.get("send_authority") is not False
        or registry.get("new_replies_verified") is not False):
        raise ValueError("upstream commercial reader unexpectedly granted authority")
    suppression=registry.get("suppression_review_count")
    if suppression is not None and (type(suppression) is not int
                                    or not 0<=suppression<=1000):
        raise ValueError("untrusted aggregate suppression count")
    needs_identity=counts.get("REVIEW_IDENTITY",0)
    needs_evidence=counts.get("REVIEW_EVIDENCE",0)
    needs_capacity=counts.get("REVIEW_BUYER_CAPACITY",0)
    reasons=[]
    if needs_identity:
        reasons.append("UNVERIFIED_FIRST_PARTY_IDENTITY")
    if needs_evidence:
        reasons.append("INDEPENDENT_INTENT_EVIDENCE_REQUIRED")
    if buyer["status"] not in ("AGGREGATE_CAPACITY_NOT_SPECIFIC_BUYBOX",):
        reasons.append("NO_VERIFIED_SPECIFIC_COMMERCIAL_BUYBOX")
    else:
        reasons.append("AGGREGATE_CAPACITY_CANNOT_PROVE_SPECIFIC_BUYBOX")
    if registry["status"]!="OBSERVE_REVIEW":
        reasons.append("CRM_OR_MAILBOX_EVIDENCE_NOT_CURRENT")
    if suppression is None or suppression>0:
        reasons.append("INDIVIDUAL_SUPPRESSION_STATE_MUST_BE_CHECKED")
    # Even a good aggregate summary cannot join a social signal to a named
    # business, tenant, recipient, suppression subject or buyer's active buy box.
    reasons.append("NO_CANONICAL_SIGNAL_TO_BUYER_OR_CRM_IDENTITY_JOIN")

    steps=[]
    if needs_identity:
        steps.append({
            "task":"FIRST_PARTY_IDENTITY_RESEARCH",
            "affected_signal_review_count":needs_identity,
            "owner":"existing_research_and_buyer_scout",
            "required_receipt":"independently_verified_company_identity",
            "action_authorized":False,
        })
    if needs_evidence:
        steps.append({
            "task":"ORIGINAL_COMMERCIAL_INTENT_EVIDENCE_REVIEW",
            "affected_signal_review_count":needs_evidence,
            "owner":"existing_intent_brain_research",
            "required_receipt":"original_authored_procurement_evidence",
            "action_authorized":False,
        })
    steps.append({
        "task":"BUYER_CAPACITY_AND_COMMERCIAL_TERMS_VERIFICATION",
        "affected_signal_review_count":needs_identity+needs_evidence+needs_capacity,
        "owner":"existing_buyer_scout_capacity_owner",
        "required_receipt":"buyer_identity_and_niche_geo_terms_capacity_delivery",
        "action_authorized":False,
    })
    steps.append({
        "task":"EXISTING_CRM_RELATIONSHIP_AND_SUPPRESSION_RECONCILIATION",
        "affected_relationship_review_count":registry.get("total_relationships"),
        "suppression_or_bounce_review_count":suppression,
        "owner":"existing_tenant_crm_and_mailbox_owner",
        "required_receipt":"current_thread_tenant_consent_suppression_and_contact_history",
        "action_authorized":False,
    })
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"COMMERCIAL_EVIDENCE_GAPS_REQUIRE_OWNER_REVIEW",
        "as_of_utc":as_of.astimezone(timezone.utc).isoformat(),
        "source_signal_review_count":len(items),
        "portfolio_lanes":dict(sorted(counts.items())),
        "buyer_capacity_status":buyer["status"],
        "buyer_capacity_source_current":buyer["source_current"],
        "buyer_capacity_counts":buyer["counts"],
        "specific_buybox_verified":False,
        "verified_buyer_capacity_for_portfolio":False,
        "buyer_capacity_auto_allocation":False,
        "relationship_registry_status":registry["status"],
        "relationship_registry_fresh":registry["registry_fresh"],
        "mailbox_current":registry["mailbox_current"],
        "new_replies_verified":False,
        "total_relationships":registry["total_relationships"],
        "relationship_counts_by_stage":registry["counts_by_stage"],
        "aggregate_suppression_or_bounce_review_count":suppression,
        "suppression_clear_for_any_individual":False,
        "individual_buyer_identity_join_verified":False,
        "review_steps":steps,
        "blocking_reasons":reasons,
        "commercial_offers_ready":0,
        "outreach_sent":0,
        "canonical_prospects_created":0,
        "customer_delivery_authorized":False,
        "verified_revenue":False,
        "database_writes":False,
        "payment_mutations":False,
        "execution_authority":"none",
    }
