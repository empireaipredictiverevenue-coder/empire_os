"""Fail-closed verifier for Empire BSC USDT smart-contract escrow events."""
from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from empire_os.bsc_usdt_verifier import (
    BSC_MAINNET_CHAIN_ID, BSC_USDT_CONTRACT, TRANSFER_TOPIC,
    PaymentVerificationError, _address, _hex_int, _rpc_request,
    _topic_address, _tx_hash, _validate_hex,
)

ESCROW_CREATED_TOPIC = "0xa059c713430165273f3068baf286a05928bcf10e7e11b90e8269b11ed451bcdf"
ESCROW_FUNDED_TOPIC = "0xb0f7b6ab70e0186c433938ee752b2498a7cab42018e6bf7596cd704c81c470bc"
ESCROW_RELEASED_TOPIC = "0x3a9c1cd29cd3be251a72ce3c367c27dc1cb697ac4589965b76a83f9a25ca0710"
ESCROW_REFUNDED_TOPIC = "0xfc31a7ddbe933aa6e67f3c98c183fbc87addd2b602fcfb10238d2f85cf026617"
ACTION_TOPICS = {
    "funded": ESCROW_FUNDED_TOPIC,
    "released": ESCROW_RELEASED_TOPIC,
    "refunded": ESCROW_REFUNDED_TOPIC,
}


def escrow_id_from_uuid(value: str) -> str:
    text = str(value or "").replace("-", "").lower()
    if len(text) != 32 or any(c not in "0123456789abcdef" for c in text):
        raise PaymentVerificationError("invalid escrow UUID")
    return "0x" + "0" * 32 + text

@dataclass(frozen=True)
class BscEscrowConfig:
    rpc_url: str
    escrow_contract: str
    beneficiary: str
    runtime_sha256: str
    min_confirmations: int = 12
    chain_id: int = BSC_MAINNET_CHAIN_ID

    @classmethod
    def from_env(cls) -> "BscEscrowConfig":
        rpc = os.getenv("BSC_RPC_URL", "").strip()
        escrow = os.getenv("BSC_ESCROW_CONTRACT", "").strip()
        beneficiary = os.getenv("BSC_ESCROW_BENEFICIARY", "").strip()
        code_hash = os.getenv("BSC_ESCROW_RUNTIME_SHA256", "").strip().lower()
        try:
            confirmations = int(os.getenv("BSC_MIN_CONFIRMATIONS", "12"))
        except ValueError as exc:
            raise PaymentVerificationError("BSC_MIN_CONFIRMATIONS must be an integer") from exc
        if not rpc or not escrow or not beneficiary:
            raise PaymentVerificationError("BSC escrow RPC, contract, and beneficiary are required")
        if len(code_hash) != 64 or any(c not in "0123456789abcdef" for c in code_hash):
            raise PaymentVerificationError("BSC escrow runtime SHA256 is required")
        if confirmations < 12:
            raise PaymentVerificationError("escrow evidence requires at least 12 confirmations")
        return cls(rpc, _address(escrow), _address(beneficiary), code_hash, confirmations)


@dataclass(frozen=True)
class EscrowEvidence:
    verified: bool
    action: str
    transaction_hash: str
    escrow_id: str
    amount_raw: int
    party_address: str
    block_number: int
    block_hash: str
    confirmations: int
    block_timestamp: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def _runtime_hash(code_hex: str) -> str:
    raw = _validate_hex(code_hex, len(str(code_hex)), "runtime bytecode")
    if len(raw) <= 2 or (len(raw) - 2) % 2:
        raise PaymentVerificationError("invalid runtime bytecode")
    return hashlib.sha256(bytes.fromhex(raw[2:])).hexdigest()


def _expected_raw(amount: Decimal | str | int | float) -> int:
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, ValueError) as exc:
        raise PaymentVerificationError("invalid escrow amount") from exc
    if not value.is_finite() or value <= 0:
        raise PaymentVerificationError("escrow amount must be finite and positive")
    numerator, denominator = value.as_integer_ratio()
    raw, remainder = divmod(numerator * 10**18, denominator)
    if remainder:
        raise PaymentVerificationError("escrow amount exceeds BSC USDT precision")
    return raw


def _event_amount(data: Any) -> int:
    return int(_validate_hex(data, 66, "escrow event amount"), 16)


def _event_party(topic: Any) -> str:
    return _topic_address(str(topic or ""))

def verify_escrow_action(
    config: BscEscrowConfig,
    transaction_hash: str,
    escrow_id: str,
    expected_amount: Decimal | str | int | float,
    *,
    action: str,
    expected_payer: str | None = None,
    rpc_call: Callable[[str, list[Any]], Any] | None = None,
) -> EscrowEvidence:
    if action not in ACTION_TOPICS:
        raise PaymentVerificationError("unsupported escrow action")
    tx_hash = _tx_hash(transaction_hash)
    escrow = _address(config.escrow_contract)
    beneficiary = _address(config.beneficiary)
    escrow_id = _validate_hex(escrow_id, 66, "escrow id")
    payer = _address(expected_payer) if expected_payer else None
    expected_raw = _expected_raw(expected_amount)
    if config.chain_id != BSC_MAINNET_CHAIN_ID or config.min_confirmations < 12:
        raise PaymentVerificationError("invalid escrow verifier chain configuration")

    raw_rpc = rpc_call or (lambda method, params: _rpc_request(config.rpc_url, method, params))
    if _hex_int(raw_rpc("eth_chainId", [])) != config.chain_id:
        raise PaymentVerificationError("wrong chain id")
    code = raw_rpc("eth_getCode", [escrow, "latest"])
    if _runtime_hash(code) != config.runtime_sha256:
        raise PaymentVerificationError("escrow runtime code fingerprint mismatch")
    tx = raw_rpc("eth_getTransactionByHash", [tx_hash])
    receipt = raw_rpc("eth_getTransactionReceipt", [tx_hash])
    if not isinstance(tx, dict) or not isinstance(receipt, dict):
        raise PaymentVerificationError("escrow transaction not found")
    if _tx_hash(tx.get("hash")) != tx_hash or _tx_hash(receipt.get("transactionHash")) != tx_hash:
        raise PaymentVerificationError("escrow transaction hash mismatch")
    if _address(tx.get("to")) != escrow:
        raise PaymentVerificationError("transaction did not call configured escrow")
    if _hex_int(receipt.get("status")) != 1:
        raise PaymentVerificationError("escrow transaction failed")

    block_number = _hex_int(receipt.get("blockNumber"))
    block_hash = _tx_hash(receipt.get("blockHash"))
    if _tx_hash(tx.get("blockHash")) != block_hash or _hex_int(tx.get("blockNumber")) != block_number:
        raise PaymentVerificationError("escrow transaction block mismatch")
    if action == "funded":
        if payer is None or _address(tx.get("from")) != payer:
            raise PaymentVerificationError("escrow funding payer mismatch")
        expected_party = payer
        transfer_from, transfer_to = payer, escrow
    elif action == "released":
        expected_party = beneficiary
        transfer_from, transfer_to = escrow, beneficiary
    else:
        if payer is None:
            raise PaymentVerificationError("refund verification requires payer")
        expected_party = payer
        transfer_from, transfer_to = escrow, payer
    event_matches = 0
    transfer_matches = 0
    logs = receipt.get("logs")
    if not isinstance(logs, list):
        raise PaymentVerificationError("escrow receipt logs missing")
    for log in logs:
        if not isinstance(log, dict) or log.get("removed") is not False:
            continue
        log_address = _address(log.get("address"))
        topics = log.get("topics")
        if not isinstance(topics, list) or not topics:
            continue
        if (_tx_hash(log.get("transactionHash")) != tx_hash
                or _tx_hash(log.get("blockHash")) != block_hash
                or _hex_int(log.get("blockNumber")) != block_number):
            raise PaymentVerificationError("escrow log provenance mismatch")

        if log_address == escrow and str(topics[0]).lower() == ACTION_TOPICS[action]:
            if len(topics) != 3:
                raise PaymentVerificationError("invalid escrow event topics")
            if _validate_hex(topics[1], 66, "escrow event id") != escrow_id:
                continue
            if _event_party(topics[2]) != expected_party or _event_amount(log.get("data")) != expected_raw:
                raise PaymentVerificationError("escrow event terms mismatch")
            event_matches += 1
        if log_address == BSC_USDT_CONTRACT and str(topics[0]).lower() == TRANSFER_TOPIC:
            if len(topics) != 3:
                raise PaymentVerificationError("invalid USDT transfer topics")
            if _topic_address(topics[1]) != transfer_from or _topic_address(topics[2]) != transfer_to:
                continue
            if int(_validate_hex(log.get("data"), 66, "USDT transfer amount"), 16) != expected_raw:
                raise PaymentVerificationError("USDT transfer amount mismatch")
            transfer_matches += 1

    if event_matches != 1 or transfer_matches != 1:
        raise PaymentVerificationError("escrow event and USDT transfer must match exactly once")

    latest = _hex_int(raw_rpc("eth_blockNumber", []))
    confirmations = max(latest - block_number + 1, 0)
    if confirmations < config.min_confirmations:
        raise PaymentVerificationError("insufficient escrow confirmations")
    canonical = raw_rpc("eth_getBlockByNumber", [hex(block_number), False])
    if (not isinstance(canonical, dict)
            or _tx_hash(canonical.get("hash")) != block_hash
            or _hex_int(canonical.get("number")) != block_number):
        raise PaymentVerificationError("escrow block is no longer canonical")

    block_timestamp = _hex_int(canonical.get("timestamp"))
    return EscrowEvidence(
        True, action, tx_hash, escrow_id, expected_raw, expected_party,
        block_number, block_hash, confirmations, block_timestamp,
    )

@dataclass(frozen=True)
class EscrowCreatedEvidence:
    verified: bool
    transaction_hash: str
    escrow_id: str
    payer_address: str
    amount_raw: int
    terms_hash: str
    funding_deadline: int
    refund_after: int
    block_number: int
    block_hash: str
    confirmations: int
    block_timestamp: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _decode_created_data(data: Any) -> tuple[int, int, int]:
    raw = _validate_hex(data, 194, "EscrowCreated data")[2:]
    amount = int(raw[0:64], 16)
    funding_deadline = int(raw[64:128], 16)
    refund_after = int(raw[128:192], 16)
    return amount, funding_deadline, refund_after

def verify_escrow_created(
    config: BscEscrowConfig,
    transaction_hash: str,
    escrow_id: str,
    expected_amount: Decimal | str | int | float,
    expected_payer: str,
    expected_terms_hash: str,
    *, rpc_call: Callable[[str, list[Any]], Any] | None = None,
) -> EscrowCreatedEvidence:
    tx_hash = _tx_hash(transaction_hash)
    escrow = _address(config.escrow_contract)
    escrow_id = _validate_hex(escrow_id, 66, "escrow id")
    payer = _address(expected_payer)
    terms_hash = _validate_hex(expected_terms_hash, 66, "terms hash")
    amount_raw = _expected_raw(expected_amount)
    if config.chain_id != BSC_MAINNET_CHAIN_ID or config.min_confirmations < 12:
        raise PaymentVerificationError("invalid escrow verifier chain configuration")
    raw_rpc = rpc_call or (lambda method, params: _rpc_request(config.rpc_url, method, params))
    if _hex_int(raw_rpc("eth_chainId", [])) != config.chain_id:
        raise PaymentVerificationError("wrong chain id")
    if _runtime_hash(raw_rpc("eth_getCode", [escrow, "latest"])) != config.runtime_sha256:
        raise PaymentVerificationError("escrow runtime code fingerprint mismatch")
    tx = raw_rpc("eth_getTransactionByHash", [tx_hash])
    receipt = raw_rpc("eth_getTransactionReceipt", [tx_hash])
    if not isinstance(tx, dict) or not isinstance(receipt, dict):
        raise PaymentVerificationError("escrow creation transaction not found")
    if _tx_hash(tx.get("hash")) != tx_hash or _tx_hash(receipt.get("transactionHash")) != tx_hash:
        raise PaymentVerificationError("escrow creation transaction hash mismatch")
    if _address(tx.get("to")) != escrow or _hex_int(receipt.get("status")) != 1:
        raise PaymentVerificationError("escrow creation call failed or wrong contract")
    block_number = _hex_int(receipt.get("blockNumber"))
    block_hash = _tx_hash(receipt.get("blockHash"))
    if _tx_hash(tx.get("blockHash")) != block_hash or _hex_int(tx.get("blockNumber")) != block_number:
        raise PaymentVerificationError("escrow creation block mismatch")

    found = None
    logs = receipt.get("logs")
    if not isinstance(logs, list):
        raise PaymentVerificationError("escrow creation logs missing")
    for log in logs:
        if not isinstance(log, dict) or log.get("removed") is not False:
            continue
        if _address(log.get("address")) != escrow:
            continue
        topics = log.get("topics")
        if not isinstance(topics, list) or len(topics) != 4:
            continue
        if str(topics[0]).lower() != ESCROW_CREATED_TOPIC:
            continue
        if _validate_hex(topics[1], 66, "escrow created id") != escrow_id:
            continue
        if _event_party(topics[2]) != payer:
            raise PaymentVerificationError("escrow created payer mismatch")
        if _validate_hex(topics[3], 66, "escrow created terms hash") != terms_hash:
            raise PaymentVerificationError("escrow created terms hash mismatch")
        amount, funding_deadline, refund_after = _decode_created_data(log.get("data"))
        if amount != amount_raw:
            raise PaymentVerificationError("escrow created amount mismatch")
        if (_tx_hash(log.get("transactionHash")) != tx_hash
                or _tx_hash(log.get("blockHash")) != block_hash
                or _hex_int(log.get("blockNumber")) != block_number):
            raise PaymentVerificationError("escrow created log provenance mismatch")
        if found is not None:
            raise PaymentVerificationError("multiple matching escrow creation events")
        found = (funding_deadline, refund_after)

    if found is None:
        raise PaymentVerificationError("matching escrow creation event not found")
    funding_deadline, refund_after = found
    latest = _hex_int(raw_rpc("eth_blockNumber", []))
    confirmations = max(latest - block_number + 1, 0)
    if confirmations < config.min_confirmations:
        raise PaymentVerificationError("insufficient escrow creation confirmations")
    canonical = raw_rpc("eth_getBlockByNumber", [hex(block_number), False])
    if (not isinstance(canonical, dict)
            or _tx_hash(canonical.get("hash")) != block_hash
            or _hex_int(canonical.get("number")) != block_number):
        raise PaymentVerificationError("escrow creation block is no longer canonical")
    block_timestamp = _hex_int(canonical.get("timestamp"))
    if not (block_timestamp < funding_deadline < refund_after):
        raise PaymentVerificationError("invalid on-chain escrow deadlines")

    return EscrowCreatedEvidence(
        True, tx_hash, escrow_id, payer, amount_raw, terms_hash,
        funding_deadline, refund_after, block_number, block_hash,
        confirmations, block_timestamp,
    )


def _verified_at_iso(now: Any = None) -> str:
    from datetime import datetime, timezone
    if now is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(now, datetime):
        dt = now.astimezone(timezone.utc)
    else:
        raise PaymentVerificationError("verified_at must be a datetime")
    return dt.isoformat().replace("+00:00", "Z")


def creation_record_payload(
    config: BscEscrowConfig,
    evidence: EscrowCreatedEvidence,
    *, verified_at: Any = None,
) -> dict[str, Any]:
    payload = evidence.to_dict()
    payload.update({
        "contract_address": _address(config.escrow_contract),
        "beneficiary_address": _address(config.beneficiary),
        "runtime_sha256": config.runtime_sha256,
        "verified_at": _verified_at_iso(verified_at),
    })
    return payload


def lifecycle_record_payload(
    evidence: EscrowEvidence,
    *, verified_at: Any = None,
) -> dict[str, Any]:
    payload = evidence.to_dict()
    payload["verified_at"] = _verified_at_iso(verified_at)
    return payload
