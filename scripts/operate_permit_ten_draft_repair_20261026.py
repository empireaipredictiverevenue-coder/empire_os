"""Single owner-controlled command for ten original Workspace Permit drafts.

The default is inspection only. Draft-only writes require BOTH an explicit
CLI selection and an independently enabled OBSERVE-only owner environment,
plus the existing Workspace user's consented Gmail Compose OAuth scope.

Never send, modify EmpireDB, configure another Gmail bot, or enable outbound.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path

from empire_os.permit_workspace_ten_draft_repair_preflight import preview
from empire_os.permit_workspace_ten_draft_repair_runner import (
    apply_exact_ten,REPAIR_APPROVAL,
)

ROOT=Path(__file__).resolve().parents[1]


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--read-only",action="store_true")
    g.add_argument("--apply-owner-approved-draft-only",action="store_true")
    args=p.parse_args(argv)
    try:
        if args.read_only:
            result=preview(root=ROOT)
        else:
            result=apply_exact_ten(root=ROOT,approval=REPAIR_APPROVAL)
        if result.get("messages_sent") or result.get("send_authorized"):
            raise ValueError("PERMIT_DRAFT_REPAIR_SEND_AUTHORITY_FORGED")
        print(json.dumps(result,sort_keys=True))
        return 0
    except ValueError as exc:
        # No private text, MIME, OAuth credentials, or recipients in error output.
        print(json.dumps({
            "status":"HELD_NO_DRAFT_EDIT_OR_SEND_AUTHORITY",
            "reason_code":str(exc) if str(exc).startswith("PERMIT_") else
                "PERMIT_DRAFT_REPAIR_REVIEW_UNAVAILABLE",
            "messages_sent":0,"outbound_authorized":False,
        },sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
