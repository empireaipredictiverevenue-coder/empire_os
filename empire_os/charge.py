"""
Charge adapter - processor-agnostic buyer charging.

Processors (in priority order):
  USDC (Solana) - real money, on-chain reconciliation via memo
  PayPal       - if PAYPAL_CLIENT_ID + PAYPAL_CLIENT_SECRET are set
  (no simulated fallback — if no real processor is available the charge
   FAILS. The NO-SIM lock forbids the 'simulated' status entirely.)

Stripe was removed from this layer because (a) we have a working
USDC path that doesn't need a third party, and (b) Stripe-card
charges require the buyer to have set up a saved card in our Stripe
Customer object which we don't operate.

Note: payout.py STILL uses Stripe for paying humans/lane-owners
(via /v1/finance/payout). That pathway is separate from the
buyer-charge layer you're looking at here.

Returns ChargeResult shape:
{
    "charge_id":   "chg_...",
    "status":      "succeeded" | "open" | "failed",
    "processor":   "usdc" | "paypal" | "failed",
    "amount_cents": 1500,
    "currency":    "USDC" | "USD",
    "fallback":    bool,
    "processor_response": <truncated dict>,
    "pay_url":     <only when usdc>,
    "memo":        <only when usdc>,
}

NO-SIM LOCK
----------
The 'simulated' status is BANNED. A charge is either real money
('succeeded'), awaiting payment ('open'/'pending'), or it failed.
assert_no_simulated() raises if any code path tries to persist
'simulated' — this is the durable guard that prevents the $0-revenue
sim-silent-drop failure from recurring.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from empire_os.crypto_charge import (
        charge_crypto, get_buyer_wallet as _cc_get_wallet,
        assert_no_simulated,
    )
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False
    def assert_no_simulated(status: str) -> None:  # noqa: D401
        if status == "simulated":
            raise RuntimeError("NO-SIM LOCK: status='simulated' is banned.")


DB = "/root/empire_os/empire_os.db"
HUB = os.environ.get("HUB_URL", "http://127.0.0.1:8000")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _post_to_hub(path: str, body: dict) -> bool:
    """Best-effort POST to hub. Returns True if accepted (2xx)."""
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{HUB}{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=4) as resp:
            return resp.status in (200, 201)
    except Exception:
        return False


def _get_pm_from_hub(buyer_id: str) -> Optional[dict]:
    """Fetch buyer's default payment method from the hub (canonical).

    Hub is the source of truth for buyer payment methods. Each
    container has its own db mirror that's used as a fallback.
    """
    try:
        import urllib.request, urllib.parse
        url = (f"{HUB}/v1/ppc/buyer_pms?buyer_id="
               + urllib.parse.quote(buyer_id))
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=4) as resp:
            pms = json.loads(resp.read().decode()).get("pms", [])
            for p in pms:
                if p.get("is_default") and not p.get("deleted_at"):
                    return p
            return pms[0] if pms else None
    except Exception:
        return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Processor selection ──────────────────────────────────────────────

def _has_paypal() -> bool:
    return bool(os.environ.get("PAYPAL_CLIENT_ID", "").strip()
               and os.environ.get("PAYPAL_CLIENT_SECRET", "").strip())


def _has_crypto(buyer_id: str = "") -> bool:
    """USDC-on-Solana is available if Solana deps + vault are configured.

    NOTE: a buyer-side wallet is NOT required — Solana Pay pushes funds
    TO the empire vault, so the payment request link is generated from
    the vault address alone. We only need the capability (deps + vault),
    independent of any stored buyer wallet. Requiring a buyer wallet here
    silently dropped 99% of charges to `simulated` and killed revenue.
    """
    if not _HAS_CRYPTO:
        return False
    return bool(os.environ.get("EMPIRE_WALLET") or
                os.environ.get("SOLANA_VAULT_WALLET"))


def pick_processor(buyer_id: str = "") -> str:
    """Priority: crypto (real USDC) > paypal.
    NO simulated fallback — if no processor, charge fails.
    """
    if _has_crypto(buyer_id):
        return "usdc"
    if _has_paypal():
        return "paypal"
    return ""  # caller handles "no processor" as failure


# ── Buyer payment method retrieval ───────────────────────────────────

def get_default_pm(buyer_id: str) -> Optional[dict]:
    """Get the buyer's default payment method.

    Hub-first: each container has its own db mirror; hub is canonical.
    Falls back to local DB if hub unreachable.
    """
    # Hub first (canonical)
    pm = _get_pm_from_hub(buyer_id)
    if pm:
        return pm
    # Local fallback
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT * FROM si_buyer_payment_methods "
        "WHERE buyer_id=? AND is_default=1 AND deleted_at IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (buyer_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def list_payment_methods(buyer_id: str) -> list[dict]:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT * FROM si_buyer_payment_methods "
        "WHERE buyer_id=? AND deleted_at IS NULL ORDER BY id DESC",
        (buyer_id,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def _resolve_buyer_email(buyer_id: str) -> str:
    """Best-effort resolve a deliverable email for a buyer.

    Checks si_buyer_outreach (the canonical outreach table) first, then
    si_buyer_payment_methods. Returns '' if none — callers MUST treat
    empty as a hard delivery failure (never a silent simulation).
    Tables are best-effort: a missing table is treated as 'no email',
    never as an exception that breaks the charge write.
    """
    for _tbl, _col, _key in (
        ("si_buyer_outreach", "email", "prospect_id"),
        ("si_buyer_payment_methods", "customer_ref", "buyer_id"),
    ):
        try:
            con = sqlite3.connect(DB)
            row = con.execute(
                f"SELECT {_col} FROM {_tbl} "
                f"WHERE {_key}=? AND {_col} IS NOT NULL AND {_col} != '' "
                "ORDER BY id DESC LIMIT 1",
                (buyer_id,)).fetchone()
            con.close()
            if row and row[0]:
                return row[0]
        except sqlite3.OperationalError:
            # table absent in this DB — skip, try next source
            continue
    return ""


def add_payment_method(buyer_id: str, processor: str,
                       customer_ref: str, payment_ref: str = "",
                       brand: str = "", last4: str = "",
                       is_default: int = 1) -> int:
    """Persist a buyer's stored payment method."""
    con = sqlite3.connect(DB)
    if is_default:
        # Clear existing defaults for that buyer/processor
        con.execute(
            "UPDATE si_buyer_payment_methods "
            "SET is_default=0 WHERE buyer_id=? AND processor=?",
            (buyer_id, processor))
    cur = con.execute(
        "INSERT OR IGNORE INTO si_buyer_payment_methods "
        "(buyer_id, processor, customer_ref, payment_ref, brand, last4,"
        " is_default, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (buyer_id, processor, customer_ref, payment_ref, brand, last4,
         is_default, now_iso()))
    con.commit()
    new_id = cur.lastrowid
    con.close()
    return new_id


# ── Charge execution per processor ──────────────────────────────────

def _charge_paypal(customer_ref: str, amount_cents: int,
                   currency: str, description: str) -> dict:
    """PayPal billing agreement capture (simulated structure)."""
    try:
        import urllib.request, urllib.error, urllib.parse
        client_id = os.environ["PAYPAL_CLIENT_ID"]
        secret = os.environ["PAYPAL_CLIENT_SECRET"]
        base = "https://api-m.paypal.com"  # live; sandbox = api-m.sandbox.paypal.com
        # Get access token
        token_req = urllib.request.Request(
            f"{base}/v1/oauth2/token",
            data=urllib.parse.urlencode({"grant_type": "client_credentials"})
                  .encode(),
            headers={"Accept": "application/json",
                     "Accept-Language": "en_US"},
            method="POST")
        import base64 as _b64
        auth = _b64.b64encode(f"{client_id}:{secret}".encode()).decode()
        token_req.add_header("Authorization", f"Basic {auth}")
        with urllib.request.urlopen(token_req, timeout=10) as r:
            tok = json.loads(r.read().decode()).get("access_token", "")
        # Capture from billing agreement
        cap_req = urllib.request.Request(
            f"{base}/v1/payments/billing-agreements/{customer_ref}/agreement-execute",
            data=json.dumps({}).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {tok}"},
            method="POST")
        with urllib.request.urlopen(cap_req, timeout=10) as r2:
            return {"ok": True,
                    "raw": json.loads(r2.read().decode())}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _charge_stripe_disabled(customer_ref: str, payment_ref: str,
                            amount_cents: int, currency: str,
                            description: str) -> dict:
    """Stripe charge - DISABLED in this build.

    Returns {'ok': False, 'error': 'stripe_disabled'} so any
    legacy code path that still names 'stripe' silently fails
    without falling back (operators explicitly chose to remove
    Stripe from the buyer-charge layer).
    """
    return {"ok": False, "error": "stripe_disabled",
            "note": "Stripe was removed from buyer-charges in this build"}


# ── Public charge() — auto-picks + records ─────────────────────────

def charge(buyer_id: str, head: int, reason: str,
           amount_cents: int, currency: str = "USD",
           call_id: str = "", lead_id: str = "",
           force_processor: str = "") -> dict:
    """Charge a buyer. Auto-picks processor from env / stored PMs.

    Returns ChargeResult. Always writes si_charges row. May call
    real processor if creds available, else returns
    status='simulated'.
    """
    charge_id = "chg_" + secrets.token_hex(8)
    pm = get_default_pm(buyer_id)
    # Pick the credit-rail based on processor. Crypto wins if buyer
    # has a stored wallet - it actually moves money on-chain.
    processor = force_processor
    if not processor:
        if pm:
            processor = pm["processor"]
        else:
            processor = pick_processor(buyer_id)
    # Pick the credit-rail based on processor
    if processor == "usdc":
        crypto_res = charge_crypto(
            buyer_id=buyer_id, head=head, reason=reason,
            amount_usdc=max(1, amount_cents / 100),
            call_id=call_id, lead_id=lead_id)
        resp = {"ok": crypto_res.get("status") != "failed",
                "raw": crypto_res,
                "pay_url": crypto_res.get("pay_url"),
                "memo": crypto_res.get("memo"),
                "matched_tx": crypto_res.get("matched_tx")}
        status = crypto_res.get("status", "failed")
    elif processor == "stripe":
        # Stripe was removed in this build. Force-fail so any
        # legacy si_buyer_payment_methods rows tagged 'stripe' do
        # NOT silently fall back to simulated.
        customer_ref = pm["customer_ref"] if pm else ""
        payment_ref = pm["payment_ref"] if pm else ""
        resp = _charge_stripe_disabled(customer_ref, payment_ref,
                                       amount_cents, currency,
                                       f"head{head}: {reason}")
    elif processor == "paypal":
        customer_ref = pm["customer_ref"] if pm else ""
        resp = _charge_paypal(customer_ref, amount_cents,
                              currency, f"head{head}: {reason}")
    else:  # no real processor — fail, don't simulate
        processor = "failed"
        resp = {"ok": False, "error": "no real payment processor available"}

    # Guard: resp must be a dict for the .get() calls below. A non-dict
    # (None / string from a misbehaving processor path) would crash
    # charge() here and lose the si_charges write entirely.
    safe = resp if isinstance(resp, dict) else {}

    if processor == "usdc":
        status = safe.get("raw", {}).get("status", status)
    elif safe.get("ok"):
        status = "succeeded"
    else:
        status = "failed"

    # Persist
    con = sqlite3.connect(DB)
    assert_no_simulated(status)  # NO-SIM LOCK — never write fake revenue
    con.execute(
        "INSERT INTO si_charges "
        "(charge_id, buyer_id, processor, customer_ref, payment_ref, "
        "head, reason, amount_cents, currency, status, "
        "processor_response, attempt_count, created_at, paid_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
        (charge_id, buyer_id, processor,
         pm["customer_ref"] if pm else "",
         pm["payment_ref"] if pm else "",
         head, reason[:200], amount_cents, currency, status,
         json.dumps(resp)[:1000],
         now_iso(),
         now_iso() if status == "succeeded" else None))
    con.commit()
    con.close()

    # ── DELIVER THE PAYMENT REQUEST (the missing spoke) ──────────────
    # A charge that generates a pay_url but never delivers it is dead:
    # the buyer can't pay, the on-chain reconcile never matches, and the
    # charge sits "open" forever. So: if we produced a pay_url AND we can
    # resolve the buyer's email, email the Solana Pay link. No email ->
    # log a hard failure + alert so it can NEVER silently sit open again.
    _pay_url = (safe.get("raw", {}).get("pay_url")
                or safe.get("pay_url") or "")
    if _pay_url and status in ("open", "pending"):
        _buyer_email = _resolve_buyer_email(buyer_id)
        if _buyer_email:
            try:
                from empire_os import mail_sender
                _amt = amount_cents / 100.0
                _sent = mail_sender._send(
                    _buyer_email,
                    f"Empire OS — payment request ({_amt:.2f} USDC)",
                    f"Please complete payment via Solana Pay:\n\n"
                    f"{_pay_url}\n\nMemo: {safe.get('raw', {}).get('memo') or safe.get('memo') or ''}\n"
                    f"Amount: {_amt:.2f} USDC\n\n"
                    f"This request was generated for: {reason[:120]}")
                if not _sent.get("ok"):
                    sys.stderr.write(
                        f"[charge] pay_url DELIVERY FAILED for {buyer_id}: "
                        f"{_sent.get('error')}\n")
            except Exception as _e:
                sys.stderr.write(
                    f"[charge] pay_url delivery exception for {buyer_id}: {_e}\n")
        else:
            # No email on file -> cannot deliver -> this is a real failure,
            # not a silent simulation. Surface it loudly.
            sys.stderr.write(
                f"[charge] NO BUYER EMAIL for {buyer_id} — pay_url "
                f"({_pay_url[:40]}...) cannot be delivered. Charge will not settle.\n")

    return {
        "charge_id": charge_id,
        "status": status,
        "processor": processor,
        "amount_cents": amount_cents,
        "currency": currency,
        "fallback": not safe.get("ok") if safe else False,
        "processor_response": json.dumps(safe)[:1000],
        # Surface the payment link + memo at top level so callers
        # (hub /v1/ppc/charge, ppc_router) can actually deliver it.
        "pay_url": safe.get("raw", {}).get("pay_url")
                   or safe.get("pay_url") or "",
        "memo": safe.get("raw", {}).get("memo")
                or safe.get("memo") or "",
    }


# ── Convenience: settle a PPC invoice ──────────────────────────────

def settle_ppc_invoice(invoice_id: str) -> dict:
    """Mark an existing ppc invoice as paid (after charge succeeds)."""
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT * FROM si_ppc_invoices WHERE invoice_id=?",
        (invoice_id,)).fetchone()
    if not row:
        con.close()
        return {"ok": False, "error": "invoice_not_found"}
    inv = dict(row)
    con.execute("UPDATE si_charges SET ledger_id=? WHERE charge_id=?",
                (invoice_id, inv["charge_id"]))
    con.execute(
        "UPDATE si_ppc_invoices SET status='paid', paid_at=? "
        "WHERE invoice_id=?",
        (now_iso(), invoice_id))
    con.commit()
    con.close()
    return {"ok": True, "invoice_id": invoice_id, "status": "paid"}


# ── CLI / introspection ─────────────────────────────────────────────

if __name__ == "__main__":
    print("[charge] active processors:")
    print("  Stripe:    removed from buyer-charges (use /v1/finance/payout for vendor payouts)")
    print(f"  USDC:      {'yes' if _HAS_CRYPTO else 'no (solana deps missing)'}")
    print(f"  PayPal:    {'yes' if _has_paypal() else 'no'}")
    print(f"  Simulated:  "
          f"{'default' if not (_has_paypal() or _HAS_CRYPTO) else 'fallback'}")
    print(f"\n[charge] selected for a new invoice: {pick_processor()}")
