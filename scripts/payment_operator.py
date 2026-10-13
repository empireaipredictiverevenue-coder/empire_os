#!/usr/bin/env python3
"""Manual BSC payment operator tool. No public HTTP route and no stored credentials."""
import argparse
import json
import os
import stat
import sys
from pathlib import Path

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


# Production operator access is not a service credential and is never added to
# public checkout env, logged, or passed as a password-bearing DSN in argv.
_ROOT_APPROVER_PASSFILE = Path(
    "/var/lib/empire-bsc-payment-operators/empire_payment_approver_login.pgpass"
)
_ROOT_APPROVER_DSN = (
    "host=/var/run/postgresql port=5432 dbname=empiredb "
    "user=empire_payment_approver_login connect_timeout=5"
)


def _local_root_approver_transport():
    """Load the existing segregated operator login, only inside a root process."""
    if os.geteuid() != 0:
        raise PaymentGovernanceError("root local operator required")
    path = _ROOT_APPROVER_PASSFILE
    directory = path.parent
    try:
        ds = directory.lstat()
        ps = path.lstat()
        if (not stat.S_ISDIR(ds.st_mode) or
                not stat.S_ISREG(ps.st_mode) or
                ds.st_uid != 0 or ps.st_uid != 0 or ps.st_gid != 0 or
                stat.S_IMODE(ds.st_mode) != 0o700 or
                stat.S_IMODE(ps.st_mode) != 0o600):
            raise ValueError("operator secret permissions invalid")
        fields = path.read_text(encoding="utf-8").rstrip("\n").split(":", 4)
        if (len(fields) != 5 or fields[:4] != [
            "/var/run/postgresql", "5432", "empiredb",
            "empire_payment_approver_login"
        ] or len(fields[4]) < 48):
            raise ValueError("operator secret identity invalid")
    except (OSError, ValueError) as exc:
        raise PaymentGovernanceError("protected operator credential unavailable") from None

    # The password remains in process memory, never in environment, argv,
    # logs or the public application.
    import psycopg
    secret = fields[4]
    return PostgresRoleRpc(
        _ROOT_APPROVER_DSN, "empire_payment_approver",
        connect_factory=lambda dsn: psycopg.connect(dsn, password=secret),
    )


def _load_live_direct_chain_config():
    """The manual approver uses the exact installed public BSC chain config."""
    from scripts.deploy_direct_bsc_readonly_checkout import (
        TARGET, EXPECTED, RPC, TREASURY,
    )
    try:
        if TARGET.is_symlink() or TARGET.read_bytes() != EXPECTED:
            raise ValueError("installed BSC checkout config drift")
    except (OSError, ValueError):
        raise PaymentGovernanceError("reviewed BSC chain configuration required") from None
    os.environ["BSC_RPC_URL"] = RPC
    os.environ["BSC_TREASURY_ADDRESS"] = TREASURY
    os.environ["BSC_MIN_CONFIRMATIONS"] = "12"


def main(argv=None):
    args = parser().parse_args(argv)
    dsn = os.getenv("EMPIRE_PAYMENT_APPROVER_DSN", "").strip()
    rpc = (PostgresRoleRpc(dsn, "empire_payment_approver")
           if dsn else _local_root_approver_transport())
    if args.action == "approve":
        _load_live_direct_chain_config()
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
