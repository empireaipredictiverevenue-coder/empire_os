"""Batched Payouts — combine all pending payouts into ONE BSC USDT deeplink.

Instead of N separate transfers (N signatures, N fees, N wallet taps),
build a single BSC Pay deeplink (BEP-20 USDT) that Trust Wallet opens and
signs in one tap. The recipient signs/client submits; the on-chain USDT
transfer settles on BSC. No BSC involvement anywhere.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("batched_payout")

# BEP-20 USDT on BSC (the only rail we use).
USDT_BSC_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
# Six decimals for USDT.
USDT_DECIMALS = 6


@dataclass
class BatchPayoutResult:
    """The combined payout + metadata."""
    batch_id: str = ""
    instruction_count: int = 0
    total_amount_usdc: float = 0.0
    total_amount_cents: int = 0
    recent_blockhash: str = ""        # BSC block number (diagnostics only)
    fee_payer: str = ""               # sender wallet (from client)
    transaction_base64: str = ""      # kept for hub compat (empty on BSC)
    bsc_pay_url: str = ""            # BSC Pay deeplink the user signs
    instructions: list = field(default_factory=list)


def build_batched_payout_tx(
    payouts: list,
    sender_wallet: str,
    mint: str = USDT_BSC_CONTRACT,
    rpc_url: str = "https://bsc-dataseed.binance.org",
    batch_id: str = "",
    blockhash: str = None,
) -> BatchPayoutResult:
    """Build a BSC USDT batched payout deeplink.

    payouts: list of {"payout_id": str, "destination": str, "amount_cents": int}
    Returns a deeplink the user opens in Trust Wallet (BSC) to sign/submit.
    """
    import urllib.request

    # Fetch a recent block number for diagnostics (optional).
    blockhash_str = blockhash or ""
    if not blockhash_str:
        payload = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber",
            "params": [],
        }).encode()
        req = urllib.request.Request(
            rpc_url, data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            blockhash_str = data.get("result", "")
        except Exception as e:
            logger.warning("bsc blockNumber failed: %s", e)
            blockhash_str = ""

    # Tally payouts (BSC USDT uses 6-decimal standard).
    instructions: list = []
    total_cents = 0
    total_usdc = 0.0

    for p in payouts:
        amount_cents = int(p.get("amount_cents", 0))
        if amount_cents <= 0:
            continue
        dest = p.get("destination", "")
        if not dest:
            continue
        amount_usdc = amount_cents / 100.0
        instructions.append({
            "payout_id": p.get("payout_id", ""),
            "destination": dest,
            "amount_usdc": amount_usdc,
        })
        total_cents += amount_cents
        total_usdc += amount_usdc

    result = BatchPayoutResult(
        batch_id=batch_id,
        instruction_count=len(instructions),
        total_amount_usdc=total_usdc,
        total_amount_cents=total_cents,
        recent_blockhash=blockhash_str,
        fee_payer=sender_wallet,
        instructions=instructions,
    )

    # BSC USDT Pay deeplink (Trust Wallet opens and signs on BSC).
    if total_cents > 0:
        result.bsc_pay_url = (
            f"bsc:{sender_wallet}"
            f"?amount={total_usdc:.6f}"
            f"&contract={mint}"
            f"&label=Empire%20OS%20Payouts"
            f"&message={len(instructions)}%20payouts"
        )

    return result


def verify_batched_payout_tx(
    tx_hash: str,
    rpc_url: str = "https://bsc-dataseed.binance.org",
    expected_amount_cents: int = 0,
    expected_memos: Optional[list] = None,
) -> dict:
    """Verify a BSC USDT payout transaction on-chain.

    Checks the receipt for a USDT Transfer log from the sender and sums
    the transferred amount.
    """
    import urllib.request

    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionReceipt",
        "params": [tx_hash],
    }).encode()
    req = urllib.request.Request(
        rpc_url, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return {"verified": False, "error": f"rpc_unreachable: {e}"}

    receipt = data.get("result")
    if not receipt:
        return {"verified": False, "error": "tx_not_found"}

    status = int(receipt.get("status", "0x0"), 16)
    if status != 1:
        return {"verified": False, "error": "tx_failed_on_chain"}

    # Inspect logs for USDT Transfer (topic0 = keccak256 Transfer(address,address,uint256))
    TRANSFER_TOPIC = (
        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    )
    sent_total = 0
    for log in receipt.get("logs", []):
        if log.get("address", "").lower() != USDT_BSC_CONTRACT.lower():
            continue
        topics = log.get("topics", [])
        if not topics or topics[0].lower() != TRANSFER_TOPIC:
            continue
        # amount is the 3rd topic (index 2), 32-byte hex
        raw = int(topics[2], 16)
        sent_total += raw / (10 ** USDT_DECIMALS)

    expected_usdt = expected_amount_cents / 100.0
    if expected_usdt and sent_total + 1e-6 < expected_usdt:
        return {
            "verified": False,
            "error": f"amount_short: sent {sent_total} < expected {expected_usdt}",
        }

    return {"verified": True, "amount_usdt": sent_total}
