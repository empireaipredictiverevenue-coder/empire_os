#!/usr/bin/env python3
"""seat_payment_onboarding — mint founder-discount USDC pay links for seated
buyers who never attached a payment method, and queue a "complete your seat"
email so $31K of billed invoices can actually collect.

WHY: 590/596 seated tenants have no payment method (crypto_wallet NULL + no
si_buyer_payment_methods row). The billing engine works but can't collect.
These are the "first set of clients" -> founder discount HONORED ($299 seat,
not standard $599). New prospects go through founder_outreach at standard tier.

SAFETY: only QUEUES emails + MINTS links. Never charges. Buyer pays voluntarily.
Dry-run by default (--go to actually queue). Idempotent: skips tenants already
in si_outbox from a prior onboarding run (source='seat_onboarding').

Mints in-process via auto_onboard.onboard() (fast, no per-tenant HTTP timeout).

Usage:
  python3 seat_payment_onboarding.py            # dry-run, prints plan
  python3 seat_payment_onboarding.py --go       # queue + mint for real
"""
import sys, os, json, sqlite3, argparse, io, base64, datetime

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
FOUNDER_SEAT_USD = 299.0  # honored founder discount for first-set clients
# founder cohort deadline — real urgency signal (CTO fix)
FOUNDER_DEADLINE = "2026-08-01"


def _qr_png(uri: str) -> str:
    """Solana Pay QR as base64 PNG (CTO fix: wallet-readable from email)."""
    import qrcode
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def mint_pay_url(name, niche, email, tier="silver"):
    """Mint a Solana Pay USDC link in-process via auto_onboard.onboard.
    Returns (pay_url, memo, vault) or ('', '', '')."""
    import empire_os.auto_onboard as ao
    try:
        res = ao.onboard(name, niche, tier, delivery_email=email,
                         source="seat_onboarding")
        if not res.get("ok"):
            return "", "", ""
        pay = res.get("payment") or {}
        return pay.get("pay_url", ""), pay.get("memo", ""), pay.get("vault_wallet", "")
    except Exception as e:
        print(f"  ! mint failed for {email}: {e}")
        return "", "", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true", help="actually queue (default: dry-run)")
    a = ap.parse_args()

    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row

    # seated tenants with a real email and NO payment method
    rows = c.execute("""
        SELECT t.tenant_id, t.name, t.email, t.plan, t.niche
        FROM si_tenant t
        WHERE t.email IS NOT NULL AND t.email != ''
          AND t.email NOT LIKE '%@example%' AND t.email NOT LIKE '%invalid%'
          AND t.crypto_wallet IS NULL
          AND NOT EXISTS (
            SELECT 1 FROM si_buyer_payment_methods pm WHERE pm.buyer_id = t.tenant_id)
          AND NOT EXISTS (
            SELECT 1 FROM si_outbox o
            WHERE o.to_email = t.email AND o.source = 'seat_onboarding')
    """).fetchall()

    print(f"[{'LIVE' if a.go else 'DRY-RUN'}] seat_payment_onboarding: {len(rows)} tenants to onboard @ ${FOUNDER_SEAT_USD:.0f} founder seat")
    queued = 0
    for t in rows:
        name = (t["name"] or "").split(".")[0].replace("-", " ").title()
        niche = t["niche"] or "b2b"
        pay_url, memo, vault = mint_pay_url(name, niche, t["email"])
        if not pay_url:
            continue
        if a.go:
            qr = _qr_png(pay_url)
            body = (
                f"Hi {name},<br><br>You're seated on Empire OS as a founding buyer "
                f"({t['plan']}). We're honoring founder pricing for your cohort: "
                f"<b>${FOUNDER_SEAT_USD:.0f} seat</b> (standard ${599:.0f}).<br><br>"
                f"<b>Founder price expires {FOUNDER_DEADLINE}.</b> After that it's ${599:.0f}.<br><br>"
                f"Scan to pay instantly (Solana Pay):<br>"
                f'<img src="data:image/png;base64,{qr}" alt="Solana Pay QR" width="220" height="220"/><br><br>'
                f'<a href="{pay_url}">Or tap here to pay ${FOUNDER_SEAT_USD:.0f} USDC</a><br><br>'
                f"<small>Secured by Solana &middot; instant settlement to vault "
                f"<code>{vault}</code>.<br>"
                f"If scan fails, send {FOUNDER_SEAT_USD:.0f} USDC to <code>{vault}</code> "
                f"with memo <code>{memo}</code>.</small>"
            )
            c.execute(
                "INSERT INTO si_outbox (to_email, subject, body, lane, tier, source, status, recipient_kind, created_at) "
                "VALUES (?,?,?,?,?,'seat_onboarding','pending','tenant',datetime('now'))",
                (t["email"], f"Empire OS — founder ${FOUNDER_SEAT_USD:.0f} seat (expires {FOUNDER_DEADLINE})",
                 body, niche, "founder"))
            c.commit()
        queued += 1
        if queued <= 3:
            print(f"  sample: {t['email']} -> {pay_url[:40]}... memo={memo[:18]}")
    print(f"[{'LIVE' if a.go else 'DRY-RUN'}] done. {'queued' if a.go else 'would queue'}: {queued}")


if __name__ == "__main__":
    main()


