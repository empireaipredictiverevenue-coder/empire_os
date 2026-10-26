"""Existing EmpireOS Permit workflow: preflight an exact ten-draft repair.

Preview only. Never calls drafts.update, drafts.send, messages.send, or writes
the pinned manifest. The original Google Workspace OAuth requires an explicit
gmail.compose grant before any full MIME header/body repair is possible.

This code must not be used to grant contact permission, founder approval,
source rights, marketing eligibility, or canonical STOP suppression.
"""
from __future__ import annotations

from datetime import datetime,timezone
from email.message import EmailMessage
from hashlib import sha256
from pathlib import Path
import base64,json
from typing import Any,Callable

from empire_os.business_contact_identity import POSTAL_ADDRESS
from empire_os.google_workspace_mailbox import GoogleWorkspaceMailboxProvider,TOKEN_PATH
from empire_os.permit_compliance_private_sources import (
    read_workbench,read_connector_observation,PRIVATE,
)
from empire_os.permit_outreach_compliance_agent import parse_body
from empire_os.permit_workspace_draft_compliance_observer import (
    _one,_headers,_body_text,refresh_pinned,
)
from empire_os.permit_national_buyer_pilot_readiness import (
    build,validate_review,
)
WORKBENCH=PRIVATE/"private_national_value_first"/"value-first-6b337f9964b9c214bc6d8826.json"
PINNED=PRIVATE/"private_national_workspace_draft_observations"/"workspace-drafts-observation-20261025.json"

ROOT=Path("/srv/empire_os")
EDIT_SCOPE="https://www.googleapis.com/auth/gmail.compose"
MODIFY_SCOPE="https://www.googleapis.com/auth/gmail.modify"
CANONICAL_REPLY_TO="reply@mail.empire-ai.co.uk"
STOP_INSTRUCTION="To opt out of future marketing emails, please reply STOP."
SENDER="phil@mail.empire-ai.co.uk"


def oauth_edit_granted(token_path:Path=TOKEN_PATH)->bool:
    # Scope check is metadata only; no tokens/secrets are returned or logged.
    try:
        data=json.loads(token_path.read_text(encoding="utf-8"))
        scopes=set(data.get("scopes") or [])
        return EDIT_SCOPE in scopes or MODIFY_SCOPE in scopes
    except (OSError,ValueError,TypeError):
        return False


def prepare_one(response:dict,pinned:dict)->dict:
    from email.utils import getaddresses
    row=_one(response=response,pinned=pinned)
    payload=response["message"]["payload"]
    headers=_headers(payload)
    if payload.get("mimeType")!="text/plain" or payload.get("parts"):
        raise ValueError("PERMIT_REPAIR_REQUIRES_PLAIN_TEXT_DRAFT")
    from_email=[x.casefold() for _,x in getaddresses([headers.get("from","")])]
    to_emails=[x.casefold() for _,x in getaddresses([headers.get("to","")])]
    if from_email!=[SENDER] or to_emails!=[pinned["recipient"]]:
        raise ValueError("PERMIT_REPAIR_IDENTITY_CHANGED")
    if headers.get("reply-to") not in (None,"",CANONICAL_REPLY_TO):
        raise ValueError("PERMIT_REPAIR_UNEXPECTED_EXISTING_REPLY_ROUTE")
    source=_body_text(payload)
    original=parse_body(
        subject=pinned["subject"],body=source,
        from_address=SENDER,recipient=pinned["recipient"])
    flags=original["static_flags"]
    if (flags["permit_work_is_guaranteed_or_misleading_claim"]
        or flags["possibly_embedded_credential"]
        or flags["syntactic_postal_footer_present"]
        or flags["optout_instruction_text_present"]):
        raise ValueError("PERMIT_REPAIR_REQUIRES_HUMAN_COPY_CONFLICT_REVIEW")
    patched=source.rstrip()+"\n\nPostal address: "+POSTAL_ADDRESS+"\n"+STOP_INSTRUCTION+"\n"
    revised=parse_body(subject=pinned["subject"],body=patched,
                       from_address=SENDER,recipient=pinned["recipient"])
    revised_flags=revised["static_flags"]
    if (not revised_flags["canonical_founder_postal_footer_present"]
        or not revised_flags["syntactic_postal_footer_present"]
        or not revised_flags["optout_instruction_text_present"]
        or revised_flags["permit_work_is_guaranteed_or_misleading_claim"]
        or revised_flags["possibly_embedded_credential"]):
        raise ValueError("PERMIT_REPAIR_CANDIDATE_FAILED_COMPLIANCE_SCAN")
    message=EmailMessage()
    message["From"]=SENDER
    message["To"]=pinned["recipient"]
    message["Reply-To"]=CANONICAL_REPLY_TO
    message["Subject"]=pinned["subject"]
    message.set_content(patched)
    # Gmail draft update API accepts RFC822 MIME encoded as URL-safe base64.
    mime=message.as_bytes()
    return {
        "draft_id":pinned["draft_id"],
        "old_message_id":pinned["message_id"],
        "old_body_sha256":sha256(source.encode()).hexdigest(),
        "candidate_body_sha256":sha256(patched.encode()).hexdigest(),
        "candidate_mime_sha256":sha256(mime).hexdigest(),
        "candidate_gmail_raw":base64.urlsafe_b64encode(mime).decode(),
        "candidate_text_length":len(patched),
        "reply_to_set":True,
        "canonical_footer_set":True,
        "stop_instruction_set":True,
        "message_sent":False,
        "draft_repin_required_after_provider_update":True,
        "original_pinned_message_id":pinned["message_id"],
        "_recipient_in_memory_only":pinned["recipient"],
    }


def preview(*,root:Path=ROOT,now:datetime|None=None,
            service_factory:Callable[[],Any]|None=None,
            token_path:Path=TOKEN_PATH)->dict:
    root=root.resolve()
    when=now or datetime.now(timezone.utc)
    workbench=read_workbench(root=root,path=root/WORKBENCH)
    pinned=read_connector_observation(
        root=root,path=root/PINNED,now=when,pin_only=True)
    api=(service_factory or GoogleWorkspaceMailboxProvider()._service)()
    copy_context={r["public_general_business_email_candidate"]:{
        "company":r["company"],"market":r["market_id"]}
        for r in workbench["owner_review_drafts"]}
    live=refresh_pinned(
        pinned_observation=pinned,now=when,service_factory=lambda:api,
        copy_context=copy_context)
    pilot=build(workbench=workbench,observation=live,at=when)
    validate_review(pilot)
    proposed=[]
    for current in pinned["drafts"]:
        response=api.users().drafts().get(
            userId="me",id=current["draft_id"],format="full").execute()
        candidate=prepare_one(response,current)
        proposed.append(candidate)
    if len(proposed)!=10 or len({r["draft_id"] for r in proposed})!=10:
        raise ValueError("PERMIT_REPAIR_PINNED_TEN_NOT_VERIFIED")
    edit_allowed=oauth_edit_granted(token_path)
    # No recipient, full raw MIME or private source body is included in result.
    return {
        "schema_version":"empire.permit.original_gmail_ten_draft_repair_preflight.v1",
        "status":("STAGED_ONLY_AWAITING_EXPLICIT_GMAIL_COMPOSE_SCOPE"
                  if not edit_allowed else "READY_FOR_SEPARATELY_REVIEWED_DRAFT_ONLY_UPDATE"),
        "reviewed_at_utc":when.astimezone(timezone.utc).isoformat(),
        "workspace_provider_identity_verified":True,
        "pinned_drafts_current":True,
        "drafts_inspected":len(proposed),
        "draft_repair_candidates_prepared_in_memory":len(proposed),
        "exact_original_recipients_preserved":True,
        "exact_original_subjects_preserved":True,
        "canonical_footer_would_be_added":10,
        "explicit_stop_instruction_would_be_added":10,
        "explicit_reply_to_would_be_added":10,
        "compose_or_modify_scope_granted":edit_allowed,
        "pinned_message_ids_would_need_rebinding":10,
        "gmail_draft_updates_performed":0,
        "messages_sent":0,
        "original_empiredb_writes":0,
        "suppression_pipeline_end_to_end_verified":False,
        "recipient_contact_eligibility_granted":False,
        "founder_exact_copy_approved":False,
        "send_authorized":False,
        "full_draft_bodies_persisted":False,
        "mime_payloads_persisted":False,
        "candidate_hashes":[r["candidate_mime_sha256"] for r in proposed],
    }
