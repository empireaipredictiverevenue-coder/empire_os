#!/usr/bin/env python3
"""Manual BSC payment operator tool. No public HTTP route and no stored credentials."""
import argparse
import json
import os
import sys

from empire_os.payment_governance import (
    PaymentGovernanceError, approve_payment_request, cancel_payment_request,
    review_payment_request, validate_review_block_anchor,
)
from empire_os.payment_role_transport import PostgresRoleRpc


def parser():
    p = argparse.ArgumentParser(description="Empire BSC payment human-approval tool")
    p.add_argument("action", choices=("review", "approve", "cancel"))
    p.add_argument("request_id")
    p.add_argument("--actor", default=os.getenv("EMPIRE_OPERATOR_ID", ""))
    p.add_argument("--note", default="")
    p.add_argument("--reason", default="")
    p.add_argument("--execute", action="store_true",
                   help="required for approve/cancel mutations")
    return p


def emit(value):
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def main(argv=None):
    args = parser().parse_args(argv)
    dsn = os.getenv("EMPIRE_PAYMENT_APPROVER_DSN", "").strip()
    if not dsn:
        raise PaymentGovernanceError("EMPIRE_PAYMENT_APPROVER_DSN is required")
    rpc = PostgresRoleRpc(dsn, "empire_payment_approver")
    review = review_payment_request(args.request_id, role_rpc=rpc)
    if args.action == "review":
        emit(review); return 0
    chain_anchor = None
    if args.action == "approve":
        chain_anchor = validate_review_block_anchor(review)
    if not args.execute:
        emit({"decision": "dry_run", "review": review,
              "chain_anchor": chain_anchor,
              "next_gate": "rerun with --execute after human review"})
        return 2
    if args.action == "approve":
        result = approve_payment_request(
            args.request_id, approved_by=args.actor, approval_note=args.note,
            operator_authorized=True, approver_rpc=rpc,
        )
    else:
        result = cancel_payment_request(
            args.request_id, actor=args.actor, reason=args.reason,
            operator_authorized=True, cancel_rpc=rpc,
        )
    emit({"review": review, "chain_anchor": chain_anchor, "result": result})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PaymentGovernanceError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
