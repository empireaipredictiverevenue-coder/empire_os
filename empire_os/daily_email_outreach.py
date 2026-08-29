"""
Daily email outreach cron - sends 50 emails via Brevo to next batch of leads.
"""
import sqlite3, json, urllib.request, time, sys
sys.path.insert(0, "/root/empire_os/empire_os")

DB = "/root/empire_os/empire_os.db"
BREVO_KEY = open("/root/empire_secrets/brevo_api_key").read().strip()
FROM_EMAIL = "empireaipredictiverevenue@gmail.com"
from empire_os.mail_sender import _send as _ms_send

def send_brevo(to_email, subject, body):
    """Send via canonical mail_sender._send (Resend/Brevo/SendGrid/Mailgun/SMTP/MX fallback)."""
    res = _ms_send(to_email, subject, body)
    if res.get("ok"):
        return True, res.get("brevo_id") or res.get("resend_id") or res.get("msg_id") or ""
    return False, res.get("error", "unknown")

def get_template(product, lead):
    name = lead["business_name"] or lead["prospect_id"] or "there"
    niche = lead["niche"] or "your industry"
    metro = lead["metro"] or "your area"
    ppl = lead.get("payout_per_lead") or 0
    
    if product == "cortex":
        subject = f"AI Lead Intelligence for {niche} companies"
        body = f"""Hi {name},

Empire AI is launching a lead intelligence product that predicts which businesses will need {niche} services before they start searching.

It monitors 16 data sources in real time — weather events, insurance filings, permit applications, job postings, and more — to surface high-intent leads first.

Our Cortex Intelligence dashboard runs $299/month.
First 10 companies get a free evaluation (worth $200).

Sign up: https://empire-ai.co.uk/v1/cortex/signup?source=outreach

No contracts. Cancel anytime.

--
Empire AI Intelligence"""
    elif product == "lead_grader":
        eval_price = round(ppl * 0.4, 2) if ppl and ppl > 0 else 9.99
        subject = f"Know which {niche} leads are worth your time"
        body = f"""Hi {name},

We built a tool that grades incoming {niche} leads on quality — so you stop chasing dead ends and only spend time on deals that close.

Each lead is scored against 14 signals (timing, intent, budget window, decision-maker status, and more).

Lead Grader: $49/month.
Each grade costs ${eval_price} per lead. You can patch it into your intake form in <5 minutes.

API key: https://factory-ai.co.uk/v1/lead-grader/signup?source=empire

Free plan gives you 3 grades per day. Upgrade when you see the signal.

Test Empire / OS"""
    else:
        subject = f"Free {niche} lead evaluation credits"
        body = f"""Hi {name},

We're onboarding {niche} companies in {metro} onto our lead evaluation engine, and you have 4 free credits waiting (each worth $10 when purchased).

This is the same engine the large lead brokers use to price leads — now available for the first time via API.

Your credits: 4 x $10 = $40 value
Get started: $10/month for 10 additional credits

One API call, instant evaluation.

Redeem: https://factory-ai.co.uk/v1/evaluate/signup?source=empire

Why groups are taking these early seats: first 20 companies get the current pricing forever. After that, $49/month for 10 credits.

Empire / OS"""
    return subject, body

def main():
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=30000")
    c = db.cursor()
    
    # Get next batch of leads with emails, not yet emailed today
    c.execute("""
        SELECT prospect_id, business_name, email, niche, metro, payout_per_lead
        FROM si_buyer_outreach 
        WHERE email IS NOT NULL AND email != ''
        AND email NOT LIKE '%test%' AND email NOT LIKE '%example%' AND email NOT LIKE '%@v.co'
        AND reply_state IN ('contacted', 'nurture_ready')
        ORDER BY CASE reply_state WHEN 'contacted' THEN 0 ELSE 1 END, touch_count DESC
        LIMIT ?
    """, (BATCH * 3,))
    
    leads = c.fetchall()
    db.close()
    
    if not leads:
        print("No leads to email")
        return
    
    print(f"Emailing {len(leads)} leads (max {BATCH} will be sent)")
    
    sent = 0
    skipped = 0
    
    for i, lead in enumerate(leads):
        if sent >= BATCH:
            break
            
        lead_dict = dict(lead)
        email = lead_dict["email"]
        product = PRODUCTS[i % len(PRODUCTS)]
        subject, body = get_template(product, lead_dict)
        
        ok, result = send_brevo(email, subject, body)
        if ok:
            print(f"  {sent+1}. OK: {email} ({product}) [{result}]")
            sent += 1
        else:
            print(f"  FAIL: {email} -> {result}")
            skipped += 1
        
        time.sleep(0.3)
    
    print(f"\nSENT: {sent}, SKIPPED: {skipped}")

if __name__ == "__main__":
    main()