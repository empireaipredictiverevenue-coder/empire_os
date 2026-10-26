"""Commercial qualification overlay for the ORIGINAL EmpireOS founder buyer queue.

A source-backed UK heat-pump research company is never an accepted buyer.
Only original Scout evidence and public first-party programme terms contribute.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from empire_os.heat_pump_market_expansion import run as market_review

SCHEMA = "empire.buyer_network.heat_pump_founder_commercial_review.v1"
SCOUT = Path("runtime/buyer_acquisition/scout_latest.json")
MAX_SCOUT_AGE = 2 * 3600
# Current 26 Oct 2026 first-party pages: source statements, not binding terms.
OFFICIAL_PROGRAMME_REVIEWS = {
    "goodenergy.co.uk": {
        "source_url": "https://www.goodenergy.co.uk/partners/",
        "classification": "SOME_CONTRACTED_PARTNERS_COMMISSION_ELIGIBILITY_UNKNOWN",
        "research_contact": "partnerships@goodenergy.co.uk",
        "condition": "Only some accredited partners are paid commission; acceptance, category, restrictions and price unknown",
    },
    "altoenergy.co.uk": {
        "source_url": "https://www.altoenergy.co.uk/contracting",
        "classification": "INSTALLATION_REFERRAL_OR_WHITE_LABEL_DELIVERY_POSSIBLE",
        "research_contact": None,
        "condition": "Delivery-partner terms are not proof Alto purchases third-party homeowner leads",
    },
    "hpin.co.uk": {
        "source_url": "https://www.hpin.co.uk/about/",
        "classification": "CERTIFIED_INSTALLER_REFERRALS_ONLY_UNLESS_SEPARATELY_APPROVED",
        "research_contact": None,
        "condition": "Advertised 500 GBP install referral bonus is part of certified installer onboarding; not a general publisher payout",
    },
    "newpoweruk.co.uk": {
        "source_url": "https://www.newpoweruk.co.uk/partners",
        "classification": "PARTNER_REFERRAL_AFTER_APPLICATION_AND_PAID_INSTALL",
        "research_contact": None,
        "condition": "Identity may collide with previously approached Newpower Advanced; no new introduction before reconciliation",
    },
}
ROLE_ACTIONS = {
    "A_B2B_TERMS_RESEARCH": "VERIFY_B2B_PROGRAMME_ELIGIBILITY_ACCEPTED_CATEGORY_AND_CONTRACT",
    "B_INSTALLER_QUALIFICATION": "QUALIFY_INSTALLER_CURRENT_BUYBOX_GEO_FORMAT_VOLUME_AND_BUYER",
    "B_NETWORK_PARTNERSHIP_RESEARCH": "IDENTIFY_NETWORK_END_PAYER_AND_INSTALLER_DISTRIBUTION_TERMS",
    "C_SUPPLY_EXCHANGE_RESEARCH": "RESEARCH_SUPPLY_EXCHANGE_RIGHTS_NOT_DIRECT_BUYER",
}
GAPS = (
    "first_party_independent_buyer_acceptance",
    "accepted_uk_regions_or_postcodes_and_operating_hours",
    "accepted_homeowner_consent_enquiry_criteria_and_tracking",
    "accepted_volume_capacity_and_rejections",
    "written_rate_or_commission_and_eligibility",
    "settlement_terms_and_payment_evidence",
)


def _read_original_scout(root: Path, *, now: datetime) -> tuple[dict, str]:
    file = root / SCOUT
    if file.is_symlink() or not file.is_file() or not 50 < file.stat().st_size < 3_000_000:
        return {}, "MISSING_OR_UNSAFE"
    raw = file.read_bytes()
    try:
        data = json.loads(raw)
        observed = datetime.fromisoformat(str(data["generated_at"]).replace("Z","+00:00"))
        age = (now-observed).total_seconds()
        if (data.get("schema_version")!="empire.buyer_acquisition_scout.v1"
            or data.get("mode")!="OBSERVE"
            or data.get("outbound_sent") is not False
            or data.get("database_write_performed") is not False
            or not isinstance(data.get("candidates"),list)
            or len(data["candidates"])>250
            or observed.utcoffset() is None
            or not 0<=age<=MAX_SCOUT_AGE):
            return {}, "STALE_OR_UNVERIFIED"
    except (ValueError,TypeError,KeyError,OverflowError):
        return {}, "INVALID_SOURCE"
    return data,sha256(raw).hexdigest()


DRAFT_RECEIPTS = Path(
    "runtime/buyer_network_intelligence/heat_pump_prepared_drafts_latest.json"
)


def read_prepared_draft_receipts(root: Path, *, now: datetime) -> dict[str,dict]:
    """Historical Gmail draft creations, not evidence of a sent message."""
    file = root / DRAFT_RECEIPTS
    if (file.is_symlink() or not file.is_file()
            or not 100 < file.stat().st_size < 30000
            or (file.stat().st_mode & 0o777) != 0o600):
        return {}
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
        observed = datetime.fromisoformat(str(data["observed_at"]).replace("Z","+00:00"))
        if (data.get("schema_version") !=
                "empire.buyer_network.heat_pump_prepared_drafts.v1"
            or data.get("status") !=
                "WORKSPACE_DRAFT_CREATION_RECEIPTS_REVIEW_ONLY"
            or data.get("source") != "connected_workspace_gmail_draft_listing"
            or data.get("live_outbound_sent") is not False
            or data.get("database_writes") is not False
            or not isinstance(data.get("drafts"),list)
            or len(data["drafts"])>12
            or observed.utcoffset() is None
            or not 0<=(now-observed).total_seconds()<=7*86400):
            return {}
        result={}
        for item in data["drafts"]:
            domain=item["domain"]
            to=item["recipient"]
            draft_id=item["gmail_draft_id"]
            message_id=item["gmail_message_id"]
            if (not isinstance(domain,str) or domain in result
                or not isinstance(to,str)
                or not to.lower().endswith("@"+domain)
                or not isinstance(draft_id,str) or not draft_id.startswith("r-")
                or not isinstance(message_id,str) or len(message_id)>32
                or not all(ch in "0123456789abcdef" for ch in message_id)
                or item.get("observation") !=
                    "DRAFT_PRESENT_AT_OBSERVATION_NOT_SEND"
                or item.get("send_authorized") is not False
                or item.get("ever_sent_verified") is not False):
                return {}
            result[domain]={
                "email_preparation_state":"WORKSPACE_DRAFT_CREATED_NOT_SENT",
                "verified_draft_observation_at":observed.isoformat(),
                "draft_id":draft_id,"message_id":message_id,
                "verified_recipient":to,
                "email_sent_verified":False,
                "new_outreach_authorized":False,
                "live_draft_state_requires_recheck":True,
            }
        return result
    except (OSError,KeyError,ValueError,TypeError,OverflowError):
        return {}


def review(root: Path, *, now: datetime|None=None) -> dict:
    now=now or datetime.now(timezone.utc)
    market=market_review(root,now=now,write=False)
    if (market.get("candidate_count")!=34
        or market.get("outbound_authorized") is not False
        or market.get("database_writes") is not False):
        raise ValueError("HEAT_PUMP_MARKET_EVIDENCE_NOT_ACCEPTABLE")
    scout, fingerprint=_read_original_scout(root,now=now)
    candidates={}
    for row in scout.get("candidates",[]):
        if isinstance(row,dict) and isinstance(row.get("domain"),str):
            candidates.setdefault(row["domain"].lower(),row)
    prior_holds={"PRIOR_OUTBOUND_REVIEW_THREAD_NO_DUPLICATE",
        "POSSIBLE_NEWPOWER_ADVANCED_ALIAS_VERIFY_NO_DUPLICATE",
        "SUPPRESSED_OR_BOUNCED_DO_NOT_SEND"}
    rows=[]
    for company in market["companies"]:
        domain=company["domain"]
        lane=company["commercial_research_lane"]
        code=company["original_contact_state"]
        existing=candidates.get(domain) or {}
        claim=existing.get("buyer_claim_provenance") or {}
        receipts=claim.get("claim_receipts") or []
        observed_count=sum(
            row.get("source_kind")=="observed_first_party_page"
            and row.get("company_domain")==domain
            and row.get("grants_outbound_authority") is False
            for row in receipts if isinstance(row,dict))
        official=OFFICIAL_PROGRAMME_REVIEWS.get(domain)
        is_consumer=company["public_role"]=="consumer_referral_restricted"
        held=code in prior_holds
        next_action=("HOLD_PRIOR_CONTACT_OR_IDENTITY_RECONCILIATION" if held else
                     "NOT_A_BUSINESS_PROGRAMME_CONSUMER_REFERRAL_RESTRICTED" if is_consumer
                     else ROLE_ACTIONS[lane])
        rows.append({
            "company":company["company"],"domain":domain,
            "market_role":company["public_role"],
            "commercial_lane":lane,
            "priority":("HOLD" if held or is_consumer else
                        "A_PARTNER_TERMS_REVIEW" if lane=="A_B2B_TERMS_RESEARCH" else
                        "B_INSTALLER_BUYBOX_REVIEW" if lane=="B_INSTALLER_QUALIFICATION" else
                        "C_INSTALLER_PARTNER_NETWORK_REVIEW" if lane=="B_NETWORK_PARTNERSHIP_RESEARCH" else
                        "D_SUPPLY_EXCHANGE_ONLY_REVIEW"),
            "founder_next_action":next_action,
            "original_contact_disposition":code,
            "source_url":company["source_url"],
            "source_class":company["source_class"],
            "public_offer_limitations":company["public_terms_limitation"],
            "current_scout_candidate_seen":bool(existing),
            "current_scout_first_party_page_receipts":observed_count,
            "current_scout_buyer_claim_state":claim.get("buyer_relationship") if existing else None,
            "programme_evidence":official,
            "missing_for_paid_relationship":list(GAPS),
            "direct_purchase_statement_verified":False,
            "offer_or_commission_accepted_for_empire":False,
            "outbound_authorized":False,
            "contact_approved":False,
            "paid_pilot_verified":False,
        })
    # Do not promote a Gmail DRAFT to a sent/accepted relationship.
    # A later Gmail state change requires a separate provider readback.
    draft_history = read_prepared_draft_receipts(root, now=now)
    for row in rows:
        row["workspace_draft_preparation"] = draft_history.get(row["domain"])
    lane_order={"A_PARTNER_TERMS_REVIEW":0,"B_INSTALLER_BUYBOX_REVIEW":1,
                "C_INSTALLER_PARTNER_NETWORK_REVIEW":2,
                "D_SUPPLY_EXCHANGE_ONLY_REVIEW":3,"HOLD":4}
    rows.sort(key=lambda x:(lane_order[x["priority"]],
                            -x["current_scout_first_party_page_receipts"],
                            x["company"].lower()))
    top=[x for x in rows if x["priority"]!="HOLD"][:12]
    return {
        "schema_version":SCHEMA,
        "generated_at":now.astimezone(timezone.utc).isoformat(),
        "status":"FOUNDER_COMMERCIAL_REVIEW_WITH_REAL_EVIDENCE_GAPS",
        "source_public_research_sha256":market["source_sha256"],
        "source_original_scout_status":("CURRENT" if scout else fingerprint),
        "source_original_scout_sha256":fingerprint if scout else None,
        "market_companies":34,
        "exact_contact_or_identity_holds":sum(x["original_contact_disposition"] in prior_holds for x in rows),
        "consumer_programme_restricted_count":sum(x["market_role"]=="consumer_referral_restricted" for x in rows),
        "research_eligible_for_role_qualification":sum(x["priority"]!="HOLD" for x in rows),
        "recent_original_scout_first_party_companies":sum(x["current_scout_first_party_page_receipts"]>0 for x in rows),
        "founder_prioritized_count":len(top),
        "historical_gmail_draft_preparations":sum(
            x["workspace_draft_preparation"] is not None for x in rows),
        "draft_creation_not_equivalent_to_contact":True,
        "founder_prioritized":top,
        "research_inventory":rows,
        "verified_payable_buyers":0,"verified_paid_pilots":0,
        "new_crm_records":0,"outbound_sent":False,
        "outbound_authorized":False,"database_writes":False,
    }
