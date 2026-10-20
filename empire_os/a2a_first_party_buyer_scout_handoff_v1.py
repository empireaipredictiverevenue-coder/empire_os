"""Contract for handoff of observed public first-party websites to Buyer Scout.

No customer records, buyer intention, outreach, or unsigned owner receipts.
Readback of company self-descriptions becomes RESEARCH evidence only.
Company-domain owner matching uses exact names/domains and never infers buyer
intent from a source's own marketing copy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
from urllib.parse import urlsplit
import re

from empire_os.a2a_first_party_recovery_readback_v1 import SCHEMA as READBACK_SCHEMA
from empire_os.a2a_owner_research_protocol_v1 import OUTBOX_SCHEMA
from empire_os.a2a_b2b_evidence_mining_v1 import SCHEMA as MINING_SCHEMA

SCHEMA = "empire.a2a.first_party_buyer_scout_evidence_handoff.v1"
_HEX = re.compile(r"^[a-f0-9]{64}$")
_TID = re.compile(r"^[a-f0-9]{24}$")


def prepare_verified_scope_buyer_scout_handoff(
    sites: Mapping[str, Any], pickup: Mapping[str, Any],
    mining: Mapping[str, Any],
) -> dict[str, Any]:
    if (not isinstance(sites, Mapping)
            or sites.get("schema_version") != READBACK_SCHEMA
            or sites.get("mode") != "OBSERVE"
            or sites.get("execution_authority") != "NONE"
            or sites.get("new_verified_sales_leads") != 0
            or sites.get("outbound_sent") != 0
            or sites.get("commercial_buying_intent_verified") is not False
            or sites.get("buyer_budget_verified") is not False):
        raise ValueError("UNTRUSTED_FIRST_PARTY_EVIDENCE")
    if (not isinstance(pickup, Mapping)
            or pickup.get("schema_version") != OUTBOX_SCHEMA
            or pickup.get("mode") != "OBSERVE"
            or pickup.get("execution_authority") != "NONE"
            or pickup.get("owner_dispatches") != 0):
        raise ValueError("UNTRUSTED_OWNER_PICKUP")
    if (not isinstance(mining, Mapping)
            or mining.get("schema_version") != MINING_SCHEMA
            or mining.get("execution_authority") != "NONE"
            or mining.get("crm_write_performed") is not False
            or mining.get("verified_real_lead_count") != 0):
        raise ValueError("UNTRUSTED_EXISTING_OWNER_MINING")
    site_rows = sites.get("source_records")
    target_rows = mining.get("target_mining_results")
    owner_map = pickup.get("pickup_by_owner")
    if (not isinstance(site_rows, list) or len(site_rows) > 9
            or not isinstance(target_rows, list) or len(target_rows) > 10
            or not isinstance(owner_map, Mapping)):
        raise ValueError("INVALID_SCOPE_ROW_COUNTS")
    buyer_jobs = owner_map.get("buyer_scout")
    if not isinstance(buyer_jobs,list) or len(buyer_jobs) > 10:
        raise ValueError("MISSING_BUYER_SCOUT_OWNER")
    ticket_map={}
    for ticket in buyer_jobs:
        if not isinstance(ticket, Mapping) or ticket.get("execution_state") != "PICKUP_AVAILABLE_NOT_DELIVERED":
            raise ValueError("UNTRUSTED_BUYER_SCOUT_TICKET")
        body=ticket.get("research_request")
        if (not isinstance(body, Mapping) or body.get("review_owner") != "buyer_scout"
                or not isinstance(ticket.get("ticket_sha256"), str)
                or not _HEX.fullmatch(ticket["ticket_sha256"])
                or not isinstance(ticket.get("ticket_id"),str)
                or not _TID.fullmatch(ticket["ticket_id"])):
            raise ValueError("UNTRUSTED_BUYER_TICKET_BINDING")
        market=body.get("market")
        sector=body.get("sector")
        if (market,sector) in ticket_map:
            raise ValueError("DUPLICATE_BUYER_TARGET_SCOPE")
        ticket_map[(market,sector)] = {
            "ticket_id":ticket["ticket_id"],
            "ticket_sha256":ticket["ticket_sha256"],
        }
    existing={}
    for target in target_rows:
        if not isinstance(target, Mapping):
            raise ValueError("INVALID_PREEXISTING_TARGET")
        key=(target.get("requested_metro"),target.get("niche"))
        if key in existing:
            raise ValueError("DUPLICATE_MINING_TARGET")
        entities=target.get("records")
        if not isinstance(entities,list) or len(entities)>30:
            raise ValueError("INVALID_OWNER_DOMAIN_SET")
        domains=set()
        for entity in entities:
            if isinstance(entity, Mapping):
                domain=entity.get("public_business_domain_for_owner_review")
                if isinstance(domain,str):
                    domains.add(domain.lower())
        existing[key]=domains
    seen=set()
    packets=[]
    for site in site_rows:
        if not isinstance(site, Mapping):
            raise ValueError("INVALID_SITE_EVIDENCE")
        url=site.get("source_url")
        if not isinstance(url,str):
            raise ValueError("INVALID_PUBLIC_SITE_URL")
        host=urlsplit(url).hostname
        if not host or urlsplit(url).scheme != "https" or not url.endswith("/"):
            raise ValueError("INVALID_PUBLIC_SITE_URL")
        canonical=host.casefold().removeprefix("www.")
        if canonical in seen:
            raise ValueError("DUPLICATE_FIRST_PARTY_SOURCE")
        seen.add(canonical)
        market,sector=site.get("market"),site.get("sector")
        scope=(market,sector)
        if scope not in ticket_map or scope not in existing:
            raise ValueError("SITE_SCOPE_NOT_OWNED")
        fetched=site.get("read_status")=="HTTP_200"
        digest=site.get("source_sha256_if_http_200")
        if fetched and (not isinstance(digest,str) or not _HEX.fullmatch(digest)):
            raise ValueError("SOURCE_EVIDENCE_HASH_REQUIRED")
        if not fetched and digest is not None:
            raise ValueError("UNREAD_SOURCE_HAS_DIGEST")
        observed_match=site.get("self_description_matches_trade_and_region") is True and fetched
        if site.get("buyer_or_lead_verified") is not False or site.get("contact_allowed") is not False:
            raise ValueError("SITE_SELF_PROMOTED_AS_LEAD")
        packet_id=sha256((ticket_map[scope]["ticket_id"]+"|"+canonical+"|"+(digest or "UNREAD")).encode()).hexdigest()[:24]
        packets.append({
            "record_id":packet_id,
            "buyer_scout_ticket_id":ticket_map[scope]["ticket_id"],
            "buyer_scout_ticket_sha256":ticket_map[scope]["ticket_sha256"],
            "public_company_website":url,
            "public_company_domain":canonical,
            "target_market":market, "target_sector":sector,
            "observed_source_sha256":digest,
            "source_read_status":site.get("read_status"),
            "scrapling_structured_page_parsed": site.get("scrapling_structured_page_parsed") is True,
            "scrapling_extraction_is_structural_not_buyer_proof": True,
            "self_published_trade_and_region_match":observed_match,
            "requires_independent_company_identity_verification":True,
            "requires_independent_service_territory_validation":True,
            "requires_independent_live_purchase_need_evidence":True,
            "requires_canonical_duplicate_and_suppression_review":True,
            "already_in_current_sector_owner_mining_research":canonical in existing[scope],
            "ready_for_buyer_scout_owner_research_review":observed_match,
            "contact_authorized":False,
            "verified_customer":False,
            "buyer_capacity_verified":False,
            "lead_created":False,
            "dispatch_status":"PREPARED_NOT_SUBMITTED",
        })
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE", "execution_authority":"NONE",
        "first_party_sites_inspected":len(site_rows),
        "research_review_candidates_with_matching_self_descriptions":sum(
            p["ready_for_buyer_scout_owner_research_review"] for p in packets
        ),
        "scoped_review_packets":packets,
        "scoped_review_packet_count":len(packets),
        "source_claims_are_self_published_not_verified_business_facts":True,
        "no_individual_contact_data_extracted":True,
        "buyer_scout_owner_tasks_dispatched":0,
        "buyer_scout_owner_acceptance_received":False,
        "canonical_buyer_records_created":0,
        "verified_buyers":0, "actual_leads_delivered":0,
        "messages_sent":0, "ads_launched":False, "payments_collected":0,
    }


def make_first_party_owner_handoff_hold(reason: str) -> dict[str, Any]:
    if reason not in ("BUYER_OWNER_SOURCE_UNAVAILABLE", "BUYER_OWNER_SOURCE_UNTRUSTED"):
        raise ValueError("INVALID_FIRST_PARTY_OWNER_HOLD")
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE", "execution_authority": "NONE",
        "source_state": reason,
        "first_party_sites_inspected": None,
        "research_review_candidates_with_matching_self_descriptions": None,
        "scoped_review_packets": [], "scoped_review_packet_count": 0,
        "buyer_scout_owner_tasks_dispatched": 0,
        "buyer_scout_owner_acceptance_received": False,
        "canonical_buyer_records_created": 0,
        "verified_buyers": 0, "actual_leads_delivered": 0,
        "messages_sent": 0,
    }
