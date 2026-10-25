"""64 exact email candidate reconciliation through the ORIGINAL EmpireDB.

No new CRM/database. Restrict canonical reads to already published PermitOS
candidate business addresses. Global outbound_suppressions/intent/events
positive hits are HOLD evidence; even zero hits are UNKNOWN, never clearance.
Original tenant authority and marketing permissions remain independently held.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime,timezone,timedelta
import re
from typing import Any,Callable,Mapping

from empire_os.permit_multimarket_registry import digest
from empire_os.permit_national_weekday_outreach_clock import validate_clock
from empire_os.buyer_network_contact_history_gate import review
from empire_os.permit_national_outreach_execution_preflight import HARD_STOP_STATES,HISTORY_REVIEW_STATES

SCHEMA="empire.permit_data.national_exact_recipient_canonical_review.v1"
SOURCE="ORIGINAL_EMPIREDB_OUTBOUND_GLOBAL_READ_ONLY"
EMAIL=re.compile(r"^[a-z0-9][a-z0-9._%+-]{0,63}@[a-z0-9-]+(?:\.[a-z0-9-]+)+$")
MAX_EMAILS=64
SQL="""
WITH targets AS (
  SELECT DISTINCT lower(btrim(value)) AS email
  FROM unnest(%s::text[]) AS t(value)
)
SELECT t.email,
  EXISTS (
    SELECT 1 FROM public.outbound_suppressions s
    WHERE s.contact_type = 'email'
      AND lower(btrim(s.normalized_contact)) IN (
        t.email, split_part(t.email,'@',2), '@'||split_part(t.email,'@',2)
      )
  ) AS suppression_hit,
  (SELECT count(*) FROM public.outbound_intents i
    WHERE i.channel='email'
    AND lower(btrim(i.normalized_recipient))=t.email) AS prior_intents,
  (SELECT count(*) FROM public.outbound_events e
    JOIN public.outbound_intents i ON i.id=e.intent_id
    WHERE i.channel='email'
    AND lower(btrim(i.normalized_recipient))=t.email
    AND e.event_type IN ('send_attempt','sent','delivered','reply_received')
  ) AS send_or_reply_events
FROM targets t ORDER BY t.email
"""


def candidate_emails(clock:Mapping[str,Any])->list[str]:
    validate_clock(clock)
    addresses=[]
    for region in clock["regional_clocks"]:
        for company in region["region_research_queue"]:
            email=company["published_email_candidate"]
            if email is None:continue
            if not isinstance(email,str) or not EMAIL.fullmatch(email):
                raise ValueError("original_research_business_candidate_invalid")
            addresses.append(email)
    if len(addresses)!=MAX_EMAILS or len(set(addresses))!=MAX_EMAILS:
        raise ValueError("only_original_64_deduplicated_research_emails")
    return sorted(addresses)


def query_existing_empiredb(*,dsn:str,clock:Mapping[str,Any],
                            connect_factory:Callable[...,Any]|None=None)->dict[str,dict]:
    """Single parameterised, read-only, bounded query via original DB role.

    This generic legacy outbound ledger read does not satisfy restricted
    Revenue CRM tenant-bound suppression *clearance* or Gmail completeness.
    Missing DSN, role permissions or any row fails without partial results.
    """
    emails=candidate_emails(clock)
    if not isinstance(dsn,str) or not dsn.strip():
        raise ValueError("ORIGINAL_EMPIREDB_READ_AUTHORITY_NOT_AVAILABLE")
    if connect_factory is None:
        import psycopg
        connect_factory=psycopg.connect
    try:
        with connect_factory(dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '6000ms'")
                cursor.execute(SQL,(emails,))
                found=cursor.fetchall()
                cursor.execute("ROLLBACK")
    except Exception:
        # Never expose DSN, relation permissions, data, user or SQL details.
        raise ValueError("CANONICAL_EXACT_RECIPIENT_READ_UNAVAILABLE") from None
    if not isinstance(found,list) or len(found)!=MAX_EMAILS:
        raise ValueError("CANONICAL_EXACT_RECIPIENT_BATCH_INCOMPLETE")
    result={}
    for entry in found:
        if not isinstance(entry,(list,tuple)) or len(entry)!=4:
            raise ValueError("CANONICAL_EXACT_RECIPIENT_ROW_SHAPE_INVALID")
        email,suppressed,intents,events=entry
        if (email not in emails or email in result
            or type(suppressed) is not bool or type(intents) is not int
            or type(events) is not int or not 0<=intents<=1_000_000
            or not 0<=events<=1_000_000):
            raise ValueError("CANONICAL_EXACT_RECIPIENT_ROW_INVALID")
        result[email]={
            "canonical_suppression_hit":suppressed,
            "canonical_prior_email_intents":intents,
            "canonical_send_or_reply_events":events,
        }
    if set(result)!=set(emails):
        raise ValueError("CANONICAL_EXACT_RECIPIENT_SET_NOT_COMPLETE")
    return result


def _context_time(context:Mapping[str,Any],at:datetime)->str:
    source=context.get("registry_generated_at")
    try:
        moment=datetime.fromisoformat(source)
        if moment.utcoffset() is None or moment>at or at-moment>timedelta(hours=24):
            return "STALE"
    except (ValueError,TypeError):
        return "UNKNOWN"
    return "OBSERVED_WITHIN_24H_NOT_COMPLETE_HISTORY"


def build_exact_review(*,clock:Mapping[str,Any],
                       context:Mapping[str,Any],
                       at:datetime,
                       canonical_rows:Mapping[str,Mapping[str,Any]]|None=None)->dict:
    validate_clock(clock)
    if not isinstance(at,datetime) or at.utcoffset() is None:
        raise ValueError("exact_reconciliation_aware_clock_required")
    now=at.astimezone(timezone.utc)
    clock_time=datetime.fromisoformat(clock["evaluated_at_utc"]).astimezone(timezone.utc)
    if now<clock_time or now-clock_time>timedelta(days=30):
        raise ValueError("original_outreach_clock_evidence_expired_or_future")
    expected=candidate_emails(clock)
    if canonical_rows is not None:
        if (not isinstance(canonical_rows,Mapping)
            or set(canonical_rows)!=set(expected)):
            raise ValueError("incomplete_or_unrequested_original_empiredb_recipient_evidence")
    if not isinstance(context,Mapping):
        raise ValueError("original_crm_history_context_not_available")
    entries=[]
    for lane in clock["regional_clocks"]:
        for company in lane["region_research_queue"]:
            email=company["published_email_candidate"]
            if email is None:continue
            domain=email.rsplit("@",1)[1]
            state=review(domain,context)
            if state.get("outbound_authorized") is not False:
                raise ValueError("unsafe_existing_contact_history_source")
            if canonical_rows is None:
                item=None
            else:
                item=canonical_rows[email]
                if (not isinstance(item,Mapping)
                    or type(item.get("canonical_suppression_hit")) is not bool
                    or type(item.get("canonical_prior_email_intents")) is not int
                    or (item.get("canonical_send_or_reply_events") is not None
                        and type(item.get("canonical_send_or_reply_events")) is not int)
                    or not 0<=item["canonical_prior_email_intents"]<=1_000_000
                    or (item.get("canonical_send_or_reply_events") is not None
                        and not 0<=item["canonical_send_or_reply_events"]<=1_000_000)):
                    raise ValueError("untrusted_original_canonical_exact_recipient_counts")
            if item is not None and "canonical_prior_domain_intents" in item:
                domain_intents=item["canonical_prior_domain_intents"]
                if (type(domain_intents) is not int
                    or not 0<=domain_intents<=1_000_000
                    or domain_intents<item["canonical_prior_email_intents"]):
                    raise ValueError("untrusted_original_canonical_domain_history_counts")
            else:
                domain_intents=None
            suppressed=item["canonical_suppression_hit"] if item else None
            intents=item["canonical_prior_email_intents"] if item else None
            events=item["canonical_send_or_reply_events"] if item else None
            prior=(item is not None and
                   (intents>0 or (events or 0)>0 or (domain_intents or 0)>0))
            history_state=state.get("state")
            if suppressed is True or history_state in HARD_STOP_STATES:
                result="HOLD_CANONICAL_SUPPRESSION_OR_CONTACT_STOP"
            elif prior or history_state in HISTORY_REVIEW_STATES:
                result="HOLD_PREVIOUS_INTENT_OR_CONVERSATION"
            elif canonical_rows is None:
                result="HOLD_CANONICAL_EXACT_RECIPIENT_READER_NOT_RUN"
            else:
                result="HOLD_NO_POSITIVE_HITS_HISTORY_AND_PERMISSION_STILL_UNKNOWN"
            entries.append({
                "company_id":company["company_id"],
                "company":company["company"],"market_id":company["market_id"],
                "original_region":lane["lane_id"],"recipient_local_zone":lane["tz_name"],
                "candidate_business_email":email,
                "recipient_sha256":digest({"email":email}),
                "original_domain_history_state":history_state,
                "original_gmail_flag_fresh":state.get("gmail_snapshot_fresh") is True,
                "exact_canonical_query_performed":item is not None,
                "canonical_suppression_positive_hit":suppressed,
                "canonical_prior_intents":intents,
                "canonical_prior_domain_intents":domain_intents,
                "canonical_send_or_reply_event_count":events,
                "first_touch_decision":result,
                "real_recipient_delivery_verified":False,
                "complete_history_authoritatively_proven":False,
                "original_crm_send_authority_proven":False,
                "marketing_compliance_attested":False,
                "specific_founder_email_copy_approved":False,
                "send_ready":False,
                "email_sent":False,
            })
    entries.sort(key=lambda e:(e["original_region"],e["market_id"],e["company"]))
    decisions=Counter(x["first_touch_decision"] for x in entries)
    outputs={
        "schema_version":SCHEMA,"reviewed_at_utc":now.isoformat(),
        "source_weekday_clock_sha256":clock["weekday_outreach_clock_sha256"],
        "original_stack":"EMPIREOS_EMPIREDB_ONE_SMART_CRM",
        "original_canonical_ledger":SOURCE,
        "canonical_read_status":(
            "64_EXACT_RECIPIENT_ROWS_QUERIED_HIT_ONLY_NEVER_CLEAR"
            if canonical_rows is not None else
            "NOT_QUERIED_AUTHORISED_READER_ABSENT"),
        "original_crm_gmail_snapshot_flag_fresh":context.get("gmail_snapshot_fresh") is True,
        "original_crm_registry_age_state":_context_time(context,now),
        "research_email_candidates":len(entries),
        "exact_recipient_rows_from_canonical":len(entries) if canonical_rows is not None else 0,
        "canonical_suppression_positive_hits":sum(x["canonical_suppression_positive_hit"] is True for x in entries),
        "canonical_intent_or_event_positive_hits":sum(
            (x["canonical_prior_intents"] or 0)>0 or
            (x["canonical_prior_domain_intents"] or 0)>0 or
            (x["canonical_send_or_reply_event_count"] or 0)>0 for x in entries),
        "canonical_prior_domain_positive_hits":sum(
            (x["canonical_prior_domain_intents"] or 0)>0 for x in entries),
        "domain_history_state_counts":dict(sorted(Counter(x["original_domain_history_state"] for x in entries).items())),
        "recipient_hold_reasons":dict(sorted(decisions.items())),
        "recipient_history_authoritatively_cleared":0,
        "recipients_approved_to_send":0,
        "emails_sent":0,"empiredb_writes":0,"smart_crm_writes":0,
        "verified_revenue_usd":"0.00","execution_authority":"none",
        "recipients":entries,
    }
    outputs["exact_recipient_review_sha256"]=digest(outputs)
    return outputs


def validate_exact_review(report:Mapping[str,Any])->None:
    if (not isinstance(report,Mapping)
        or report.get("schema_version")!=SCHEMA
        or report.get("exact_recipient_review_sha256")!=digest({
            k:v for k,v in report.items() if k!="exact_recipient_review_sha256"})
        or report.get("original_stack")!="EMPIREOS_EMPIREDB_ONE_SMART_CRM"
        or report.get("original_canonical_ledger")!=SOURCE
        or report.get("research_email_candidates")!=64
        or report.get("recipient_history_authoritatively_cleared")!=0
        or report.get("recipients_approved_to_send")!=0
        or report.get("emails_sent")!=0
        or report.get("empiredb_writes")!=0
        or report.get("smart_crm_writes")!=0
        or report.get("verified_revenue_usd")!="0.00"
        or report.get("execution_authority")!="none"):
        raise ValueError("canonical_recipient_reconciliation_illegally_promoted_to_send")
    items=report.get("recipients")
    if not isinstance(items,list) or len(items)!=64:
        raise ValueError("unbounded_or_missing_original_exact_recipients")
    seen=set();states=Counter()
    for item in items:
        email=item.get("candidate_business_email")
        if (not isinstance(email,str) or not EMAIL.fullmatch(email)
            or email in seen
            or item.get("recipient_sha256")!=digest({"email":email})
            or item.get("first_touch_decision") not in (
                "HOLD_CANONICAL_SUPPRESSION_OR_CONTACT_STOP",
                "HOLD_PREVIOUS_INTENT_OR_CONVERSATION",
                "HOLD_CANONICAL_EXACT_RECIPIENT_READER_NOT_RUN",
                "HOLD_NO_POSITIVE_HITS_HISTORY_AND_PERMISSION_STILL_UNKNOWN")
            or item.get("real_recipient_delivery_verified") is not False
            or item.get("complete_history_authoritatively_proven") is not False
            or item.get("original_crm_send_authority_proven") is not False
            or item.get("marketing_compliance_attested") is not False
            or item.get("specific_founder_email_copy_approved") is not False
            or item.get("send_ready") is not False
            or item.get("email_sent") is not False):
            raise ValueError("canonical_read_used_as_false_email_clearance")
        seen.add(email)
        states[item["first_touch_decision"]]+=1
    if (report.get("recipient_hold_reasons")!=dict(sorted(states.items()))
        or report.get("exact_recipient_rows_from_canonical") not in (0,64)
        or report.get("canonical_read_status") not in (
            "NOT_QUERIED_AUTHORISED_READER_ABSENT",
            "64_EXACT_RECIPIENT_ROWS_QUERIED_HIT_ONLY_NEVER_CLEAR")
        or (report["exact_recipient_rows_from_canonical"]==0)!=
            (report["canonical_read_status"]=="NOT_QUERIED_AUTHORISED_READER_ABSENT")
        or report.get("canonical_suppression_positive_hits")!=sum(
            e.get("canonical_suppression_positive_hit") is True for e in items)
        or report.get("canonical_intent_or_event_positive_hits")!=sum(
            (e.get("canonical_prior_intents") or 0)>0 or
            (e.get("canonical_prior_domain_intents") or 0)>0 or
            (e.get("canonical_send_or_reply_event_count") or 0)>0 for e in items)
        or report.get("canonical_prior_domain_positive_hits",0)!=sum(
            (e.get("canonical_prior_domain_intents") or 0)>0 for e in items)):
        raise ValueError("canonical_read_reconciliation_counts_not_consistent")
    if report["exact_recipient_rows_from_canonical"]==0 and any(
        x["exact_canonical_query_performed"] is not False or
        x["canonical_suppression_positive_hit"] is not None or
        x["canonical_prior_intents"] is not None or
        x.get("canonical_prior_domain_intents") is not None or
        x["canonical_send_or_reply_event_count"] is not None
        for x in items):
        raise ValueError("unqueried_canonical_evidence_falsely_populated")
