#!/usr/bin/env python3
"""Manual BSC verifier tool. Defaults to OBSERVE preview; --record is explicit."""
import argparse
import json
import os
import sys

from empire_os.bsc_payment_evidence import preview_payment
from empire_os.bsc_usdt_verifier import PaymentVerificationError
from empire_os.payment_governance import PaymentGovernanceError, record_payment_preview
from empire_os.payment_role_transport import PostgresRoleRpc


def parser():
    p = argparse.ArgumentParser(description="Empire BSC USDT verifier")
    p.add_argument("request_id")
    p.add_argument("transaction_hash")
    p.add_argument("--record", action="store_true",
                   help="record verified evidence through the dedicated verifier role")
    return p


def emit(value):
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def main(argv=None):
    args = parser().parse_args(argv)
    preview = preview_payment(args.request_id, args.transaction_hash)
    if not args.record:
        emit(preview); return 0
    dsn = os.getenv("EMPIRE_BSC_VERIFIER_DSN", "").strip()
    if not dsn:
        raise PaymentGovernanceError("EMPIRE_BSC_VERIFIER_DSN is required for --record")
    rpc = PostgresRoleRpc(dsn, "empire_bsc_verifier")
    result = record_payment_preview(
        preview, verifier_authorized=True, verifier_rpc=rpc,
    )
    emit({"preview": preview, "record": result})
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PaymentGovernanceError, PaymentVerificationError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
