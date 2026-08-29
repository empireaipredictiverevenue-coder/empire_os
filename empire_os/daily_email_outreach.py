"""
Daily email outreach cron - sends 50 emails via Brevo to next batch of leads.
"""
import sqlite3, json, urllib.request, time, sys
sys.path.insert(0, "/root/empire_os/empire_os")

DB = "/root/empire_os/empire_os.db"
BREVO_KEY = open("/root/empire_secrets/brevo_api_key").read().strip()
FROM_EMAIL = "empireaipredictiverevenue@gmail.com"
from empire_os.mail_sender import _brevo_api_send as _ms_send

BATCH = 500  # daily cap; under EMAIL_SEND_DAILY_LIMIT (2000). 7-day cooldown paces the 16K pool.
PRODUCTS = ["cortex", "lead_grader", "evaluate"]
COOLDOWN_DAYS = 7

def send_brevo(to_email, subject, body):
    """Send via canonical mail_sender._send (Resend/Brevo/SendGrid/Mailgun/SMTP/MX fallback)."""
    res = _ms_send(to_email, subject, body)
    if res.get("ok"):
        return True, res.get("brevo_id") or res.get("resend_id") or res.get("msg_id") or ""
    return False, res.get("error", "unknown")

# Trust Wallet (BSC USDT) — zero-friction payment rail
_VAULT = "0x1339b487046B0ad924a10c20b1791608EA8595a8"
_USDT = "0x55d398326f99059fF775485246999027B3197955"

def _usdt_cta():
    return (
        "\n\n--\n"
        "PAY IN USDT (BSC) — no card, no calls:\n"
        f"  bsc:{_VAULT}?amount=10&contract={_USDT}&memo=EMPIRE-OUTREACH\n"
        "  or reply 'YES' and we send your pay link.\n"
        "  verify: https://bscscan.com/token/" + _USDT + "?a=" + _VAULT + "#transfer\n"
        "Empire AI — empire-ai.co.uk"
    )

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

Cortex Intelligence: $299/month. First 10 companies get a free evaluation (worth $200).
Start: https://empire-ai.co.uk/v1/cortex/signup?source=outreach""" + _usdt_cta()
    elif product == "lead_grader":
        eval_price = round(ppl * 0.4, 2) if ppl and ppl > 0 else 9.99
        subject = f"Know which {niche} leads are worth your time"
        body = f"""Hi {name},

We built a tool that grades incoming {niche} leads on quality — so you stop chasing dead ends and only spend time on deals that close.

Each lead is scored against 14 signals (timing, intent, budget window, decision-maker status, and more).

Lead Grader: $49/month. Each grade ${eval_price}/lead. Patch into your intake form in <5 minutes.
API key: https://empire-ai.co.uk/v1/lead-grader/signup?source=empire""" + _usdt_cta()
    else:
        subject = f"Free {niche} lead evaluation credits"
        body = f"""Hi {name},

We're onboarding {niche} companies in {metro} onto our lead evaluation engine, and you have 4 free credits waiting (each worth $10).

Same engine the large lead brokers use to price leads — now via API. $10/month for 10 credits.
Redeem: https://empire-ai.co.uk/v1/evaluate/signup?source=empire""" + _usdt_cta()
    return subject, body

def main():
    db = sqlite3.connect(DB, timeout=60)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=60000")
    # ensure cooldown column exists
    try:
        db.execute("ALTER TABLE si_buyer_outreach ADD COLUMN last_emailed TEXT")
        db.commit()
    except sqlite3.OperationalError:
        pass  # already exists
    c = db.cursor()

    # Next batch: valid email, not emailed within cooldown. Includes COLD leads
    # (the 22K untapped pool) — not just already-contacted. Paces via last_emailed.
    # GROUP BY email so we hit UNIQUE addresses (table has many duplicate-row emails).
    c.execute("""
        SELECT MIN(prospect_id) AS prospect_id, business_name, email, niche, metro,
               MIN(payout_per_lead) AS payout_per_lead
        FROM si_buyer_outreach
        WHERE email IS NOT NULL AND email != ''
        AND email NOT LIKE '%test%' AND email NOT LIKE '%example%' AND email NOT LIKE '%@v.co%'
        AND (email_status IS NULL OR email_status != 'junk')
        AND (last_emailed IS NULL OR last_emailed < datetime('now', ?))
        GROUP BY email
        ORDER BY CASE reply_state WHEN 'cold' THEN 0 ELSE 1 END,
                 MIN(touch_count) ASC, MIN(last_touch_at) ASC
        LIMIT ?
    """, (f"-{COOLDOWN_DAYS} days", BATCH * 3))

    leads = c.fetchall()

    if not leads:
        print("No leads to email")
        db.close()
        return

    print(f"Emailing {len(leads)} leads (max {BATCH} will be sent)")

    sent = 0
    skipped = 0
    seen_emails = set()

    for i, lead in enumerate(leads):
        if sent >= BATCH:
            break

        lead_dict = dict(lead)
        email = lead_dict["email"]
        if email in seen_emails:  # dedupe within batch
            continue
        seen_emails.add(email)
        product = PRODUCTS[i % len(PRODUCTS)]
        subject, body = get_template(product, lead_dict)

        ok, result = send_brevo(email, subject, body)
        if ok:
            print(f"  {sent+1}. OK: {email} ({product}) [{result}]")
            sent += 1
            db.execute(
                "UPDATE si_buyer_outreach SET last_emailed=datetime('now'), "
                "touch_count=touch_count+1, reply_state='contacted', "
                "last_touch_at=datetime('now') WHERE prospect_id=?",
                (lead_dict["prospect_id"],))
            db.commit()
        else:
            print(f"  FAIL: {email} -> {result}")
            skipped += 1

        time.sleep(0.3)

    print(f"\nSENT: {sent}, SKIPPED: {skipped}")
    db.close()

if __name__ == "__main__":
    main()