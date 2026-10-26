"""Existing EmpireOS Gmail evidence cycle OPTIONAL Permit compliance observer.

Runs only after the original buyer reconcile succeeds, no second timer/daemon.
Checks exactly ten already-pinned, unsent Workspace Gmail draft messages using
original Workspace OAuth provider, with no Gmail writes and no sender access.
Never turns a draft into approved marketing outreach. If source/provider is
unavailable, emits a HOLD and exits non-zero, without failing the primary
Gmail buyer-evidence cycle. Owner-private and production modes are separate.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json,os,stat
from pathlib import Path
from typing import Callable,Any

from empire_os.permit_national_buyer_pilot_readiness import build,validate_review
from empire_os.permit_outreach_compliance_agent import audit_batch,validate_batch
from empire_os.permit_workflow_skill_bindings import bind_existing_skills,validate_bindings
from empire_os.permit_workspace_draft_compliance_observer import refresh_pinned
from empire_os.permit_workspace_ten_draft_repair_preflight import oauth_edit_granted
from empire_os.permit_workspace_stop_alias_observer import inspect as inspect_workspace_stop_alias
from empire_os.permit_compliance_private_sources import (
    read_workbench,read_connector_observation,PRIVATE,
)

ROOT=Path(__file__).resolve().parents[1]
WORKBENCH=PRIVATE/"private_national_value_first"/"value-first-6b337f9964b9c214bc6d8826.json"
PINNED=PRIVATE/"private_national_workspace_draft_observations"/"workspace-drafts-observation-20261025.json"
OUTPUT=PRIVATE/"private_national_first_buyer_pilot_review"/"permit_compliance_latest.json"
RECEIPT=PRIVATE/"private_national_first_buyer_pilot_review"/"permit_compliance_latest.receipt.json"


def _store_private(path:Path,body:bytes)->None:
    if path.is_symlink() or (path.exists() and (
        not path.is_file() or stat.S_IMODE(path.stat().st_mode)!=0o600)):
        raise ValueError("ORIGINAL_PERMIT_COMPLIANCE_DESTINATION_UNSAFE")
    stage=path.with_name(path.name+".next")
    if stage.exists() or stage.is_symlink():
        raise ValueError("ORIGINAL_PERMIT_COMPLIANCE_STAGE_CONFLICT")
    fd=os.open(stage,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(stage,path)
    finally:
        if stage.exists():
            stage.unlink()


def _runtime_write_permitted(*,root:Path,
                             production_root:Path=Path("/srv/empire_os"),
                             environment:dict|None=None)->bool:
    """Explicit deploy-time OBSERVE consent; never sender authority.

    The existing 15-minute Gmail cycle forces outbound flags to "0".
    An extra production-only enable bit must be provided by the reviewed
    service release owner. It is NOT derived from a user's reply, skill,
    email body, or a passing compliance report.
    """
    if root.resolve()!=production_root.resolve():
        return True  # test / original isolated Permit worktree only
    env=environment if environment is not None else os.environ
    return (
        env.get("EMPIRE_PERMIT_COMPLIANCE_OBSERVER_READONLY")=="1"
        and env.get("EMPIRE_MODE")=="OBSERVE"
        and all(env.get(name)=="0" for name in (
            "OUTBOUND_ENABLED","EMPIRE_OUTBOUND_ENABLED","LIVE_OUTBOUND"))
    )


def _latest(root:Path,summary:dict,*,production_root:Path=Path("/srv/empire_os"),
            environment:dict|None=None)->None:
    root=root.resolve()
    if not _runtime_write_permitted(
        root=root,production_root=production_root,environment=environment):
        raise ValueError("PERMIT_COMPLIANCE_PRODUCTION_RUNTIME_NOT_APPROVED")
    path=root/OUTPUT
    folder=path.parent
    # Every nested runtime directory must be real, not a symlink. This is
    # checked before and after creating the final 0700 output directory.
    parts=(root/"runtime",root/"runtime/permit_intelligence",
           root/"runtime/permit_intelligence/founder_growth_previews",
           folder)
    if any(p.is_symlink() for p in parts):
        raise ValueError("PERMIT_COMPLIANCE_PROTECTED_RUNTIME_SYMLINK")
    if (folder.exists() and (
        not folder.is_dir() or stat.S_IMODE(folder.stat().st_mode)!=0o700)):
        raise ValueError("PERMIT_COMPLIANCE_EXISTING_PRIVATE_FOLDER_UNSAFE")
    folder.mkdir(parents=True,mode=0o700,exist_ok=True)
    if folder.is_symlink() or stat.S_IMODE(folder.stat().st_mode)!=0o700:
        raise ValueError("PERMIT_COMPLIANCE_OUTPUT_FOLDER_UNSAFE")
    if (summary.get("status")!="PASS_HELD_NO_SEND"
        or summary.get("new_send_authorized") is not False
        or summary.get("outbound_sent") is not False
        or summary.get("database_writes") is not False
        or summary.get("smart_crm_writes") is not False
        or summary.get("execution_authority")!="NONE"
        or summary.get("ten_workspace_drafts_inspected")!=10
        or summary.get("drafts_held")!=10
        or summary.get("skillforge_scripts_executed") is not False):
        raise ValueError("PERMIT_COMPLIANCE_RUNTIME_CANNOT_PERSIST_SEND_AUTHORITY")
    blob=(json.dumps(summary,sort_keys=True,indent=2)+"\n").encode()
    proof={
        "schema_version":"empire.permit_intelligence.original_timer_compliance_receipt.v1",
        "report_sha256":sha256(blob).hexdigest(),
        "source_pilot_sha256":summary.get("pilot_sha256"),
        "authorised_to_send":False,
        "outbound_sent":False,
        "database_writes":False,
    }
    _store_private(path,blob)
    _store_private(root/RECEIPT,(json.dumps(proof,sort_keys=True,indent=2)+"\n").encode())


def run(*,root:Path=ROOT,now:datetime|None=None,
        provider_factory:Callable[[],Any]|None=None,
        write:bool=False)->dict:
    root=root.resolve()
    when=now or datetime.now(timezone.utc)
    if when.utcoffset() is None:
        raise ValueError("PERMIT_COMPLIANCE_OBSERVER_CLOCK_MISSING")
    base={
        "schema_version":"empire.permit_intelligence.original_timer_optional_compliance.v1",
        "mode":"OBSERVE",
        "observed_at_utc":when.astimezone(timezone.utc).isoformat(),
        "original_timer_step":"OPTIONAL_AFTER_BUYER_GMAIL_RECONCILIATION",
        "status":"HELD",
        "ten_workspace_drafts_inspected":0,
        "drafts_held":10,
        "new_send_authorized":False,
        "outbound_sent":False,
        "database_writes":False,
        "smart_crm_writes":False,
        "execution_authority":"NONE",
    }
    try:
        # ORIGINAL SkillForge selects existing task instructions by exact hash.
        # The current trust registry has no approvals; selection cannot
        # elevate an advisory skill into any tool or sending authority.
        skill_chain=bind_existing_skills(repo_root=root,now=when)
        validate_bindings(skill_chain)
        workbench=read_workbench(root=root,path=root/WORKBENCH)
        pinned=read_connector_observation(root=root,path=root/PINNED,now=when,
                                          pin_only=True)
        # Only original authenticated Workspace Gmail provider may read the
        # ten exact DRAFT IDs; tests can inject an explicit fake provider.
        copy_context={
            x["public_general_business_email_candidate"]:{
                "company":x["company"],"market":x["market_id"]}
            for x in workbench["owner_review_drafts"]
        }
        fresh=refresh_pinned(
            pinned_observation=pinned,now=when,
            service_factory=provider_factory,copy_context=copy_context,
        )
        pilot=build(workbench=workbench,observation=fresh,at=when)
        validate_review(pilot)
        policy=audit_batch(pilot_report=pilot,now=when)
        validate_batch(policy)
        # Same original Workspace OAuth account, bounded read-only alias
        # observation. It never creates an intent, sends or writes a
        # suppression. If the alias query fails, report UNKNOWN rather
        # than breaking mandatory buyer Gmail/CRM cycle steps.
        alias_review=inspect_workspace_stop_alias(
            service_factory=provider_factory,now=when)
        summary={
            **base,
            "status":"PASS_HELD_NO_SEND",
            "ten_workspace_drafts_inspected":policy["checked_drafts"],
            "drafts_held":policy["hold_drafts"],
            "observed_contact_candidates":pilot["observed_contact_candidates"],
            "verified_format_ready_drafts":pilot["verified_format_ready_drafts"],
            "evidence_review_ready_drafts":policy["review_ready_drafts"],
            "evidence_observed_check_count":policy["evidence_observed_check_count"],
            "evidence_independently_verified_check_count":
                policy["evidence_verified_check_count"],
            "evidence_progress_counts":policy["evidence_progress_counts"],
            "canonical_send_release_confirmed":False,
            "postal_footer_missing":pilot["actual_workspace_drafts_without_postal_address"],
            "canonical_founder_postal_footer_missing":sum(
                not r["canonical_business_postal_footer_in_draft"]
                for r in pilot["owner_review_queue"]),
            "explicit_reply_to_header_missing":sum(
                not r["expected_reply_to_header_in_draft"]
                for r in pilot["owner_review_queue"]),
            "canonical_postal_footer_configured":True,
            "workspace_stop_to_empiredb_suppression_e2e_verified":False,
            "workspace_reply_alias_monitor_state":alias_review["status"],
            "workspace_reply_alias_inbox_messages_observed":
                alias_review["workspace_reply_alias_inbox_messages_observed"],
            "workspace_reply_alias_explicit_stop_candidates":
                alias_review["workspace_reply_alias_explicit_stop_candidates"],
            "workspace_reply_alias_scan_complete":
                alias_review["workspace_reply_alias_scan_complete"],
            "workspace_reply_alias_delivery_observed":
                alias_review["workspace_reply_alias_delivery_observed"],
            "workspace_reply_alias_canonical_sent_intent_lineage_verified":False,
            "workspace_reply_alias_unresolved_stop_hold":(
                alias_review["workspace_reply_alias_explicit_stop_candidates"]>0),
            "draft_repair_full_mime_edit_scope_present":oauth_edit_granted(),
            "draft_repair_scope_needed":"gmail.compose",
            "draft_repair_changes_applied":0,
            "drafts_must_repin_after_update":True,
            "explicit_stop_text_missing":policy["blocker_counts"].get(
                "COPY_MISSING_EXPLICIT_OPTOUT_INSTRUCTION",0),
            "canonical_copywriter_scanned_drafts":sum(
                r["original_canonical_copywriter_quality"] is not None
                for r in pilot["owner_review_queue"]),
            "canonical_copywriter_quality_review_needed":policy["blocker_counts"].get(
                "COPYWRITER_ORIGINAL_QUALITY_REVIEW_REQUIRED",0),
            "canonical_copywriter_human_gate_blocked":sum(
                x["original_canonical_copywriter_quality"] is not None
                and x["original_canonical_copywriter_quality"]["human_copy_gate_eligible"] is False
                for x in pilot["owner_review_queue"]),
            "blocker_counts":policy["blocker_counts"],
            "pilot_sha256":pilot["pilot_readiness_sha256"],
            "compliance_sha256":policy["report_sha256"],
            "skillforge_binding_sha256":skill_chain["skill_bindings_sha256"],
            "skillforge_selection_state":skill_chain["workflow_skill_authority_state"],
            "skillforge_tasks_selected":skill_chain["skills_discovered"],
            "skillforge_skills_approved_pinned":skill_chain["skills_approved_pinned"],
            "skillforge_stage_names":[
                x["stage"] for x in skill_chain["skillforge_stages"]],
            "skillforge_scripts_executed":False,
            "actual_email_body_retained":False,
        }
        if write:_latest(root,summary)
        return summary
    except Exception:
        # An optional poller must not break incoming buyer-reply checks or
        # reveal a provider exception, DSN, private path, recipient or body.
        return {**base,"status":"HELD",
                "reason_code":"COMPLIANCE_REVIEW_SOURCE_OR_PROVIDER_UNAVAILABLE"}


def main(argv=None)->int:
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--write",action="store_true")
    args=cli.parse_args(argv)
    out=run(write=args.write)
    print(json.dumps(out,sort_keys=True))
    return 0 if out["status"]=="PASS_HELD_NO_SEND" else 2


if __name__=="__main__":
    raise SystemExit(main())
