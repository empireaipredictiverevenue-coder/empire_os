"""Source-verified, read-only Scout-to-Buyer-Network handoff.

Preserves independent cohorts. Does not insert into Buyer Network, approve
outreach, validate a commercial buy-box or infer a person's identity.
"""
from __future__ import annotations
from datetime import datetime, timezone
from urllib.parse import urlsplit
from typing import Mapping, Any

SCHEMA = "empire.scout_buyer_network_admission_review.v1"
RESEARCH = "POTENTIAL_BUSINESS_REQUIRES_INDEPENDENT_BUYER_CHECK"

class HandoffHold(ValueError):
    pass

def _required(doc, schema, key, count_name, row_key):
    if not isinstance(doc,Mapping) or doc.get("schema_version") != schema:
        raise HandoffHold(f"{key}_schema_untrusted")
    rows=doc.get(row_key)
    if not isinstance(rows,list) or len(rows)>10000:
        raise HandoffHold(f"{key}_rows_invalid")
    if count_name and (type(doc.get(count_name)) is not int or doc[count_name]!=len(rows)):
        raise HandoffHold(f"{key}_count_drift")
    seen={}
    for row in rows:
        if not isinstance(row,Mapping):
            raise HandoffHold(f"{key}_row_invalid")
        domain=row.get("domain")
        if not isinstance(domain,str) or not domain or domain!=domain.casefold() or domain in seen:
            raise HandoffHold(f"{key}_duplicate_or_malformed_domain")
        seen[domain]=row
    return seen

def build_network_admission_review(scout, quality, network, founder, *, now):
    if now.tzinfo is None:
        raise HandoffHold("audit_clock_must_be_aware")
    if (scout.get("outbound_sent") is not False or
        scout.get("database_write_performed") is not False or
        founder.get("mode") != "OBSERVE" or
        founder.get("execution_authority") != "none" or
        founder.get("outbound_sent") is not False or
        founder.get("outbound_enabled") is not False or
        network.get("authority") != "OBSERVE" or
        not isinstance(network.get("governance"),Mapping) or
        network["governance"].get("outbound_authority") is not False or
        quality.get("schema_version") != "empire.acquisition_candidate_quality.v1" or
        quality.get("automated_outreach_sent") is not False or
        quality.get("verified_commercial_buyers_created") != 0):
        raise HandoffHold("source_authority_contract_untrusted")
    scout_rows=_required(scout,"empire.buyer_acquisition_scout.v1","scout","candidate_count","candidates")
    network_rows=_required(network,"buyer-network-candidate-queue-v1","network","candidate_count","candidates")
    founder_rows=_required(founder,"empire.buyer_qualification_actions.v1","founder","shortlisted_count","targets")
    if founder.get("network_candidate_count") != len(network_rows) or not set(founder_rows).issubset(network_rows):
        raise HandoffHold("founder_targets_network_source_unreconciled")
    quality_rows=quality.get("scout_source_quality")
    if not isinstance(quality_rows,list) or len(quality_rows)!=len(scout_rows):
        raise HandoffHold("quality_scout_population_mismatch")
    qc={}
    for row in quality_rows:
        if not isinstance(row,Mapping) or row.get("domain") not in scout_rows or row["domain"] in qc:
            raise HandoffHold("quality_scout_domain_mismatch")
        if row.get("automated_outreach_authorized") is not False:
            raise HandoffHold("quality_outreach_authority_changed")
        qc[row["domain"]]=row
    if set(qc)!=set(scout_rows):
        raise HandoffHold("quality_scout_domain_incomplete")
    if (quality.get("scout_research_candidates_inspected") != len(scout_rows) or
        quality.get("held_platform_duplicate_or_bad_domain_count") !=
            sum(x.get("review_status","").startswith("HOLD_") for x in quality_rows)):
        raise HandoffHold("quality_counts_untrusted")
    tasks=[]
    for domain, source in qc.items():
        qstate=source.get("review_status")
        seen_in_network=domain in network_rows
        founder_action=founder_rows.get(domain)
        if qstate!=RESEARCH:
            lane="HELD_SOURCE_NOT_ELIGIBLE_FOR_NETWORK_ADMISSION"
            next_steps=["CONFIRM_INDEPENDENT_FIRST_PARTY_BUSINESS_DOMAIN"]
        elif founder_action is not None:
            lane="EXISTING_FOUNDER_QUALIFICATION_NOT_YET_PURCHASE_PROOF"
            next_steps=founder_action.get("missing_evidence") or ["INDEPENDENT_BUYER_EVIDENCE_REVIEW"]
            if not isinstance(next_steps,list) or not all(isinstance(x,str) for x in next_steps):
                raise HandoffHold("founder_gap_contract_untrusted")
        elif seen_in_network:
            lane="NETWORK_DISCOVERY_EXISTS_QUALIFICATION_ACTION_NOT_PRESENT"
            next_steps=["EXISTING_NETWORK_EVIDENCE_REVIEW","FIRST_PARTY_ACTIVE_BUY_BOX_VERIFICATION"]
        else:
            lane="NOT_IN_NETWORK_INDEPENDENT_RESEARCH_HANDOFF_REQUIRED"
            next_steps=["SOURCE_DOMAIN_FIRST_PARTY_REVIEW","BUYING_ROLE_AND_UK_US_TERRITORY_VERIFICATION",
                        "ACTIVE_BUY_BOX_AND_PAYOUT_EVIDENCE","BUYER_CONTACT_SUPPRESSION_REVIEW"]
        original=scout_rows[domain]
        site=original.get("website")
        first_party_url=None
        if isinstance(site,str) and len(site)<=2048:
            parts=urlsplit(site)
            if (parts.scheme in ("https","http") and parts.hostname and
                parts.hostname.lower().removeprefix("www.")==domain and
                not parts.username and not parts.password):
                first_party_url=site
        if qstate==RESEARCH and first_party_url is None:
            raise HandoffHold("research_company_first_party_url_unverified")
        intent=original.get("intent_evidence_url")
        original_evidence_url=None
        if isinstance(intent,str) and len(intent)<=2048:
            parts=urlsplit(intent)
            if (parts.scheme in ("https","http") and parts.hostname and
                not parts.username and not parts.password):
                original_evidence_url=intent
        if qstate==RESEARCH and intent and original_evidence_url is None:
            raise HandoffHold("research_intent_source_url_invalid")
        tasks.append({
            "domain":domain, "review_lane":lane,
            "first_party_company_site_to_review":first_party_url if qstate==RESEARCH else None,
            "original_signal_page_review_url":original_evidence_url if qstate==RESEARCH else None,
            "original_social_author_company_affiliation_verified":False,
            "source_quality_status":qstate,
            "exists_in_network_discovery":seen_in_network,
            "exists_in_founder_qualification":founder_action is not None,
            "independent_buyer_purchase_receipt_verified":False,
            "accepting_buy_box_verified":False,
            "payout_terms_verified":False,
            "available_capacity_verified":False,
            "verified_decision_maker_contact":False,
            "outreach_authorized":False,
            "contact_identity_promoted":False,
            "next_evidence_tasks":next_steps,
        })
    order={"EXISTING_FOUNDER_QUALIFICATION_NOT_YET_PURCHASE_PROOF":0,
           "NETWORK_DISCOVERY_EXISTS_QUALIFICATION_ACTION_NOT_PRESENT":1,
           "NOT_IN_NETWORK_INDEPENDENT_RESEARCH_HANDOFF_REQUIRED":2,
           "HELD_SOURCE_NOT_ELIGIBLE_FOR_NETWORK_ADMISSION":3}
    tasks.sort(key=lambda x:(order[x["review_lane"]], x["domain"]))
    return {
        "schema_version":SCHEMA, "mode":"READ_ONLY",
        "generated_at":now.astimezone(timezone.utc).isoformat(),
        "scout_discovery_denominator":len(scout_rows),
        "buyer_network_discovery_denominator":len(network_rows),
        "founder_qualification_denominator":len(founder_rows),
        "exact_domain_scout_to_network_matches":len(set(scout_rows)&set(network_rows)),
        "exact_domain_scout_to_founder_matches":len(set(scout_rows)&set(founder_rows)),
        "source_held_count":sum(x["review_lane"].startswith("HELD_") for x in tasks),
        "unlinked_research_count":sum(x["review_lane"]=="NOT_IN_NETWORK_INDEPENDENT_RESEARCH_HANDOFF_REQUIRED" for x in tasks),
        "qualification_join_does_not_establish_buyer_readiness":True,
        "candidate_task_count":len(tasks),
        "admission_executed":False,"crm_mutation":False,"database_writes":False,
        "outbound_sent":False,"commercial_terms_accepted":False,
        "execution_authority":"NONE","items":tasks,
    }
