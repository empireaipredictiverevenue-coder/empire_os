"""Owner-review-first, no-send commercial copy for Permit Intelligence.

One brief value-first question for the original ten first-party-general
business research contacts. Not generic automated mailing. Does not claim
buyer intent, awards, active work, permit data rights or SMTP deliverability.
Offer an opted-in sample only AFTER genuine human response and source rights.
"""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from typing import Any,Mapping

from empire_os.permit_multimarket_registry import digest
from empire_os.permit_national_weekday_outreach_clock import (
    validate_clock,next_occurrences,
)
from empire_os.permit_national_outreach_execution_preflight import validate_preflight

SCHEMA="empire.permit_data.national_permit_value_first_original_owner_review.v1"
MARKET_LABEL={
    "nyc":"New York City","philadelphia":"Philadelphia",
    "chicago":"Chicago","austin":"Austin",
    "seattle":"Seattle","san_francisco":"San Francisco Bay Area",
}
TRADE_LABEL={
    "fire_protection":"fire-protection installation and upgrade work",
    "commercial_roofing":"commercial roofing projects",
    "commercial_hvac":"commercial HVAC projects",
    "hvac":"HVAC work",
    "commercial_plumbing":"commercial plumbing jobs",
    "electrical":"electrical contracting projects",
    "general_contractor":"general contracting work",
    "construction":"construction projects",
    "structural_steel":"structural steel projects",
    "hvac_fire_protection":"HVAC and fire-protection projects",
}


def build_workbench(*,clock:Mapping[str,Any],preflight:Mapping[str,Any],
                    at:datetime)->dict:
    validate_clock(clock)
    validate_preflight(preflight)
    if not isinstance(at,datetime) or at.utcoffset() is None:
        raise ValueError("permit_value_first_review_clock_must_be_aware")
    now=at.astimezone(timezone.utc)
    checked=datetime.fromisoformat(preflight["reviewed_at_utc"]).astimezone(timezone.utc)
    if (preflight["source_clock_sha256"]!=clock["weekday_outreach_clock_sha256"]
        or now<checked or now-checked>timedelta(hours=24)):
        raise ValueError("permit_value_first_preflight_not_same_original_schedule")
    index={x["company_id"]:x for x in preflight["recipients"]}
    drafts=[]
    for lane in clock["regional_clocks"]:
        for row in lane["region_research_queue"]:
            source=index.get(row["company_id"])
            if (source is None or source["published_business_email_candidate"]!=row["published_email_candidate"]
                or source["region"]!=lane["lane_id"]):
                raise ValueError("permit_original_contact_route_or_approval_mismatch")
            if source["first_touch_classification"]!="UNVERIFIED_GENERAL_BUSINESS_REVIEW":
                continue
            if row["sector"] not in TRADE_LABEL or row["market_id"] not in MARKET_LABEL:
                raise ValueError("unreviewed_first_party_sector_or_market")
            market=MARKET_LABEL[row["market_id"]]
            trade=TRADE_LABEL[row["sector"]]
            subject=f"{market} permit-stage research — one useful check"
            content=(
                f"Hello {row['company']} team,\n\n"
                "One check that can prevent wasted research: an application "
                "filed or approved is not, by itself, evidence that the actual "
                "permit was issued. The record's stage and observation date "
                "are worth cross-checking before treating it as a project signal.\n\n"
                f"For {trade} around {market}, how does your team currently "
                "distinguish permit applications from issued permits when "
                "deciding which opportunities are worth investigating?\n\n"
                "I'm comparing workflow challenges, not claiming a permit "
                "represents an available contract. No job list or sample is "
                "attached. An email reply is fine, and please say if you'd "
                "prefer no further contact.\n\n"
                "Empire AI | Permit Intelligence\n"
            )
            if content.count("?")!=1 or "$" in content or "https://" in content:
                raise ValueError("first_touch_copy_not_value_first_single_question")
            proposed=next_occurrences(when=now,tz_name=lane["tz_name"],limit=1)[0]
            drafts.append({
                "company_id":row["company_id"],
                "company":row["company"],
                "market_id":row["market_id"],
                "sector":row["sector"],
                "region":lane["lane_id"],
                "recipient_local_zone":lane["tz_name"],
                "public_general_business_email_candidate":row["published_email_candidate"],
                "original_preflight_slot_key":source["time_slot_id_sha256"],
                "original_history_state":source["original_domain_history_state"],
                "owner_hold_reasons":source["blocking_reasons"],
                "suggested_next_weekday_0800_local":proposed["local_wall_time"],
                "suggested_next_uk_time":proposed["uk_wall_time"],
                "message_stage":"VALUE_FIRST_SINGLE_WORKFLOW_QUESTION_UNSENT",
                "subject_draft":subject,
                "body_draft":content,
                "copy_sha256":digest({"subject":subject,"body":content}),
                "genuine_buyer_reply_needed_before_sample":True,
                "only_permissioned_source_checked_sample_after_reply":True,
                "recipient_contact_purpose_approved":False,
                "original_crm_recipient_domain_suppression_cleared":False,
                "founder_exact_copy_approval":False,
                "original_sender_authorized":False,
                "opted_in_sample_requested":False,
                "message_sent":False,
                "sample_sent":False,
                "verified_revenue_usd":"0.00",
            })
    drafts.sort(key=lambda row:(row["region"],row["market_id"],row["company"]))
    result={
        "schema_version":SCHEMA,
        "reviewed_at_utc":now.isoformat(),
        "source_clock_sha256":clock["weekday_outreach_clock_sha256"],
        "source_original_crm_preflight_sha256":preflight["execution_preflight_sha256"],
        "one_original_permit_intelligence_product":True,
        "prospect_research_companies":70,
        "published_business_email_candidates":64,
        "general_business_first_contact_copy_drafts":len(drafts),
        "general_first_contact_candidates_held_before_draft":10-len(drafts),
        "drafts_currently_approved":0,
        "contacts_sent":0,"samples_sent":0,
        "verified_buyers":0,"empiredb_writes":0,
        "smart_crm_writes":0,"verified_revenue_usd":"0.00",
        "execution_authority":"none",
        "owner_review_drafts":drafts,
    }
    result["value_first_workbench_sha256"]=digest(result)
    return result


def validate_workbench(report:Mapping[str,Any])->None:
    if (not isinstance(report,Mapping)
        or report.get("schema_version")!=SCHEMA
        or report.get("value_first_workbench_sha256")!=digest({
            k:v for k,v in report.items() if k!="value_first_workbench_sha256"})
        or report.get("one_original_permit_intelligence_product") is not True
        or report.get("prospect_research_companies")!=70
        or report.get("published_business_email_candidates")!=64
        or type(report.get("general_business_first_contact_copy_drafts")) is not int
        or not 0<=report.get("general_business_first_contact_copy_drafts")<=10
        or report.get("general_first_contact_candidates_held_before_draft")!=(
            10-report.get("general_business_first_contact_copy_drafts"))
        or report.get("drafts_currently_approved")!=0
        or report.get("contacts_sent")!=0
        or report.get("samples_sent")!=0
        or report.get("verified_buyers")!=0
        or report.get("empiredb_writes")!=0
        or report.get("smart_crm_writes")!=0
        or report.get("verified_revenue_usd")!="0.00"
        or report.get("execution_authority")!="none"):
        raise ValueError("permit_value_first_owner_workbench_send_claim_forged")
    rows=report.get("owner_review_drafts")
    if (not isinstance(rows,list)
        or len(rows)!=report["general_business_first_contact_copy_drafts"]
        or len({r.get("company_id") for r in rows})!=len(rows)):
        raise ValueError("permit_value_first_draft_company_count_invalid")
    for row in rows:
        body=row.get("body_draft");subject=row.get("subject_draft")
        if (not isinstance(body,str) or not isinstance(subject,str)
            or body.count("?")!=1 or "$" in body or "https://" in body
            or row.get("copy_sha256")!=digest({"subject":subject,"body":body})
            or row.get("message_stage")!="VALUE_FIRST_SINGLE_WORKFLOW_QUESTION_UNSENT"
            or row.get("genuine_buyer_reply_needed_before_sample") is not True
            or row.get("only_permissioned_source_checked_sample_after_reply") is not True
            or row.get("recipient_contact_purpose_approved") is not False
            or row.get("original_crm_recipient_domain_suppression_cleared") is not False
            or row.get("founder_exact_copy_approval") is not False
            or row.get("original_sender_authorized") is not False
            or row.get("opted_in_sample_requested") is not False
            or row.get("message_sent") is not False
            or row.get("sample_sent") is not False
            or row.get("verified_revenue_usd")!="0.00"):
            raise ValueError("permit_value_first_draft_illegally_promoted_to_send")
