"""One-shot first-party checkout mode and BSC payment admission inspection.

READ_ONLY: never sends funds, writes to EmpireDB, creates customers or orders.
The historical 4-product conditional founder approval is recorded already.
"""
from __future__ import annotations

import argparse
import json
import os
from unittest.mock import patch

from empire_os.runtime_env import load_runtime_env
from empire_os.bsc_escrow_verifier import BscEscrowConfig
from empire_os.escrow_mainnet_role_readiness import (
    EscrowRoleConfig, role_config_snapshot, verify_escrow_runtime_roles_and_backing,
)
from empire_os.self_serve_escrow_bridge import (
    escrow_config_snapshot,
    escrow_mainnet_activation_flag,
    settlement_mode,
    verify_escrow_checkout_contract,
    verify_escrow_operator_memberships,
)
from empire_os.self_serve_payment_readiness import (
    CheckoutPaymentPreflightHold,
    checkout_bsc_config_snapshot,
    verify_checkout_bsc_chain,
)


def inspection(*, probe_chain: bool = False) -> dict:
    env = load_runtime_env("/etc/empire_os.env")
    try:
        checkout_mode = settlement_mode(env)
    except CheckoutPaymentPreflightHold:
        checkout_mode = "unsupported"
    if checkout_mode == "escrow":
        config = escrow_config_snapshot(environ=env)
        mainnet_gate = escrow_mainnet_activation_flag(env)
    elif checkout_mode == "direct":
        config = checkout_bsc_config_snapshot(env=env)
        mainnet_gate = False
    else:
        config = {"configured":False,"status":"UNSUPPORTED_CHECKOUT_SETTLEMENT_MODE"}
        mainnet_gate = False

    status = config["status"]
    chain_verified = False
    escrow_runtime_verified = False
    escrow_operator_memberships_verified = False
    escrow_onchain_expected_roles_verified = False
    escrow_backing_verified = False
    anchor_age_seconds = None
    if config["configured"]:
        role_config = (role_config_snapshot(env) if checkout_mode == "escrow"
                       else {"configured":True,"status":"not_applicable"})
        if checkout_mode == "escrow" and not mainnet_gate:
            status = "ESCROW_MAINNET_ACTIVATION_HELD"
        elif not role_config["configured"]:
            status = role_config["status"]
        else:
            status = "CHAIN_READ_NOT_YET_VERIFIED"
            if probe_chain:
                with patch.dict(os.environ, env):
                    try:
                        if checkout_mode == "escrow":
                            result = verify_escrow_checkout_contract()
                            escrow_runtime_verified = result["escrow_runtime_verified"]
                            onchain = verify_escrow_runtime_roles_and_backing(
                                deployment=BscEscrowConfig.from_env(),
                                roles=EscrowRoleConfig.from_env(),
                            )
                            escrow_onchain_expected_roles_verified = (
                                onchain["expected_role_holders_verified"] == 4
                            )
                            escrow_backing_verified = (
                                onchain["escrow_backing_solvency_pass"] is True
                            )
                            role_result = verify_escrow_operator_memberships()
                            escrow_operator_memberships_verified = (
                                role_result["status"] ==
                                "ESCROW_OPERATOR_MEMBERSHIPS_PRESENT_READ_ONLY"
                            )
                            chain_verified = (
                                escrow_runtime_verified
                                and escrow_onchain_expected_roles_verified
                                and escrow_backing_verified
                                and escrow_operator_memberships_verified
                            )
                        else:
                            result = verify_checkout_bsc_chain()
                            chain_verified = result["chain_verified"]
                    except CheckoutPaymentPreflightHold as exc:
                        status = str(exc)
                    else:
                        status = result["status"]
                        anchor_age_seconds = result["block_age_seconds"]
    return {
        "schema_version": "empire.self-serve-bsc-payment-activation-preflight.v2",
        "mode": "READ_ONLY",
        "checkout_settlement_mode": checkout_mode,
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
        "escrow_contract_runtime_verified": escrow_runtime_verified,
        "escrow_operator_memberships_verified": escrow_operator_memberships_verified,
        "escrow_expected_onchain_role_holders_verified": escrow_onchain_expected_roles_verified,
        "escrow_backing_solvency_verified": escrow_backing_verified,
        "role_grant_exclusivity_audited": False,
        "external_smart_contract_security_audit_verified": False,
        "escrow_mainnet_activation_permission_present": mainnet_gate,
        "block_age_seconds": anchor_age_seconds,
        "dedicated_payment_approver_automatically_authorized": False,
        "dedicated_escrow_verifier_automatically_authorized": False,
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
        help="Read configured BSC chain, canonical token and (when escrow) contract code/identity only; no writes",
    )
    opts = parser.parse_args()
    print(json.dumps(inspection(probe_chain=opts.probe_chain), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
