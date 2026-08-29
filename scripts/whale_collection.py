#!/usr/bin/env python3
"""
Whale Collection Engine — pursues the 26 whale buyers with $995K in unpaid invoices.
Contacts each whale ONCE per stage with their AGGREGATE balance (not per-invoice spam).
Escalating: invoice → overdue → urgent → final notice.
Laptop-closed via systemd timer. Emails via Gmail SMTP.
"""
import sqlite3, json, os, sys, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
import math

DB = "/root/empire_os/empire_os.db"
LOG = "/root/empire_os/feedback/whale_collection.log"
WALLET = "0xfb1F11b7A6815EE00eD2DbAD7aF58DA773914ba5"
GMAIL_USER = "flavag83@gmail.com"
GMAIL_PASS = "jvtn qpnk nktv vden"
# Skip these junk emails
BAN = ["example.com","email.com","johndoe","@email","gmail.com/google","google.com","sentry.io","@company.com"]

def clean_email(e):
    if not e: return None
    e = e.strip()
    if len(e) < 5 or "@" not in e or " " in e and " " in e.strip(): return None
    if any(b in e.lower() for b in BAN): return None
    if e.startswith(("%20","_","@",".")): return None
    # Block short/test local-parts but NOT real prefixes like info/sales/contact
    local = e.split("@")[0]
    if len(local) < 3: return None
    domain = e.split("@")[1].split(".")[0]
    if len(domain) < 2: return None
    if e.lower().startswith(("test@","testco","johndoe","user@","name@","example")): return None
    if not e.lower().endswith((".com",".co.uk",".net",".org",".io",".us",".ca",".info",".biz")): return None
    return e

def send_gmail(to_email, subject, html):
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = "Empire AI <founder@empire-ai.co.uk>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as s:
            s.starttls()
            s.login(GMAIL_USER, GMAIL_PASS)
            s.sendmail(msg["From"], [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"    gmail fail: {e}", flush=True)
        return False

def build_email(business, total, inv_count, stage, oldest_days):
    titles = {
        "invoice_1": f"Settlement due: ${total:,.0f} for delivered leads",
        "invoice_2": f"Overdue balance: ${total:,.0f} across {inv_count} invoices",
        "invoice_3": f"URGENT — ${total:,.0f} overdue {oldest_days} days",
        "invoice_4": f"FINAL NOTICE — ${total:,.0f} balance, delivery suspended",
    }
    urgency = f"Please settle your balance of <b>${total:,.0f}</b> ({inv_count} delivered-lead invoices). Fresh lead delivery continues once settled."
    if stage == "invoice_3":
        urgency = f"Your account owes <b>${total:,.0f}</b> over {inv_count} invoices, oldest {oldest_days} days. Settlement REQUIRED within 48h to keep the account active."
    if stage == "invoice_4":
        urgency = f"FINAL: ${total:,.0f} owed. Account will be SUSPENDED and legal/compliance path opened if not settled in 24h."
    return f"""<div style="font-family:Arial;max-width:600px;margin:auto;color:#eee;background:#111;padding:30px;border-radius:8px">
  <h2 style="color:#eab308">Empire AI — {stage.replace('_',' ').upper()}</h2>
  <p>{business or 'Valued buyer'},</p>
  <p>{urgency}</p>
  <div style="background:#1a1a1a;border:1px solid #333;padding:15px;border-radius:6px;margin:15px 0">
    <b>Balance: ${total:,.0f}</b> ({inv_count} invoices, oldest {oldest_days} days)<br><br>
    <b>Pay — USDT (BEP20/BSC)</b><br>
    Wallet: <code>{WALLET}</code><br>
    Network: BSC · Token: USDT
  </div>
  <p><a href="https://empire-ai.co.uk/pay" style="background:#eab308;color:#111;padding:12px 24px;border-radius:6px;text-decoration:none">Settle Balance</a></p>
  <p style="color:#666;font-size:12px">Reply to verify ledger accuracy or arrange terms.</p>
</div>"""

def run(max_whales=15):
    conn = sqlite3.connect(DB, timeout=60, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc)

    # Top whales by aggregate unpaid, with a valid email
    whales = conn.execute("""
        SELECT i.buyer_id, o.business_name, o.email, o.phone,
               COUNT(*) as invs, SUM(i.amount_usdc) as total,
               MIN(i.created_at) as oldest
        FROM si_ppc_invoices i
        LEFT JOIN si_buyer_outreach o ON i.buyer_id = o.prospect_id
        WHERE i.status='open' AND i.buyer_id NOT LIKE '%test%'
        GROUP BY i.buyer_id
        HAVING SUM(i.amount_usdc) > 500
        ORDER BY total DESC LIMIT ?
    """, (max_whales * 3,)).fetchall()

    sent=0; skipped_email=0; charged_target=0.0
    for w in whales:
        total = w['total'] or 0
        email = clean_email(w['email'])
        invs = w['invs']
        try:
            oldest_days = max(0, (now - datetime.fromisoformat(w['oldest'].replace('Z','+00:00'))).days)
        except Exception:
            oldest_days = 0

        if not email:
            print(f"  SKIP (no valid email): {w['buyer_id']} ${total:,.0f} ({invs} invs)")
            skipped_email += 1
            continue

        # Escalation stage from oldest invoice age
        stage = "invoice_1" if oldest_days < 3 else "invoice_2" if oldest_days < 7 else "invoice_3" if oldest_days < 14 else "invoice_4"
        subject = f"Empire AI — ${total:,.0f} settlement ({stage.replace('_',' ')})"
        html = build_email(w['business_name'], total, invs, stage, oldest_days)

        ok = send_gmail(email, subject, html)
        if ok:
            charged_target += total
            print(f"  SENT [{stage}] ${total:,.0f} ({invs} inv, {oldest_days}d) -> {email} ({w['business_name'] or ''})")
        else:
            print(f"  FAIL {email}")
    conn.close()

    with open(LOG,"a") as f:
        f.write(json.dumps({"ts":now.isoformat(),"sent_max":max_whales,"targeted_emailed_dollars":round(charged_target,2),"skipped_no_email":skipped_email})+"\n")
    print(f"\nWhale run: emailed ${charged_target:,.0f} of whale debt (no-email skipped: {skipped_email})")
    return charged_target

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    run(n)