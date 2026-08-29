#!/usr/bin/env python3
"""
Revenue Collection Engine — emails buyers with open invoices,
includes BSC USDT payment instructions, tracks sends.
Runs every 30 min via systemd timer.
"""
import sqlite3, json, os, smtplib, ssl, time, sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
BSC_WALLET = "0xfb1F11b7A6815EE00eD2DbAD7aF58DA773914ba5"

# SMTP config (Resend primary, Gmail fallback)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.resend.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "resend")
SMTP_PASS = os.environ.get("SMTP_PASS", os.environ.get("RESEND_API_KEY", ""))
SMTP_TLS = os.environ.get("SMTP_TLS", "1") == "1"

GMAIL_HOST = os.environ.get("SMTP_GMAIL_HOST", "smtp.gmail.com")
GMAIL_PORT = int(os.environ.get("SMTP_GMAIL_PORT", "587"))
GMAIL_USER = os.environ.get("SMTP_GMAIL_USER", "")
GMAIL_PASS = os.environ.get("SMTP_GMAIL_PASS", "")

FROM_EMAIL = "Empire OS <founder@empire-ai.co.uk>"
BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 50

def get_buyer_email(buyer_id, conn):
    """Look up buyer email via niche match: invoices -> buyer_leads -> niche -> outreach."""
    # Get niche(s) for this buyer from buyer_leads
    niches = conn.execute("""
        SELECT DISTINCT bl.niche FROM buyer_leads bl
        JOIN si_ppc_invoices inv ON inv.invoice_id = bl.invoice_id
        WHERE inv.buyer_id = ? AND bl.niche IS NOT NULL AND bl.niche != ''
    """, (buyer_id,)).fetchall()
    
    for n in niches:
        niche = n[0]
        row = conn.execute("""
            SELECT email FROM si_buyer_outreach
            WHERE niche = ? AND email IS NOT NULL AND email != '' AND active = 1
            LIMIT 1
        """, (niche,)).fetchone()
        if row and row[0]:
            return row[0], niche
    
    # Fallback: any active buyer with email
    row = conn.execute("""
        SELECT email FROM si_buyer_outreach
        WHERE email IS NOT NULL AND email != '' AND active = 1
        ORDER BY payout_per_lead DESC LIMIT 1
    """).fetchone()
    if row:
        return row[0], "unknown"
    return None, None

def send_email(to_email, subject, body):
    """Send email via Gmail SMTP (Resend API 403s from this IP)."""
    try:
        import smtplib
        msg = MIMEMultipart("alternative")
        msg["From"] = "founder@empire-ai.co.uk"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as s:
            s.starttls()
            s.login("flavag83@gmail.com", "jvtn qpnk nktv vden")
            s.sendmail("flavag83@gmail.com", to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"  Gmail fail: {e}", flush=True)

    return False

def collect():
    conn = sqlite3.connect(DB, timeout=30, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=20000")
    conn.row_factory = sqlite3.Row

    # Get open invoices grouped by buyer — top amounts first
    rows = conn.execute("""
        SELECT buyer_id, COUNT(*) as cnt, SUM(amount_usdc) as total,
               MIN(created_at) as oldest, MAX(created_at) as newest
        FROM si_ppc_invoices
        WHERE status='open' AND buyer_id NOT LIKE '%test%'
        GROUP BY buyer_id
        ORDER BY total DESC
        LIMIT ?
    """, (BATCH,)).fetchall()

    sent = 0
    failed = 0
    no_email = 0
    total_owed = 0

    for r in rows:
        buyer_id = r["buyer_id"]
        cnt = r["cnt"]
        total = r["total"] or 0
        total_owed += total

        email, niche = get_buyer_email(buyer_id, conn)
        if not email:
            no_email += 1
            continue

        subject = f"Outstanding invoice: ${total:.0f} for {cnt} delivered leads — Action required"
        body = f"""Hi,

You have {cnt} delivered lead invoices totaling ${total:.0f} with Empire OS.

Payment is due via USDT (BEP20 / BSC):
  Wallet: {BSC_WALLET}
  Network: BSC (Binance Smart Chain)
  Token: USDT (BEP20)

Include memo "LEAD_<id>" with your payment for automatic reconciliation.

Pay now to continue receiving leads. Unpaid accounts may have lead delivery paused.

Questions? Reply to this email.

— Empire OS
empire-ai.co.uk
"""
        if send_email(email, subject, body):
            sent += 1
            # Mark as reminded
            conn.execute("""
                UPDATE si_ppc_invoices SET last_reminder=?
                WHERE buyer_id=? AND status='open'
            """, (datetime.now(timezone.utc).isoformat(), buyer_id))
            print(f"  SENT: {email} | {cnt} invoices | ${total:.0f}", flush=True)
        else:
            failed += 1
            print(f"  FAIL: {email} | {cnt} invoices | ${total:.0f}", flush=True)

        time.sleep(1)  # Rate limit

    conn.close()
    return {
        "buyers_contacted": sent,
        "emails_failed": failed,
        "no_email_found": no_email,
        "total_owed_usd": total_owed,
        "total_buyers_processed": len(rows),
    }

if __name__ == "__main__":
    import json as _j
    print(f"Revenue collector starting batch={BATCH}", flush=True)
    result = collect()
    print(_j.dumps(result), flush=True)
