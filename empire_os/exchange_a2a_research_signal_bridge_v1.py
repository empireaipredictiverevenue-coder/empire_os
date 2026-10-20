"""Research-only A2A/BScout signal counts for Exchange founder fulfilment review.

Use just verified owner-side summary structure. This must never increase
canonical inventory, buyer capacity, payment, MRR or eligible lead delivery.
Never emit company domains, emails, names, contact details or search results.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import re

SCHEMA="empire.buyer_scout.source_verification_queue.v1"
HEX24=re.compile(r"^[a-f0-9]{24}$")
DNS=re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
ALLOWED={
    ("tampa, fl","roofing"),
    ("little rock, ar","hvac"),
    ("nyc","general_contractor"),
}


def _hold(reason:str)->dict[str,Any]:
    return {
        "state":"HOLD",
        "reason":reason,
        "counts_count_as_canonical_inventory":False,
        "buyer_capacity_added":0,
        "saleable_personal_leads_added":0,
        "approved_buyer_deliveries":0,
        "revenue_added_cents":0,
        "crm_writes":False,
        "outbound_sent":False,
    }


def summarise_a2a_for_exchange(queue:Mapping[str,Any]|None)->dict[str,Any]:
    if queue is None:
        return _hold("a2a_owner_queue_not_supplied")
    if (not isinstance(queue,Mapping) or queue.get("schema_version")!=SCHEMA
            or queue.get("mode")!="OBSERVE"
            or queue.get("execution_authority")!="NONE"
            or queue.get("owner")!="existing_buyer_scout"
            or queue.get("search_api_results_persisted") is not False
            or queue.get("verified_revenue_buyers")!=0
            or queue.get("canonical_crm_records_created")!=0
            or queue.get("canonical_empiredb_duplicate_checks_completed")!=0
            or queue.get("tasks_dispatched_to_live_buyer_scout")!=0
            or queue.get("outbound_messages_sent")!=0):
        return _hold("a2a_source_authority_mismatch")
    ready=queue.get("ready_first_party_verification_tasks")
    held=queue.get("held_site_tasks")
    historical=queue.get("historical_official_company_context")
    if (not isinstance(ready,list) or len(ready)>9
            or not isinstance(held,list) or len(held)>9
            or not isinstance(historical,list) or len(historical)>40
            or queue.get("ready_first_party_verification_count")!=len(ready)
            or queue.get("held_site_count")!=len(held)
            or queue.get("historical_official_context_count")!=len(historical)):
        return _hold("a2a_source_count_or_size_mismatch")
    market_counts:dict[str,int]={}
    site_domains=set()
    for row in ready:
        if not isinstance(row,Mapping):
            return _hold("a2a_untrusted_site_row")
        domain=row.get("public_company_domain")
        market=row.get("market")
        sector=row.get("sector")
        ticket=row.get("stable_review_task_id")
        if (not isinstance(domain,str) or not DNS.fullmatch(domain)
                or domain in site_domains
                or (market,sector) not in ALLOWED
                or not isinstance(ticket,str) or not HEX24.fullmatch(ticket)
                or row.get("state")!="OWNER_REVIEW_NOT_DELIVERED"
                or row.get("contact_allowed") is not False
                or row.get("can_create_customer") is not False
                or row.get("can_send_message") is not False
                or row.get("commercial_claims_verified") is not False
                or row.get("requires_canonical_empiredb_duplicate_and_suppression_check") is not True):
            return _hold("a2a_unqualified_or_duplicate_company")
        site_domains.add(domain)
        token=f"{sector}:{market}"
        market_counts[token]=market_counts.get(token,0)+1
    for row in held:
        if (not isinstance(row,Mapping)
                or row.get("contact_allowed") is not False
                or row.get("state")!="SOURCE_HOLD_NO_RETRY_OR_PERSISTENCE"):
            return _hold("a2a_held_site_promoted")
    for row in historical:
        if (not isinstance(row,Mapping)
                or row.get("not_a_verified_buyer") is not True
                or row.get("not_a_current_project_demand_signal") is not True
                or row.get("contact_allowed") is not False):
            return _hold("a2a_historical_permit_promoted")
    return {
        "state":"OWNER_RESEARCH_COUNTS_ONLY",
        "ready_company_website_review_tasks":len(ready),
        "held_policy_or_source_sites":len(held),
        "historical_permit_company_hypotheses":len(historical),
        "markets_requiring_independent_buyer_review":[
            {"market_sector":k,"research_site_count":v}
            for k,v in sorted(market_counts.items())
        ],
        "freshness_not_proven_by_queue_alone":True,
        "canonical_buyer_identity_matches_verified":0,
        "approved_commercial_purchase_demand_verified":0,
        "buyer_capacity_added":0,
        "counts_count_as_canonical_inventory":False,
        "saleable_personal_leads_added":0,
        "approved_buyer_deliveries":0,
        "revenue_added_cents":0,
        "crm_writes":False,
        "outbound_sent":False,
    }
