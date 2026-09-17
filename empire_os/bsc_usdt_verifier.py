"""Fail-closed BNB Smart Chain USDT payment verification.

This module never signs or broadcasts transactions. It only reads chain state
and verifies evidence against an expected Empire payment request.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

BSC_MAINNET_CHAIN_ID = 56
BSC_USDT_CONTRACT = "0x55d398326f99059ff775485246999027b3197955"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
DECIMALS_SELECTOR = "0x313ce567"


class PaymentVerificationError(RuntimeError):
    pass


def _validate_hex(value: str | None, length: int, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != length or not text.startswith("0x"):
        raise PaymentVerificationError(f"invalid {label}")
    if any(char not in "0123456789abcdef" for char in text[2:]):
        raise PaymentVerificationError(f"invalid {label}")
    return text


def _address(value: str | None) -> str:
    return _validate_hex(value, 42, "EVM address")


def _tx_hash(value: str | None) -> str:
    return _validate_hex(value, 66, "transaction hash")


@dataclass(frozen=True)
class BscUsdtConfig:
    rpc_url: str
    treasury_address: str
    token_contract: str
    min_confirmations: int = 12
    chain_id: int = BSC_MAINNET_CHAIN_ID

    @classmethod
    def from_env(cls) -> "BscUsdtConfig":
        rpc = os.getenv("BSC_RPC_URL", "").strip()
        treasury = os.getenv("BSC_TREASURY_ADDRESS", "").strip()
        token = os.getenv("BSC_USDT_TOKEN_CONTRACT", BSC_USDT_CONTRACT).strip()
        if not rpc or not treasury:
            raise PaymentVerificationError("BSC_RPC_URL and BSC_TREASURY_ADDRESS are required")
        token = _address(token)
        if token != BSC_USDT_CONTRACT:
            raise PaymentVerificationError("token contract is not canonical BSC USDT")
        try:
            min_confirmations = int(os.getenv("BSC_MIN_CONFIRMATIONS", "12"))
        except ValueError as exc:
            raise PaymentVerificationError("BSC_MIN_CONFIRMATIONS must be an integer") from exc
        if min_confirmations < 1:
            raise PaymentVerificationError("BSC_MIN_CONFIRMATIONS must be positive")
        return cls(
            rpc_url=rpc,
            treasury_address=_address(treasury),
            token_contract=token,
            min_confirmations=min_confirmations,
        )


@dataclass(frozen=True)
class PaymentEvidence:
    verified: bool
    transaction_hash: str
    chain_id: int
    token_contract: str
    treasury_address: str
    sender_address: str | None
    token_decimals: int | None
    amount_raw: int | None
    amount_token: str | None
    block_number: int | None
    confirmations: int
    reason: str
    block_hash: str = ""
    log_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rpc_request(rpc_url: str, method: str, params: list[Any]) -> Any:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(
        rpc_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode())
    if payload.get("error"):
        raise PaymentVerificationError(f"rpc error for {method}: {payload['error']}")
    return payload.get("result")


def _hex_int(value: Any) -> int:
    if value in (None, ""):
        raise PaymentVerificationError("missing hex integer")
    try:
        parsed = int(str(value), 16)
    except (TypeError, ValueError) as exc:
        raise PaymentVerificationError("invalid hex integer") from exc
    if parsed < 0:
        raise PaymentVerificationError("negative hex integer")
    return parsed


def _topic_address(topic: str) -> str:
    text = str(topic or "").lower()
    _validate_hex(text, 66, "address topic")
    if text[2:26] != "0" * 24:
        raise PaymentVerificationError("invalid address topic padding")
    return _address("0x" + text[-40:])


def _token_decimals(config: BscUsdtConfig, rpc: Callable[[str, list[Any]], Any]) -> int:
    raw = rpc("eth_call", [{"to": config.token_contract, "data": DECIMALS_SELECTOR}, "latest"])
    decimals = _hex_int(raw)
    if decimals < 0 or decimals > 36:
        raise PaymentVerificationError("implausible token decimals")
    return decimals


def verify_payment(
    config: BscUsdtConfig,
    transaction_hash: str,
    expected_amount: Decimal | str | float | int,
    *,
    expected_payer: str | None = None,
    rpc_call: Callable[[str, list[Any]], Any] | None = None,
) -> PaymentEvidence:
    tx_hash = _tx_hash(transaction_hash)
    treasury = _address(config.treasury_address)
    token = _address(config.token_contract)
    if config.chain_id != BSC_MAINNET_CHAIN_ID:
        raise PaymentVerificationError("configured chain is not BSC mainnet")
    if token != BSC_USDT_CONTRACT:
        raise PaymentVerificationError("configured token is not canonical BSC USDT")
    if config.min_confirmations < 1:
        raise PaymentVerificationError("minimum confirmations must be positive")
    payer = _address(expected_payer) if expected_payer else None
    try:
        expected = Decimal(str(expected_amount))
    except (InvalidOperation, ValueError) as exc:
        raise PaymentVerificationError("invalid expected amount") from exc
    if not expected.is_finite() or expected <= 0:
        raise PaymentVerificationError("expected amount must be finite and positive")

    raw_rpc = rpc_call or (lambda method, params: _rpc_request(config.rpc_url, method, params))
    chain_id = _hex_int(raw_rpc("eth_chainId", []))
    if chain_id != config.chain_id:
        raise PaymentVerificationError(f"wrong chain id: {chain_id}")

    tx = raw_rpc("eth_getTransactionByHash", [tx_hash])
    receipt = raw_rpc("eth_getTransactionReceipt", [tx_hash])
    if not isinstance(tx, dict) or not isinstance(receipt, dict):
        raise PaymentVerificationError("transaction not found")
    if _tx_hash(tx.get("hash")) != tx_hash or _tx_hash(receipt.get("transactionHash")) != tx_hash:
        raise PaymentVerificationError("RPC transaction hash mismatch")
    if _hex_int(receipt.get("status")) != 1:
        raise PaymentVerificationError("transaction failed on chain")

    sender = _address(tx.get("from"))
    if payer and sender != payer:
        raise PaymentVerificationError("transaction sender does not match expected payer")

    block_number = _hex_int(receipt.get("blockNumber"))
    block_hash = _tx_hash(receipt.get("blockHash"))
    if (_tx_hash(tx.get("blockHash")) != block_hash
            or _hex_int(tx.get("blockNumber")) != block_number):
        raise PaymentVerificationError("transaction and receipt block mismatch")
    decimals = _token_decimals(config, raw_rpc)
    # Integer ratios avoid rounding through the process-wide Decimal context.
    numerator, denominator = expected.as_integer_ratio()
    expected_raw, remainder = divmod(numerator * 10 ** decimals, denominator)
    if remainder:
        raise PaymentVerificationError("expected amount exceeds token precision")
    if expected_raw > 2 ** 256 - 1:
        raise PaymentVerificationError("expected amount exceeds uint256")
    matched_index = None
    matched_raw = 0
    matched_from: str | None = None

    logs = receipt.get("logs")
    if not isinstance(logs, list):
        raise PaymentVerificationError("receipt logs are missing or invalid")

    for log in logs:
        if not isinstance(log, dict) or _address(log.get("address")) != token:
            continue
        topics = log.get("topics") or []
        if not isinstance(topics, list) or not topics or str(topics[0]).lower() != TRANSFER_TOPIC:
            continue
        if len(topics) != 3:
            raise PaymentVerificationError("invalid Transfer topics")
        if log.get("removed") is not False:
            raise PaymentVerificationError("removed or unconfirmed log")
        if (_tx_hash(log.get("transactionHash")) != tx_hash
                or _tx_hash(log.get("blockHash")) != block_hash
                or _hex_int(log.get("blockNumber")) != block_number):
            raise PaymentVerificationError("log provenance mismatch")
        transfer_from = _topic_address(topics[1])
        transfer_to = _topic_address(topics[2])
        if transfer_to != treasury:
            continue
        if payer and transfer_from != payer:
            continue
        amount_raw = int(_validate_hex(log.get("data"), 66, "transfer data"), 16)
        log_index = _hex_int(log.get("logIndex"))
        if amount_raw > matched_raw:
            matched_raw = amount_raw
            matched_from = transfer_from
            matched_index = log_index

    if matched_raw < expected_raw:
        raise PaymentVerificationError("no qualifying USDT transfer to treasury")

    block_number = _hex_int(receipt.get("blockNumber"))
    latest_block = _hex_int(raw_rpc("eth_blockNumber", []))
    confirmations = max(latest_block - block_number + 1, 0)
    if confirmations < config.min_confirmations:
        raise PaymentVerificationError(
            f"insufficient confirmations: {confirmations}/{config.min_confirmations}"
        )

    canonical = raw_rpc("eth_getBlockByNumber", [hex(block_number), False])
    if (not isinstance(canonical, dict)
            or _tx_hash(canonical.get("hash")) != block_hash
            or _hex_int(canonical.get("number")) != block_number):
        raise PaymentVerificationError("receipt block is no longer canonical")
    digits = str(matched_raw).zfill(decimals + 1)
    amount = (digits[:-decimals] + "." + digits[-decimals:]).rstrip("0").rstrip(".") if decimals else digits
    return PaymentEvidence(
        verified=True,
        transaction_hash=tx_hash,
        chain_id=chain_id,
        token_contract=token,
        treasury_address=treasury,
        sender_address=matched_from or sender,
        token_decimals=decimals,
        amount_raw=matched_raw,
        amount_token=amount,
        block_number=block_number,
        confirmations=confirmations,
        reason="verified_bsc_usdt_transfer",
        block_hash=block_hash,
        log_index=matched_index,
    )
