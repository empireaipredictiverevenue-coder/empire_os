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

import base64
import json
import os
import sqlite3
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ── NO-SIM LOCK ──────────────────────────────────────────────────────────
# The 'simulated' charge status is BANNED. Any code path that would persist
# a 'simulated' charge is a regression of the $0-revenue silent-drop bug.
# This guard is the durable backstop: call it before every si_charges write.
SIMULATED_BANNED = True


def assert_no_simulated(status: str) -> None:
    """Raise if a charge would be persisted with status='simulated'.

    Real charges are 'succeeded'. Unpaid-but-requested are 'open'/'pending'.
    'simulated' means fake — we never write fake revenue.
    """
    if SIMULATED_BANNED and status == "simulated":
        raise RuntimeError(
            "NO-SIM LOCK: refusing to persist status='simulated'. "
            "Use 'open' (awaiting payment) or 'failed', never 'simulated'."
        )


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


def _decode_memo(ix: dict) -> str:
    """Decode a spl-memo instruction's data to a UTF-8 string.

    Handles both encodings the RPC may return: jsonParsed returns the
    memo as a base64 string in `data`; some endpoints return it raw.
    """
    raw = ix.get("data")
    if not raw:
        return ""
    if isinstance(raw, str):
        # `data` may be base64 (jsonParsed spl-memo) or already-decoded text.
        # Only treat as base64 if it round-trips back to the same string;
        # otherwise it was raw text and we return it as-is.
        try:
            cand = base64.b64decode(raw, validate=True)
            text = cand.decode("utf-8", "ignore").strip()
            # round-trip check: re-encoding must reproduce the input
            if text and base64.b64encode(text.encode()).decode() == raw:
                return text
        except Exception:
            pass
        return raw.strip()
    return ""


def fetch_vault_recent_inbound(memo_contains: str = "",
                               lookback_seconds: int = 86400 * 7) -> list[dict]:
    """Fetch recent transfers INTO the vault (SOL or USDC) and parse memo.

    The Empire vault receives payments as native SOL `system transfer`
    instructions (with the invoice id in a spl-memo instruction) OR as
    USDC SPL `transferChecked` instructions. We match BOTH so real
    on-chain payments actually reconcile.

    Filters by memo_contains (e.g. 'INV_inv_crypto_') if provided.
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
        if not sig or (block_time and abs(time.time() - block_time) > lookback_seconds):
            continue
        tx = _rpc("getTransaction", [
            sig,
            {"encoding": "jsonParsed",
             "commitment": "finalized",
             "maxSupportedTransactionVersion": 0},
        ])
        if "error" in tx or not tx.get("result"):
            continue
        msg = tx["result"].get("transaction", {}).get("message", {})
        meta = tx["result"].get("meta", {})
        # Decode memo from spl-memo instructions
        memo_str = ""
        for ix in msg.get("instructions", []):
            if ix.get("program") == "spl-memo":
                memo_str = _decode_memo(ix)
                if memo_str:
                    break
        # 1) SOL system transfer INTO vault
        for ix in msg.get("instructions", []):
            parsed = ix.get("parsed", {})
            if ix.get("program") == "system" and parsed.get("type") == "transfer":
                info = parsed.get("info", {})
                if info.get("destination") == SOLANA_VAULT:
                    lamp = int(info.get("lamports", 0))
                    amount_sol = lamp / 1_000_000_000
                    if memo_contains and memo_contains not in memo_str:
                        # still record but skip if filter set and no match
                        if memo_contains:
                            continue
                    out.append({
                        "signature": sig,
                        "block_time": block_time,
                        "from": info.get("source"),
                        "amount": amount_sol,
                        "currency": "SOL",
                        "memo": memo_str,
                    })
        # 2) USDC transferChecked INTO vault
        for ix in msg.get("instructions", []):
            parsed = ix.get("parsed", {})
            if parsed.get("type") == "transferChecked":
                info = parsed.get("info", {})
                if info.get("destination") == SOLANA_VAULT:
                    amt = float(info.get("tokenAmount", {}).get(
                        "uiAmount", 0) or 0)
                    if memo_contains and memo_contains not in memo_str:
                        continue
                    out.append({
                        "signature": sig,
                        "block_time": block_time,
                        "from": info.get("authority") or info.get("source"),
                        "amount": amt,
                        "currency": "USDC",
                        "memo": memo_str,
                    })
    return out


def charge_crypto(buyer_id: str, head: int, reason: str,
                  amount_usdc: float,
                  call_id: str = "", lead_id: str = "") -> dict:
    """Generate a crypto payment request + reconcile if already paid.

    Returns ChargeResult-shaped dict (status=open if we
    cannot detect inbound yet, status=succeeded if matched).

    NOTE: status is NEVER 'simulated'. An unmatched charge is 'open'
    (awaiting on-chain payment), not fake. The NO-SIM lock forbids the
    'simulated' status entirely — see assert_no_simulated().
    """
    invoice_id = "inv_crypto_" + os.urandom(4).hex()
    charge_id = "chg_crypto_" + os.urandom(4).hex()
    memo = f"INV_{invoice_id}"
    # Solana Pay is push-to-vault: the buyer sends USDC/SOL to OUR vault
    # with the memo. A stored buyer wallet is NOT required to generate the
    # payment request link — only the vault address matters. Requiring it
    # silently killed 99% of charges (no pay_url -> no payment -> no revenue).
    wallet = get_buyer_wallet(buyer_id) or buyer_id or ""
    pay_req = build_expected_payment(wallet, amount_usdc, memo)
    # Try reconcile against recent inbound (match by invoice id in memo)
    inbound = fetch_vault_recent_inbound(memo_contains=memo,
                                          lookback_seconds=86400 * 7)
    matched = None
    for tx in inbound:
        if tx.get("amount", 0) >= amount_usdc * 0.99:
            matched = tx
            break
    status = "succeeded" if matched else "open"
    assert_no_simulated(status)
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


def settle_charge(charge_id: str, invoice_id: str, sig: str,
                  paid_at: str) -> bool:
    """Mark a charge + invoice as paid and emit a settled funnel event.

    IDEMPOTENT + ATOMIC: only settles if the invoice is still 'open',
    guarded by a transaction + busy_timeout so concurrent ticks of
    solana_listener (20s) and billing_collector can't double-settle or
    insert duplicate si_funnel_event rows. Returns True if it settled,
    False if it was already paid (no-op).
    """
    con = sqlite3.connect(DB, timeout=15)
    con.execute("PRAGMA busy_timeout=15000")
    try:
        with con:  # transaction; commits on success, rolls back on error
            row = con.execute(
                "SELECT status FROM si_ppc_invoices WHERE invoice_id=?",
                (invoice_id,)).fetchone()
            if row and row[0] == "paid":
                return False  # already settled — no double count
            con.execute(
                "UPDATE si_charges SET status='succeeded', paid_at=? "
                "WHERE charge_id=? AND status!='succeeded'",
                (paid_at, charge_id))
            con.execute(
                "UPDATE si_ppc_invoices SET status='paid', paid_at=? "
                "WHERE invoice_id=? AND status!='paid'",
                (paid_at, invoice_id))
            con.execute(
                "INSERT INTO si_funnel_event "
                "(prospect_id, from_state, to_state, actor, notes, occurred_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (charge_id, "open", "settled", "crypto_charge",
                 json.dumps({
                     "invoice_id": invoice_id,
                     "charge_id": charge_id,
                     "signature": sig,
                     "settled_at": paid_at,
                 }), paid_at))
        return True
    except Exception as e:
        sys.stderr.write(f"settle_charge failed: {e}\n")
        return False
    finally:
        con.close()


# Centralized SOL→USD assumption (env-overridable; replace with a price
# feed if/when live pricing matters for settlement accuracy).
SOL_USD = float(os.environ.get("SOL_USD", "150.0"))


def reconcile_open_invoices(lookback_seconds: int = 86400 * 7) -> list[dict]:
    """Scan the vault for inbound payments matching OPEN invoices.

    Called by the settlement listener on every tick. Returns the list
    of invoices that were just settled. Only pulls invoices still in
    'open' state (already-paid ones are skipped), and settle_charge
    is idempotent, so concurrent callers can't double-settle.
    """
    con = sqlite3.connect(DB, timeout=15)
    con.execute("PRAGMA busy_timeout=15000")
    open_inv = con.execute(
        "SELECT invoice_id, charge_id, amount_usdc, buyer_id FROM "
        "si_ppc_invoices WHERE status='open'").fetchall()
    con.close()
    if not open_inv:
        return []
    # Pull every inbound tx to the vault (no memo filter) once
    inbound = fetch_vault_recent_inbound(memo_contains="",
                                         lookback_seconds=lookback_seconds)
    settled = []
    for inv_id, chg_id, amt_usdc, buyer in open_inv:
        memo = f"INV_{inv_id}"
        for tx in inbound:
            if memo not in (tx.get("memo") or ""):
                continue
            # amount check: SOL amount should cover USD value at SOL_USD
            # or USDC amount covers directly
            ok = False
            if tx.get("currency") == "USDC" and tx.get("amount", 0) >= amt_usdc * 0.99:
                ok = True
            elif tx.get("currency") == "SOL":
                approx_usd = tx.get("amount", 0) * SOL_USD
                if approx_usd >= amt_usdc * 0.99:
                    ok = True
            if not ok:
                continue
            paid_at = (datetime.fromtimestamp(
                tx["block_time"], tz=timezone.utc).isoformat()
                if tx.get("block_time") else now_iso())
            if settle_charge(chg_id, inv_id, tx["signature"], paid_at):
                settled.append({"invoice_id": inv_id, "charge_id": chg_id,
                                "signature": tx["signature"], "amount": amt_usdc})
            break
    return settled


if __name__ == "__main__":
    print("[crypto_charge] config:")
    print(f"  SOLANA_VAULT:    {SOLANA_VAULT}")
    print(f"  USDC_MINT:       {USDC_MINT}")
    print(f"  SOLANA_RPC:      {SOLANA_RPC[:60]}...")
    print(f"\n[crypto_charge] testing RPC connectivity...")
    r = _rpc("getHealth", [])
    print(f"  health: {r}")
    print(f"\n[crypto_charge] reconcile open invoices:")
    settled = reconcile_open_invoices()
    print(f"  settled: {len(settled)} -> {settled}")
    print(f"\n[crypto_charge] test payment_collector (no buyer wallet):")
    res = charge_crypto("test_buyer", 1, "verify", 15.0)
    print(f"  -> {res.get('status')} {res.get('error', 'ok')}")
