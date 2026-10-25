"""Source-provenance enrichment over ONE existing EmpireOS Permit list.

Reconcile original 50-company source research with the two independently
published first-party discovery waves, with strict identity, hash and source
receipt matching. Enrichment is research workflow metadata NOT buyer
qualification, deliverability proof, contact permission or licensed output.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime,timedelta,timezone
from typing import Any,Mapping

from empire_os.permit_multimarket_registry import digest
from empire_os.permit_national_public_business_discovery import (
    validate_discovery, SEEDS, WAVE2_SEEDS, SOURCE_WAVE2_KEY,
)
from empire_os.permit_national_volume_intake import validate_volume_intake

SCHEMA="empire.permit_data.national_permit_volume_evidence_enrichment.v1"
HISTORICAL="HISTORICAL_RESEARCH_NEEDS_FRESH_COMPANY_SOURCE"
LIVE_GENERAL="CURRENT_EXACT_FIRST_PARTY_GENERAL_BUSINESS"
LIVE_LIMITED="CURRENT_EXACT_FIRST_PARTY_PURPOSE_RESTRICTED"
NO_EMAIL="BUSINESS_CONTACT_ADDRESS_NOT_YET_FOUND"
RECHECK="OFFICIAL_COMPANY_SOURCE_RECHECK_UNRESOLVED"
TIERS=(LIVE_GENERAL,LIVE_LIMITED,HISTORICAL,NO_EMAIL)
RESTRICTED=frozenset({
    "ESTIMATING_SERVICE","QUOTE_SALES_INBOX","QUOTE_AND_GENERAL",
    "QUOTE_REQUEST_ROUTE","PROJECT_QUOTE_ROUTE","PROJECT_ENQUIRIES",
    "BID_REQUEST_ROUTE","SERVICE_REQUEST_ROUTE","SALES_SUPPORT",
    "COMMERCIAL_PROJECT_INQUIRY","SERVICE_REQUESTS",
})
GENERAL=frozenset({"GENERAL_COMPANY"})
ORIGINAL_SOURCE_COUNT=50
MAX_AGE=timedelta(hours=72)


def build_enrichment(*,volume:Mapping[str,Any],
                     original_discovery:Mapping[str,Any],
                     second_discovery:Mapping[str,Any],
                     at:datetime)->dict:
    validate_volume_intake(volume)
    validate_discovery(original_discovery)
    validate_discovery(second_discovery)
    if not isinstance(at,datetime) or at.utcoffset() is None:
        raise ValueError("national_enrichment_aware_clock_required")
    now=at.astimezone(timezone.utc)
    if (original_discovery.get("source_wave_key") is not None
        or second_discovery.get("source_wave_key")!=SOURCE_WAVE2_KEY
        or volume.get("source_legacy_company_count")!=ORIGINAL_SOURCE_COUNT):
        raise ValueError("permit_national_two_source_wave_custody_invalid")
    observations={}
    for packet in (original_discovery,second_discovery):
        seen=set()
        stamp=datetime.fromisoformat(packet["observed_at_utc"]).astimezone(timezone.utc)
        if stamp>now or now-stamp>timedelta(days=30):
            raise ValueError("permit_national_source_evidence_expired_or_future")
        for row in packet["observations"]:
            key=(row["market_id"],row["company"])
            if key in observations or key in seen:
                raise ValueError("duplicate_cross_wave_company_identity")
            seen.add(key)
            observations[key]=row
    if len(observations)!=len(SEEDS)+len(WAVE2_SEEDS):
        raise ValueError("national_contact_wave_source_observations_incomplete")
    original_imports={
        (r["market_id"],r["company"]):r for packet in (original_discovery,second_discovery)
        for r in packet["candidate_intake_json_rows"]
    }
    seen_imported=set();enriched=[]
    for row in volume["companies"]:
        key=(row["market_id"],row["company"])
        match=observations.get(key)
        is_external=row["research_cohort"]=="EXTERNAL_USER_EVIDENCE_PENDING_OWNER"
        if is_external:
            if match is None or key not in original_imports:
                # Any future third-party/manual candidate requires an
                # independent source attachment before scoring. Do not allow
                # a plausible email string to become a verified observation.
                raise ValueError("external_candidate_without_exact_first_party_receipt")
            imported=original_imports[key]
            if (row["public_business_email"]!=imported["public_business_email"]
                or row["official_company_url"]!=imported["official_company_url"]
                or row["source_observed_at_utc"]!=imported["evidence_observed_at_utc"]
                or not match["expected_email_exactly_present"]):
                raise ValueError("import_identity_not_matched_to_company_source_receipt")
            seen_imported.add(key)
            age=now-datetime.fromisoformat(row["source_observed_at_utc"])
            if age<timedelta(0):
                raise ValueError("future_source_match_for_enrichment")
            context=match["contact_route_purpose"]
            if context in GENERAL:
                tier=LIVE_GENERAL if age<=MAX_AGE else HISTORICAL
            elif context in RESTRICTED:
                tier=LIVE_LIMITED if age<=MAX_AGE else HISTORICAL
            else:
                raise ValueError("unclassified_first_party_contact_purpose")
            next_step=(
                "Original CRM owner: independently confirm public route purpose, suppression and prior contact before any sales proposal"
                if tier==LIVE_GENERAL else
                "Source owner: confirm non-bid/vendor-appropriate mailbox; first-party appearance alone is insufficient"
                if tier==LIVE_LIMITED else
                "Refresh exact official company contact page before deciding on mailbox suitability"
            )
            evidence_url=match["official_company_contact_url"]
        else:
            if match is not None and match["expected_email_exactly_present"]:
                raise ValueError("new_source_claim_conflicts_with_original_first_fifty")
            tier=HISTORICAL if row["public_business_email"] else NO_EMAIL
            context="PREEXISTING_PERMIT_RESEARCH"
            next_step=("Refresh company-owned public contact source and reconfirm business email"
                       if row["public_business_email"] else
                       "Look for suitable current first-party business contact route; no email guessing")
            evidence_url=row["evidence_url"]
        score={LIVE_GENERAL:85,LIVE_LIMITED:60,HISTORICAL:25,NO_EMAIL:0}[tier]
        enriched.append({
            "stable_research_company_id":row["stable_research_company_id"],
            "market_id":row["market_id"],"company":row["company"],
            "sector":row["sector"],"candidate_business_email":row["public_business_email"],
            "source_cohort":row["research_cohort"],
            "source_url":evidence_url,
            "contact_purpose":context,
            "source_provenance_tier":tier,
            "source_quality_points_not_buyer_probability":score,
            "first_party_exact_email_observed":is_external,
            "next_enrichment_action":next_step,
            "company_identity_and_trade_fit":"RESEARCH_HYPOTHESIS_NOT_COMMERCIAL_VERIFICATION",
            "delivery_accepted_or_mailbox_verified":False,
            "original_smart_crm_suppression_checked":False,
            "buyer_need_and_budget_confirmed":False,
            "commercial_permit_source_rights_cleared":False,
            "qualified_customer":False,
            "outreach_authorized":False,
            "revenue_attributed_usd":"0.00",
        })
    if seen_imported!=set(original_imports):
        raise ValueError("source_discovery_matched_company_not_in_cumulative_inventory")
    if len(enriched)!=volume["deduplicated_research_companies"]:
        raise ValueError("missing_or_surplus_enriched_company")
    enriched.sort(key=lambda r:(
        -r["source_quality_points_not_buyer_probability"],r["market_id"],r["company"]))
    classes=Counter(row["source_provenance_tier"] for row in enriched)
    market_counts=Counter(row["market_id"] for row in enriched)
    sector_counts=Counter(row["sector"] for row in enriched)
    states=Counter(x["source_observation_state"] for x in observations.values())
    output={
        "schema_version":SCHEMA,"evaluated_at_utc":now.isoformat(),
        "source_volume_sha256":volume["volume_intake_sha256"],
        "source_first_wave_sha256":original_discovery["discovery_sha256"],
        "source_second_wave_sha256":second_discovery["discovery_sha256"],
        "existing_empireos_stack":True,
        "deduplicated_research_companies":len(enriched),
        "business_email_candidates":sum(bool(x["candidate_business_email"]) for x in enriched),
        "first_party_company_pages_checked":len(observations),
        "first_party_exact_page_matches":len(original_imports),
        "first_party_failed_or_no_exact_match":len(observations)-len(original_imports),
        "evidence_tier_counts":{k:classes.get(k,0) for k in TIERS},
        "by_market":dict(sorted(market_counts.items())),
        "by_sector":dict(sorted(sector_counts.items())),
        "source_state_counts":dict(sorted(states.items())),
        "unresolved_source_review_tasks":sum(
            x["source_provenance_tier"] in (HISTORICAL,NO_EMAIL) for x in enriched)
            +len(observations)-len(original_imports),
        "business_email_verified_deliverable":0,
        "confirmed_buyer_needs":0,
        "qualified_customers":0,"approved_outreach_recipients":0,
        "outbound_sent":0,"new_permit_row_gets":0,
        "empiredb_writes":0,"smart_crm_writes":0,
        "verified_revenue_usd":"0.00",
        "execution_authority":"none",
        "companies":enriched,
    }
    output["enrichment_sha256"]=digest(output)
    return output


def validate_enrichment(packet:Mapping[str,Any])->None:
    if (not isinstance(packet,Mapping)
        or packet.get("schema_version")!=SCHEMA
        or packet.get("enrichment_sha256")!=digest({
            k:v for k,v in packet.items() if k!="enrichment_sha256"})
        or packet.get("existing_empireos_stack") is not True
        or packet.get("business_email_verified_deliverable")!=0
        or packet.get("confirmed_buyer_needs")!=0
        or packet.get("qualified_customers")!=0
        or packet.get("approved_outreach_recipients")!=0
        or packet.get("outbound_sent")!=0
        or packet.get("new_permit_row_gets")!=0
        or packet.get("empiredb_writes")!=0
        or packet.get("smart_crm_writes")!=0
        or packet.get("verified_revenue_usd")!="0.00"
        or packet.get("execution_authority")!="none"):
        raise ValueError("national_volume_enrichment_unsafe")
    rows=packet.get("companies")
    if (not isinstance(rows,list)
        or len(rows)!=packet.get("deduplicated_research_companies")
        or len({r.get("stable_research_company_id") for r in rows})!=len(rows)
        or sum(r.get("candidate_business_email") is not None for r in rows)
           !=packet.get("business_email_candidates")
        or sum(r.get("first_party_exact_email_observed") is True for r in rows)
           !=packet.get("first_party_exact_page_matches")):
        raise ValueError("national_enrichment_research_totals_mismatch")
    classes=Counter(x.get("source_provenance_tier") for x in rows)
    if packet.get("evidence_tier_counts")!={k:classes[k] for k in TIERS}:
        raise ValueError("national_enrichment_tier_totals_mismatch")
    for item in rows:
        tier=item.get("source_provenance_tier")
        if (tier not in TIERS or
            item.get("source_quality_points_not_buyer_probability")!={LIVE_GENERAL:85,LIVE_LIMITED:60,HISTORICAL:25,NO_EMAIL:0}[tier]
            or (tier==NO_EMAIL)!=(item.get("candidate_business_email") is None)
            or (tier in (LIVE_GENERAL,LIVE_LIMITED) and
                item.get("first_party_exact_email_observed") is not True)
            or item.get("delivery_accepted_or_mailbox_verified") is not False
            or item.get("original_smart_crm_suppression_checked") is not False
            or item.get("buyer_need_and_budget_confirmed") is not False
            or item.get("commercial_permit_source_rights_cleared") is not False
            or item.get("qualified_customer") is not False
            or item.get("outreach_authorized") is not False
            or item.get("revenue_attributed_usd")!="0.00"):
            raise ValueError("national_enrichment_illegal_quality_or_buyer_promotion")
