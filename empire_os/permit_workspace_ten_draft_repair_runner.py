"""Governed draft-only repair of ten existing Permit Workspace Gmail drafts.

Disabled by default. Requires both a newly consented gmail.compose OAuth
scope AND an explicit one-time owner draft-only approval switch. It NEVER
calls any Gmail send action, and is never invoked by the 15-minute timer.

All original ten recipients/subjects/source-workbench must be proven again
before any Gmail update. Partial API failures HOLD and retain original pins
until an operator reconciles the provider IDs. No false atomic Gmail claim.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import fcntl,json,os,re,stat
from typing import Callable,Any

from empire_os.google_workspace_mailbox import (
    GoogleWorkspaceMailboxProvider,TOKEN_PATH,
)
from empire_os.permit_compliance_private_sources import (
    read_workbench,read_connector_observation,
)
from empire_os.permit_multimarket_registry import digest
from empire_os.permit_national_buyer_pilot_readiness import (
    validate_observation,MSG_ID,
)
from empire_os.permit_workspace_draft_compliance_observer import _one
from empire_os.permit_workspace_ten_draft_repair_preflight import (
    ROOT,PINNED,WORKBENCH,prepare_one,oauth_edit_granted,
)
from scripts.run_permit_compliance_cycle_observer import _store_private

PIN_LABEL="DRAFT"
REPAIR_APPROVAL="APPROVE_EXACT_TEN_EXISTING_WORKSPACE_DRAFT_EDITS_NO_SEND"
EDIT_ENV="EMPIRE_PERMIT_OWNER_DRAFT_EDIT"
LOCK="permit_exact_ten_draft_edit.lock"


def _approved_environment(env:dict)->bool:
    return (env.get(EDIT_ENV)=="1"
            and env.get("EMPIRE_MODE")=="OBSERVE"
            and all(env.get(k)=="0" for k in (
                "OUTBOUND_ENABLED","EMPIRE_OUTBOUND_ENABLED","LIVE_OUTBOUND")))


def apply_exact_ten(*,root:Path=ROOT,now:datetime|None=None,
                    token_path:Path=TOKEN_PATH,
                    provider_factory:Callable[[],Any]|None=None,
                    approval:str="",environment:dict|None=None)->dict:
    if approval!=REPAIR_APPROVAL:
        raise ValueError("PERMIT_EXACT_DRAFT_OWNER_APPROVAL_REQUIRED")
    env=os.environ if environment is None else environment
    if not _approved_environment(env):
        raise ValueError("PERMIT_DRAFT_ONLY_RUNTIME_GATES_NOT_APPROVED")
    if not oauth_edit_granted(token_path):
        raise ValueError("PERMIT_GMAIL_COMPOSE_OAUTH_CONSENT_REQUIRED")
    root=root.resolve()
    when=now or datetime.now(timezone.utc)
    if when.utcoffset() is None:
        raise ValueError("PERMIT_DRAFT_REPAIR_CLOCK_UNVERIFIED")
    folder=(root/PINNED).parent
    if (not folder.is_dir() or folder.is_symlink()
        or stat.S_IMODE(folder.stat().st_mode)!=0o700):
        raise ValueError("PERMIT_PRIVATE_PIN_FOLDER_UNTRUSTED")
    lock=folder/LOCK
    fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    updated=0
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        workbench=read_workbench(root=root,path=root/WORKBENCH)
        original=read_connector_observation(
            root=root,path=root/PINNED,now=when,pin_only=True)
        original_file=root/PINNED
        old_raw=original_file.read_bytes()
        receipt_path=original_file.with_name(original_file.stem+".receipt.json")
        old_receipt=receipt_path.read_bytes()
        approved={r["public_general_business_email_candidate"]
                  for r in workbench["owner_review_drafts"]}
        if approved!={r["recipient"] for r in original["drafts"]}:
            raise ValueError("PERMIT_ORIGINAL_WORKBENCH_RECIPIENT_MISMATCH")
        try:
            api=(provider_factory or GoogleWorkspaceMailboxProvider()._service)()
        except Exception:
            raise ValueError("PERMIT_WORKSPACE_PROVIDER_IDENTITY_UNAVAILABLE") from None
        candidates=[]
        # Full read-only set validation BEFORE the FIRST mutation.
        for row in original["drafts"]:
            try:
                current=api.users().drafts().get(
                    userId="me",id=row["draft_id"],format="full").execute()
                candidates.append((row,prepare_one(current,row)))
            except Exception:
                raise ValueError("PERMIT_ORIGINAL_PINNED_DRAFT_PREFLIGHT_FAILED") from None
        if len(candidates)!=10:
            raise ValueError("PERMIT_TEN_EXACT_DRAFTS_NOT_PREPARED")

        # Backup the old private pin and receipt, never the full message bodies.
        marker=sha256(old_raw).hexdigest()[:16]
        bak1=folder/("workspace-drafts.pre-repair-"+marker+".json")
        bak2=folder/("workspace-drafts.pre-repair-"+marker+".receipt.json")
        if any(p.exists() or p.is_symlink() for p in (bak1,bak2)):
            raise ValueError("PERMIT_DRAFT_REPAIR_BACKUP_ALREADY_EXISTS")
        _store_private(bak1,old_raw)
        _store_private(bak2,old_receipt)
        refreshed=[]
        for pin,plan in candidates:
            try:
                # MUST NOT call drafts.send, messages.send, create or delete.
                response=api.users().drafts().update(
                    userId="me",id=pin["draft_id"],
                    body={"id":pin["draft_id"],
                          "message":{"raw":plan["candidate_gmail_raw"]}},
                ).execute()
                updated+=1
                if response.get("id")!=pin["draft_id"]:
                    raise ValueError("DRAFT_ID_CHANGED")
                current=api.users().drafts().get(
                    userId="me",id=pin["draft_id"],format="full").execute()
                new_id=current.get("message",{}).get("id")
                if not isinstance(new_id,str) or not MSG_ID.fullmatch(new_id):
                    raise ValueError("REPLACEMENT_MESSAGE_ID_UNTRUSTED")
                owner_pin={**pin,"message_id":new_id}
                inspected=_one(response=current,pinned=owner_pin)
                if (inspected.get("body_has_canonical_postal_footer") is not True
                    or inspected.get("body_has_reply_opt_out_request") is not True
                    or inspected.get("expected_explicit_reply_to_header_present") is not True
                    or inspected.get("actually_sent") is not False):
                    raise ValueError("NEW_DRAFT_BODY_OR_REPLY_TO_NOT_VERIFIED")
                refreshed.append(inspected)
            except Exception:
                # Not atomic across Gmail. Original pinned cohort remains
                # unchanged and optional 15-minute watcher will fail closed.
                raise ValueError(
                    "PERMIT_GMAIL_DRAFT_REPAIR_PARTIAL_HOLD_RECONCILE_PROVIDER_IDS"
                ) from None
        replacement=deepcopy(original)
        replacement["drafts"]=refreshed
        replacement["observed_at_utc"]=when.astimezone(timezone.utc).isoformat()
        replacement["observation_sha256"]=digest({
            k:v for k,v in replacement.items() if k!="observation_sha256"})
        validate_observation(replacement,when)
        if (original_file.read_bytes()!=old_raw
            or receipt_path.read_bytes()!=old_receipt):
            raise ValueError("PERMIT_PIN_CHANGED_DURING_GMAIL_REPAIR")
        new_raw=(json.dumps(replacement,sort_keys=True,indent=2)+"\n").encode()
        receipt={
            "schema_version":"empire.permit_data.workspace_drafts_local_sha_receipt.v1",
            "observed_data_sha256":sha256(new_raw).hexdigest(),
            "source_observation_sha256":replacement["observation_sha256"],
            "read_only":True,
            "new_messages_sent":False,
            "ten_drafts_repaired_without_sends":True,
        }
        new_receipt=(json.dumps(receipt,sort_keys=True,indent=2)+"\n").encode()
        # Not a cross-file transaction; incomplete pair fails closed in
        # original custody reader and must be reconciled from backup.
        _store_private(original_file,new_raw)
        _store_private(receipt_path,new_receipt)
        read_connector_observation(
            root=root,path=original_file,now=when,pin_only=True)
        return {
            "status":"EXACT_TEN_GMAIL_DRAFTS_REPAIRED_REPINNED_HELD_NO_SEND",
            "draft_updates_verified":10,
            "same_original_draft_ids":True,
            "new_provider_message_ids_custodied":10,
            "private_custody_receipt_verified":True,
            "canonical_suppression_e2e_verified":False,
            "all_recipients_send_held":True,
            "messages_sent":0,
            "source_db_writes":0,
        }
    finally:
        os.close(fd)
