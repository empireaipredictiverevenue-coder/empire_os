#!/usr/bin/env python3
"""nudge_awaiting.py — email the pay link to every awaiting_payment seat.

The 49 seats minted by the founder loop have a stored payment_ref memo but
never received their pay link by email (ppc_router only fires on a NEW charge
event, not for already-awaiting subs). This reconstructs the exact original
BSC Pay URL from the stored memo + price_cents + vault, and emails it,
so the buyer can fund and the loop closes.

Usage:
  nudge_awaiting.py            # email all awaiting seats not yet nudged
  nudge_awaiting.py --dry      # print what would be sent, no send
"""
import os, sys, sqlite3, argparse

# load env files (.env first, then llm.env + secret files override)
def _load_env(p):
    try:
        for ln in open(p):
            ln = ln.strip()
            if ln and "=" in ln and not ln.startswith("#"):
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass

_load_env("/root/empire_os/.env")
_load_env("/root/empire_secrets/llm.env")
# direct secret files
for nm, envk in (("bsc_wallet_address", "BSC_WALLET_ADDRESS"),
                 ("bsc_usdt_contract", "BSC_USDT_CONTRACT")):
    sp = f"/root/empire_secrets/{nm}"
    if os.path.exists(sp) and not os.environ.get(envk):
        os.environ[envk] = open(sp).read().strip()

sys.path.insert(0, "/root/empire_os")
from empire_os import mail_sender as ms

DB = "/root/empire_os/empire_os.db"
VAULT = os.environ.get("BSC_WALLET_ADDRESS", "")
MINT = os.environ.get("BSC_USDT_CONTRACT", "0x55d398326f99059fF775485246999027B3197955")

def build_pay_url(price_cents, memo):
    usdc = price_cents / 100.0
    sol = f"bsc:{VAULT}?amount={usdc:.6f}&contract={MINT}&memo={memo}"
    bsc_addr = os.environ.get("BSC_WALLET_ADDRESS", "")
    bsc = ""
    if bsc_addr:
        bsc = f"\nOr pay {usdc:.2f} USDT (BEP20) to: {bsc_addr}\nMemo: {memo}"
    return f'{sol}{bsc}'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    c = sqlite3.connect(DB, timeout=30.0); c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=30000")
    c.execute("PRAGMA journal_mode=WAL")

    # 1. purge stale 'failed' outbox rows (old contamination)
    before = c.execute("SELECT COUNT(*) FROM si_outbox WHERE status='failed'").fetchone()[0]
    if not a.dry:
        c.execute("DELETE FROM si_outbox WHERE status='failed'")
        c.commit()
    after = c.execute("SELECT COUNT(*) FROM si_outbox WHERE status='failed'").fetchone()[0]
    print(f"[purge] failed outbox rows: {before} -> {after}")

    # 2. awaiting seats not yet nudged (track via si_outbox source='pay_nudge')
    FREE = ("gmail.com","hotmail.com","yahoo.com","outlook.com","msn.com",
            "icloud.com","aol.com","proton.me","protonmail.com")
    rows = c.execute(
        "SELECT s.tenant_id, t.email, s.price_cents, s.payment_ref, s.plan "
        "FROM si_subscription s JOIN si_tenant t ON t.tenant_id=s.tenant_id "
        "WHERE s.status='awaiting_payment' AND s.payment_ref!='' "
        "AND t.email IS NOT NULL AND t.email!='' "
        "AND t.email NOT LIKE '%@example%'").fetchall()
    rows = [r for r in rows
            if r["email"].split("@")[-1].lower() not in FREE
            and not r["email"].endswith("@domain.com")]
    # dedupe: skip tenants already nudged this run / prior
    already = {row[0] for row in c.execute(
        "SELECT meta_json FROM si_outbox WHERE source='pay_nudge'").fetchall()}
    done_tenants = set()
    import json as _json
    for m in already:
        try:
            done_tenants.add(_json.loads(m).get("tenant_id"))
        except Exception:
            pass
    rows = [r for r in rows if r["tenant_id"] not in done_tenants]
    print(f"[nudge] {len(rows)} awaiting seats to email (junk+dedupe filtered)")
    sent = 0
    for r in rows:
        pay_url = build_pay_url(r["price_cents"], r["payment_ref"])
        usd = f"${r['price_cents']/100:.0f}"
        subject = f"Empire OS — your seat is reserved ({usd}/mo, pay to activate)"
        body = (
            f"Hi,<br><br>Your Empire OS buyer seat is reserved.<br><br>"
            f"Amount due: <b>{usd}/mo</b> (exclusive leads in your lane).<br>"
            f'<a href="{pay_url}">Pay now with USDT on BSC</a><br><br>'
            f"<small>Seat ref: {r['payment_ref']} — include this memo so we "
            f"activate your seat automatically on payment.</small>")
        if a.dry:
            print(f"  [dry] {r['email']} -> {pay_url[:60]}...")
            continue
        # enqueue to outbox; mail_sender daemon delivers (Brevo/Resend/SMTP)
        status = "pending"
        c.execute(
            "INSERT INTO si_outbox (to_email, subject, body, lane, tier, source, status, recipient_kind, meta_json, created_at) "
            "VALUES (?,?,?,?,?, 'pay_nudge', ?, 'buyer', ?, datetime('now'))",
            (r["email"], subject, body, r["plan"], "founder",
             status, f'{{"tenant_id":"{r["tenant_id"]}"}}'))
        # record expected payment so payment_matcher can match incoming USDT by amount
        c.execute(
            "INSERT INTO expected_payments (amount_usd, email, tenant_id, ref, status, created_at) "
            "VALUES (?,?,?,?,'pending',datetime('now'))",
            (r["price_cents"] / 100.0, r["email"], r["tenant_id"], r["payment_ref"]))
        c.commit()
        sent += 1
        print(f"  {status}: {r['email']}")
    print(f"[done] nudged {sent}/{len(rows)} seats")

if __name__ == "__main__":
    main()
