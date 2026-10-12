"""One-shot first-party escrow role-history evidence inspector.

Default = no network and no writes. --verify-history performs only BSC JSON-RPC
reads after an exact approved deployment tx/block + contract/role configuration.
No deployment, signing, role grant, order, DB write, payment or activation.
"""
from __future__ import annotations

import argparse
import json
import os
from unittest.mock import patch

from empire_os.bsc_escrow_verifier import BscEscrowConfig
from empire_os.escrow_mainnet_role_readiness import (
    EscrowRoleConfig, role_config_snapshot, verify_escrow_runtime_roles_and_backing,
)
from empire_os.escrow_role_history import (
    EscrowDeploymentProvenance, verify_escrow_access_control_history,
)
from empire_os.runtime_env import load_runtime_env
from empire_os.self_serve_escrow_bridge import (
    escrow_config_snapshot, verify_escrow_checkout_contract,
)
from empire_os.self_serve_payment_readiness import CheckoutPaymentPreflightHold

CONFIG_PATH = "/etc/empire_os.env"


def inspection(*, verify_history: bool = False, env: dict | None = None) -> dict:
    config = load_runtime_env(CONFIG_PATH) if env is None else env
    deployed = escrow_config_snapshot(environ=config)
    role = role_config_snapshot(config)
    provenance_configured = False
    try:
        EscrowDeploymentProvenance.from_env(config)
        provenance_configured = True
    except CheckoutPaymentPreflightHold:
        pass

    result = {
        "schema_version": "empire.escrow-mainnet-role-history-preflight.v1",
        "mode": "READ_ONLY",
        "status": "ESCROW_ROLE_HISTORY_HELD",
        "reason": (
            deployed["status"] if not deployed["configured"] else
            role["status"] if not role["configured"] else
            "ESCROW_DEPLOYMENT_TX_AND_BLOCK_MISSING"
            if not provenance_configured else
            "ESCROW_ROLE_HISTORY_NOT_YET_PROBED"
        ),
        "contract_configured": deployed["configured"],
        "role_owner_addresses_configured": role["configured"],
        "deployment_provenance_configured": provenance_configured,
        "onchain_deployed_code_approved_beneficiary_and_pause_verified": False,
        "expected_onchain_role_holders_and_escrow_backing_verified": False,
        "role_grant_exclusivity_at_confirmed_height_verified": False,
        "role_grant_exclusivity_independently_audited": False,
        "external_smart_contract_security_audit_verified": False,
        "role_history_blocks_scanned": 0,
        "role_grants_replayed": 0,
        "confirmed_through_block": None,
        "requester_would_be_allowed_to_move_funds": False,
        "payment_activation_performed": False,
        "onchain_transactions_sent": 0,
        "database_mutations": 0,
        "financial_roles_changed": 0,
        "actual_revenue": False,
        "execution_authority": "none",
    }
    if not verify_history:
        return result
    if not deployed["configured"] or not role["configured"] or not provenance_configured:
        return result
    try:
        with patch.dict(os.environ, config):
            deployment = BscEscrowConfig.from_env()
            expected_roles = EscrowRoleConfig.from_env()
            receipt = EscrowDeploymentProvenance.from_env(config)
            escrow = verify_escrow_checkout_contract(config=deployment)
            holders = verify_escrow_runtime_roles_and_backing(
                deployment=deployment, roles=expected_roles
            )
            history = verify_escrow_access_control_history(
                deployment=deployment, roles=expected_roles, provenance=receipt
            )
        if (escrow.get("escrow_runtime_verified") is not True
                or holders.get("expected_role_holders_verified") != 4
                or holders.get("escrow_backing_solvency_pass") is not True
                or history.get("role_grant_exclusivity_verified_for_confirmed_window") is not True):
            raise CheckoutPaymentPreflightHold("escrow_readiness_evidence_incomplete")
    except CheckoutPaymentPreflightHold as exc:
        result["reason"] = str(exc)
        return result
    # Exactly historical completeness through confirmed block, not a signed
    # independent audit and not authority to transact.
    result.update({
        "status": "ESCROW_ROLE_HISTORY_ONCHAIN_READ_PROOF_COMPLETE",
        "reason": "INDEPENDENT_EXTERNAL_AUDIT_AND_OPERATOR_GATES_STILL_REQUIRED",
        "onchain_deployed_code_approved_beneficiary_and_pause_verified": True,
        "expected_onchain_role_holders_and_escrow_backing_verified": True,
        "role_grant_exclusivity_at_confirmed_height_verified": True,
        "role_history_blocks_scanned": history["contiguous_blocks_scanned"],
        "role_grants_replayed": history["role_grants_replayed"],
        "confirmed_through_block": history["confirmed_through_block"],
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-history", action="store_true",
        help="Perform bounded first-party BSC read-only role log and deployment receipt verification",
    )
    args = parser.parse_args()
    print(json.dumps(inspection(verify_history=args.verify_history), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
