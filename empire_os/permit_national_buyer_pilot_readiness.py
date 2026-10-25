"""Existing EmpireOS Permit Intelligence first buyer-pilot readiness.

Combine original SHA-custodied 10-company owner-review workbench with
read-only metadata observations of ACTUAL unsent Workspace Gmail drafts.
No SMTP, mail transport, CRM writes, consent inference or automatic sends.

The connector observation is not an independently signed Gmail provider
receipt. Its presence is evidence of a draft seen, never mailbox delivery,
complete history, address verification or legal marketing permission.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timezone,timedelta
import re
from typing import Any,Mapping

from empire_os.permit_multimarket_registry import digest
from empire_os.permit_national_outreach_value_first_workbench import (
    validate_workbench,
)

SCHEMA="empire.permit_data.original_ten_buyer_pilot_commercial_readiness.v1"
OBS_SCHEMA="empire.permit_data.connected_workspace_ten_drafts_observation.v1"
SOURCE="CHATGPT_CONNECTED_WORKSPACE_GMAIL_READONLY_OBSERVATION_NOT_SEND_AUTHORITY"
LIVE_SOURCE="ORIGINAL_EMPIREOS_WORKSPACE_GMAIL_PINNED_READONLY"
EXPECTED_MAILBOX="phil@empire-ai.co.uk"
REVIEW_STATES={
    "DRAFT_PRESENT_CONTENT_CHECK_PENDING_BUSINESS_POSTAL_AND_OWNER",
    "DRAFT_PRESENT_CONTENT_AND_COMPLIANCE_OWNER_REVIEW",
}
MARKET_LANES={"chicago","austin","seattle","philadelphia"}
US_COMMERCIAL_REQUIRED_REVIEW=(
    "US_COMMERCIAL_SENDER_PHYSICAL_POSTAL_ADDRESS_UNVERIFIED",
    "US_COMMERCIAL_PURPOSE_AND_SUBJECT_HUMAN_REVIEW_REQUIRED",
    "REPLY_BASED_OPTOUT_CHANNEL_PROCESSING_NOT_ATTESTED",
    "ORIGINAL_CRM_COMPLETE_CONTACT_HISTORY_NOT_PROVEN",
    "EXACT_RECIPIENT_PERMISSION_AND_SOURCE_PURPOSE_NOT_APPROVED",
    "FOUNDER_EXACT_GMAIL_MESSAGE_NOT_APPROVED",
)
DRAFT_ID=re.compile(r"r-?\d{8,30}\Z")
MSG_ID=re.compile(r"[0-9a-f]{16,24}\Z")


def _aware(iso:str)->datetime:
    if not isinstance(iso,str):
        raise ValueError("ORIGINAL_DRAFT_REVIEW_TIME_NOT_ATTESTED")
    try:
        when=datetime.fromisoformat(iso.replace("Z","+00:00"))
    except ValueError:
        raise ValueError("ORIGINAL_DRAFT_REVIEW_TIME_NOT_ATTESTED") from None
    if when.utcoffset() is None:
        raise ValueError("ORIGINAL_DRAFT_REVIEW_TIME_NOT_ATTESTED")
    return when.astimezone(timezone.utc)


def validate_observation(observation:Mapping[str,Any],at:datetime)->None:
    now=at.astimezone(timezone.utc)
    if (not isinstance(observation,Mapping)
        or observation.get("schema_version")!=OBS_SCHEMA
        or observation.get("observation_sha256")!=digest({
            k:v for k,v in observation.items() if k!="observation_sha256"})
        or observation.get("source") not in (SOURCE,LIVE_SOURCE)
        or (observation.get("source")==LIVE_SOURCE
            and (observation.get("source_provider_runtime")!=
                 "ORIGINAL_EMPIREOS_WORKSPACE_GMAIL_PINNED_READ_API"
                 or observation.get("full_body_inspected_in_memory_only") is not True))
        or observation.get("sender_account")!=EXPECTED_MAILBOX
        or observation.get("read_only") is not True
        or observation.get("send_authorized") is not False
        or observation.get("emails_sent")!=0):
        raise ValueError("UNTRUSTED_CONNECTED_GMAIL_DRAFT_OBSERVATION")
    observed=_aware(observation.get("observed_at_utc"))
    if observed>now+timedelta(minutes=2) or now-observed>timedelta(hours=48):
        raise ValueError("STALE_OR_FUTURE_GMAIL_DRAFT_OBSERVATION")
    rows=observation.get("drafts")
    if not isinstance(rows,list) or len(rows)!=10:
        raise ValueError("TEN_EXACT_WORKSPACE_DRAFTS_REQUIRED")
    emails=set();ids=set();msgs=set()
    for entry in rows:
        if (not isinstance(entry,Mapping)
            or not isinstance(entry.get("recipient"),str)
            or not re.fullmatch(r"[a-z0-9_.+%-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+",
                               entry["recipient"])
            or entry["recipient"] in emails
            or not isinstance(entry.get("draft_id"),str)
            or not DRAFT_ID.fullmatch(entry["draft_id"])
            or entry["draft_id"] in ids
            or not isinstance(entry.get("message_id"),str)
            or not MSG_ID.fullmatch(entry["message_id"])
            or entry["message_id"] in msgs
            or not isinstance(entry.get("subject"),str)
            or not 10<=len(entry["subject"])<=200
            or entry.get("labels")!=["DRAFT"]
            or entry.get("attachments") is not False
            or type(entry.get("body_has_postal_address")) is not bool
            or type(entry.get("body_has_reply_opt_out_request")) is not bool
            or type(entry.get("body_has_brand_identity")) is not bool
            or type(entry.get("body_mentions_no_job_list")) is not bool
            or entry.get("actually_sent") is not False):
            raise ValueError("WORKSPACE_DRAFT_OBSERVATION_ROW_UNTRUSTED")
        quality=entry.get("canonical_copywriter_qa")
        if quality is not None and (
            not isinstance(quality,Mapping)
            or quality.get("canonical_engine")!="empire_os.outreach_message_optimizer"
            or quality.get("send_enabled") is not False
            or quality.get("source_specific_proof_verified") is not False
            or quality.get("requires_founder_exact_copy_review") is not True
            or type(quality.get("quality_score")) is not int
            or not 0<=quality["quality_score"]<=100
            or not isinstance(quality.get("quality_issues"),list)
            or any(not isinstance(v,str) for v in quality["quality_issues"])
            or type(quality.get("human_copy_gate_eligible")) is not bool):
            raise ValueError("WORKSPACE_ORIGINAL_COPYWRITER_REVIEW_UNTRUSTED")
        emails.add(entry["recipient"])
        ids.add(entry["draft_id"])
        msgs.add(entry["message_id"])


def build(*,workbench:Mapping[str,Any],observation:Mapping[str,Any],
          at:datetime)->dict:
    validate_workbench(workbench)
    if not isinstance(at,datetime) or at.utcoffset() is None:
        raise ValueError("PERMIT_BUYER_PILOT_REVIEW_REQUIRES_UTC_CLOCK")
    now=at.astimezone(timezone.utc)
    validate_observation(observation,now)
    when=_aware(workbench["reviewed_at_utc"])
    if now<when or now-when>timedelta(days=14):
        raise ValueError("ORIGINAL_BUYER_WORKBENCH_OUT_OF_REVIEW_WINDOW")
    researched={x["public_general_business_email_candidate"]:x
                for x in workbench["owner_review_drafts"]}
    if len(researched)!=10 or set(researched)!={x["recipient"] for x in observation["drafts"]}:
        raise ValueError("GMAIL_DRAFT_NOT_BOUND_TO_ORIGINAL_TEN_COMPANIES")
    rows=[]
    for current in observation["drafts"]:
        original=researched[current["recipient"]]
        if (original["market_id"] not in MARKET_LANES
            or original["recipient_local_zone"] not in (
                "America/New_York","America/Chicago",
                "America/Los_Angeles")):
            raise ValueError("UNEXPECTED_NON_US_COMMERCIAL_OUTREACH_ROUTE")
        reasons=list(US_COMMERCIAL_REQUIRED_REVIEW)
        if not current["body_has_postal_address"]:
            reasons.append("ACTUAL_GMAIL_DRAFT_BODY_POSTAL_ADDRESS_ABSENT")
        if not current["body_has_reply_opt_out_request"]:
            reasons.append("ACTUAL_GMAIL_DRAFT_REPLY_OPTOUT_REQUEST_MISSING")
        if not current["body_has_brand_identity"]:
            reasons.append("ACTUAL_GMAIL_DRAFT_IDENTITY_NOT_PRESENT")
        if not current["body_mentions_no_job_list"]:
            reasons.append("VERIFY_COPY_DOES_NOT_PROMISE_UNVERIFIED_JOBS")
        copy_qa=current.get("canonical_copywriter_qa")
        if copy_qa is not None and (
            not copy_qa["human_copy_gate_eligible"]
            or copy_qa["quality_score"]<80
            or not copy_qa.get("one_primary_question",False)):
            reasons.append("ORIGINAL_CANONICAL_COPYWRITER_NEEDS_REVIEW")
        # A body mentioning an address is NOT verification of its truth.
        # Likewise, a message claiming opt-out does not prove the reply
        # monitoring/STOP-processing mechanism will work after sending.
        rows.append({
            "company_id":original["company_id"],
            "company":original["company"],
            "market_id":original["market_id"],
            "sector":original["sector"],
            "trade_lane":original["sector"],
            "recipient":current["recipient"],
            "draft_id":current["draft_id"],
            "message_id":current["message_id"],
            "workspace_subject_observed":current["subject"],
            "draft_state":"GMAIL_DRAFT_CONFIRMED_UNSENT",
            "permit_owner_workbench_copy_sha256":original["copy_sha256"],
            "original_canonical_copywriter_quality":copy_qa,
            "local_workbench_copy_is_gmail_copy_verified_identical":False,
            "canonical_original_history_state":original["original_history_state"],
            "global_canonical_hits_cannot_authorize_this_gmail_draft":True,
            "verified_business_postal_address":False,
            "functional_optout_processing_attested":False,
            "recipient_contact_purpose_approved":False,
            "permit_job_data_distribution_approved":False,
            "actual_buyer_interest_verified":False,
            "manual_approved_to_send":False,
            "send_enabled":False,
            "message_sent":False,
            "commercial_hold_reasons":reasons,
            "priority_review_stage":(
                "DRAFT_PRESENT_CONTENT_CHECK_PENDING_BUSINESS_POSTAL_AND_OWNER"
                if not current["body_has_postal_address"]
                else "DRAFT_PRESENT_CONTENT_AND_COMPLIANCE_OWNER_REVIEW"
            ),
        })
    rows.sort(key=lambda r:(r["market_id"],r["sector"],r["company"]))
    result={
        "schema_version":SCHEMA,
        "reviewed_at_utc":now.isoformat(),
        "original_workbench_sha256":workbench["value_first_workbench_sha256"],
        "connected_workspace_observation_sha256":observation["observation_sha256"],
        "observation_not_a_signed_provider_send_receipt":True,
        "workspace_observation_is_not_original_owner_64_row_report":True,
        "owner_canonical_recipient_clearance_not_inferred":True,
        "commercial_message_jurisdiction_review":"UNITED_STATES_CAN_SPAM_FTC",
        "original_stack":"ONE_EMPIREOS_EMPIREDB_SMART_CRM",
        "company_count":10,
        "verified_unique_workspace_drafts":10,
        "actual_workspace_drafts_without_postal_address":sum(
            not x["body_has_postal_address"] for x in observation["drafts"]),
        "market_counts":dict(sorted(Counter(x["market_id"] for x in rows).items())),
        "trade_counts":dict(sorted(Counter(x["sector"] for x in rows).items())),
        "approved_recipients":0,
        "live_outbound_sent":0,
        "verified_buyer_conversations":0,
        "actual_revenue_usd":"0.00",
        "empiredb_writes":0,
        "smart_crm_writes":0,
        "execution_authority":"none",
        "owner_review_queue":rows,
    }
    result["pilot_readiness_sha256"]=digest(result)
    return result


def validate_review(report:Mapping[str,Any])->None:
    if (not isinstance(report,Mapping)
        or report.get("schema_version")!=SCHEMA
        or report.get("pilot_readiness_sha256")!=digest({
            k:v for k,v in report.items() if k!="pilot_readiness_sha256"})
        or report.get("company_count")!=10
        or report.get("verified_unique_workspace_drafts")!=10
        or report.get("approved_recipients")!=0
        or report.get("live_outbound_sent")!=0
        or report.get("verified_buyer_conversations")!=0
        or report.get("actual_revenue_usd")!="0.00"
        or report.get("empiredb_writes")!=0
        or report.get("smart_crm_writes")!=0
        or report.get("execution_authority")!="none"):
        raise ValueError("ORIGINAL_BUYER_PILOT_REVIEW_AUTHORITY_FORGED")
    rows=report.get("owner_review_queue")
    if not isinstance(rows,list) or len(rows)!=10:
        raise ValueError("ORIGINAL_BUYER_PILOT_REVIEW_ROW_COUNT_UNTRUSTED")
    for row in rows:
        if (row.get("draft_state")!="GMAIL_DRAFT_CONFIRMED_UNSENT"
            or row.get("manual_approved_to_send") is not False
            or row.get("send_enabled") is not False
            or row.get("message_sent") is not False
            or row.get("actual_buyer_interest_verified") is not False
            or row.get("recipient_contact_purpose_approved") is not False
            or row.get("permit_job_data_distribution_approved") is not False
            or row.get("functional_optout_processing_attested") is not False
            or row.get("verified_business_postal_address") is not False
            or row.get("priority_review_stage") not in REVIEW_STATES
            or not isinstance(row.get("commercial_hold_reasons"),list)
            or not set(US_COMMERCIAL_REQUIRED_REVIEW).issubset(
                row["commercial_hold_reasons"])):
            raise ValueError("ORIGINAL_BUYER_PILOT_SEND_AUTHORITY_FORGED")
