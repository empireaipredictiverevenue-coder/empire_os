#!/usr/bin/env python3
"""recovery_sequence.py — 3-touch USDC pay-link recovery on awaiting deals.

The biggest uncollected-revenue lever: 496 buyer seats minted (awaiting_payment)
but never paid = $297k. This runs a 3-touch nudge:
  T1 (day 0):  "Your Empire OS seat is reserved — pay $X to activate"
  T2 (day 3):  "Reminder: your pay link expires soon"
  T3 (day 7):  "Final notice + limited offer (2 months free on annual)"
Each touch emails the buyer their exact Solana Pay link (re-derived from the
live tenant), logs to crm_deals.touch_N, and queues via the outbox (Brevo).

Run: python3 recovery_sequence.py [--dry-run] [--max N]
Idempotent: only touches deals whose next touch is due and not yet sent.
"""
import sqlite3, time, datetime, argparse, sys, os

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
HUB = "http://127.0.0.1:8081"

# ── load .env so SOLANA_VAULT_WALLET + secrets are available ──
_ENV_PATH = "/root/empire_os/.env"
if os.path.exists(_ENV_PATH):
    try:
        for _ln in open(_ENV_PATH).read().splitlines():
            _ln = _ln.strip()
            if not _ln or _ln.startswith("#") or "=" not in _ln:
                continue
            _k, _v = _ln.split("=", 1)
            _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v
    except Exception:
        pass

# touch schedule (days since deal created_at)
TOUCHES = [
    {"n": 1, "delay": 0,  "subject": "Your Empire OS buyer seat is reserved — activate now"},
    {"n": 2, "delay": 3,  "subject": "Reminder: your Empire OS pay link is still open"},
    {"n": 3, "delay": 7,  "subject": "Final notice: claim your Empire OS seat (2 months free)"},
]

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def days_since(iso):
    try:
        s = iso.replace("Z", "")
        # handle both naive and tz-aware; normalize to naive UTC
        if "+" in s:
            s = s.split("+")[0]
        d = datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - d).days
    except Exception:
        return 99

def get_pay_url(tenant_id):
    """Reconstruct the Solana Pay link for an existing tenant from the DB.

    The apply flow stores payment_ref (Solana memo) in si_subscription and the
    vault wallet in SOLANA_VAULT_WALLET. The pay_url is the standard Solana Pay
    URI: solana:<vault>?memo=<ref>&amount=<usdc>. No new hub endpoint needed.
    """
    import os
    try:
        c = sqlite3.connect(DB)
        row = c.execute(
            "SELECT payment_ref, price_cents FROM si_subscription "
            "WHERE tenant_id=?", (tenant_id,)).fetchone()
        c.close()
        if not row or not row[0]:
            return None
        vault = os.environ.get("SOLANA_VAULT_WALLET", "")
        usdc = (row[1] or 0) / 100.0
        return f"solana:{vault}?memo={row[0]}&amount={usdc}"
    except Exception:
        return None

def queue_email(to_email, subject, body, tenant_id):
    """Queue into si_outbox via the hub enqueue endpoint (Brevo flushes)."""
    import urllib.request, json
    payload = json.dumps({
        "to_email": to_email, "subject": subject, "body": body,
        "lane": "recovery", "tier": "", "lead_id": tenant_id,
        "source": "recovery_sequence",
    }).encode()
    req = urllib.request.Request(f"{HUB}/v1/outbox/enqueue", data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception:
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max", type=int, default=50)
    args = ap.parse_args()

    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    awaiting = c.execute(
        "SELECT * FROM crm_deals WHERE stage='awaiting_payment'").fetchall()

    sent_total = 0
    for d in awaiting:
        tenant_id = d["tenant_id"]
        age = days_since(d["created_at"])
        email = d["contact_email"]
        if not email or "@" not in str(email) or str(email).startswith("tenant:"):
            continue
        # determine next due touch
        next_touch = None
        for t in TOUCHES:
            col = f"touch_{t['n']}_sent"
            if not d[col] and age >= t["delay"]:
                next_touch = t
                break
        if not next_touch:
            continue
        if args.dry_run:
            print(f"[dry] {email} tenant={tenant_id} -> touch {next_touch['n']} (age {age}d)")
            sent_total += 1
            if sent_total >= args.max:
                break
            continue
        pay_url = get_pay_url(tenant_id)
        if not pay_url:
            print(f"[skip] no pay_url for {tenant_id}")
            continue
        body = (
            f"Hi {email},\n\n"
            f"Your Empire OS buyer seat is reserved but not yet activated.\n\n"
            f"Pay your balance in USDC to go live:\n{pay_url}\n\n"
            f"(Touch {next_touch['n']}/3)\n"
        )
        ok = queue_email(email, next_touch["subject"], body, tenant_id)
        if ok:
            c.execute(f"UPDATE crm_deals SET touch_{next_touch['n']}_sent=1, "
                      f"updated_at=? WHERE id=?", (now_iso(), d["id"]))
            c.commit()
            sent_total += 1
            print(f"[sent] touch {next_touch['n']} -> {email}")
        else:
            print(f"[fail] touch {next_touch['n']} queue failed {email}")
        if sent_total >= args.max:
            break
        time.sleep(0.5)

    c.close()
    print(f"\nDone. Touches queued this run: {sent_total}")

if __name__ == "__main__":
    main()
