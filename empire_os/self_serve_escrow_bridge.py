"""First-party BSC USDT escrow checkout admission (no on-chain writes).

Reuses Empire's existing escrow contract verifier and proposal machinery. This
module validates deployment provenance *before* a buyer/order row is created.
Nothing here signs, broadcasts, grants financial roles or sends payment details.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
import re
from typing import Any, Callable, Mapping

from empire_os.bsc_escrow_verifier import BscEscrowConfig, _runtime_hash
from empire_os.bsc_usdt_verifier import (
    BSC_MAINNET_CHAIN_ID,
    BSC_USDT_CONTRACT,
    DECIMALS_SELECTOR,
    PaymentVerificationError,
    _address,
    _hex_int,
    _rpc_request,
    get_block_anchor,
)
from empire_os.self_serve_payment_readiness import (
    CheckoutPaymentPreflightHold,
    MAX_BLOCK_AGE_SECONDS,
    MAX_CLOCK_AHEAD_SECONDS,
)

# ABI selectors generated from the *existing* EmpireBscUsdtEscrow ABI:
# ethers.id("beneficiary()"), ethers.id("token()"), ethers.id("paused()").
BENEFICIARY_SELECTOR = "0x38af3eed"
TOKEN_SELECTOR = "0xfc0c546a"
PAUSED_SELECTOR = "0x5c975abb"
HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
ON_FLAGS = frozenset({"ON", "YES", "TRUE", "1"})

Rpc = Callable[[str, list[Any]], Any]


def settlement_mode(environ: Mapping[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    mode = str(source.get("EMPIRE_SELF_SERVE_SETTLEMENT_MODE", "direct")).strip().lower()
    if mode not in {"direct", "escrow"}:
        raise CheckoutPaymentPreflightHold("unsupported_checkout_settlement_mode")
    return mode


def escrow_config_snapshot(*, environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Report only safe statuses; source never leaks treasury, RPC, or code hash."""
    source = os.environ if environ is None else environ
    needed = ("BSC_RPC_URL", "BSC_ESCROW_CONTRACT",
              "BSC_ESCROW_BENEFICIARY", "BSC_ESCROW_RUNTIME_SHA256")
    if not all(isinstance(source.get(k), str) and source[k].strip() for k in needed):
        return {
            "configured": False,
            "status": "ESCROW_MAINNET_CONFIG_MISSING",
            "mainnet_activation_verified": False,
        }
    try:
        token = _address(str(source.get("BSC_USDT_TOKEN_CONTRACT") or BSC_USDT_CONTRACT))
        config = BscEscrowConfig(
            rpc_url=str(source["BSC_RPC_URL"]).strip(),
            escrow_contract=_address(source["BSC_ESCROW_CONTRACT"]),
            beneficiary=_address(source["BSC_ESCROW_BENEFICIARY"]),
            runtime_sha256=str(source["BSC_ESCROW_RUNTIME_SHA256"]).strip().lower(),
            min_confirmations=int(source.get("BSC_MIN_CONFIRMATIONS") or "12"),
        )
        if (config.chain_id != BSC_MAINNET_CHAIN_ID
                or token != BSC_USDT_CONTRACT
                or not HEX_DIGEST.fullmatch(config.runtime_sha256)
                or config.min_confirmations < 12
                or int(config.beneficiary, 16) == 0
                or int(config.escrow_contract, 16) == 0
                or config.beneficiary == config.escrow_contract):
            raise PaymentVerificationError("invalid canonical escrow configuration")
    except (PaymentVerificationError, ValueError, TypeError):
        return {
            "configured": False,
            "status": "ESCROW_MAINNET_CONFIG_INVALID",
            "mainnet_activation_verified": False,
        }
    return {
        "configured": True,
        "status": "ESCROW_CONFIG_PRESENT_DEPLOYMENT_NOT_VERIFIED",
        "mainnet_activation_verified": False,
    }


def escrow_mainnet_activation_flag(environ: Mapping[str, str] | None = None) -> bool:
    source = os.environ if environ is None else environ
    return str(source.get("EMPIRE_SELF_SERVE_ESCROW_MAINNET_APPROVED", "OFF")).strip().upper() in ON_FLAGS


def verify_escrow_checkout_contract(
    *,
    config: BscEscrowConfig | None = None,
    rpc_call: Rpc | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read verified mainnet escrow bytecode, terms and pause state; zero writes.

    This check *never* implies the escrow has been created for any order;
    per-request EscrowCreated verification is a separate signed role flow.
    """
    if config is None:
        try:
            config = BscEscrowConfig.from_env()
        except (PaymentVerificationError, ValueError, TypeError) as exc:
            raise CheckoutPaymentPreflightHold("escrow_mainnet_config_unavailable") from exc
    if (config.chain_id != BSC_MAINNET_CHAIN_ID
            or config.min_confirmations < 12
            or not HEX_DIGEST.fullmatch(str(config.runtime_sha256).lower())):
        raise CheckoutPaymentPreflightHold("escrow_mainnet_config_invalid")
    try:
        escrow = _address(config.escrow_contract)
        beneficiary = _address(config.beneficiary)
        if escrow == beneficiary or int(escrow, 16) == 0 or int(beneficiary, 16) == 0:
            raise PaymentVerificationError("invalid escrow identities")
    except PaymentVerificationError as exc:
        raise CheckoutPaymentPreflightHold("escrow_mainnet_config_invalid") from exc

    rpc = rpc_call or (lambda method, params: _rpc_request(config.rpc_url, method, params))
    try:
        anchor = get_block_anchor(config, rpc_call=rpc)
        token_decimals = _hex_int(rpc(
            "eth_call", [{"to": BSC_USDT_CONTRACT, "data": DECIMALS_SELECTOR}, "latest"]
        ))
        code_hash = _runtime_hash(rpc("eth_getCode", [escrow, "latest"]))
        encoded_beneficiary = rpc(
            "eth_call", [{"to": escrow, "data": BENEFICIARY_SELECTOR}, "latest"]
        )
        encoded_token = rpc(
            "eth_call", [{"to": escrow, "data": TOKEN_SELECTOR}, "latest"]
        )
        paused = _hex_int(rpc(
            "eth_call", [{"to": escrow, "data": PAUSED_SELECTOR}, "latest"]
        ))
        if (not isinstance(encoded_beneficiary, str)
                or not isinstance(encoded_token, str)
                or not re.fullmatch(r"0x[0-9a-fA-F]{64}", encoded_beneficiary)
                or not re.fullmatch(r"0x[0-9a-fA-F]{64}", encoded_token)):
            raise PaymentVerificationError("malformed escrow ABI addresses")
        actual_beneficiary = _address("0x" + encoded_beneficiary[-40:])
        actual_token = _address("0x" + encoded_token[-40:])
        if encoded_beneficiary[2:26].lower() != "0"*24 or encoded_token[2:26].lower() != "0"*24:
            raise PaymentVerificationError("escrow ABI address padding incorrect")
    except (PaymentVerificationError, ValueError, TypeError, OSError, TimeoutError) as exc:
        raise CheckoutPaymentPreflightHold("escrow_mainnet_read_unavailable") from exc

    if code_hash != config.runtime_sha256.lower():
        raise CheckoutPaymentPreflightHold("escrow_runtime_code_mismatch")
    if token_decimals != 18 or actual_token != BSC_USDT_CONTRACT:
        raise CheckoutPaymentPreflightHold("escrow_usdt_token_mismatch")
    if actual_beneficiary != beneficiary:
        raise CheckoutPaymentPreflightHold("escrow_beneficiary_mismatch")
    if paused != 0:
        raise CheckoutPaymentPreflightHold("escrow_contract_paused")
    current = now or datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise CheckoutPaymentPreflightHold("escrow_clock_untrusted")
    age = current.astimezone(timezone.utc).timestamp() - anchor["timestamp"]
    if age < -MAX_CLOCK_AHEAD_SECONDS or age > MAX_BLOCK_AGE_SECONDS:
        raise CheckoutPaymentPreflightHold("escrow_block_stale")

    return {
        "status": "ESCROW_MAINNET_RUNTIME_VERIFIED_READ_ONLY",
        "configured": True,
        "escrow_runtime_verified": True,
        "token_decimals": token_decimals,
        "chain_id": anchor["chain_id"],
        "block_number": anchor["block_number"],
        "block_age_seconds": round(age, 3),
        "buyer_order_created": False,
        "escrow_created": False,
        "payment_instructions_ready": False,
        "payment_request_created": False,
        "financial_approval_automated": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }



def verify_escrow_operator_memberships(
    *, reader: Callable[[], list[tuple[str, bool, bool, int]]] | None = None,
) -> dict[str, Any]:
    """Check existing sovereign EmpireDB role memberships without writes.

    This verifies admission prerequisites only. It never loads payment-role
    credentials into the public checkout process, impersonates an approver,
    grants roles, or claims that an operator has actually executed approval.
    """
    if reader is None:
        def live_reader() -> list[tuple[str, bool, bool, int]]:
            from empire_os.runtime_env import load_runtime_env
            import psycopg
            env = load_runtime_env("/etc/empire_os.env")
            dsn = env.get("EMPIREDB_DSN")
            if not dsn:
                raise CheckoutPaymentPreflightHold("escrow_role_catalog_unavailable")
            with psycopg.connect(
                conninfo=dsn, connect_timeout=5,
                application_name="empire-escrow-checkout-role-readonly"
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute("SET LOCAL statement_timeout = '4000ms'")
                    cursor.execute("""
                        SELECT role.rolname, role.rolcanlogin, role.rolinherit,
                          count(DISTINCT member.oid)
                            FILTER (WHERE member.rolcanlogin) ::integer
                        FROM pg_roles AS role
                        LEFT JOIN pg_auth_members AS membership ON membership.roleid = role.oid
                        LEFT JOIN pg_roles AS member ON member.oid = membership.member
                        WHERE role.rolname IN ('empire_payment_approver','empire_escrow_verifier')
                        GROUP BY role.oid, role.rolname, role.rolcanlogin, role.rolinherit
                        ORDER BY role.rolname
                    """)
                    rows = cursor.fetchall()
                conn.rollback()
            return rows
        reader = live_reader
    try:
        rows = reader()
    except CheckoutPaymentPreflightHold:
        raise
    except Exception as exc:
        raise CheckoutPaymentPreflightHold("escrow_role_catalog_unavailable") from exc
    if not isinstance(rows, list) or len(rows) != 2:
        raise CheckoutPaymentPreflightHold("escrow_operator_roles_unprovisioned")
    expected = ("empire_escrow_verifier", "empire_payment_approver")
    for row, role in zip(rows, expected):
        if (not isinstance(row, (tuple, list)) or len(row) != 4
                or row[0] != role
                or row[1] is not False
                or row[2] is not False
                or type(row[3]) is not int or row[3] < 1):
            raise CheckoutPaymentPreflightHold("escrow_operator_roles_unprovisioned")
    return {
        "status": "ESCROW_OPERATOR_MEMBERSHIPS_PRESENT_READ_ONLY",
        "roles_checked": 2,
        "dedicated_credentials_exposed": False,
        "payment_approval_performed": False,
        "escrow_verification_recorded": False,
        "orders_created": 0,
        "actual_revenue": False,
    }
