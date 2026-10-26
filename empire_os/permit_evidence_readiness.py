"""Evidence-driven commercial readiness for the ORIGINAL EmpireOS Permit workflow.

An observed draft, an independent proof and a send approval are different
facts. This module advances a review checklist ONLY; it never creates a
canonical intent, sends an email, grants legal compliance or writes a DB.

External claims are accepted only through a verifier callback that checks
their actual source; arbitrary supplied booleans cannot grant readiness.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime,timezone,timedelta
from typing import Any,Callable,Mapping
from empire_os.permit_multimarket_registry import digest

SCHEMA="empire.permit_intelligence.commercial_evidence_readiness.v1"
EXTERNAL_REQUIREMENTS={
    "business_address_rights":"SENDER_IDENTITY_RECORD",
    "sender_legal_identity":"SENDER_IDENTITY_RECORD",
    "reply_alias_delivery":"WORKSPACE_DELIVERY_TEST",
    "stop_suppression_process":"EMPIREDB_SUPPRESSION_TEST",
    "commercial_subject_review":"FOUNDER_COPY_REVIEW",
    "advertising_disclosure_review":"FOUNDER_COPY_REVIEW",
    "complete_contact_history":"EMPIREDB_CONTACT_HISTORY",
    "exact_domain_suppression":"EMPIREDB_SUPPRESSION_READER",
    "contact_source_rights":"PUBLIC_CONTACT_SOURCE_REVIEW",
    "recipient_marketing_eligibility":"PUBLIC_CONTACT_SOURCE_REVIEW",
    "exact_copy_approval":"FOUNDER_COPY_REVIEW",
    "source_specific_copy_quality":"CANONICAL_COPYWRITER_REVIEW",
}
OBSERVATION_REQUIREMENTS=(
    "canonical_postal_footer",
    "explicit_reply_to",
    "stop_instruction",
    "sender_brand",
)
ALL_REQUIREMENTS=(*OBSERVATION_REQUIREMENTS,*EXTERNAL_REQUIREMENTS)
MAX_EVIDENCE_AGE=timedelta(hours=24)


def _observed(draft:Mapping[str,Any])->dict[str,bool]:
    # These flags were produced by the pinned original Gmail draft reader,
    # never a legal, address-ownership or reply-delivery attestation.
    hold=set(draft.get("commercial_hold_reasons") or [])
    return {
        "canonical_postal_footer":(
            draft.get("canonical_business_postal_footer_in_draft") is True
            and "ACTUAL_GMAIL_DRAFT_CANONICAL_FOOTER_MISSING" not in hold
            and "ACTUAL_GMAIL_DRAFT_BODY_POSTAL_ADDRESS_ABSENT" not in hold),
        "explicit_reply_to":(
            draft.get("expected_reply_to_header_in_draft") is True
            and "ACTUAL_GMAIL_DRAFT_EXPLICIT_REPLY_TO_MISSING" not in hold),
        "stop_instruction":(
            draft.get("optout_instruction_in_draft") is True
            and "ACTUAL_GMAIL_DRAFT_REPLY_OPTOUT_REQUEST_MISSING" not in hold),
        "sender_brand":(
            draft.get("sender_brand_in_draft") is True
            and "ACTUAL_GMAIL_DRAFT_IDENTITY_NOT_PRESENT" not in hold),
    }


def review(*,draft:Mapping[str,Any],now:datetime,
           evidence:Mapping[str,Mapping[str,Any]]|None=None,
           verify_source:Callable[[str,Mapping[str,Any]],bool]|None=None)->dict:
    """Return granular evidence progress, NOT mail-send authority.

    The independent source verifier must resolve an actual source record,
    including proof identity and freshness. Source labels or self-attestations
    alone are insufficient.
    """
    if (not isinstance(now,datetime) or now.utcoffset() is None
        or draft.get("draft_state")!="GMAIL_DRAFT_CONFIRMED_UNSENT"
        or draft.get("message_sent") is not False
        or draft.get("send_enabled") is not False):
        raise ValueError("PERMIT_REVIEW_UNTRUSTED_DRAFT_OR_CLOCK")
    if not isinstance(draft.get("recipient"),str) or not draft.get("draft_id"):
        raise ValueError("PERMIT_REVIEW_MISSING_DRAFT_IDENTITY")
    if evidence is not None and not isinstance(evidence,Mapping):
        raise ValueError("PERMIT_REVIEW_EVIDENCE_SHAPE_UNTRUSTED")
    supplied=evidence or {}
    if set(supplied)-set(EXTERNAL_REQUIREMENTS):
        raise ValueError("PERMIT_REVIEW_UNKNOWN_EVIDENCE_CHECK")
    if supplied and verify_source is None:
        raise ValueError("PERMIT_REVIEW_INDEPENDENT_VERIFIER_REQUIRED")

    statuses={k:("OBSERVED" if value else "MISSING")
              for k,value in _observed(draft).items()}
    for check,required_source in EXTERNAL_REQUIREMENTS.items():
        record=supplied.get(check)
        if record is None:
            statuses[check]="MISSING"
            continue
        if not isinstance(record,Mapping):
            raise ValueError("PERMIT_REVIEW_PROOF_SHAPE_UNTRUSTED")
        if (record.get("source_kind")!=required_source
            or record.get("recipient_sha256")!=digest(
                {"email":draft["recipient"].casefold()})
            or record.get("draft_id")!=draft["draft_id"]
            or record.get("message_id")!=draft.get("message_id")
            or not isinstance(record.get("source_ref"),str)
            or not 8<=len(record["source_ref"])<=180
            or record.get("independent_source_verified") is not True):
            raise ValueError("PERMIT_REVIEW_EVIDENCE_IDENTITY_UNVERIFIED")
        try:
            checked=datetime.fromisoformat(record["checked_at_utc"])
        except (TypeError,ValueError,KeyError):
            raise ValueError("PERMIT_REVIEW_PROOF_TIME_UNVERIFIED") from None
        if checked.utcoffset() is None or not (
            timedelta(seconds=-120)<=now-checked<=MAX_EVIDENCE_AGE
        ):
            statuses[check]="STALE"
            continue
        if verify_source is None or verify_source(check,record) is not True:
            raise ValueError("PERMIT_REVIEW_EVIDENCE_SOURCE_NOT_VERIFIED")
        statuses[check]="VERIFIED"
    counts=dict(Counter(statuses.values()))
    unresolved=[name for name,state in statuses.items()
                if state not in ("OBSERVED","VERIFIED")]
    missing_external=[name for name in EXTERNAL_REQUIREMENTS
                      if statuses[name]!="VERIFIED"]
    complete=not unresolved and not missing_external
    return {
        "schema_version":SCHEMA,
        "draft_id":draft["draft_id"],
        "recipient_sha256":digest({"email":draft["recipient"].casefold()}),
        "checks":statuses,
        "counts":counts,
        "observed_format_checks":sum(statuses[x]=="OBSERVED"
                                    for x in OBSERVATION_REQUIREMENTS),
        "independently_verified_checks":sum(
            statuses[x]=="VERIFIED" for x in EXTERNAL_REQUIREMENTS),
        "unresolved_requirements":unresolved,
        "review_state":("EVIDENCE_COMPLETE_FOR_SEPARATE_CANONICAL_PREFLIGHT"
                        if complete else "EVIDENCE_INCOMPLETE"),
        "separate_canonical_governor_required":True,
        "legal_compliance_certified":False,
        "send_authorized":False,
        "mail_sent":False,
    }
