"""Permit Intelligence original Smart CRM outbound readiness + slot replay guard.

READ-ONLY operating preflight: consumes already source-custodied 70-company
region-local weekday clock plus the existing contact history reader's snapshot.
Unknown history, stale Gmail, opt-outs, restricted routes, source rights, exact
recipient and founder authorisation all fail closed. This module does NOT grant
any of those authorities, contact anyone or alter any production systems.

Stable per-recipient + destination-local calendar slot hashes detect duplicate
candidate dispatch attempts. They are *NOT* provider-confirmed sends or ledger
locks. A future real sender needs atomic durable claims and provider receipts.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime,timedelta,timezone
from typing import Any,Mapping

from empire_os.permit_multimarket_registry import digest
from empire_os.permit_national_weekday_outreach_clock import (
    validate_clock,due_at,LANES,
)
from empire_os.buyer_network_contact_history_gate import review

SCHEMA="empire.permit_data.national_outreach_execution_readonly_preflight.v1"
HARD_STOP_STATES=frozenset({
    "DO_NOT_PURSUE","DELIVERY_HOLD",
    "EXISTING_CONVERSATION_PARTIAL_BOUNCE",
})
HISTORY_REVIEW_STATES=frozenset({
    "ALREADY_CONTACTED","WORKSPACE_SENT_ALREADY_CONTACTED",
    "FOUNDER_FORM_SUBMITTED","EXISTING_CONVERSATION",
    "FOUNDER_REVIEWED_PRIOR_GMAIL_THREAD",
})
NO_FIRST_INTRO=frozenset(HARD_STOP_STATES|HISTORY_REVIEW_STATES)
MAX_CLOCK_SOURCE_AGE=timedelta(hours=72)
MAX_REGISTRY_AGE=timedelta(hours=24)


def _clock(text:str)->datetime:
    try:
        value=datetime.fromisoformat(text)
    except (ValueError,TypeError) as exc:
        raise ValueError("permit_outreach_preflight_datetime_invalid") from exc
    if value.utcoffset() is None:
        raise ValueError("permit_outreach_preflight_naive_datetime")
    return value.astimezone(timezone.utc)


def _context_readonly(context:Mapping[str,Any],at:datetime)->tuple[str,list[str]]:
    if not isinstance(context,Mapping):
        raise ValueError("permit_original_crm_context_missing")
    holds=[]
    source_state="ORIGINAL_CRM_SNAPSHOT_UNAVAILABLE"
    if context.get("available") is not True:holds.append("ORIGINAL_CRM_HISTORY_SOURCE_UNAVAILABLE")
    if context.get("gmail_snapshot_fresh") is not True:
        holds.append("ORIGINAL_GMAIL_HISTORY_MARKED_STALE")
    if context.get("workspace_source_available") is not True:
        holds.append("ORIGINAL_WORKSPACE_SENT_HISTORY_COVERAGE_UNKNOWN")
    if context.get("founder_review_delivery_source_safe") is not True:
        holds.append("ORIGINAL_OWNER_DELIVERY_EVIDENCE_UNSAFE")
    generated=context.get("registry_generated_at")
    try:
        last=_clock(generated)
        age=at-last
        if age<timedelta(0) or age>MAX_REGISTRY_AGE:
            holds.append("ORIGINAL_CRM_REGISTRY_TIME_TOO_OLD_OR_FUTURE")
        source_state="CRM_REGISTRY_OBSERVED_NEVER_RECIPIENT_CLEARANCE"
    except ValueError:
        holds.append("ORIGINAL_CRM_REGISTRY_TIMESTAMP_NOT_VERIFIABLE")
    return source_state,sorted(set(holds))


def _row_holds(*,candidate:Mapping[str,Any],
               reviewed_history:Mapping[str,Any],
               global_holds:list[str],
               stale_source:bool,
               used:bool)->list[str]:
    holds=list(global_holds)
    if stale_source:holds.append("CONTACT_SOURCE_EVIDENCE_EXCEEDS_72_HOURS")
    if candidate["owner_review_workflow"]!="REVIEW_GENERAL_BUSINESS_ROUTE_NO_SEND":
        holds.append(candidate["owner_review_workflow"])
    email=candidate["published_email_candidate"]
    if email is None:
        holds.append("NO_BUSINESS_RECIPIENT_ADDRESS")
    if reviewed_history.get("history_verified_complete") is not True:
        holds.append("COMPLETE_ORIGINAL_RECIPIENT_HISTORY_NOT_PROVEN")
    if reviewed_history.get("gmail_snapshot_fresh") is not True:
        holds.append("ORIGINAL_RECIPIENT_GMAIL_SNAPSHOT_STALE")
    state=reviewed_history.get("state")
    if state in HARD_STOP_STATES:
        holds.append("CANONICAL_CONTACT_HARD_STOP_OR_BOUNCE")
    elif state in HISTORY_REVIEW_STATES:
        holds.append("KNOWN_PRIOR_CONTACT_REVIEW_EXISTING_RELATIONSHIP")
    else:
        holds.append("CANONICAL_CONTACT_HISTORY_UNKNOWN_NOT_CLEARANCE")
    if reviewed_history.get("confirmed_hard_bounce") is True:
        holds.append("CANONICAL_DELIVERY_HARD_BOUNCE")
    if reviewed_history.get("workspace_sent_metadata_observed") is True:
        holds.append("WORKSPACE_PRIOR_SEND_OBSERVED")
    if used:holds.append("EXISTING_SLOT_ATTEMPT_KEY_REPLAY_HOLD")
    # The original owner has NOT supplied independently attested, current,
    # recipient-specific permission, exact-copy approval or source licences.
    holds.extend([
        "ORIGINAL_EXACT_RECIPIENT_AND_DOMAIN_SUPPRESSION_NOT_CLEARED",
        "RECIPIENT_BUSINESS_ROLE_AND_MAILBOX_DELIVERY_NOT_VERIFIED",
        "APPLICABLE_MARKETING_COMPLIANCE_NOT_ATTESTED",
        "EXACT_VALUE_FIRST_COPY_AND_FOUNDER_SEND_NOT_APPROVED",
        "PERMIT_SOURCE_CUSTOMER_DISTRIBUTION_RIGHTS_NOT_CLEARED",
        "ORIGINAL_PROVIDER_SEND_RECEIPT_AND_ATOMIC_LOCK_NOT_AVAILABLE",
    ])
    return sorted(set(holds))


def _slot_key(candidate:Mapping[str,Any],lane:Mapping[str,Any],date:str)->str:
    # An exact-address change changes the slot key, but the future original
    # CRM domain suppression must still prevent duplicate company first touch.
    return digest({
        "namespace":"ONE_EMPIREOS_PERMIT_LOCAL_OUTREACH_ATTEMPT_V1",
        "company_id":candidate["company_id"],
        "recipient_business_email":candidate["published_email_candidate"],
        "region":lane["lane_id"],
        "local_business_date":date,
        "scheduled_local_hour":"08:00",
    })


def build_preflight(*,clock:Mapping[str,Any],
                    crm_context:Mapping[str,Any],
                    at:datetime,
                    previous_attempt_keys:list[str]|None=None,
                    canonical_exact_review:Mapping[str,Any]|None=None)->dict:
    validate_clock(clock)
    if not isinstance(at,datetime) or at.utcoffset() is None:
        raise ValueError("permit_outreach_preflight_aware_clock_required")
    now=at.astimezone(timezone.utc)
    source_time=_clock(clock["evaluated_at_utc"])
    if now<source_time or now-source_time>timedelta(days=30):
        raise ValueError("clock_source_expired_or_future_no_original_custody")
    if previous_attempt_keys is None:previous_attempt_keys=[]
    if (not isinstance(previous_attempt_keys,list)
        or len(previous_attempt_keys)>100000
        or any(not isinstance(k,str) or
               len(k)!=64 or any(c not in "0123456789abcdef" for c in k)
               for k in previous_attempt_keys)
        or len(set(previous_attempt_keys))!=len(previous_attempt_keys)):
        raise ValueError("untrusted_duplicate_slot_ledger_keys")
    previously_seen=set(previous_attempt_keys)
    canonical={}
    if canonical_exact_review is not None:
        # Lazy import avoids cyclic dependency with the canonical reader's
        # original CRM contact-history policy constants.
        from empire_os.permit_national_exact_recipient_canonical_review import validate_exact_review
        validate_exact_review(canonical_exact_review)
        exact_reviewed=_clock(canonical_exact_review["reviewed_at_utc"])
        if (canonical_exact_review["source_weekday_clock_sha256"]!=clock["weekday_outreach_clock_sha256"]
            or exact_reviewed>now or now-exact_reviewed>timedelta(hours=72)):
            raise ValueError("original_exact_recipient_review_wrong_clock_or_expired")
        canonical={
            item["candidate_business_email"]:item
            for item in canonical_exact_review["recipients"]
        }
        expected={row["published_email_candidate"] for lane in clock["regional_clocks"]
                  for row in lane["region_research_queue"] if row["published_email_candidate"]}
        if len(canonical)!=64 or set(canonical)!=expected:
            raise ValueError("original_exact_recipient_reconciliation_does_not_match_64")
    state,global_holds=_context_readonly(crm_context,now)
    age=now-source_time
    stale_source=age>MAX_CLOCK_SOURCE_AGE
    rows=[];seen_keys=set();status=Counter()
    markets=Counter();lane_stats=[]
    for lane,expected in zip(clock["regional_clocks"],LANES):
        if lane["lane_id"]!=expected[0]:
            raise ValueError("preflight_outreach_market_mismatch")
        local_date=now.astimezone(timezone.utc).astimezone(
            __import__("zoneinfo").ZoneInfo(lane["tz_name"])).date().isoformat()
        due=due_at(when=now,tz_name=lane["tz_name"])
        lane_count=0;lane_general=0
        for candidate in lane["region_research_queue"]:
            address=candidate["published_email_candidate"]
            domain=(address.rsplit("@",1)[1] if address else "")
            history=review(domain,crm_context) if domain else {
                "state":"NO_BUSINESS_EMAIL","history_verified_complete":False,
                "gmail_snapshot_fresh":False,"outbound_authorized":False,
                "confirmed_hard_bounce":False,
            }
            if history.get("outbound_authorized") is not False:
                raise ValueError("original_contact_review_not_readonly")
            key=_slot_key(candidate,lane,local_date)
            if key in seen_keys:
                raise ValueError("same_slot_recipient_key_appears_multiple_times")
            seen_keys.add(key)
            used=key in previously_seen
            holds=_row_holds(candidate=candidate,reviewed_history=history,
                             global_holds=global_holds,stale_source=stale_source,
                             used=used)
            if not due:
                holds.append("NOT_CURRENTLY_DESTINATION_LOCAL_WEEKDAY_0800_MINUTE")
            exact_row=canonical.get(address) if address else None
            exact_hit=exact_row is not None and exact_row["canonical_suppression_positive_hit"] is True
            exact_prior=exact_row is not None and (
                (exact_row["canonical_prior_intents"] or 0)>0 or
                (exact_row.get("canonical_prior_domain_intents") or 0)>0 or
                (exact_row["canonical_send_or_reply_event_count"] or 0)>0)
            if exact_row is not None:
                holds.append("ORIGINAL_CANONICAL_EXACT_RECIPIENT_READ_IS_NOT_SEND_CLEARANCE")
            if exact_hit:
                holds.append("ORIGINAL_CANONICAL_EMAIL_SUPPRESSION_POSITIVE_HIT")
            if exact_prior:
                holds.append("ORIGINAL_CANONICAL_PRIOR_INTENT_OR_EVENT_POSITIVE_HIT")
            holds=sorted(set(holds))
            if exact_hit or history.get("state") in HARD_STOP_STATES:
                cls="CANONICAL_HARD_STOP"
            elif exact_prior or history.get("state") in HISTORY_REVIEW_STATES:
                cls="PREVIOUS_CONTACT_NEEDS_OWNER_REVIEW"
            elif candidate["owner_review_workflow"]!="REVIEW_GENERAL_BUSINESS_ROUTE_NO_SEND":
                cls="SOURCE_OR_CONTACT_PURPOSE_HOLD"
            elif used:
                cls="REPLAY_ATTEMPT_HELD"
            else:
                cls="UNVERIFIED_GENERAL_BUSINESS_REVIEW"
            rows.append({
                "company_id":candidate["company_id"],
                "market_id":candidate["market_id"],
                "business_name":candidate["company"],
                "published_business_email_candidate":address,
                "region":lane["lane_id"],
                "timezone":lane["tz_name"],
                "recipient_local_date":local_date,
                "time_slot_id_sha256":key,
                "prior_attempt_key_observed":used,
                "due_for_review_minute":due,
                "original_domain_history_state":history.get("state"),
                "original_history_complete":history.get("history_verified_complete") is True,
                "exact_canonical_evidence_matched":exact_row is not None,
                "exact_canonical_suppression_positive_hit":exact_hit,
                "exact_canonical_prior_contact_positive_hit":exact_prior,
                "first_touch_classification":cls,
                "blocking_reasons":holds,
                "original_crm_recipient_suppression_cleared":False,
                "confirmed_buyer_signal":False,
                "exact_recipient_and_copy_authorized":False,
                "automatic_sending_enabled":False,
                "email_sent":False,
                "verified_revenue_usd":"0.00",
            })
            status[cls]+=1;markets[candidate["market_id"]]+=1;lane_count+=1
            lane_general+=cls=="UNVERIFIED_GENERAL_BUSINESS_REVIEW"
        lane_stats.append({
            "region":lane["lane_id"],
            "iana_timezone":lane["tz_name"],
            "destination_local_business_date":local_date,
            "local_0800_review_due_now":due,
            "companies":lane_count,
            "general_business_workflow_candidates":lane_general,
            "recipients_cleared":0,"outbound_sent":0,
        })
    if len(rows)!=70 or len(seen_keys)!=70:
        raise ValueError("original_seventy_company_schedule_not_reconciled")
    report={
        "schema_version":SCHEMA,
        "reviewed_at_utc":now.isoformat(),
        "source_clock_sha256":clock["weekday_outreach_clock_sha256"],
        "original_exact_recipient_review_sha256":(
            canonical_exact_review["exact_recipient_review_sha256"]
            if canonical_exact_review is not None else None),
        "original_exact_recipient_evidence_bound_count":sum(
            x["exact_canonical_evidence_matched"] for x in rows),
        "original_exact_canonical_suppression_hit_count":sum(
            x["exact_canonical_suppression_positive_hit"] for x in rows),
        "original_exact_canonical_prior_contact_count":sum(
            x["exact_canonical_prior_contact_positive_hit"] for x in rows),
        "original_stack":"ONE_EMPIREOS_PERMIT_ONE_SMART_CRM",
        "crm_registry_read_state":state,
        "original_crm_snapshot_flag_fresh":crm_context.get("gmail_snapshot_fresh") is True,
        "original_crm_registry_generated_at":crm_context.get("registry_generated_at"),
        "original_crm_global_holds":global_holds,
        "clock_source_evidence_older_than_72h":stale_source,
        "previous_attempt_keys_evaluated":len(previously_seen),
        "attempt_key_replay_matches":sum(x["prior_attempt_key_observed"] for x in rows),
        "companies_reviewed":len(rows),
        "business_email_candidates":sum(x["published_business_email_candidate"] is not None for x in rows),
        "original_source_market_count":len(markets),
        "history_states":dict(sorted(Counter(x["original_domain_history_state"] for x in rows).items())),
        "first_touch_classes":dict(sorted(status.items())),
        "lane_reviews":lane_stats,
        "outbound_ready_recipients":0,
        "outbound_attempts_reserved":0,
        "new_prospect_emails_sent":0,
        "bounces_recovered":0,
        "replies_observed":0,
        "empiredb_writes":0,"smart_crm_writes":0,
        "verified_revenue_usd":"0.00",
        "execution_authority":"none",
        "recipients":rows,
    }
    report["execution_preflight_sha256"]=digest(report)
    return report


def validate_preflight(report:Mapping[str,Any])->None:
    if (not isinstance(report,Mapping)
        or report.get("schema_version")!=SCHEMA
        or report.get("execution_preflight_sha256")!=digest({
            k:v for k,v in report.items() if k!="execution_preflight_sha256"})
        or report.get("original_stack")!="ONE_EMPIREOS_PERMIT_ONE_SMART_CRM"
        or report.get("companies_reviewed")!=70
        or report.get("business_email_candidates")!=64
        or report.get("original_source_market_count")!=6
        or report.get("outbound_ready_recipients")!=0
        or report.get("outbound_attempts_reserved")!=0
        or report.get("new_prospect_emails_sent")!=0
        or report.get("bounces_recovered")!=0
        or report.get("replies_observed")!=0
        or report.get("empiredb_writes")!=0
        or report.get("smart_crm_writes")!=0
        or report.get("verified_revenue_usd")!="0.00"
        or report.get("execution_authority")!="none"):
        raise ValueError("permit_execution_preflight_false_send_claim")
    rows=report.get("recipients")
    if not isinstance(rows,list) or len(rows)!=70 or len({
        x.get("time_slot_id_sha256") for x in rows})!=70:
        raise ValueError("preflight_recipient_slot_key_collision_or_missing")
    classes=Counter()
    states=Counter()
    for row in rows:
        holds=row.get("blocking_reasons")
        if (not isinstance(holds,list) or not holds or holds!=sorted(set(holds))
            or type(row.get("exact_canonical_evidence_matched")) is not bool
            or type(row.get("exact_canonical_suppression_positive_hit")) is not bool
            or type(row.get("exact_canonical_prior_contact_positive_hit")) is not bool
            or row.get("original_crm_recipient_suppression_cleared") is not False
            or row.get("confirmed_buyer_signal") is not False
            or row.get("exact_recipient_and_copy_authorized") is not False
            or row.get("automatic_sending_enabled") is not False
            or row.get("email_sent") is not False
            or row.get("verified_revenue_usd")!="0.00"
            or "ORIGINAL_EXACT_RECIPIENT_AND_DOMAIN_SUPPRESSION_NOT_CLEARED" not in holds
            or "EXACT_VALUE_FIRST_COPY_AND_FOUNDER_SEND_NOT_APPROVED" not in holds
            or "ORIGINAL_PROVIDER_SEND_RECEIPT_AND_ATOMIC_LOCK_NOT_AVAILABLE" not in holds):
            raise ValueError("preflight_outreach_authority_or_hold_tampered")
        classes[row["first_touch_classification"]]+=1
        states[row["original_domain_history_state"]]+=1
    if (report.get("first_touch_classes")!=dict(sorted(classes.items()))
        or report.get("history_states")!=dict(sorted(states.items()))
        or report.get("original_exact_recipient_evidence_bound_count")!=sum(
            x.get("exact_canonical_evidence_matched") is True for x in rows)
        or report.get("original_exact_canonical_suppression_hit_count")!=sum(
            x.get("exact_canonical_suppression_positive_hit") is True for x in rows)
        or report.get("original_exact_canonical_prior_contact_count")!=sum(
            x.get("exact_canonical_prior_contact_positive_hit") is True for x in rows)
        or (report.get("original_exact_recipient_review_sha256") is None
            and report.get("original_exact_recipient_evidence_bound_count")!=0)
        or (report.get("original_exact_recipient_review_sha256") is not None
            and report.get("original_exact_recipient_evidence_bound_count")!=64)
        or any(x.get("exact_canonical_suppression_positive_hit") is True and
               ("ORIGINAL_CANONICAL_EMAIL_SUPPRESSION_POSITIVE_HIT" not in x.get("blocking_reasons",[])
                or x.get("first_touch_classification")!="CANONICAL_HARD_STOP")
               for x in rows)
        or any(x.get("exact_canonical_prior_contact_positive_hit") is True and
               "ORIGINAL_CANONICAL_PRIOR_INTENT_OR_EVENT_POSITIVE_HIT" not in x.get("blocking_reasons",[])
               for x in rows)
        or report.get("attempt_key_replay_matches")!=sum(
            x["prior_attempt_key_observed"] is True for x in rows)
        or sum(x["published_business_email_candidate"] is not None for x in rows)!=64
        or report.get("original_crm_global_holds")!=sorted(set(
            report.get("original_crm_global_holds",[])))):
        raise ValueError("preflight_crm_history_or_slot_metrics_forged")
