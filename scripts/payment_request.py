#!/usr/bin/env python3
"""Manual BSC payment-request proposal tool. Defaults to OBSERVE dry-run."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
import sys

from empire_os.bsc_usdt_verifier import BscUsdtConfig, PaymentVerificationError, get_block_anchor
from empire_os.bsc_escrow_verifier import BscEscrowConfig
from empire_os.payment_governance import (
    PaymentGovernanceError, build_escrow_proposal, build_payment_proposal,
    submit_payment_proposal,
)


def parser():
    p = argparse.ArgumentParser(description="Empire governed BSC payment request tool")
    p.add_argument("fulfilment_order_id")
    p.add_argument("amount_usdt")
    p.add_argument("payer_address")
    p.add_argument("idempotency_key")
    p.add_argument("--mode", choices=("direct", "escrow"), default="direct")
    p.add_argument("--actor", default=os.getenv("EMPIRE_OPERATOR_ID", ""))
    p.add_argument("--expires-minutes", type=int, default=1440)
    p.add_argument("--submit", action="store_true",
                   help="create the pending request through service_role")
    return p


def emit(value):
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def main(argv=None):
    args = parser().parse_args(argv)
    config = BscUsdtConfig.from_env() if args.mode == "direct" else BscEscrowConfig.from_env()
    anchor = get_block_anchor(config)
    now = datetime.now(timezone.utc)
    common = dict(
        fulfilment_order_id=args.fulfilment_order_id, amount_usdt=args.amount_usdt,
        payer_address=args.payer_address, min_block_number=anchor["block_number"],
        expires_at=now + timedelta(minutes=args.expires_minutes),
        idempotency_key=args.idempotency_key, actor=args.actor, now=now,
    )
    if args.mode == "direct":
        plan = build_payment_proposal(treasury_address=config.treasury_address, **common)
    else:
        plan = build_escrow_proposal(beneficiary_address=config.beneficiary, **common)
    output = {"chain_anchor": anchor, "proposal": plan}
    if not args.submit:
        output["next_gate"] = "rerun with --submit after operator review"
        emit(output); return 0
    result = submit_payment_proposal(plan, operator_authorized=True)
    output["submit"] = result
    emit(output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PaymentGovernanceError, PaymentVerificationError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
