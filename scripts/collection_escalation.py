#!/usr/bin/env python3
"""
Collection Escalation Engine — pursues unpaid invoices with escalating pressure.
Targets the $853K in open invoices, prioritizing highest-value buyers.
Works laptop-closed via systemd timer.
"""
import sqlite3, json, os, sys, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

DB = "/root/empire_os/empire_os.db"
LOG = "/root/empire_os/feedback/collection_escalation.log"
WALLET = "0xfb1F11b7A6815EE00eD2DbAD7aF58DA773914ba5"

# Gmail SMTP (works, has spaces in app password)
GMAIL_USER = "flavag83@gmail.com"
GMAIL_PASS = "jvtn qpnk nktv vden"

# Escalation thresholds by invoice age
def escalation_stage(days_open):
    if days_open < 3: return "invoice_1", "Reminder — Invoice Due"
    if days_open < 7: return "invoice_2", "Final Reminder — Invoice Overdue"
    if days_open < 14: return "invoice_3", "URGENT — Payment Required"
    return "invoice_4", "FINAL NOTICE — Account Suspension"

def send_gmail(to_email, subject, html):
    import smtplib
    msg = MIMEMultipart("alternative")
    msg["From"] = "Empire AI <founder@empire-ai.co.uk>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as s:
            s.starttls()
            s.login(GMAIL_USER, GMAIL_PASS)
            s.sendmail(msg["From"], [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"  gmail fail: {e}", flush=True)
        return False

def payment_email(business, amount, stage, days):
    """Build escalating collection email with USDT payment instructions."""
    titles = {
        "invoice_1": f"Payment Due: ${amount:,.0f} for delivered leads",
        "invoice_2": f"Overdue Invoice: ${amount:,.0f} — please settle",
        "invoice_3": f"URGENT: ${amount:,.0f} payment overdue {days} days",
        "invoice_4": f"FINAL NOTICE: ${amount:,.0f} — action required",
    }
    urgency = "Please remit payment within 7 days to continue receiving leads."
    if stage == "invoice_3":
        urgency = "Settlement is REQUIRED within 48 hours to maintain your buyer account."
    if stage == "invoice_4":
        urgency = "Your buyer account will be SUSPENDED and lead delivery halted if not settled within 24 hours."

    return f"""<div style="font-family:Arial;max-width:600px;margin:auto;color:#ddd;background:#111;padding:30px;border-radius:8px">
  <h2 style="color:#eab308">Empire AI — {stage.replace('_',' ').upper()}</h2>
  <p>{business},</p>
  <p>You have delivered leads totaling <b style="color:#eab308">${amount:,.0f}</b> that are unpaid ({days} days overdue).</p>
  <p>{urgency}</p>
  <div style="background:#1a1a1a;border:1px solid #333;padding:15px;border-radius:6px;margin:15px 0">
    <b>Payment — USDT (BEP20/BSC)</b><br>
    Wallet: <code>{WALLET}</code><br>
    Network: BSC (Binance Smart Chain)<br>
    Token: USDT (BEP20)
  </div>
  <p>Once paid, your invoice is marked settled and fresh leads resume immediately.</p>
  <p><a href="https://empire-ai.co.uk/pay" style="background:#eab308;color:#111;padding:12px 24px;border-radius:6px;text-decoration:none">Pay Invoice</a></p>
  <p style="color:#666;font-size:12px">Reply to discuss payment terms or ledger accuracy.</p>
</div>"""

def run(batch_size=50):
    conn = sqlite3.connect(DB, timeout=60, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row

    now = datetime.now(timezone.utc)
    sent = 0
    skipped = 0
    amount_pursued = 0.0

    # Get top unpaid invoices with buyer email, skip test
    invoices = conn.execute("""
        SELECT i.invoice_id, i.amount_usdc, i.created_at, i.status,
               o.business_name, o.email
        FROM si_ppc_invoices i
        JOIN si_buyer_outreach o ON i.buyer_id = o.prospect_id
        WHERE i.status='open'
          AND i.buyer_id NOT LIKE '%test%'
          AND i.created_at IS NOT NULL
          AND o.email IS NOT NULL AND o.email != ''
          AND o.email NOT LIKE '%@example.com'
          AND o.email NOT LIKE '%@email.com'
          AND o.email NOT LIKE '%johndoe%'
        ORDER BY i.amount_usdc DESC
        LIMIT ?
    """, (batch_size,)).fetchall()

    for inv in invoices:
        try:
            created = datetime.fromisoformat(inv['created_at'].replace('Z','+00:00'))
        except Exception:
            created = now
        days = max(0, (now - created).days)
        stage, _ = escalation_stage(days)

        # Skip if reminded same stage already
        if inv['status'] != 'open':
            skipped += 1
            continue

        amount = inv['amount_usdc'] or 0
        if amount < 100:  # only pursue meaningful invoices
            skipped += 1
            continue

        subject = f"Payment Due: ${amount:,.0f} — {inv['business_name'] or 'Empire AI buyer'}"
        html = payment_email(inv['business_name'] or 'Buyer', amount, stage, days)

        ok = send_gmail(inv['email'], subject, html)
        if ok:
            # Mark escalation stage so we don't re-send same stage
            meta = json.loads(inv['metadata'] or '{}')
            meta['escalation_stage'] = stage
            meta['last_pursued'] = now.isoformat()
            conn.execute("UPDATE si_ppc_invoices SET metadata=?, last_reminder=? WHERE invoice_id=?",
                         (json.dumps(meta), now.isoformat(), inv['invoice_id']))
            sent += 1
            amount_pursued += amount
            print(f"  SENT [{stage}] ${amount:,.0f} -> {inv['email']}")
        else:
            print(f"  FAIL {inv['email']}")

    conn.commit()
    conn.close()

    log = {"ts": now.isoformat(), "sent": sent, "skipped": skipped, "amount_pursued_dollars": round(amount_pursued,2)}
    with open(LOG, "a") as f:
        f.write(json.dumps(log) + "\n")

    print(f"\nCollection run: sent={sent}, skipped={skipped}, ${amount_pursued:,.0f} pursued")
    return sent

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    run(n)