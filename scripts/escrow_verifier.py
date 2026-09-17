#!/usr/bin/env python3
"""Manual BSC escrow verifier. OBSERVE by default; --record is explicit."""
import argparse
import json
import os
import sys

from empire_os.bsc_escrow_verifier import (
    BscEscrowConfig, creation_record_payload, escrow_id_from_uuid,
    lifecycle_record_payload, verify_escrow_action, verify_escrow_created,
)
from empire_os.bsc_usdt_verifier import PaymentVerificationError
from empire_os.payment_governance import PaymentGovernanceError
from empire_os.payment_role_transport import PostgresRoleRpc


def parser():
    p = argparse.ArgumentParser(description="Empire BSC USDT smart-contract escrow verifier")
    p.add_argument("request_id")
    p.add_argument("transaction_hash")
    p.add_argument("--action", required=True,
                   choices=("created", "funded", "released", "refunded"))
    p.add_argument("--record", action="store_true",
                   help="record proof through dedicated escrow-verifier role")
    return p


def emit(value):
    print(json.dumps(value, indent=2, sort_keys=True, default=str))

def main(argv=None):
    args = parser().parse_args(argv)
    dsn = os.getenv("EMPIRE_ESCROW_VERIFIER_DSN", "").strip()
    if not dsn:
        raise PaymentGovernanceError("EMPIRE_ESCROW_VERIFIER_DSN is required")
    rpc = PostgresRoleRpc(dsn, "empire_escrow_verifier")
    review = rpc("get_bsc_escrow_request_review", {"p_request_id": args.request_id})
    config = BscEscrowConfig.from_env()

    if review.get("beneficiary_address") != config.beneficiary:
        raise PaymentGovernanceError("configured escrow beneficiary does not match approved request")
    if review.get("status") != "approved":
        raise PaymentGovernanceError("approved escrow payment request required")

    escrow_id = review.get("escrow_id") or escrow_id_from_uuid(args.request_id)
    amount = review.get("amount_usdt")
    payer = review.get("payer_address")
    terms_hash = "0x" + review.get("commercial_terms_sha256", "")

    if args.action == "created":
        evidence = verify_escrow_created(
            config, args.transaction_hash, escrow_id, amount, payer, terms_hash,
        )
        payload = creation_record_payload(config, evidence)
        record_name = "record_bsc_escrow_creation"
        record_params = {"p_request_id": args.request_id, "p_evidence": payload}
    else:
        if not review.get("agreement_id"):
            raise PaymentGovernanceError("verified escrow creation must be recorded first")
        evidence = verify_escrow_action(
            config, args.transaction_hash, escrow_id, amount,
            action=args.action, expected_payer=payer,
        )
        payload = lifecycle_record_payload(evidence)
        record_name = "record_bsc_escrow_lifecycle"
        record_params = {
            "p_agreement_id": review["agreement_id"],
            "p_action": args.action,
            "p_evidence": payload,
        }

    preview = {
        "mode": "OBSERVE",
        "recorded": False,
        "actual_revenue": False,
        "review": review,
        "evidence": payload,
    }
    if not args.record:
        emit(preview)
        return 0

    result = rpc(record_name, record_params)
    emit({"preview": preview, "record": result})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PaymentGovernanceError, PaymentVerificationError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
