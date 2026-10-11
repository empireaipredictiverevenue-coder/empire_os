"""Read-only checkout payment activation inspector.

Provides safe, non-secret reason codes for founder/ASTRA task monitoring.
Never creates synthetic buyers, orders, requests, or on-chain transactions.
"""
from __future__ import annotations

import argparse
import json
import os
from unittest.mock import patch

from empire_os.runtime_env import load_runtime_env
from empire_os.self_serve_payment_readiness import (
    CheckoutPaymentPreflightHold, checkout_bsc_config_snapshot,
    verify_checkout_bsc_chain,
)


def inspection(*, probe_chain: bool = False) -> dict:
    env = load_runtime_env("/etc/empire_os.env")
    config = checkout_bsc_config_snapshot(env=env)
    status = config["status"]
    chain_verified = False
    anchor_age_seconds = None
    if config["configured"]:
        status = "CHAIN_READ_NOT_YET_VERIFIED"
        if probe_chain:
            with patch.dict(os.environ, env):
                try:
                    result = verify_checkout_bsc_chain()
                except CheckoutPaymentPreflightHold as exc:
                    status = str(exc)
                else:
                    status = result["status"]
                    chain_verified = result["chain_verified"]
                    anchor_age_seconds = result["block_age_seconds"]
    return {
        "schema_version": "empire.self-serve-bsc-payment-activation-preflight.v1",
        "mode": "READ_ONLY",
        "status": ("BSC_PREFLIGHT_PASS" if chain_verified
                   else "BSC_PAYMENT_ACTIVATION_HELD"),
        "reason": status,
        "founder_approved_activation_scope": [
            "competitor_search_gap",
            "search_opportunity_map",
            "technical_search_audit",
            "solar_opportunity_map_us",
        ],
        "bsc_configuration_present": config["configured"],
        "chain_verified": chain_verified,
        "block_age_seconds": anchor_age_seconds,
        "dedicated_payment_approver_automatically_authorized": False,
        "allow_binding_orders": False,
        "enable_payment_flags": False,
        "funds_transferred": False,
        "buyer_records_written": 0,
        "orders_created": 0,
        "payment_requests_created": 0,
        "outbound_sent": False,
        "actual_revenue": False,
        "authority": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--probe-chain", action="store_true",
        help="Read chain ID, current block and canonical token decimals via configured RPC; no writes",
    )
    opts = parser.parse_args()
    print(json.dumps(inspection(probe_chain=opts.probe_chain), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
