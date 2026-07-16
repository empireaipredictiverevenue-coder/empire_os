#!/usr/bin/env python3
"""payout — Solana USDC payout engine for Empire OS (hub-side only).

Uses solders (already installed, pure prebuilt wheels, no Rust) to build +
sign USDC transfers, and httpx for RPC. All signing happens HERE, inside the
hub billing path — never in a webhook.

SPL Token `transfer_checked` instruction is built by hand (no spl-token pip
package required): index 12, then u64 amount (LE) + u8 decimals.

Testnet-first: set SOLANA_RPC_URL to devnet + a devnet-funded payer to
validate the flow before pointing at mainnet.

Functions:
  usdc_transfer(payer_secret_b58, sender_ata, recipient_ata, amount_usd) -> sig
  pay_invoice(invoice_id)  -> marks si_ppc_invoices paid on confirmed tx
"""
from __future__ import annotations
import os, sqlite3, logging, base58, struct, json, asyncio
from decimal import Decimal
import httpx
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.message import MessageV0
from solders.transaction import VersionedTransaction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("empire_payout")

SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com")
USDC_MINT = Pubkey.from_string(os.getenv("USDC_MINT", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"))
USDC_DECIMALS = 6
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
# Payer secret (base58) kept server-side ONLY. Never exposed via API/webhook.
PAYER_SECRET_B58 = os.getenv("SOLANA_PAYER_SECRET", "")


def _transfer_checked_ix(src: Pubkey, mint: Pubkey, dst: Pubkey,
                         owner: Pubkey, amount_raw: int) -> Instruction:
    """Hand-built SPL Token transfer_checked (instruction index 12)."""
    data = struct.pack("<BQb", 12, amount_raw, USDC_DECIMALS)
    return Instruction(
        program_id=TOKEN_PROGRAM_ID,
        accounts=[
            AccountMeta(pubkey=src, is_signer=False, is_writable=True),
            AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=dst, is_signer=False, is_writable=True),
            AccountMeta(pubkey=owner, is_signer=True, is_writable=False),
        ],
        data=data,
    )


async def usdc_transfer(payer_secret_b58: str, sender_ata: str,
                        recipient_ata: str, amount_usd: float) -> str:
    """Send `amount_usd` USDC from sender_ata -> recipient_ata. Returns tx sig."""
    if not payer_secret_b58:
        raise RuntimeError("SOLANA_PAYER_SECRET not set — payout aborted (safe).")
    payer = Keypair.from_bytes(base58.b58decode(payer_secret_b58))
    amount_raw = int(Decimal(str(amount_usd)) * (10 ** USDC_DECIMALS))
    async with httpx.AsyncClient(timeout=30) as client:
        # latest blockhash
        r = await client.post(SOLANA_RPC_URL, json={
            "jsonrpc": "2.0", "id": 1, "method": "getLatestBlockhash",
            "params": [{"commitment": "finalized"}]})
        bh = r.json()["result"]["value"]["blockhash"]
        ix = _transfer_checked_ix(Pubkey.from_string(sender_ata), USDC_MINT,
                                  Pubkey.from_string(recipient_ata), payer.pubkey(), amount_raw)
        msg = MessageV0.try_compile(payer.pubkey(), [ix], [], bh)
        txn = VersionedTransaction(msg, [payer])
        raw = base58.b58encode(txn.serialize()).decode()
        # send
        r2 = await client.post(SOLANA_RPC_URL, json={
            "jsonrpc": "2.0", "id": 1, "method": "sendTransaction",
            "params": [raw, {"encoding": "base64", "preflightCommitment": "confirmed"}]})
        sig = r2.json().get("result")
        if not sig:
            raise RuntimeError(f"sendTransaction failed: {r2.json().get('error')}")
        logger.info("USDC payout %s -> %s : %s USDC | sig %s",
                    sender_ata, recipient_ata, amount_usd, sig)
        return sig


async def pay_invoice(invoice_id: str, sender_ata: str, recipient_ata: str,
                      amount_usd: float, db_path: str = "/root/empire_os/empire_os.db"):
    """Pay a validated invoice and mark it paid on confirmed on-chain tx."""
    sig = await usdc_transfer(PAYER_SECRET_B58, sender_ata, recipient_ata, amount_usd)
    c = sqlite3.connect(db_path, timeout=15)
    c.execute("UPDATE si_ppc_invoices SET status='paid', metadata=? WHERE invoice_id=?",
              (f"paid {sig}", invoice_id))
    c.commit(); c.close()
    logger.info("invoice %s marked paid (sig %s)", invoice_id, sig)
    return sig


class PayoutEngine:
    """Hub-facing wrapper around the USDC payout functions."""

    def __init__(self, payer_secret_b58: str = "", rpc_url: str = ""):
        self.payer_secret_b58 = payer_secret_b58 or PAYER_SECRET_B58
        self.rpc_url = rpc_url or SOLANA_RPC_URL

    async def usdc_transfer(self, sender_ata, recipient_ata, amount_usd):
        return await usdc_transfer(self.payer_secret_b58, sender_ata, recipient_ata, amount_usd)

    async def pay_invoice(self, invoice_id, sender_ata, recipient_ata, amount_usd, db_path=None):
        return await pay_invoice(invoice_id, sender_ata, recipient_ata, amount_usd,
                                 db_path or "/root/empire_os/empire_os.db")
