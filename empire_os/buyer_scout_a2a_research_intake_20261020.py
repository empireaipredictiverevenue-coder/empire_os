"""Buyer Scout owner-side read-only acceptance of A2A public research evidence.

Accepts bounded, first-party HTTP200 company page receipts and official
mechanical-permit business-name context. This is research triage, NOT an
authenticated signed owner receipt, not a CRM promotion or buyer acceptance.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse
import json
import re
from empire_os.buyer_scout_first_party_evidence_binding_20261020 import verify_site_source_binding

SCHEMA="empire.buyer_scout.a2a_owner_evidence_intake.v1"
WEB_SCHEMA="empire.a2a.first_party_buyer_scout_evidence_handoff.v1"
PERMIT_SCHEMA="empire.a2a.official_permit_buyer_scout_owner_review.v1"
HEX64=re.compile(r"^[0-9a-f]{64}$")
HEX24=re.compile(r"^[0-9a-f]{24}$")
HOST=re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
KNOWN_SOCIAL={"reddit.com","facebook.com","instagram.com","linkedin.com","youtube.com"}
MARKETS={("tampa, fl","roofing"),("little rock, ar","hvac"),("nyc","general_contractor")}


def _require(value: Any, predicate: bool, error: str) -> None:
    if not predicate:
        raise ValueError(error)


def _normal_domain(value: Any) -> str:
    if not isinstance(value,str) or len(value)>180:
        raise ValueError("UNTRUSTED_COMPANY_DOMAIN")
    parsed=urlparse(value if value.startswith("https://") else "https://"+value)
    if (parsed.scheme!="https" or parsed.username or parsed.password
            or parsed.port is not None or parsed.query or parsed.fragment
            or (parsed.path not in ("","/"))):
        raise ValueError("INVALID_COMPANY_ORIGIN")
    host=(parsed.hostname or "").lower().removeprefix("www.")
    if not HOST.fullmatch(host) or host in KNOWN_SOCIAL:
        raise ValueError("UNTRUSTED_COMPANY_HOST")
    return host


def read_bounded_json(path: Path, *, ceiling: int=130_000)->dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size>ceiling:
        raise ValueError("UNSAFE_BUYER_SCOUT_OWNER_SOURCE_FILE")
    root=json.loads(path.read_text(encoding="utf8"))
    if not isinstance(root,dict):
        raise ValueError("UNTRUSTED_BUYER_SCOUT_OWNER_SOURCE")
    return root


def stage_a2a_owner_research(
    websites: Mapping[str,Any],
    permits: Mapping[str,Any],
    current_scout: Mapping[str,Any],
    current_search_seeds: Mapping[str,Any],
    source_readback: Mapping[str,Any] | None = None,
)->dict[str,Any]:
    if (not isinstance(websites,Mapping)
            or websites.get("schema_version")!=WEB_SCHEMA
            or websites.get("mode")!="OBSERVE"
            or websites.get("execution_authority")!="NONE"
            or websites.get("verified_buyers")!=0
            or websites.get("canonical_buyer_records_created")!=0
            or websites.get("buyer_scout_owner_tasks_dispatched")!=0
            or websites.get("messages_sent")!=0):
        raise ValueError("A2A_WEBSITE_SOURCE_AUTHORITY_FAILURE")
    if (not isinstance(permits,Mapping)
            or permits.get("schema_version")!=PERMIT_SCHEMA
            or permits.get("mode")!="OBSERVE"
            or permits.get("execution_authority")!="NONE"
            or permits.get("verified_hvac_lead_buyers")!=0
            or permits.get("owner_tasks_dispatched")!=0
            or permits.get("outbound_sent")!=0
            or permits.get("source_distribution_rights_unverified") is not True):
        raise ValueError("A2A_PERMIT_SOURCE_AUTHORITY_FAILURE")
    if (not isinstance(current_scout,Mapping)
            or current_scout.get("mode")!="OBSERVE"
            or current_scout.get("database_write_performed") is not False
            or current_scout.get("outbound_sent") is not False):
        raise ValueError("SCOUT_CANONICAL_VIEW_UNTRUSTED")
    if (not isinstance(current_search_seeds,Mapping)
            or current_search_seeds.get("schema_version")!="empire.buyer_public_research_seeds.v1"
            or current_search_seeds.get("database_write_performed") is not False
            or current_search_seeds.get("outbound_sent") is not False):
        raise ValueError("SEARCH_SEEDS_UNTRUSTED")
    source_recent = False
    if source_readback is not None:
        if (not isinstance(source_readback,Mapping)
                or source_readback.get("schema_version") !=
                    "empire.a2a.first_party_source_recovery_review.v1"
                or source_readback.get("execution_authority") != "NONE"
                or source_readback.get("new_verified_sales_leads") != 0
                or source_readback.get("outbound_sent") != 0):
            raise ValueError("UNTRUSTED_SOURCE_FRESHNESS_EVIDENCE")
        source_recent = source_readback.get("source_state") == "CACHED_FIRST_PARTY_PUBLIC_RESEARCH_WITHIN_7_DAYS"
    raw_sites=websites.get("scoped_review_packets")
    raw_permits=permits.get("public_contractor_businesses_for_owner_review")
    scout_candidates=current_scout.get("candidates")
    search_seeds=current_search_seeds.get("seeds")
    if (not isinstance(raw_sites,list) or len(raw_sites)>9
            or not isinstance(raw_permits,list) or len(raw_permits)>40
            or not isinstance(scout_candidates,list) or len(scout_candidates)>100
            or not isinstance(search_seeds,list) or len(search_seeds)>100):
        raise ValueError("UNBOUNDED_OWNER_SOURCE_INPUT")
    if (websites.get("scoped_review_packet_count")!=len(raw_sites)
            or permits.get("businesses_for_owner_review_count")!=len(raw_permits)):
        raise ValueError("OWNER_SOURCE_COUNT_MISMATCH")
    known=set()
    for entry in [*scout_candidates,*search_seeds]:
        if not isinstance(entry,Mapping):
            raise ValueError("INVALID_KNOWN_SOURCE_ROW")
        candidate=entry.get("domain") or entry.get("website")
        if candidate:
            try:known.add(_normal_domain(candidate))
            except ValueError:pass  # pre-existing source URLs may contain paths
    binding=verify_site_source_binding(raw_sites, source_readback)
    seen=set()
    site_review=[]
    for row in raw_sites:
        if not isinstance(row,Mapping):
            raise ValueError("UNTRUSTED_A2A_PUBLIC_WEBSITE_ROW")
        domain=_normal_domain(row.get("public_company_website"))
        if (domain != row.get("public_company_domain")
                or domain in seen
                or (row.get("target_market"),row.get("target_sector")) not in MARKETS
                or row.get("dispatch_status")!="PREPARED_NOT_SUBMITTED"
                or row.get("verified_customer") is not False
                or row.get("buyer_capacity_verified") is not False
                or row.get("contact_authorized") is not False
                or row.get("lead_created") is not False):
            raise ValueError("UNTRUSTED_A2A_PUBLIC_BUSINESS_CLAIM")
        seen.add(domain)
        receipt=row.get("observed_source_sha256")
        good=row.get("source_read_status")=="HTTP_200"
        if good and (not isinstance(receipt,str) or not HEX64.fullmatch(receipt)):
            raise ValueError("A2A_WEBSITE_EVIDENCE_SHA_REQUIRED")
        if not good and receipt is not None:
            raise ValueError("UNREAD_WEBPAGE_HAS_SOURCE_DIGEST")
        site_review.append({
            "company_domain":domain,
            "market":row["target_market"],"vertical":row["target_sector"],
            "existing_search_or_scout_domain_overlap":domain in known,
            "public_page_content_sha256":receipt if good else None,
            "source_receipt_bound_to_independent_collector_readback":binding[row["public_company_website"]],
            "a2a_ticket_id":row.get("buyer_scout_ticket_id"),
            "research_status":("PENDING_OWNER_COMPANY_AND_COMMERCIAL_NEED_VERIFICATION"
                               if good and source_recent and binding[row["public_company_website"]]
                               and row.get("ready_for_buyer_scout_owner_research_review") is True
                               else "SOURCE_STALE_OR_HELD_NOT_CURRENT"),
            "buyer_identity_verified":False,"live_buying_need_verified":False,
            "contact_authorized":False,"can_be_added_to_canonical_crm":False,
        })
    company_names=set()
    permit_review=[]
    for row in raw_permits:
        if (not isinstance(row,Mapping)
                or row.get("not_a_homeowner_lead") is not True
                or row.get("not_a_qualified_lead_buyer") is not True
                or row.get("contact_authorized") is not False):
            raise ValueError("UNTRUSTED_OFFICIAL_COMPANY_NAME_CLAIM")
        name=row.get("company_name_hypothesis")
        digest=row.get("business_name_review_id")
        if (not isinstance(name,str) or len(name)>90
                or not isinstance(digest,str) or not HEX24.fullmatch(digest)
                or digest in company_names):
            raise ValueError("UNTRUSTED_OR_DUPLICATE_OFFICIAL_COMPANY")
        company_names.add(digest)
        permit_review.append({
            "company_name_hypothesis":name,
            "public_business_review_id":digest,
            "official_source_url":"https://maps.littlerock.gov/server/rest/services/Permits/MapServer/0",
            "market":"little rock, ar",
            "permit_date_status":permits.get("source_state"),
            "independently_verified_company_identity":False,
            "actual_lead_purchase_demand_verified":False,
            "individually_contactable":False,
            "can_be_added_to_canonical_crm":False,
        })
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE","execution_authority":"NONE",
        "owner":"existing_buyer_scout",
        "source_evidence_read_into_owner_workspace":True,
        "source_schema_validated":True,
        "website_research_records":site_review,
        "website_research_record_count":len(site_review),
        "website_receipts_individually_bound_to_source":sum(binding.values()),
        "website_source_recency_independently_crosschecked":source_readback is not None,
        "website_source_within_seven_days":source_recent,
        "website_source_records_eligible_for_further_owner_review":sum(
            x["research_status"] == "PENDING_OWNER_COMPANY_AND_COMMERCIAL_NEED_VERIFICATION"
            for x in site_review),
        "website_records_overlapping_known_search_or_scout":sum(x["existing_search_or_scout_domain_overlap"] for x in site_review),
        "official_company_research_records":permit_review,
        "official_company_record_count":len(permit_review),
        "owner_verified_buyers":0,
        "owner_live_purchase_demand_verified":0,
        "owner_canonical_accepted_customer_records":0,
        "owner_receipt_cryptographic_signature_verified":False,
        "canonical_crm_read_queried":False,
        "canonical_crm_modified":False,
        "canonical_outreach_modified":False,
        "messages_sent":0,
        "next_gate":"OWNER_INDEPENDENT_COMPANY_BUDGET_NEED_AND_CRYPTOGRAPHIC_RECEIPT_VERIFICATION",
    }
