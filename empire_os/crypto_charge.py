"""
Crypto charge - USDT-on-BSC payment collector.

Crypto must be PUSHED by the buyer. Our job is to reconcile + record.

Flow for Head 2 / Head 1 / Head 4 crypto billing:
  1. Charge triggers (call_tick at 90s, etc.)
  2. We generate a payment-expected record:
        amount_usdt, our memo = "INV_<head>_<inv_id>_<charge_id>"
  3. We POST it to the hub at /v1/ppc/expect_payment so other
     listeners (vendor agent, /products, /outreach emails) can
     send the buyer the request-to-pay link
  4. We poll the BSC RPC for incoming USDT transfers to the
     vault (using the BSC_WALLET_ADDRESS + BSC_USDT_CONTRACT env vars)
     matching our memo
  5. When the transfer arrives, we mark si_charges.paid_at +
     si_ppc_invoices.status='paid' + emit a 'settled' event.

Real money actually moves because this is on-chain. No Stripe needed.
The payer just needs BNB for gas (~0.0002 BNB = ~$0.05).
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
SIMULATED_BANNED = True


def assert_no_simulated(status: str) -> None:
    """Raise if a charge would be persisted with status='simulated'."""
    if SIMULATED_BANNED and status == "simulated":
        raise RuntimeError(
            "NO-SIM LOCK: refusing to persist status='simulated'. "
            "Use 'open' (awaiting payment) or 'failed', never 'simulated'."
        )


DB = "/root/empire_os/empire_os.db"
BSC_RPC = os.environ.get(
    "BSC_RPC", "https://bsc-dataseed.bnbchain.org")
BSC_USDT_CONTRACT = os.environ.get(
    "BSC_USDT_CONTRACT", "0x55d398326f99059fF775485246999027B3197955")
BSC_VAULT = os.environ.get(
    "BSC_WALLET_ADDRESS",
    "0x1339b487046B0ad924a10c20b1791608EA8595a8")
# ERC-20 Transfer(address,address,uint256) event signature
TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef")
# 1:1 — USDT has 18 decimals but uiAmount is already whole USDT.
USDT_DECIMALS = 18


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rpc(method: str, params: list) -> dict:
    """Call BSC JSON-RPC. Returns dict with 'result' or 'error'."""
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method,
         "params": params}).encode()
    req = urllib.request.Request(
        BSC_RPC,
        data=body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"http {e.code}", "body": e.read().decode()[:200]}
    except Exception as e:
        return {"error": str(e)[:200]}


def _decode_memo(input_data: str) -> str:
    """Decode a BSC tx input / memo blob to UTF-8 where possible."""
    if not input_data:
        return ""
    raw = input_data
    if raw.startswith("0x"):
        raw = raw[2:]
    try:
        cand = bytes.fromhex(raw)
        # strip trailing zeros, try utf-8
        text = cand.decode("utf-8", "ignore").strip("\x00").strip()
        return text
    except Exception:
        return ""


def build_expected_payment(buyer_wallet: str, amount_usdt: float,
                          memo: str) -> dict:
    """Return the payment request we send to the buyer.

    Buyer authorizes by sending one USDT transfer to our vault
    with the memo embedded in the tx input / reference.
    """
    return {
        "from": buyer_wallet,
        "to": BSC_VAULT,
        "amount_usdt": round(amount_usdt, 6),
        "token_contract": BSC_USDT_CONTRACT,
        "memo": memo,
        "bsc_pay_url": (
            f"https://bscscan.com/address/{BSC_VAULT}"
            f"?memo={urllib.parse.quote(memo)}"
        ),
        "note": (
            f"Send {round(amount_usdt,6)} USDT (BEP-20) to {BSC_VAULT} "
            f"with memo/reference '{memo}'."
        ),
    }


def get_buyer_wallet(buyer_id: str) -> Optional[str]:
    """Get the buyer's crypto wallet from si_buyer_payment_methods.

    Returns None if no real wallet is on file — caller MUST require a real
    wallet; we never fall back to a placeholder.
    """
    con = sqlite3.connect(DB)
    row = con.execute(
        "SELECT customer_ref FROM si_buyer_payment_methods "
        "WHERE buyer_id=? AND processor='usdt' AND is_default=1 "
        "AND deleted_at IS NULL ORDER BY id DESC LIMIT 1",
        (buyer_id,)).fetchone()
    con.close()
    w = row[0] if row else None
    if not w or not w.startswith("0x") or len(w) < 10:
        return None
    return w


def fetch_vault_recent_inbound(memo_contains: str = "",
                              lookback_blocks: int = 6_500_000) -> list[dict]:
    """Fetch recent USDT Transfer events INTO the vault on BSC.

    Uses eth_getLogs with the ERC-20 Transfer topic filtered to the vault
    as topic[2] (to). Parses amount (uint256, 18 decimals) + memo from the
    tx input. Returns list of {signature, block_time, from, amount,
    currency, memo}.
    """
    # current block
    head = _rpc("eth_blockNumber", [])
    if "error" in head or "result" not in head:
        return []
    try:
        latest = int(head["result"], 16)
    except Exception:
        return []
    from_block = max(1, latest - lookback_blocks)
    to_topic = "0x" + "0" * 24 + BSC_VAULT[2:].lower()
    params = [{
        "address": BSC_USDT_CONTRACT,
        "topics": [TRANSFER_TOPIC, None, to_topic],
        "fromBlock": hex(from_block),
        "toBlock": "latest",
    }]
    res = _rpc("eth_getLogs", params)
    if "error" in res or "result" not in res:
        return []
    out = []
    for log in res.get("result", []):
        try:
            tx_hash = log.get("transactionHash")
            block = int(log.get("blockNumber", "0x0"), 16)
            # amount is topic[3] (uint256, 18 decimals)
            amt_raw = int(log["topics"][3], 16)
            amount = amt_raw / (10 ** USDT_DECIMALS)
            # pull memo from the tx input
            tx = _rpc("eth_getTransactionByHash", [tx_hash])
            memo = ""
            if "result" in tx and tx["result"]:
                memo = _decode_memo(tx["result"].get("input", ""))
                from_addr = tx["result"].get("from")
            else:
                from_addr = None
            if memo_contains and memo_contains not in memo:
                continue
            out.append({
                "signature": tx_hash,
                "block": block,
                "block_time": int(time.time()),
                "from": from_addr,
                "amount": amount,
                "currency": "USDT",
                "memo": memo,
            })
        except Exception:
            continue
    return out


def charge_crypto(buyer_id: str, head: int, reason: str,
                  amount_usdt: float,
                  call_id: str = "", lead_id: str = "",
                  charge_id: str = None) -> dict:
    """Generate a crypto payment request + reconcile if already paid.

    Returns ChargeResult-shaped dict (status=open if we
    cannot detect inbound yet, status=succeeded if matched).

    NOTE: status is NEVER 'simulated'. An unmatched charge is 'open'
    (awaiting on-chain payment), not fake. The NO-SIM lock forbids the
    'simulated' status entirely — see assert_no_simulated().
    """
    invoice_id = "inv_crypto_" + os.urandom(4).hex()
    charge_id = charge_id or ("chg_crypto_" + os.urandom(4).hex())
    memo = f"INV_{invoice_id}"
    # A real buyer wallet is REQUIRED. We do NOT fall back to the buyer id
    # (that is not a wallet and silently produces an undeliverable pay link).
    wallet = get_buyer_wallet(buyer_id)
    if not wallet:
        return {
            "charge_id": charge_id,
            "invoice_id": invoice_id,
            "status": "blocked",
            "reason": "no_usdt_wallet_on_file",
            "processor": "usdt",
            "currency": "USDT",
            "amount_usd": amount_usdt,
            "memo": memo,
        }
    pay_req = build_expected_payment(wallet, amount_usdt, memo)
    inbound = fetch_vault_recent_inbound(memo_contains=memo)
    matched = None
    for tx in inbound:
        if tx.get("amount", 0) >= amount_usdt * 0.99:
            matched = tx
            break
    status = "succeeded" if matched else "open"
    assert_no_simulated(status)
    paid_at = (datetime.fromtimestamp(
        matched["block_time"], tz=timezone.utc).isoformat()
        if matched else None)
    con = sqlite3.connect(DB)
    con.execute(
        "INSERT OR IGNORE INTO si_ppc_invoices "
        "(invoice_id, charge_id, buyer_id, head, lead_id, call_id, "
        "amount_usd, amount_usdt, status, metadata, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (invoice_id, charge_id, buyer_id, head, lead_id, call_id,
         amount_usdt, amount_usdt,
         "paid" if status == "succeeded" else "open",
         json.dumps(pay_req)[:500],
         now_iso()))
    con.commit()
    con.close()
    return {
        "charge_id": charge_id,
        "invoice_id": invoice_id,
        "status": status,
        "processor": "usdt",
        "currency": "USDT",
        "amount_usd": amount_usdt,
        "amount_usdt": amount_usdt,
        "wallet": wallet,
        "memo": memo,
        "pay_url": pay_req["bsc_pay_url"],
        "matched_tx": matched.get("signature") if matched else None,
    }


def settle_charge(charge_id: str, invoice_id: str, sig: str,
                  paid_at: str) -> bool:
    """Mark a charge + invoice as paid and emit a settled funnel event.

    IDEMPOTENT + ATOMIC: only settles if the invoice is still 'open',
    guarded by a transaction + busy_timeout so concurrent ticks can't
    double-settle. Returns True if it settled, False if already paid.
    """
    con = sqlite3.connect(DB, timeout=15)
    con.execute("PRAGMA busy_timeout=15000")
    try:
        with con:
            row = con.execute(
                "SELECT status FROM si_ppc_invoices WHERE invoice_id=?",
                (invoice_id,)).fetchone()
            if row and row[0] == "paid":
                return False
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


def reconcile_open_invoices(lookback_blocks: int = 6_500_000) -> list[dict]:
    """Scan the vault for inbound USDT matching OPEN invoices.

    Called by the settlement listener on every tick. Returns the list
    of invoices just settled. Only pulls 'open' invoices; settle_charge
    is idempotent, so concurrent callers can't double-settle.
    """
    con = sqlite3.connect(DB, timeout=15)
    con.execute("PRAGMA busy_timeout=15000")
    open_inv = con.execute(
        "SELECT invoice_id, charge_id, amount_usdt, buyer_id FROM "
        "si_ppc_invoices WHERE status='open'").fetchall()
    con.close()
    if not open_inv:
        return []
    inbound = fetch_vault_recent_inbound(memo_contains="")
    settled = []
    for inv_id, chg_id, amt_usdt, buyer in open_inv:
        memo = f"INV_{inv_id}"
        for tx in inbound:
            if memo not in (tx.get("memo") or ""):
                continue
            if tx.get("currency") == "USDT" and tx.get("amount", 0) >= amt_usdt * 0.99:
                paid_at = (datetime.fromtimestamp(
                    tx["block_time"], tz=timezone.utc).isoformat()
                    if tx.get("block_time") else now_iso())
                if settle_charge(chg_id, inv_id, tx["signature"], paid_at):
                    settled.append({"invoice_id": inv_id, "charge_id": chg_id,
                                    "signature": tx["signature"], "amount": amt_usdt})
                break
    return settled


if __name__ == "__main__":
    print("[crypto_charge] config:")
    print(f"  BSC_VAULT:         {BSC_VAULT}")
    print(f"  BSC_USDT_CONTRACT: {BSC_USDT_CONTRACT}")
    print(f"  BSC_RPC:           {BSC_RPC[:60]}...")
    print(f"\n[crypto_charge] testing RPC connectivity...")
    r = _rpc("eth_blockNumber", [])
    print(f"  block: {r}")
    print(f"\n[crypto_charge] reconcile open invoices:")
    settled = reconcile_open_invoices()
    print(f"  settled: {len(settled)} -> {settled}")
    print(f"\n[crypto_charge] RPC + reconciliation self-test complete.")
