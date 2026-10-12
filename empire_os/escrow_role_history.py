"""Replay Empire BSC escrow AccessControl grant/revoke history, READ ONLY.

This is a bounded release-admission proof, not a checkout-request hot path.
Only a verified deployment receipt and complete, contiguous, confirmed log
coverage can establish the expected set of role holders at the scanned height.
RPC responses remain trust-dependent; external audit remains a separate gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from empire_os.bsc_escrow_verifier import BscEscrowConfig
from empire_os.bsc_usdt_verifier import (
    BSC_MAINNET_CHAIN_ID, PaymentVerificationError,
    _address, _hex_int, _rpc_request, _tx_hash, _validate_hex,
    get_block_anchor,
)
from empire_os.escrow_mainnet_role_readiness import EscrowRoleConfig, ROLES
from empire_os.self_serve_payment_readiness import CheckoutPaymentPreflightHold

# From ethers.id and OpenZeppelin IAccessControl / DefaultAdminRules ABI.
ROLE_GRANTED = "0x2f8788117e7eff1d82e926ec794901d17c78024a50270940304540a733656f0d"
ROLE_REVOKED = "0xf6391f5c32d9c69d2a47ea670b442974b53935d1edc7fd64eb21e047a839171b"
ROLE_ADMIN_CHANGED = "0xbd79b86ffe0ab8e8776151514217cd7cacd52c909f66475c3af44e129f0b00ff"
ADMIN_TRANSFER_SCHEDULED = "0x3377dc44241e779dd06afab5b788a35ca5f3b778836e2990bdb26a2a4b2e5ed6"
ADMIN_TRANSFER_CANCELLED = "0x8886ebfc4259abdbc16601dd8fb5678e54878f47b3c34836cfc51154a9605109"
ADMIN_DELAY_CHANGE_SCHEDULED = "0xf1038c18cf84a56e432fdbfaf746924b7ea511dfe03a6506a0ceba4888788d9b"
ADMIN_DELAY_CHANGE_CANCELLED = "0x2b1fa2edafe6f7b9e97c1a9e0c3660e645beb2dcaa2d45bdbf9beaf5472e1ec5"
ACCESS_CONTROL_TOPICS = [
    ROLE_GRANTED, ROLE_REVOKED, ROLE_ADMIN_CHANGED,
    ADMIN_TRANSFER_SCHEDULED, ADMIN_TRANSFER_CANCELLED,
    ADMIN_DELAY_CHANGE_SCHEDULED, ADMIN_DELAY_CHANGE_CANCELLED,
]

# Hard bound protects checkout uptime and avoids an unbounded RPC log walk.
MAX_HISTORY_BLOCKS = 100_000
LOG_CHUNK_BLOCKS = 1_000
MAX_LOGS_PER_CHUNK = 3_000
Rpc = Callable[[str, list[Any]], Any]


@dataclass(frozen=True)
class EscrowDeploymentProvenance:
    deployment_transaction_hash: str
    deployment_block: int

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "EscrowDeploymentProvenance":
        try:
            tx = _tx_hash(env.get("BSC_ESCROW_DEPLOY_TX_HASH"))
            block = int(env["BSC_ESCROW_DEPLOY_BLOCK"])
            if type(block) is not int or block < 1:
                raise ValueError("invalid deployment block")
        except (KeyError, PaymentVerificationError, ValueError, TypeError) as exc:
            raise CheckoutPaymentPreflightHold("escrow_deployment_provenance_missing") from exc
        return cls(deployment_transaction_hash=tx, deployment_block=block)


def _address_topic(value: str, *, label: str) -> str:
    topic = _validate_hex(value, 66, label)
    if topic[2:26] != "0" * 24:
        raise CheckoutPaymentPreflightHold("escrow_role_history_malformed")
    return _address("0x" + topic[-40:])


def _checked_log(log: Any, contract: str, first: int, last: int) -> dict:
    try:
        if not isinstance(log, dict):
            raise ValueError("not a log")
        if log.get("removed") is not False:
            raise ValueError("removed or ambiguous chain event")
        if _address(log["address"]) != contract:
            raise ValueError("foreign emitter")
        number = _hex_int(log["blockNumber"])
        position = _hex_int(log["transactionIndex"])
        idx = _hex_int(log["logIndex"])
        _tx_hash(log["transactionHash"])
        _tx_hash(log["blockHash"])
        if number < first or number > last:
            raise ValueError("event outside requested block range")
        topics = log["topics"]
        if not isinstance(topics, list) or len(topics) < 1:
            raise ValueError("missing topics")
        topic0 = _validate_hex(topics[0], 66, "event signature")
        if topic0 not in ACCESS_CONTROL_TOPICS:
            raise ValueError("unrequested event")
        if topic0 in (ROLE_GRANTED, ROLE_REVOKED, ROLE_ADMIN_CHANGED):
            if len(topics) != 4 or log.get("data") != "0x":
                raise ValueError("invalid AccessControl indexed ABI event")
        elif topic0 == ADMIN_TRANSFER_SCHEDULED:
            if len(topics) != 2 or len(str(log.get("data", ""))) != 66:
                raise ValueError("invalid admin transfer schedule")
        elif topic0 == ADMIN_DELAY_CHANGE_SCHEDULED:
            if len(topics) != 1:
                raise ValueError("invalid delay schedule")
            _validate_hex(log.get("data"), 130, "admin delay schedule")
        elif topic0 in (ADMIN_TRANSFER_CANCELLED, ADMIN_DELAY_CHANGE_CANCELLED):
            if len(topics) != 1 or log.get("data") != "0x":
                raise ValueError("invalid admin change cancel")
        for topic in topics:
            _validate_hex(topic, 66, "event topic")
        if topic0 in (ROLE_GRANTED, ROLE_REVOKED):
            role_id = topics[1].lower()
            account = _address_topic(topics[2], label="role account")
            _address_topic(topics[3], label="role sender")
        else:
            role_id = None
            account = None
        return {
            "block": number,
            "position": position,
            "index": idx,
            "signature": topic0,
            "role": role_id,
            "account": account,
            "block_hash": str(log["blockHash"]).lower(),
            "transaction_hash": str(log["transactionHash"]).lower(),
        }
    except (KeyError, PaymentVerificationError, ValueError, TypeError) as exc:
        raise CheckoutPaymentPreflightHold("escrow_role_history_malformed") from exc


def verify_escrow_access_control_history(
    *,
    deployment: BscEscrowConfig,
    roles: EscrowRoleConfig,
    provenance: EscrowDeploymentProvenance,
    rpc_call: Rpc | None = None,
) -> dict[str, Any]:
    """Confirm exclusive expected holders over *all confirmed logs since deploy*.

    Requires a verified deployment receipt, contiguous chunk responses,
    confirmation-depth anchor and unchanged anchor at end of scan.

    No statement is made about future grants, a malicious RPC, or an external
    security audit. Runtime hasRole()/contract bytecode checks remain mandatory.
    """
    if deployment.chain_id != BSC_MAINNET_CHAIN_ID or deployment.min_confirmations < 12:
        raise CheckoutPaymentPreflightHold("escrow_role_history_config_invalid")
    try:
        contract = _address(deployment.escrow_contract)
        expected = {role_id: _address(getattr(roles, name)) for name, role_id in ROLES}
        tx = _tx_hash(provenance.deployment_transaction_hash)
        first = provenance.deployment_block
        if (first < 1 or len(set(expected.values())) != 4
                or int(contract, 16) == 0 or any(int(x, 16) == 0 for x in expected.values())):
            raise ValueError("unsafe role deployment")
    except (PaymentVerificationError, ValueError, TypeError, AttributeError) as exc:
        raise CheckoutPaymentPreflightHold("escrow_role_history_config_invalid") from exc
    rpc = rpc_call or (
        lambda method, params: _rpc_request(deployment.rpc_url, method, params)
    )
    try:
        if _hex_int(rpc("eth_chainId", [])) != BSC_MAINNET_CHAIN_ID:
            raise CheckoutPaymentPreflightHold("escrow_role_history_wrong_chain")
        tip = _hex_int(rpc("eth_blockNumber", []))
        confirmed = tip - deployment.min_confirmations + 1
        if confirmed < first or confirmed - first + 1 > MAX_HISTORY_BLOCKS:
            raise CheckoutPaymentPreflightHold("escrow_role_history_range_unbounded")
        anchor = get_block_anchor(deployment, block_number=confirmed, rpc_call=rpc)
        receipt = rpc("eth_getTransactionReceipt", [tx])
        if not isinstance(receipt, dict):
            raise CheckoutPaymentPreflightHold("escrow_deployment_receipt_missing")
        if _tx_hash(receipt.get("transactionHash")) != tx:
            raise CheckoutPaymentPreflightHold("escrow_deployment_receipt_mismatch")
        receipt_address = _address(receipt.get("contractAddress"))
        if (receipt_address != contract
                or receipt.get("to") is not None
                or _hex_int(receipt.get("status")) != 1
                or _hex_int(receipt.get("blockNumber")) != first):
            raise CheckoutPaymentPreflightHold("escrow_deployment_receipt_mismatch")
        receipt_block_hash = _tx_hash(receipt.get("blockHash"))
        deployment_block = get_block_anchor(deployment, block_number=first, rpc_call=rpc)
        if receipt_block_hash != deployment_block["block_hash"]:
            raise CheckoutPaymentPreflightHold("escrow_deployment_receipt_noncanonical")

        holders = {role: set() for role in expected}
        granted = {role: 0 for role in expected}
        event_count = 0
        last_key = (-1, -1, -1)
        last_seen: set[tuple[int, int, int]] = set()
        for start in range(first, confirmed + 1, LOG_CHUNK_BLOCKS):
            end = min(start + LOG_CHUNK_BLOCKS - 1, confirmed)
            logs = rpc("eth_getLogs", [{
                "address": contract,
                "fromBlock": hex(start),
                "toBlock": hex(end),
                "topics": [ACCESS_CONTROL_TOPICS],
            }])
            if not isinstance(logs, list) or len(logs) > MAX_LOGS_PER_CHUNK:
                raise CheckoutPaymentPreflightHold("escrow_role_history_log_coverage_unverified")
            for raw in logs:
                event = _checked_log(raw, contract, start, end)
                position = (event["block"], event["position"], event["index"])
                if position <= last_key or position in last_seen:
                    raise CheckoutPaymentPreflightHold("escrow_role_history_order_or_duplicate")
                last_key = position
                last_seen.add(position)
                event_count += 1
                sig = event["signature"]
                if sig != ROLE_GRANTED:
                    # For the initial audited deployment policy, any role
                    # change, revoke, or admin-transfer schedule requires a
                    # fresh independent security review; never auto-admit it.
                    raise CheckoutPaymentPreflightHold("escrow_role_history_unreviewed_change")
                role_id = event["role"]
                if role_id not in expected or event["account"] != expected[role_id]:
                    raise CheckoutPaymentPreflightHold("escrow_role_history_extra_grant")
                # Constructor must have granted the four expected roles.
                # A late approval/grant is not proof of deployment ownership.
                if (event["block"] != first
                        or event["transaction_hash"] != tx):
                    raise CheckoutPaymentPreflightHold("escrow_role_history_not_constructor_grant")
                if event["account"] in holders[role_id]:
                    raise CheckoutPaymentPreflightHold("escrow_role_history_duplicate_grant")
                holders[role_id].add(event["account"])
                granted[role_id] += 1

        if any(count != 1 for count in granted.values()):
            raise CheckoutPaymentPreflightHold("escrow_role_history_incomplete")
        final = get_block_anchor(deployment, block_number=confirmed, rpc_call=rpc)
        if final["block_hash"] != anchor["block_hash"]:
            raise CheckoutPaymentPreflightHold("escrow_role_history_anchor_changed")
    except CheckoutPaymentPreflightHold:
        raise
    except (PaymentVerificationError, ValueError, TypeError, OSError, TimeoutError) as exc:
        raise CheckoutPaymentPreflightHold("escrow_role_history_rpc_unavailable") from exc

    return {
        "status": "ESCROW_CONFIRMED_ROLE_GRANT_HISTORY_EXCLUSIVE_AT_HEIGHT",
        "deployment_provenance_verified": True,
        "confirmed_through_block": confirmed,
        "confirmation_depth": deployment.min_confirmations,
        "contiguous_blocks_scanned": confirmed - first + 1,
        "role_grants_replayed": event_count,
        "expected_current_role_holders": 4,
        "extra_role_grants_seen": False,
        "role_grant_exclusivity_verified_for_confirmed_window": True,
        "independent_external_security_audit": False,
        "future_role_changes_covered": False,
        "transactions_sent": 0,
        "permissions_changed": False,
        "funds_moved": False,
        "actual_revenue": False,
    }
