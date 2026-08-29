#!/usr/bin/env python3
"""
Subscription Launch Blast — emails the 22 Sellable Products to all buyers/affiliates.
Objective: convert the $115K MRR potential (10 subs @ T2) into recurring revenue.
Laptop-closed via systemd timer. Gmail SMTP outbound.
"""
import sqlite3, json, os, sys, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
LOG = "/root/empire_os/feedback/subscription_blast.log"
WALLET = "0xfb1F11b7A6815EE00eD2DbAD7aF58DA773914ba5"
SIGNUP_URL = "https://empire-ai.co.uk/subscribe"
GMAIL_USER = "flavag83@gmail.com"
GMAIL_PASS = "jvtn qpnk nktv vden"

def clean_email(e):
    if not e: return None
    e = e.strip()
    if len(e) < 6 or "@" not in e: return None
    if any(b in e.lower() for b in ["example.com","email.com","johndoe","@email","sentry.io","@company.com","user@","name@","test@","testco"]): return None
    local = e.split("@")[0]
    if len(local) < 3: return None
    domain = e.split("@")[1]
    if len(domain.split(".")[0]) < 2: return None
    if e.startswith(("%20","_","@","."," ")): return None
    if "=" in e or "<" in e or ">" in e: return None
    if any(c in e for c in ["&","%","+"," "]) and " " not in e.strip(): pass
    if not e.lower().endswith((".com",".co.uk",".net",".org",".io",".us",".ca",".info",".biz",".ai",".co")): return None
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

def catalog_html(products):
    rows = ""
    for p in products:
        rows += f"""<div style="background:#1a1a1a;border:1px solid #333;border-radius:6px;margin:8px 0;padding:12px">
          <h4 style="margin:0;color:#eab308">{p['name']}</h4>
          <p style="margin:4px 0;font-size:13px;color:#bbb">{p['description'][:140]}...</p>
          <span style="color:#4ade80">${p['tier1']}/mo</span>
          <span style="color:#888"> · ${p['tier4']}/mo</span>
        </div>"""
    return rows

def build_email(products, top3):
    catalog = catalog_html(top3[:3])
    return f"""<div style="font-family:Arial;max-width:620px;margin:auto;color:#eee;background:#111;padding:30px;border-radius:8px">
  <h2 style="color:#eab308">Empire AI — Subscription Catalog</h2>
  <p>You've been receiving lead deliveries. Level up with our {len(products)} subscription products — recurring lead streams, API access, and intelligence tools.</p>
  <h3 style="color:#eab308">Featured</h3>
  {catalog}
  <p style="margin:15px 0;color:#aaa">All 22 products available from $29/mo. Each includes USDT (BEP20/BSC) settlement, API access, and live support.</p>
  <p style="text-align:center;margin:20px 0">
    <a href="{SIGNUP_URL}" style="background:#eab308;color:#111;padding:14px 28px;border-radius:6px;text-decoration:none;font-weight:bold">View Full Catalog & Subscribe</a>
  </p>
  <p style="color:#666;font-size:12px">Network: BSC · Token: USDT · Pay to: <code>{WALLET}</code></p>
</div>"""

def run(max_sends=100):
    conn = sqlite3.connect(DB, timeout=60, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc)

    # Load products
    products = []
    for r in conn.execute("SELECT sku,name,description,tier1_usdc,tier4_usdc FROM si_products WHERE active=1 ORDER BY tier4_usdc DESC"):
        products.append({"sku":r[0],"name":r[1],"description":r[2] or "","tier1":r[3] or 0,"tier4":r[4] or 0})
    # Top 3 by tier4 (highest value)
    top3 = sorted(products, key=lambda x: x['tier4'], reverse=True)[:3]

    # Recipients: buyers + affiliates (dedupe by email), prefer those with history
    emails = []
    seen = set()
    for r in conn.execute("SELECT email FROM si_buyer_outreach WHERE email IS NOT NULL AND email != '' AND active=1"):
        e = clean_email(r["email"])
        if e and e.lower() not in seen:
            seen.add(e.lower()); emails.append(e)
    for r in conn.execute("SELECT DISTINCT o.email FROM affiliate_refs a JOIN si_buyer_outreach o ON a.label LIKE '%'||o.prospect_id||'%' WHERE o.email IS NOT NULL AND o.email != ''"):
        e = clean_email(r["email"])
        if e and e.lower() not in seen:
            seen.add(e.lower()); emails.append(e)

    print(f"Total unique recipients: {len(emails)} | products: {len(products)}", flush=True)
    # Shuffle-ish: prioritize those who owe money (have invoices) first
    owe = set()
    for r in conn.execute("SELECT DISTINCT buyer_id FROM si_ppc_invoices WHERE status='open' AND buyer_id NOT LIKE '%test%'"):
        b = r["buyer_id"]
        row = conn.execute("SELECT email FROM si_buyer_outreach WHERE prospect_id=?", (b,)).fetchone()
        if row:
            e = clean_email(row["email"])
            if e: owe.add(e.lower())
    # Order: payers/owe-money first, then rest
    priority = [e for e in emails if e.lower() in owe] + [e for e in emails if e.lower() not in owe]
    # Filter to max_sends
    batch = priority[:max_sends]

    sent = 0; ok_sends = 0
    for email in batch:
        subject = f"Empire AI Catalog: {len(products)} subscription products from $29/mo"
        html = build_email(products, top3)
        ok = send_gmail(email, subject, html)
        sent += 1; ok_sends += 1 if ok else 0
        status = "SENT" if ok else "FAIL"
        print(f"  [{status}] {email}", flush=True)
        if sent >= max_sends: break
    
    conn.close()
    with open(LOG,"a") as f:
        f.write(json.dumps({"ts":now.isoformat(),"attempted":sent,"delivered":ok_sends,"recipients_total":len(emails)})+ "\n")
    print(f"\nBlast: emailed {ok_sends}/{sent} of {len(emails)} total recipients")
    return ok_sends

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run(n)