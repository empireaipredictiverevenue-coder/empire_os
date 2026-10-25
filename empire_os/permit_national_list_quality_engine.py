"""Original EmpireOS Permit Intelligence: evidence-ranked company contact inventory.

Turns original 38 sourced companies and the 20-site bounded audit into an
honest, reproducible evidence quality board, a bounded owner-review/recheck
queue, and change intelligence. No contact readiness or conversion forecasts.
No network/DB/SMTP access. Fail closed on altered source receipts.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime,timedelta,timezone
from typing import Any,Mapping

from empire_os.permit_multimarket_registry import digest
from empire_os.permit_national_email_list_expansion import (
    build_expanded_list,validate_expanded_list,
)
from empire_os.permit_national_public_email_spotcheck import validate_spotcheck

SCHEMA="empire.permit_data.national_company_contact_quality_engine.v1"
DELTA_SCHEMA="empire.permit_data.national_contact_source_change_intelligence.v1"
FRESH_HOURS=72
TIERS=(
    "L1_OBSERVED_FIRST_PARTY_GENERAL",
    "L2_GENERAL_WEB_RECHECK",
    "L3_LEGACY_FIRST_PARTY_GENERAL_RECHECK",
    "L4_PURPOSE_RESTRICTED",
    "L5_EXTERNAL_NAMED_REVERIFY",
    "L6_FORM_ONLY",
)
MARKET_PRIORITY={"nyc":0,"seattle":1,"san_francisco":2,"austin":3,"chicago":4,"philadelphia":5}

def _clock(value:str)->datetime:
    try:
        out=datetime.fromisoformat(value)
    except (ValueError,TypeError) as exc:
        raise ValueError("source_observation_clock_invalid") from exc
    if out.utcoffset() is None:
        raise ValueError("source_observation_clock_not_aware")
    return out.astimezone(timezone.utc)


def build_quality_board(*,source_list:Mapping[str,Any],
                        website_check:Mapping[str,Any],
                        at:datetime)->dict:
    validate_expanded_list(source_list)
    validate_spotcheck(website_check)
    if not isinstance(at,datetime) or at.utcoffset() is None:
        raise ValueError("quality_board_clock_not_aware")
    now=at.astimezone(timezone.utc)
    list_at=_clock(source_list["as_of_utc"])
    source_at=_clock(website_check["researched_at_utc"])
    if (website_check["original_list_sha256"]!=source_list["expanded_list_sha256"]
        or now<source_at or now<list_at
        or now-source_at>timedelta(days=30)
        or now-list_at>timedelta(days=30)):
        raise ValueError("website_evidence_not_bound_to_original_company_inventory")
    # Explicit evidence age and recrawl priority, no stale match promoted.
    fresh=now-source_at<=timedelta(hours=FRESH_HOURS)
    sites={(r["market_id"],r["company"]):r for r in website_check["results"]}
    if len(sites)!=20:
        raise ValueError("twenty_unique_company_source_evidence_required")
    records=[]
    for row in source_list["companies"]:
        key=(row["market_id"],row["company"])
        website=sites.get(key)
        if website is not None and row["cohort"]!="NEW_FIRST_PARTY_TWENTY":
            raise ValueError("unapproved_spotcheck_company_identity")
        observed=(website is not None and
                  website["source_observation_state"]=="EXACT_PUBLIC_ADDRESS_OBSERVED")
        general=row["route_quality"]=="FIRST_PARTY_GENERAL_ROLE_INBOX_REVIEW"
        restricted=row["route_quality"]=="RESTRICTED_PURPOSE_RECONFIRM"
        external=row["route_quality"]=="THIRD_PARTY_OR_NAMED_RECONFIRM"
        form=row["route_quality"]=="FORM_ONLY_NOT_AN_EMAIL_ADDRESS"
        if form:
            tier=TIERS[5]; score=0
            next_step="Seek current first-party general enquiries route; do not infer an email"
        elif external:
            tier=TIERS[4];score=12
            next_step="Independently confirm third-party/named address and current business role"
        elif restricted:
            tier=TIERS[3];score=30 if observed and fresh else 18
            next_step="Find a general business route appropriate for vendor research; estimating/service inbox not approved"
        elif website is not None and observed and fresh and general:
            tier=TIERS[0];score=85
            next_step="Request original Smart CRM/history/suppression review before any value-first draft"
        elif website is not None and general:
            tier=TIERS[1];score=45 if observed else 25
            next_step="Recheck original exact first-party page for publicly displayed contact address"
        elif general:
            tier=TIERS[2];score=40
            next_step="Repeat bounded, first-party contact-page check; inherited historical source is not fresh"
        else:
            raise ValueError("unrecognised_national_contact_quality_route")
        reason="NO_NEW_WEBSITE_AUDIT"
        if website is not None:
            reason=website["source_observation_state"]
            if observed and not fresh:
                reason="STALE_PREVIOUS_PAGE_MATCH_RECHECK"
        records.append({
            "market_id":row["market_id"],
            "company":row["company"],
            "sector":row["sector"],
            "business_email":row["email"],
            "canonical_email_key":row["email"],
            "published_contact_source_url":row["source_url"],
            "source_cohort":row["cohort"],
            "mailbox_context":row["mailbox_context"],
            "quality_tier":tier,
            "source_research_score_not_buyer_probability":score,
            "recheck_priority":100-score,
            "website_observation_state":reason,
            "fresh_source_page_match":bool(observed and fresh),
            "source_observation_age_hours":round((now-source_at).total_seconds()/3600,2) if website else None,
            "first_party_contact_source_observed_in_latest_audit":bool(observed),
            "needs_first_party_evidence_recheck":bool(tier in (TIERS[1],TIERS[2],TIERS[5])),
            "research_owner_next_action":next_step,
            "source_licence_and_distribution_release":"HOLD",
            "recipient_suppression":"UNKNOWN_NOT_CHECKED",
            "deliverability_state":"NOT_CHECKED",
            "real_buyer_interest":"UNVERIFIED",
            "qualified_lead":False,
            "approved_to_contact":False,
            "customer_value_delivery_authorized":False,
            "execution_authority":"none",
        })
    records.sort(key=lambda r:(TIERS.index(r["quality_tier"]),
                                MARKET_PRIORITY[r["market_id"]],r["company"]))
    counts=Counter(r["quality_tier"] for r in records)
    by_market={market:{
        "research_companies":sum(r["market_id"]==market for r in records),
        "fresh_observed_general_inboxes":sum(
            r["market_id"]==market and r["quality_tier"]==TIERS[0] for r in records),
        "site_rechecks":sum(r["market_id"]==market and r["needs_first_party_evidence_recheck"] for r in records),
    } for market in MARKET_PRIORITY}
    output={
        "schema_version":SCHEMA,
        "evaluated_at_utc":now.isoformat(),
        "original_stack":"ONE_EMPIREOS_PERMIT_INTELLIGENCE",
        "source_list_sha256":source_list["expanded_list_sha256"],
        "source_spotcheck_sha256":website_check["spotcheck_sha256"],
        "companies":38,
        "public_email_candidates":37,
        "latest_website_observed_exact_matches":website_check["company_page_match_count"],
        "latest_website_held_or_unavailable":website_check["robots_or_website_hold_count"],
        "evidence_fresh_within_72h":fresh,
        "tier_counts":{tier:counts.get(tier,0) for tier in TIERS},
        "owner_recheck_queue_count":sum(r["needs_first_party_evidence_recheck"] for r in records),
        "market_quality_counts":by_market,
        "qualified_buyers":0,
        "send_ready_recipient_count":0,
        "live_source_permit_rows_ingested":0,
        "outbound_sent":0,
        "email_deliverability_probes":0,
        "empiredb_writes":0,
        "smart_crm_writes":0,
        "verified_revenue_usd":"0.00",
        "execution_authority":"none",
        "quality_rows":records,
    }
    output["quality_board_sha256"]=digest(output)
    return output


def validate_quality_board(report:Mapping[str,Any])->None:
    if (not isinstance(report,Mapping)
        or report.get("schema_version")!=SCHEMA
        or report.get("quality_board_sha256")!=digest({
            k:v for k,v in report.items() if k!="quality_board_sha256"})
        or report.get("original_stack")!="ONE_EMPIREOS_PERMIT_INTELLIGENCE"
        or report.get("companies")!=38
        or report.get("public_email_candidates")!=37
        or report.get("qualified_buyers")!=0
        or report.get("send_ready_recipient_count")!=0
        or report.get("live_source_permit_rows_ingested")!=0
        or report.get("outbound_sent")!=0
        or report.get("email_deliverability_probes")!=0
        or report.get("empiredb_writes")!=0
        or report.get("smart_crm_writes")!=0
        or report.get("verified_revenue_usd")!="0.00"
        or report.get("execution_authority")!="none"):
        raise ValueError("unsafe_national_contact_quality_report")
    rows=report.get("quality_rows")
    if not isinstance(rows,list) or len(rows)!=38:
        raise ValueError("national_contact_quality_rows_missing")
    seen=set();types=Counter()
    for row in rows:
        key=(row.get("market_id"),row.get("company"))
        if key in seen or row.get("quality_tier") not in TIERS:
            raise ValueError("duplicate_company_or_unknown_quality_tier")
        seen.add(key);types[row["quality_tier"]]+=1
        tier=row["quality_tier"]
        score=row.get("source_research_score_not_buyer_probability")
        quality_rules={
            TIERS[0]:({85},False,True),
            TIERS[1]:({25,45},True,False),
            TIERS[2]:({40},True,False),
            TIERS[3]:({18,30},False,False),
            TIERS[4]:({12},False,False),
            TIERS[5]:({0},True,False),
        }
        scores,expected_recheck,_=quality_rules[tier]
        if (row.get("market_id") not in MARKET_PRIORITY
            or score not in scores
            or type(score) is not int
            or row.get("recheck_priority") != 100-score
            or row.get("needs_first_party_evidence_recheck") is not expected_recheck
            or (tier==TIERS[0] and (
                row.get("fresh_source_page_match") is not True
                or row.get("website_observation_state")!="EXACT_PUBLIC_ADDRESS_OBSERVED"
                or row.get("source_cohort")!="NEW_FIRST_PARTY_TWENTY"))
            or (tier==TIERS[2] and row.get("website_observation_state")!="NO_NEW_WEBSITE_AUDIT")
            or (tier==TIERS[5] and row.get("business_email") is not None)
            or (tier!=TIERS[5] and not row.get("business_email"))
            or (tier==TIERS[4] and row.get("source_cohort")!="ORIGINAL_NATIONAL_TEN")
            or (tier==TIERS[3] and row.get("mailbox_context") not in (
                "BID_INVITATIONS_ONLY","BIDS_AND_INFORMATION",
                "ESTIMATING_DEPARTMENT","NEW_CONSTRUCTION_BIDS",
                "SERVICE_TEAM","ROOF_ESTIMATING_AND_GENERAL"))):
            raise ValueError("national_contact_score_or_source_status_forged")
        if (row.get("qualified_lead") is not False
            or row.get("approved_to_contact") is not False
            or row.get("customer_value_delivery_authorized") is not False
            or row.get("source_licence_and_distribution_release")!="HOLD"
            or row.get("recipient_suppression")!="UNKNOWN_NOT_CHECKED"
            or row.get("deliverability_state")!="NOT_CHECKED"
            or row.get("real_buyer_interest")!="UNVERIFIED"
            or row.get("execution_authority")!="none"):
            raise ValueError("contact_quality_promotion_without_original_owner")
    if report.get("tier_counts")!={tier:types[tier] for tier in TIERS}:
        raise ValueError("national_contact_quality_tier_count_drift")
    if report.get("owner_recheck_queue_count")!=sum(
        r["needs_first_party_evidence_recheck"] is True for r in rows):
        raise ValueError("national_contact_quality_recheck_count_drift")
    if (report.get("latest_website_held_or_unavailable") !=
        20-report.get("latest_website_observed_exact_matches", -1)):
        raise ValueError("national_contact_exact_site_evidence_disagreement")
    if report.get("latest_website_observed_exact_matches")!=sum(
        r["first_party_contact_source_observed_in_latest_audit"] is True for r in rows):
        raise ValueError("national_contact_website_matches_count_wrong")


def compare_quality_boards(*,prior:Mapping[str,Any],current:Mapping[str,Any])->dict:
    validate_quality_board(prior);validate_quality_board(current)
    before=_clock(prior["evaluated_at_utc"]);after=_clock(current["evaluated_at_utc"])
    if before>after:
        raise ValueError("national_contact_quality_replay_out_of_order")
    if prior["source_list_sha256"]==current["source_list_sha256"]:
        old={(r["market_id"],r["company"]):r for r in prior["quality_rows"]}
        new={(r["market_id"],r["company"]):r for r in current["quality_rows"]}
        if set(old)!=set(new):raise ValueError("national_contact_company_identity_drift")
    else:
        # New cohorts must be independently admitted by a future list-owner
        # version, not silently merged with the current 38-company contract.
        raise ValueError("national_contact_underlying_company_list_changed")
    changes=[]
    for key in sorted(old):
        a=old[key];b=new[key]
        if a["business_email"]!=b["business_email"] or a["published_contact_source_url"]!=b["published_contact_source_url"]:
            raise ValueError("national_contact_email_identity_changed_without_research")
        if (a["quality_tier"],a["website_observation_state"]) != (
            b["quality_tier"],b["website_observation_state"]):
            changes.append({
                "market_id":key[0],"company":key[1],
                "prior_quality_tier":a["quality_tier"],
                "new_quality_tier":b["quality_tier"],
                "prior_source_state":a["website_observation_state"],
                "new_source_state":b["website_observation_state"],
                "change_is_commercial_authority":False,
            })
    output={
        "schema_version":DELTA_SCHEMA,
        "prior_quality_board_sha256":prior["quality_board_sha256"],
        "current_quality_board_sha256":current["quality_board_sha256"],
        "source_quality_changes":len(changes),
        "changes":changes,
        "owner_review_only":True,
        "outbound_authorized":False,
        "revenue_credited_usd":"0.00",
        "execution_authority":"none",
    }
    output["delta_sha256"]=digest(output)
    return output
