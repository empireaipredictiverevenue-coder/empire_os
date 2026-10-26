"""Original Permit: canonical EmpireDB + Workspace proof, read-only.

Run only in the original sender-role approved execution environment. Uses the
original owner-private ten-draft workbench and Gmail source. Never reads an
alternative database, prompts for credentials, sends, or marks recipients
commercially eligible from an empty contact-history search.
"""
from __future__ import annotations
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from typing import Callable,Any

from empire_os.google_workspace_mailbox import GoogleWorkspaceMailboxProvider
from empire_os.permit_canonical_db_evidence import inspect as inspect_db
from empire_os.permit_compliance_private_sources import (
    read_workbench,read_connector_observation,
)
from empire_os.permit_national_buyer_pilot_readiness import (
    build as build_pilot,validate_review,
)
from empire_os.permit_workspace_draft_compliance_observer import refresh_pinned
from empire_os.permit_workspace_stop_alias_observer import inspect as inspect_alias
from scripts.audit_founder_email_db_visibility_20261023 import (
    load_sender_dsn,SENDER_ENV,
)
from scripts.run_permit_compliance_cycle_observer import ROOT,WORKBENCH,PINNED


def run(*,root:Path=ROOT,env_path:Path=SENDER_ENV,
        at:datetime|None=None,gmail_factory:Callable[[],Any]|None=None,
        db_connect_factory:Callable[...,Any]|None=None,
        dsn_loader:Callable[[Path],str]=load_sender_dsn)->dict:
    when=at or datetime.now(timezone.utc)
    base={
        "schema_version":"empire.permit.original_canonical_ten_bridge.v1",
        "status":"HELD_PROTECTED_READER_OR_SOURCE_UNAVAILABLE",
        "original_ten_drafts":10,
        "canonical_suppression_checks_verified":0,
        "canonical_full_history_verified":False,
        "workspace_reply_alias_delivery_verified":False,
        "recipient_marketing_eligibility_verified":False,
        "automatic_send_authorized":False,
        "emails_sent":False,
        "empiredb_writes":False,
    }
    try:
        # This credential is root-protected. Normal ubuntu must receive HOLD.
        dsn=dsn_loader(env_path)
        root=root.resolve()
        wb=read_workbench(root=root,path=root/WORKBENCH)
        pinned=read_connector_observation(
            root=root,path=root/PINNED,now=when,pin_only=True)
        factory=gmail_factory or GoogleWorkspaceMailboxProvider()._service
        context={
            x["public_general_business_email_candidate"]:{
                "company":x["company"],"market":x["market_id"]
            } for x in wb["owner_review_drafts"]
        }
        fresh=refresh_pinned(
            pinned_observation=pinned,now=when,
            service_factory=factory,copy_context=context)
        pilot=build_pilot(workbench=wb,observation=fresh,at=when)
        validate_review(pilot)
        report=inspect_db(pilot=pilot,dsn=dsn,now=when,
                          connect_factory=db_connect_factory)
        alias=inspect_alias(service_factory=factory,now=when)
        if report["full_rls_visibility_verified"] is not True:
            raise ValueError("PERMIT_CANONICAL_RLS_NOT_VERIFIED")
        return {
            **base,
            "status":"CANONICAL_DB_AND_WORKSPACE_READONLY_CHECKED_NOT_SEND_CLEARANCE",
            "source_role":report["source_role"],
            "full_rls_visibility_verified":True,
            "checked_at_utc":when.astimezone(timezone.utc).isoformat(),
            "canonical_suppression_checks_verified":
                report["canonical_zero_suppression_checks_verified"],
            "canonical_suppression_matches_found":
                report["canonical_suppression_matches_found"],
            "canonical_prior_domain_intents_found":
                report["canonical_prior_domain_intents_found"],
            "canonical_prior_exact_intents_found":
                report["canonical_prior_exact_intents_found"],
            "candidate_states":report["states"],
            "workspace_reply_alias_monitor_state":alias["status"],
            "workspace_reply_alias_inbound_count":
                alias["workspace_reply_alias_inbox_messages_observed"],
            "workspace_reply_alias_explicit_stop_candidates":
                alias["workspace_reply_alias_explicit_stop_candidates"],
            "workspace_alias_scan_complete":
                alias["workspace_reply_alias_scan_complete"],
            "original_draft_format_ready_count":
                pilot["verified_format_ready_drafts"],
            "canonical_full_history_verified":False,
            "workspace_reply_alias_delivery_verified":False,
            "recipient_marketing_eligibility_verified":False,
            "automatic_send_authorized":False,
            "emails_sent":False,
            "empiredb_writes":False,
        }
    except Exception:
        return base


def main(argv=None)->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--read-only",required=True,action="store_true")
    ap.parse_args(argv)
    result=run()
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"].startswith("CANONICAL_DB_") else 2


if __name__=="__main__":
    raise SystemExit(main())
