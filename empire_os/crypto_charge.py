"""
Crypto charge - USDC-on-Solana payment collector.

Different than Stripe/PayPal: cards are pushed to us. Crypto must
be PUSHED by the buyer. Our job is to reconcile + record.

Flow for Head 2 / Head 1 / Head 4 crypto billing:
  1. Charge triggers (call_tick at 90s, etc.)
  2. We generate a payment-expected record:
        amount_usdc, our memo = "INV_<head>_<inv_id>_<charge_id>"
        buyer_wallet = si_buyer_payment_methods[customer_ref=walled]
  3. We POST it to the hub at /v1/ppc/expect_payment so other
     listeners (vendor agent, /products, /outreach emails) can
     send the buyer the request-to-pay link
  4. We poll the Solana RPC for incoming USDC transfers to the
     vault (using the SOLANA_VAULT_WALLET + USDC_MINT env vars)
     matching our memo
  5. When the transfer arrives, we mark si_charges.paid_at +
     si_ppc_invoices.status='paid' + emit a 'settled' event.

Real money actually moves because this is on-chain. No Stripe
needed. The payer just needs SOL for gas (~0.000005 SOL = ~$0.001).
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DB = "/root/empire_os/empire_os.db"
SOLANA_RPC = os.environ.get(
    "SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
USDC_MINT = os.environ.get(
    "USDC_MINT", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
SOLANA_VAULT = os.environ.get(
    "SOLANA_VAULT_WALLET",
    "egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM")
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rpc(method: str, params: list) -> dict:
    """Call Solana JSON-RPC. Returns dict with 'result' or 'error'."""
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method,
         "params": params}).encode()
    req = urllib.request.Request(
        SOLANA_RPC + ("/" if "?" not in SOLANA_RPC else ""),
        data=body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"http {e.code}", "body": e.read().decode()[:200]}
    except Exception as e:
        return {"error": str(e)[:200]}


def build_expected_payment(buyer_wallet: str, amount_usdc: float,
                          memo: str) -> dict:
    """Return the payment request that we'd send to the buyer.

    Buyer authorizes by sending one USDC transfer to our vault
    with the memo in the SPL token transfer's `memo` instruction
    (Solana memo program) OR by using invoice_id in the
    reference.
    """
    return {
        "from": buyer_wallet,
        "to": SOLANA_VAULT,
        "amount_usdc": round(amount_usdc, 6),
        "amount_micro": int(round(amount_usdc * 1_000_000)),
        "token_mint": USDC_MINT,
        "memo": memo,
        "solana_pay_url": (
            f"solana:{SOLANA_VAULT}"
            f"?amount={int(round(amount_usdc * 1_000_000))}"
            f"&spl-token={USDC_MINT}"
            f"&label={urllib.parse.quote(memo)}"
            f"&message=Empire+OS"
        ),
    }


def get_buyer_wallet(buyer_id: str) -> Optional[str]:
    """Get the buyer's crypto wallet from si_buyer_payment_methods."""
    con = sqlite3.connect(DB)
    row = con.execute(
        "SELECT customer_ref FROM si_buyer_payment_methods "
        "WHERE buyer_id=? AND processor='usdc' AND is_default=1 "
        "AND deleted_at IS NULL ORDER BY id DESC LIMIT 1",
        (buyer_id,)).fetchone()
    con.close()
    return row[0] if row else None


def fetch_token_accounts(owner: str) -> list[dict]:
    """RPC: getTokenAccountsByOwner for USDC mint.

    Returns list of {pubkey, mint, amount, decimals}.
    """
    res = _rpc("getTokenAccountsByOwner", [
        owner,
        {"programId": TOKEN_PROGRAM_ID},
        {"encoding": "jsonParsed"},
    ])
    if "error" in res:
        return []
    out = []
    for acct in res.get("result", {}).get("value", []):
        info = acct.get("account", {}).get("data", {}).get(
            "parsed", {}).get("info", {})
        out.append({
            "pubkey": acct.get("pubkey"),
            "mint": info.get("mint"),
            "amount": float(info.get("tokenAmount", {}).get(
                "uiAmount", 0) or 0),
            "amount_raw": int(info.get("tokenAmount", {}).get(
                "amount", 0)),
            "decimals": info.get("tokenAmount", {}).get("decimals"),
            "owner": info.get("owner"),
        })
    return out


def fetch_vault_recent_inbound(memo_starts_with: str = "",
                               lookback_seconds: int = 86400) -> list[dict]:
    """Fetch recent SPL token transfers INTO the vault.

    Uses getSignaturesForAddress + getTransaction to pull each tx,
    parses the SPL token transfer amount + memo.

    Filters by memo_starts_with (e.g. 'INV_1_') if provided.
    """
    sigs = _rpc("getSignaturesForAddress", [
        SOLANA_VAULT,
        {"limit": 50, "commitment": "finalized"},
    ])
    if "error" in sigs:
        return []
    out = []
    for s in sigs.get("result", [])[:50]:
        sig = s.get("signature")
        block_time = s.get("blockTime", 0)
        if not sig or abs(time.time() - block_time) > lookback_seconds:
            continue
        tx = _rpc("getTransaction", [
            sig,
            {"encoding": "jsonParsed",
             "commitment": "finalized",
             "maxSupportedTransactionVersion": 0},
        ])
        if "error" in tx or not tx.get("result"):
            continue
        msg = tx["result"].get("transaction", {}).get(
            "message", {})
        meta = tx["result"].get("meta", {})
        # find token transfers TO vault
        for inner in msg.get("instructions", []):
            parsed = inner.get("parsed", {})
            if parsed.get("type") == "transferChecked":
                info = parsed.get("info", {})
                if info.get("destination") == SOLANA_VAULT:
                    memo = meta.get("memoInstructions", [{}])
                    memo_str = ""
                    if meta.get("memoInstructions"):
                        m = meta["memoInstructions"][-1].get("memo", "")
                        if isinstance(m, str):
                            memo_str = m
                    if (memo_starts_with and not memo_str.startswith(
                            memo_starts_with)):
                        continue
                    out.append({
                        "signature": sig,
                        "block_time": block_time,
                        "from": info.get("source"),
                        "amount": float(info.get("tokenAmount", {}).get(
                            "uiAmount", 0) or 0),
                        "amount_raw": int(info.get(
                            "tokenAmount", {}).get("amount", 0)),
                        "decimals": info.get("tokenAmount", {}).get(
                            "decimals"),
                        "memo": memo_str,
                    })
    return out


def charge_crypto(buyer_id: str, head: int, reason: str,
                  amount_usdc: float,
                  call_id: str = "", lead_id: str = "") -> dict:
    """Generate a crypto payment request + reconcile if already paid.

    Returns ChargeResult-shaped dict (status=simulated if we
    cannot detect inbound yet, status=succeeded if matched).
    """
    invoice_id = "inv_crypto_" + os.urandom(4).hex()
    charge_id = "chg_crypto_" + os.urandom(4).hex()
    memo = f"INV_{invoice_id}"
    wallet = get_buyer_wallet(buyer_id)
    if not wallet:
        return {"ok": False, "error": "no_buyer_wallet",
                "status": "failed",
                "charge_id": charge_id, "invoice_id": invoice_id}
    pay_req = build_expected_payment(wallet, amount_usdc, memo)
    # Try reconcile against recent inbound
    inbound = fetch_vault_recent_inbound(memo_starts_with=memo[:10],
                                          lookback_seconds=86400)
    matched = None
    for tx in inbound:
        if tx.get("amount", 0) >= amount_usdc * 0.99:
            matched = tx
            break
    status = "succeeded" if matched else "simulated"
    paid_at = (datetime.fromtimestamp(
        matched["block_time"], tz=timezone.utc).isoformat()
        if matched else None)
    # Persist locally
    con = sqlite3.connect(DB)
    con.execute(
        "INSERT OR IGNORE INTO si_charges "
        "(charge_id, buyer_id, processor, customer_ref, payment_ref, "
        "head, reason, amount_cents, currency, status, "
        "processor_response, attempt_count, created_at, paid_at) "
        "VALUES (?, ?, 'usdc', ?, ?, ?, ?, ?, 'USDC', ?, ?, 1, ?, ?)",
        (charge_id, buyer_id, wallet, memo,
         head, reason[:200], int(amount_usdc * 100),
         status,
         json.dumps({"pay_req": pay_req,
                     "matched_tx": matched})[:500],
         now_iso(), paid_at))
    con.execute(
        "INSERT OR IGNORE INTO si_ppc_invoices "
        "(invoice_id, charge_id, buyer_id, head, lead_id, call_id, "
        "amount_cents, amount_usdc, status, metadata, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (invoice_id, charge_id, buyer_id, head, lead_id, call_id,
         int(amount_usdc * 100), amount_usdc,
         "paid" if status == "succeeded" else "open",
         json.dumps(pay_req)[:500],
         now_iso()))
    con.commit()
    con.close()
    return {
        "charge_id": charge_id,
        "invoice_id": invoice_id,
        "status": status,
        "processor": "usdc",
        "amount_cents": int(amount_usdc * 100),
        "currency": "USDC",
        "wallet": wallet,
        "memo": memo,
        "pay_url": pay_req["solana_pay_url"],
        "matched_tx": matched.get("signature") if matched else None,
        "fallback": not bool(wallet),
    }


if __name__ == "__main__":
    print("[crypto_charge] config:")
    print(f"  SOLANA_VAULT:    {SOLANA_VAULT}")
    print(f"  USDC_MINT:       {USDC_MINT}")
    print(f"  SOLANA_RPC:      {SOLANA_RPC[:60]}...")
    print(f"\\n[crypto_charge] testing RPC connectivity...")
    r = _rpc("getHealth", [])
    print(f"  health: {r}")
    print(f"\\n[crypto_charge] test payment_collector (no buyer wallet):")
    res = charge_crypto("test_buyer", 1, "verify", 15.0)
    print(f"  -> {res.get('status')} {res.get('error', 'ok')}")
