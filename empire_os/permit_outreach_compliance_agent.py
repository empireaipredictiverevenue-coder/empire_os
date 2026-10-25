"""Automated, conservative outreach compliance checks for ONE EmpireOS.

Runs as a rule-based agent inside the existing Permit Intelligence owner
review pipeline, prior to ANY possible send handoff. Not a lawyer or consent
source: syntactic checks do not establish regulatory compliance or marketing
permission. No DB, mail API, SMTP, credentials, new timers, or AI-to-send path.

Sources: US FTC CAN-SPAM B2B email guidance, UK ICO B2B/PECR guidance.
Rules are versioned and fail closed. This is review intelligence only.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime,timezone
from typing import Any,Mapping
import re

from empire_os.permit_multimarket_registry import digest

SCHEMA="empire.permit_intelligence.original_outreach_compliance_agent.v1"
POLICY="US_B2B_POTENTIALLY_COMMERCIAL_CAN_SPAM_REVIEW_V1"
FTC="https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business"
ICO="https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/business-to-business-marketing/"
ALLOWED_JURISDICTIONS={"US"}
EMAIL=re.compile(r"^[a-z0-9][a-z0-9._%+-]{0,63}@[a-z0-9-]+(?:\.[a-z0-9-]+)+$")
# String recognition is not evidence that the named premises exist or that
# Empire AI has authority to use their address as its business contact.
POSTAL_SYNTAX=re.compile(
    r"(?im)(?:^|\n)\s*(?:business (?:postal )?address|postal address|"
    r"address)\s*:\s*[^\n]{10,180}\b(?:[A-Z]{2}\s+\d{5}(?:-\d{4})?|"
    r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\s*$"
)
OPT_OUT_TEXT=re.compile(
    r"(?i)\b(?:unsubscribe|opt[ -]?out|stop (?:contacting|emailing)|"
    r"please (?:reply|email) (?:with )?stop|don't contact)\b"
)
CREDENTIAL_TOKENS=re.compile(r"(?i)(?:api[_-]?key|secret|refresh[_-]?token)\s*[:=]")
MISLEADING_PROMISE=re.compile(
    r"(?i)\b(?:guaranteed (?:jobs|leads|contracts|wins)|"
    r"confirmed (?:available|unawarded) (?:jobs|contracts)|"
    r"your (?:approved|issued) permit (?:is|has)|"
    r"ready[- ]to[- ]bid contracts?)\b"
)
KNOWN_MARKETING_KEYWORDS=re.compile(
    r"(?i)\b(?:services?\b|leads?\b|business opportunities?\b|"
    r"contracts?\b|pilot\b|subscription\b|"
    r"introduce (?:our|my)\b|we can help\b)"
)
SEVERITY={"AUTO_BLOCK","OWNER_EVIDENCE_REQUIRED","COPY_REVIEW"}
PROOF_FIELDS=(
    "sender_legal_identity_attested",
    "sender_physical_postal_address_attested",
    "sender_reply_to_verified",
    "functional_optout_channel_attested",
    "stop_processing_and_suppression_attested",
    "canonical_suppression_full_visibility_current",
    "original_crm_history_complete_for_recipient",
    "contact_source_purpose_and_rights_approved",
    "recipient_marketing_eligibility_reviewed",
    "founder_exact_copy_approved",
)


def parse_body(*,subject:str,body:str,from_address:str,recipient:str)->dict:
    """Automatic copy inspection; never interprets matched text as proof."""
    if (not isinstance(subject,str) or not 3<=len(subject)<=200
        or not isinstance(body,str) or not 15<=len(body)<=20_000
        or not isinstance(from_address,str) or not isinstance(recipient,str)
        or not EMAIL.fullmatch(from_address.casefold())
        or not EMAIL.fullmatch(recipient.casefold())):
        raise ValueError("OUTREACH_DRAFT_BODY_FIELDS_UNVERIFIED")
    postal_match=POSTAL_SYNTAX.search(body)
    flags={
        "syntactic_postal_footer_present":postal_match is not None,
        "optout_instruction_text_present":OPT_OUT_TEXT.search(body) is not None,
        "truthful_sender_name_text_present":"Empire AI" in body,
        "apparent_commercial_purpose_review_needed":(
            KNOWN_MARKETING_KEYWORDS.search(subject+" "+body) is not None),
        "permit_work_is_guaranteed_or_misleading_claim":(
            MISLEADING_PROMISE.search(subject+" "+body) is not None),
        "possibly_embedded_credential":CREDENTIAL_TOKENS.search(body) is not None,
        "subject_may_need_human_purpose_review":True,
    }
    return {
        "schema_version":"empire.permit_intelligence.draft_static_text_scan.v1",
        "copy_sha256":digest({"subject":subject,"body":body}),
        "sender_sha256":digest({"email":from_address.casefold()}),
        "recipient_sha256":digest({"email":recipient.casefold()}),
        "static_flags":flags,
        "postal_address_truth_verified":False,
        "unsubscription_processing_verified":False,
        "send_authorized":False,
    }


def audit_one(*,draft:Mapping[str,Any],jurisdiction:str="US",
              owner_evidence:Mapping[str,Any]|None=None)->dict:
    """Audits existing verified draft *observations*, not self-reported grants.

    No input values are permitted to promote a recipient to send ready. We
    show missing proof even where a drafted body seems syntactically complete.
    """
    if jurisdiction not in ALLOWED_JURISDICTIONS:
        raise ValueError("UNREVIEWED_OUTREACH_JURISDICTION")
    if (not isinstance(draft,Mapping)
        or draft.get("draft_state")!="GMAIL_DRAFT_CONFIRMED_UNSENT"
        or draft.get("send_enabled") is not False
        or draft.get("manual_approved_to_send") is not False
        or draft.get("message_sent") is not False
        or draft.get("actual_buyer_interest_verified") is not False
        or not isinstance(draft.get("recipient"),str)
        or not EMAIL.fullmatch(draft["recipient"])
        or not isinstance(draft.get("draft_id"),str)):
        raise ValueError("UNVERIFIED_OR_ALREADY_SENT_OUTREACH_DRAFT")
    # Evidence of a filled checkbox is not operator-signed permission; only
    # independent source attestations can ever satisfy these gates.
    if owner_evidence is not None and (
        not isinstance(owner_evidence,Mapping)
        or any(owner_evidence.get(field) is True for field in PROOF_FIELDS)
    ):
        raise ValueError("UNTRUSTED_OWNER_ATTESTATION_ATTEMPT")
    found=set(draft.get("commercial_hold_reasons",[]))
    if not isinstance(draft.get("commercial_hold_reasons"),list):
        raise ValueError("ORIGINAL_COMPLIANCE_HOLDS_UNTRUSTED")
    reasons={
        "POSTAL_ADDRESS_NOT_VERIFIED":(
            "ACTUAL_GMAIL_DRAFT_BODY_POSTAL_ADDRESS_ABSENT" in found
            or draft.get("verified_business_postal_address") is not True
        ),
        "SENDER_IDENTITY_AND_REPLYTO_NOT_ATTESTED":True,
        "SUBJECT_AND_COMMERCIAL_PRIMARY_PURPOSE_NEED_REVIEW":True,
        "AD_DISCLOSURE_AS_REQUIRED_NOT_REVIEWED":True,
        "OPT_OUT_PATH_AND_STOP_SLA_NOT_PROVEN":True,
        "EXACT_AND_DOMAIN_SUPPRESSION_SEND_TIME_GATE_NOT_PROVEN":True,
        "COMPLETE_CONTACT_HISTORY_NOT_PROVEN":True,
        "CONTACT_RIGHTS_SUBSCRIBER_AND_SOURCE_PURPOSE_NOT_APPROVED":True,
        "EXACT_COPY_FOUNDER_APPROVAL_NOT_PRESENT":True,
    }
    if "ORIGINAL_CANONICAL_COPYWRITER_NEEDS_REVIEW" in found:
        reasons["COPYWRITER_ORIGINAL_QUALITY_REVIEW_REQUIRED"]=True
    if draft.get("original_canonical_copywriter_quality") is None:
        reasons["CANONICAL_COPYWRITER_LIVE_QUALITY_NOT_OBSERVED"]=True
    if "ACTUAL_GMAIL_DRAFT_REPLY_OPTOUT_REQUEST_MISSING" in found:
        reasons["COPY_MISSING_EXPLICIT_OPTOUT_INSTRUCTION"]=True
    if "ACTUAL_GMAIL_DRAFT_IDENTITY_NOT_PRESENT" in found:
        reasons["COPY_MISSING_SENDER_IDENTITY_TEXT"]=True
    if "VERIFY_COPY_DOES_NOT_PROMISE_UNVERIFIED_JOBS" in found:
        reasons["PERMIT_JOB_AVAILABILITY_CLAIMS_REVIEW"]=True
    active=[name for name,value in reasons.items() if value]
    # Suggested remediations are recommendations, not automatic edits or
    # invented personal addresses / unsubscribe links.
    advice=[]
    if reasons["POSTAL_ADDRESS_NOT_VERIFIED"]:
        advice.append("OWNER_PROVIDE_VERIFIED_LAWFUL_BUSINESS_POSTAL_ADDRESS")
    advice.extend((
        "VERIFY_FROM_REPLYTO_AND_COMMERCIAL_SUBJECT_CLASSIFICATION",
        "TEST_OPTOUT_REPLY_INTAKE_STOP_SUPPRESSION_WITH_A_SAFE_INTERNAL_TEST",
        "PERFORM_SEND_TIME_CANONICAL_SUPPRESSION_AND_HISTORIC_CONTACT_CHECK",
        "OWNER_VERIFY_SOURCE_CONTACT_PURPOSE_SUBSCRIBER_TYPE_AND_COPY",
    ))
    if "COPY_MISSING_EXPLICIT_OPTOUT_INSTRUCTION" in reasons:
        advice.insert(1,"ADD_CLEAR_UNSUBSCRIBE_OR_STOP_INSTRUCTION_AFTER_PROVIDER_TEST")
    return {
        "schema_version":SCHEMA,
        "jurisdiction":jurisdiction,"policy":POLICY,
        "recipient_sha256":digest({"email":draft["recipient"]}),
        "draft_id":draft["draft_id"],
        "detected_blocker_codes":active,
        "auto_detected_count":len(active),
        "source_draft_label":"DRAFT",
        "state":"HOLD_NEEDS_OWNER_VERIFICATION",
        "suggested_actions":advice,
        "verified_legal_compliance":False,
        "pre_send_compliance_granted":False,
        "mail_sent":False,
        "source_rights_claimed":False,
    }


def audit_batch(*,pilot_report:Mapping[str,Any],now:datetime)->dict:
    """Callable as part of the *existing* Permit Intelligence review cycle."""
    from empire_os.permit_national_buyer_pilot_readiness import validate_review
    validate_review(pilot_report)
    if not isinstance(now,datetime) or now.utcoffset() is None:
        raise ValueError("OUTREACH_COMPLIANCE_AGENT_CLOCK_REQUIRED")
    reviewed=datetime.fromisoformat(pilot_report["reviewed_at_utc"]).astimezone(timezone.utc)
    when=now.astimezone(timezone.utc)
    if when<reviewed or (when-reviewed).total_seconds()>24*60*60:
        raise ValueError("OUTREACH_COMPLIANCE_AGENT_STALE_PILOT")
    rows=[audit_one(draft=x) for x in pilot_report["owner_review_queue"]]
    counts=Counter(action for row in rows for action in row["detected_blocker_codes"])
    result={
        "schema_version":"empire.permit_intelligence.original_ten_compliance_batch.v1",
        "policy":POLICY,
        "policy_primary_source_ftc":FTC,
        "secondary_uk_guidance_reference":ICO,
        "original_stack":"ONE_EMPIREOS_ONE_EMPIREDB_ONE_SMART_CRM",
        "pilot_report_sha256":pilot_report["pilot_readiness_sha256"],
        "reviewed_at_utc":when.isoformat(),
        "checked_drafts":len(rows),
        "hold_drafts":sum(x["state"]=="HOLD_NEEDS_OWNER_VERIFICATION" for x in rows),
        "blocker_counts":dict(sorted(counts.items())),
        "fully_verified_compliant":0,
        "outbound_authorized":False,
        "emails_sent":0,
        "production_db_writes":0,
        "rows":rows,
    }
    result["report_sha256"]=digest(result)
    return result


def validate_batch(report:Mapping[str,Any])->None:
    if (not isinstance(report,Mapping)
        or report.get("schema_version")!="empire.permit_intelligence.original_ten_compliance_batch.v1"
        or report.get("report_sha256")!=digest({
            k:v for k,v in report.items() if k!="report_sha256"})
        or report.get("checked_drafts")!=10
        or report.get("hold_drafts")!=10
        or report.get("fully_verified_compliant")!=0
        or report.get("outbound_authorized") is not False
        or report.get("emails_sent")!=0
        or report.get("production_db_writes")!=0
        or not isinstance(report.get("rows"),list)
        or len(report["rows"])!=10
        or any(x.get("pre_send_compliance_granted") is not False
               or x.get("verified_legal_compliance") is not False
               or x.get("mail_sent") is not False
               for x in report["rows"])):
        raise ValueError("COMPLIANCE_AGENT_OUTPUT_HAS_FORGED_SEND_AUTHORITY")
