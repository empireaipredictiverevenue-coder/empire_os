"""Bounded actual Workspace Gmail draft inspection for Permit Compliance Agent.

Uses the original configured Workspace Gmail provider identity/profile and
only Gmail drafts().get calls. Pins EXACT ten existing owner-reviewed draft
IDs; no Gmail send/modify/list, no new OAuth client or token, no message bodies
ever returned, printed, or saved. In-memory text is analysed and discarded.
This read-only operation does not imply the broader stored OAuth token lacks
send scope; the operation itself does not invoke any write method.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from email.utils import getaddresses
import re
from typing import Any,Mapping,Callable

from empire_os.permit_multimarket_registry import digest
from empire_os.permit_national_buyer_pilot_readiness import (
    validate_observation,EXPECTED_MAILBOX,LIVE_SOURCE,
)
from empire_os.permit_outreach_compliance_agent import parse_body

ALLOWED_FROM={EXPECTED_MAILBOX,"phil@mail.empire-ai.co.uk"}
MAX_TEXT=20_000
MAX_DEPTH=6


def _headers(payload:dict)->dict:
    raw=payload.get("headers")
    if not isinstance(raw,list) or len(raw)>150:
        raise ValueError("DRAFT_MIME_HEADERS_UNVERIFIED")
    found={}
    for item in raw:
        if not isinstance(item,dict):
            raise ValueError("DRAFT_MIME_HEADER_SHAPE_UNVERIFIED")
        k=str(item.get("name") or "").casefold()
        if k in ("subject","from","to","reply-to"):
            if k in found:
                raise ValueError("DRAFT_DUPLICATE_SECURITY_RELEVANT_HEADER")
            value=item.get("value")
            if not isinstance(value,str) or len(value)>1500:
                raise ValueError("DRAFT_HEADER_TOO_LONG_OR_INVALID")
            found[k]=value
    return found


def _body_text(payload:dict,depth:int=0)->str:
    if depth>MAX_DEPTH or not isinstance(payload,dict):
        raise ValueError("DRAFT_MIME_NESTING_UNVERIFIED")
    if payload.get("filename") or payload.get("body",{}).get("attachmentId"):
        raise ValueError("DRAFT_ATTACHMENT_UNEXPECTED_IN_PILOT")
    parts=payload.get("parts") or []
    if parts:
        if not isinstance(parts,list) or len(parts)>10:
            raise ValueError("DRAFT_MIME_PARTS_UNBOUNDED")
        plain=[_body_text(p,depth+1) for p in parts]
        content="\n".join(filter(None,plain))
        if len(content)>MAX_TEXT:
            raise ValueError("DRAFT_BODY_EXCEEDS_REVIEW_BOUND")
        return content
    if payload.get("mimeType")!="text/plain":
        return ""  # do NOT classify HTML snippets as full compliant text.
    encoded=payload.get("body",{}).get("data")
    if not isinstance(encoded,str) or len(encoded)>50_000:
        raise ValueError("DRAFT_TEXT_BODY_UNAVAILABLE")
    try:
        data=base64.urlsafe_b64decode(encoded+"="*(-len(encoded)%4))
        text=data.decode("utf-8",errors="strict")
    except (UnicodeError,ValueError):
        raise ValueError("DRAFT_TEXT_BODY_ENCODING_INVALID") from None
    if not 15<=len(text)<=MAX_TEXT:
        raise ValueError("DRAFT_PLAIN_BODY_UNEXPECTED_LENGTH")
    return text


def _one(*,response:Mapping[str,Any],pinned:Mapping[str,Any],
         copy_company:str|None=None,copy_market:str|None=None)->dict:
    if (not isinstance(response,Mapping)
        or response.get("id")!=pinned["draft_id"]):
        raise ValueError("WORKSPACE_DRAFT_ID_NOT_SAME_PINNED_OWNER_DRAFT")
    msg=response.get("message")
    if (not isinstance(msg,dict)
        or msg.get("id")!=pinned["message_id"]
        or sorted(msg.get("labelIds") or [])!=["DRAFT"]
        or not isinstance(msg.get("payload"),dict)):
        raise ValueError("WORKSPACE_PINNED_DRAFT_NOT_UNSENT_OR_CHANGED")
    payload=msg["payload"]
    hdr=_headers(payload)
    _,froms=getaddresses([hdr.get("from","")])[0] if getaddresses([hdr.get("from","")]) else ("","")
    tos=[x.casefold() for _,x in getaddresses([hdr.get("to","")])]
    if (len(tos)!=1 or tos[0]!=pinned["recipient"]
        or froms.casefold() not in ALLOWED_FROM
        or hdr.get("subject")!=pinned["subject"]):
        raise ValueError("WORKSPACE_DRAFT_SENDER_RECIPIENT_SUBJECT_CHANGED")
    body=_body_text(payload)
    scan=parse_body(subject=hdr["subject"],body=body,
                    from_address=froms,recipient=tos[0])
    flags=scan["static_flags"]
    existing_quality=None
    if copy_company is not None and copy_market is not None:
        from empire_os.permit_canonical_copywriter_review import check_existing_draft
        existing_quality=check_existing_draft(
            company=copy_company,market=copy_market,
            subject=hdr["subject"],body=body,
        )
    # The presence of unsubscribe text alone never verifies that a STOP
    # reply creates a canonical suppression in the original EmpireDB.
    return {
        **dict(pinned),
        "body_has_postal_address":flags["syntactic_postal_footer_present"],
        "body_has_reply_opt_out_request":flags["optout_instruction_text_present"],
        "body_has_brand_identity":flags["truthful_sender_name_text_present"],
        "body_mentions_no_job_list":not flags["permit_work_is_guaranteed_or_misleading_claim"],
        "source_draft_body_sha256":scan["copy_sha256"],
        "potential_commercial_primary_purpose":flags["apparent_commercial_purpose_review_needed"],
        "auto_block_misleading_permit_claim":flags["permit_work_is_guaranteed_or_misleading_claim"],
        "credential_leak_pattern_observed":flags["possibly_embedded_credential"],
        "canonical_copywriter_qa":existing_quality,
    }


def refresh_pinned(*,pinned_observation:Mapping[str,Any],
                   now:datetime,service_factory:Callable[[],Any]|None=None,
                   copy_context:Mapping[str,Mapping[str,str]]|None=None)->dict:
    # The local 0600 observation is an exact ten-ID locator manifest, not a
    # claim that its originally observed body flags are still current.
    # Permit a short bounded review cohort to be re-read live every cycle.
    # At 30 days require fresh owner review/re-pinning.
    from empire_os.permit_national_buyer_pilot_readiness import _aware
    anchor=_aware(pinned_observation.get("observed_at_utc"))
    validate_observation(pinned_observation,anchor)
    if now.utcoffset() is None or (now-anchor)>timedelta(days=30) or now<anchor:
        raise ValueError("PINNED_WORKSPACE_DRAFT_REVIEW_COHORT_EXPIRED")
    if service_factory is None:
        from empire_os.google_workspace_mailbox import GoogleWorkspaceMailboxProvider
        service_factory=GoogleWorkspaceMailboxProvider()._service
    try:
        api=service_factory()  # existing Workspace profile checked by provider
    except Exception:
        raise ValueError("WORKSPACE_PROVIDER_READONLY_DRAFT_SERVICE_UNAVAILABLE") from None
    recipients={r["recipient"] for r in pinned_observation["drafts"]}
    if copy_context is not None and set(copy_context)!=recipients:
        raise ValueError("WORKSPACE_PINNED_DRAFT_CANONICAL_COPY_CONTEXT_MISMATCH")
    rows=[]
    # No body leaves this function; only fingerprints + flags.
    for pinned in pinned_observation["drafts"]:
        try:
            msg=api.users().drafts().get(
                userId="me",id=pinned["draft_id"],format="full",
            ).execute()
            context=copy_context.get(pinned["recipient"]) if copy_context is not None else None
            observed=_one(response=msg,pinned=pinned,
                          copy_company=context["company"] if context else None,
                          copy_market=context["market"] if context else None)
        except ValueError:
            raise
        except Exception:
            raise ValueError("WORKSPACE_PINNED_DRAFT_READ_UNAVAILABLE") from None
        rows.append(observed)
    result=deepcopy(dict(pinned_observation))
    result["drafts"]=rows
    result["observed_at_utc"]=now.astimezone(timezone.utc).isoformat()
    result["source"]=LIVE_SOURCE
    result["source_provider_runtime"]="ORIGINAL_EMPIREOS_WORKSPACE_GMAIL_PINNED_READ_API"
    result["full_body_inspected_in_memory_only"]=True
    result["outbound_automation_authority"]=False
    result["observation_sha256"]=digest({
        k:v for k,v in result.items() if k!="observation_sha256"})
    validate_observation(result,now)
    return result
