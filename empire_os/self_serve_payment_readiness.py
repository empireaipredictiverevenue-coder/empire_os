"""Read-only BSC checkout preflight before ANY accepted order is written.

The caller must hold exact product + binding-order + payment-proposal gates.
This module never creates a buyer, order, request, transaction or revenue row.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Callable, Mapping

from empire_os.bsc_usdt_verifier import (
    BSC_MAINNET_CHAIN_ID,
    BSC_USDT_CONTRACT,
    BscUsdtConfig,
    DECIMALS_SELECTOR,
    PaymentVerificationError,
    _address,
    _hex_int,
    _rpc_request,
    get_block_anchor,
)

REQUIRED_DECIMALS = 18
MAX_BLOCK_AGE_SECONDS = 300
MAX_CLOCK_AHEAD_SECONDS = 30
RpcCall = Callable[[str, list[Any]], Any]


class CheckoutPaymentPreflightHold(RuntimeError):
    """Holds binding orders before writes when BSC payment evidence is unsafe."""


def checkout_bsc_config_snapshot(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Local-only preflight. Exposes no treasury address, RPC URL, or secrets."""
    source = dict(os.environ if env is None else env)
    if not str(source.get("BSC_RPC_URL") or "").strip() or not str(source.get("BSC_TREASURY_ADDRESS") or "").strip():
        return {
            "configured": False,
            "status": "BSC_CONFIG_MISSING",
            "chain_verified": False,
            "payment_collection_ready": False,
        }
    try:
        if env is None:
            config = BscUsdtConfig.from_env()
        else:
            token = _address(source.get("BSC_USDT_TOKEN_CONTRACT") or BSC_USDT_CONTRACT)
            if token != BSC_USDT_CONTRACT:
                raise PaymentVerificationError("wrong USDT contract")
            confirmations = int(source.get("BSC_MIN_CONFIRMATIONS") or "12")
            if confirmations < 1:
                raise PaymentVerificationError("invalid confirmation count")
            config = BscUsdtConfig(
                rpc_url=str(source["BSC_RPC_URL"]).strip(),
                treasury_address=_address(source["BSC_TREASURY_ADDRESS"]),
                token_contract=token,
                min_confirmations=confirmations,
            )
        if config.chain_id != BSC_MAINNET_CHAIN_ID:
            raise PaymentVerificationError("wrong chain")
        if config.token_contract != BSC_USDT_CONTRACT:
            raise PaymentVerificationError("wrong token")
        if config.treasury_address == "0x" + "0" * 40:
            raise PaymentVerificationError("zero treasury address")
    except (PaymentVerificationError, ValueError, TypeError):
        return {
            "configured": False,
            "status": "BSC_CONFIG_INVALID",
            "chain_verified": False,
            "payment_collection_ready": False,
        }
    return {
        "configured": True,
        "status": "BSC_CONFIGURED_CHAIN_UNVERIFIED",
        "chain_verified": False,
        "payment_collection_ready": False,
    }


def verify_checkout_bsc_chain(
    *,
    rpc_call: RpcCall | None = None,
    now: datetime | None = None,
    config: BscUsdtConfig | None = None,
) -> dict[str, Any]:
    """Three first-party READ calls. No request or order may exist yet."""
    if config is None:
        try:
            config = BscUsdtConfig.from_env()
        except (PaymentVerificationError, ValueError) as exc:
            raise CheckoutPaymentPreflightHold("bsc_payment_config_unavailable") from exc
    if (config.chain_id != BSC_MAINNET_CHAIN_ID
            or config.token_contract != BSC_USDT_CONTRACT
            or config.treasury_address == "0x" + "0" * 40):
        raise CheckoutPaymentPreflightHold("bsc_payment_config_invalid")
    rpc = rpc_call or (
        lambda method, params: _rpc_request(config.rpc_url, method, params)
    )
    try:
        anchor = get_block_anchor(config, rpc_call=rpc)
        raw_decimals = rpc(
            "eth_call", [{"to": config.token_contract, "data": DECIMALS_SELECTOR}, "latest"]
        )
        decimals = _hex_int(raw_decimals)
    except (PaymentVerificationError, ValueError, TypeError, OSError, TimeoutError) as exc:
        raise CheckoutPaymentPreflightHold("bsc_chain_read_unavailable") from exc
    if decimals != REQUIRED_DECIMALS:
        raise CheckoutPaymentPreflightHold("bsc_token_decimals_unverified")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise CheckoutPaymentPreflightHold("checkout_clock_untrusted")
    delta = current.astimezone(timezone.utc).timestamp() - anchor["timestamp"]
    if delta < -MAX_CLOCK_AHEAD_SECONDS or delta > MAX_BLOCK_AGE_SECONDS:
        raise CheckoutPaymentPreflightHold("bsc_chain_head_stale")
    return {
        "chain_verified": True,
        "status": "FRESH_BSC_MAINNET_USDT_ANCHOR",
        "block_number": anchor["block_number"],
        "block_age_seconds": round(delta, 3),
        "chain_id": anchor["chain_id"],
        "token_decimals": decimals,
        "payment_execution": False,
        "actual_revenue": False,
        "orders_created": 0,
        "payment_requests_created": 0,
    }
