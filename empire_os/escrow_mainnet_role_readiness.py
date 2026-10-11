"""First-party read-only role and backing proof for deployed BSC escrow.

This supplements (never replaces) the existing code-hash, canonical-token,
beneficiary and pause checks in self_serve_escrow_bridge. No contract writes,
signing, approvals, role grants, transaction creation or funds movement.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Callable, Mapping

from empire_os.bsc_escrow_verifier import BscEscrowConfig
from empire_os.bsc_usdt_verifier import (
    BSC_MAINNET_CHAIN_ID, PaymentVerificationError,
    _address, _hex_int, _rpc_request, _validate_hex,
)
from empire_os.self_serve_payment_readiness import CheckoutPaymentPreflightHold

# Exact Keccak-256 method selectors and role hashes were checked using
# ethers.id against EmpireBscUsdtEscrow.sol's compiled ABI (12 Oct 2026).
HAS_ROLE_SELECTOR = "0x91d14854"
DECISION_DELAY_SELECTOR = "0xcfefde00"
ESCROW_BACKING_SELECTOR = "0x02922b37"
ROLES = (
    ("admin", "0x" + "0" * 64),
    ("requester", "0x61a3517f153a09154844ed8be639dabc6e78dc22315c2d9a91f7eddf9398c002"),
    ("arbiter", "0xbb08418a67729a078f87bbc8d02a770929bb68f5bfdf134ae2ead6ed38e2f4ae"),
    ("pauser", "0x65d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a"),
)
KEYS = {
    "admin": "BSC_ESCROW_ADMIN_ADDRESS",
    "requester": "BSC_ESCROW_REQUESTER_ADDRESS",
    "arbiter": "BSC_ESCROW_ARBITER_ADDRESS",
    "pauser": "BSC_ESCROW_PAUSER_ADDRESS",
}
MIN_DECISION_DELAY_SECONDS = 3600
MAX_DECISION_DELAY_SECONDS = 7 * 24 * 3600
Rpc = Callable[[str, list[Any]], Any]


@dataclass(frozen=True)
class EscrowRoleConfig:
    admin: str
    requester: str
    arbiter: str
    pauser: str
    decision_delay_seconds: int

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "EscrowRoleConfig":
        source = os.environ if env is None else env
        try:
            addresses = {name: _address(source[key]) for name, key in KEYS.items()}
            seconds = int(source["BSC_ESCROW_DECISION_DELAY_SECONDS"])
            if (len(set(addresses.values())) != 4
                    or any(int(v, 16) == 0 for v in addresses.values())
                    or not MIN_DECISION_DELAY_SECONDS <= seconds <= MAX_DECISION_DELAY_SECONDS):
                raise ValueError("escrow role policy")
        except (KeyError, PaymentVerificationError, ValueError, TypeError) as exc:
            raise CheckoutPaymentPreflightHold("escrow_roles_config_unverified") from exc
        return cls(**addresses, decision_delay_seconds=seconds)


def role_config_snapshot(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    try:
        EscrowRoleConfig.from_env(env)
    except CheckoutPaymentPreflightHold:
        return {
            "configured": False,
            "status": "ESCROW_ROLE_OWNER_CONFIGURATION_MISSING_OR_INVALID",
            "mainnet_role_evidence_verified": False,
        }
    return {
        "configured": True,
        "status": "ESCROW_ROLE_OWNERS_CONFIGURED_UNVERIFIED",
        "mainnet_role_evidence_verified": False,
    }


def _abi_word(value: Any, label: str) -> str:
    # Strict ABI decoding: never accept short, malformed or noncanonical words.
    try:
        return _validate_hex(str(value or ""), 66, label)
    except PaymentVerificationError as exc:
        raise CheckoutPaymentPreflightHold("escrow_role_chain_read_invalid") from exc


def verify_escrow_runtime_roles_and_backing(
    *,
    deployment: BscEscrowConfig,
    roles: EscrowRoleConfig,
    rpc_call: Rpc | None = None,
) -> dict[str, Any]:
    """Read a deployed escrow's *expected* role holders, delay and liabilities.

    Caller must first verify chain, bytecode SHA256, canonical USDT, beneficiary
    and pause state via verify_escrow_checkout_contract. AccessControl's
    hasRole() proves expected holders, not absence of additional grant holders;
    externally reviewed RoleGranted/Revoked event history is still required.
    """
    if (deployment.chain_id != BSC_MAINNET_CHAIN_ID
            or deployment.min_confirmations < 12):
        raise CheckoutPaymentPreflightHold("escrow_role_chain_config_unverified")
    contract = _address(deployment.escrow_contract)
    if int(contract, 16) == 0:
        raise CheckoutPaymentPreflightHold("escrow_role_chain_config_unverified")
    try:
        holders = [_address(getattr(roles, name)) for name, _ in ROLES]
        valid = (
            len(set(holders)) == 4
            and all(int(holder, 16) != 0 for holder in holders)
            and type(roles.decision_delay_seconds) is int
            and MIN_DECISION_DELAY_SECONDS <= roles.decision_delay_seconds <= MAX_DECISION_DELAY_SECONDS
        )
    except (PaymentVerificationError, ValueError, TypeError, AttributeError) as exc:
        raise CheckoutPaymentPreflightHold("escrow_roles_config_unverified") from exc
    if not valid:
        raise CheckoutPaymentPreflightHold("escrow_roles_config_unverified")
    rpc = rpc_call or (
        lambda method, params: _rpc_request(deployment.rpc_url, method, params)
    )
    try:
        if _hex_int(rpc("eth_chainId", [])) != BSC_MAINNET_CHAIN_ID:
            raise CheckoutPaymentPreflightHold("escrow_role_wrong_network")
        for name, role_id in ROLES:
            address = getattr(roles, name)
            # hasRole(bytes32,address) ABI: selector + 32-byte role + 32-byte EVM address
            data = HAS_ROLE_SELECTOR + role_id[2:] + "0" * 24 + address[2:]
            raw = rpc("eth_call", [{"to": contract, "data": data}, "latest"])
            if _hex_int(_abi_word(raw, f"{name} hasRole")) != 1:
                raise CheckoutPaymentPreflightHold("escrow_expected_role_holder_unverified")
        decision_delay = _hex_int(_abi_word(
            rpc("eth_call", [{"to": contract, "data": DECISION_DELAY_SELECTOR}, "latest"]),
            "decision delay",
        ))
        raw_backing = str(rpc("eth_call", [
            {"to": contract, "data": ESCROW_BACKING_SELECTOR}, "latest"
        ]) or "")
        backing = _validate_hex(raw_backing, 130, "escrow backing")
        balance = int(backing[2:66], 16)
        liability = int(backing[66:130], 16)
    except CheckoutPaymentPreflightHold:
        raise
    except (PaymentVerificationError, ValueError, TypeError, OSError, TimeoutError) as exc:
        raise CheckoutPaymentPreflightHold("escrow_role_chain_read_unavailable") from exc
    if decision_delay != roles.decision_delay_seconds:
        raise CheckoutPaymentPreflightHold("escrow_onchain_decision_delay_mismatch")
    if liability > balance:
        raise CheckoutPaymentPreflightHold("escrow_liabilities_exceed_backing")
    return {
        "status": "ESCROW_EXPECTED_ROLE_HOLDERS_AND_BACKING_VERIFIED_READ_ONLY",
        "expected_role_holders_verified": 4,
        "all_role_holders_exclusivity_verified": False,
        "role_grant_history_independently_audited": False,
        "decision_delay_seconds": decision_delay,
        "escrow_backing_solvency_pass": True,
        "balance_equals_liability": balance == liability,
        "escrow_contract_deployed_by_this_check": False,
        "financial_approval_performed": False,
        "role_grants_created": 0,
        "funds_moved": False,
        "actual_revenue": False,
    }
