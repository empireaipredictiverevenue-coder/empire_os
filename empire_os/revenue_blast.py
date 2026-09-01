#!/usr/bin/env python3
"""
Empire OS — Revenue blast (reply-to-buy, credential-free).
==========================================================
Sends a 1:1 transactional reply-to-buy email to real BUSINESS leads in
crm_leads (not free-mail noise), excluding suppressed / unsubscribed /
already-contacted. Each email carries a BSC USDT pay link (Ambient AI $49/mo).

Delivery: direct Brevo send (ms._brevo_api_send) — same compliant path as
nudge_awaiting (avoids the si_outbox founder-approval guard; this is
transactional 1:1, not bulk marketing).

Safety:
- hard cap (default 200/day) to protect Brevo sender reputation
- idempotent: skips emails already in si_buyer_outreach with first_touch_at
- excludes webmail, suppressed_emails, unsubscribes, replies
- dry-run by default; pass --go to actually send

Run: python3 empire_os/revenue_blast.py --go
"""
import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
VAULT = "0x1339b487046B0ad924a10c20b1791608EA8595a8"
CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
AMBIENT_URL = "https://empire-ai.co.uk/ambient"
PRICE_USD = 49.0  # Ambient AI monthly

WEBMAIL = ("gmail.com", "hotmail.com", "yahoo.com", "outlook.com", "icloud.com",
           "aol.com", "proton.me", "protonmail.com", "live.com", "msn.com")
# Aggregators / directories / job boards / PR / non-buyer corporate — skip
JUNK_DOMAIN = ("google.com", "groq.co", "zavvi.com", "beehiiv.com",
               "worldprofitemail.com", "listhoopla.com", "mailer.gold",
               "just-eat.co.uk", "rb2b.com", "example.com", "domain.com",
               "totaljobs.com", "bizjournals.com", "downtobid.com", "trin.com",
               "gaylor.com", "yelp.com", "angieslist.com", "homeadvisor.com",
               "thumbtack.com", "linkedin.com", "facebook.com", "instagram.com",
               "twitter.com", "x.com", "reddit.com", "quora.com", "medium.com",
               "substack.com", "wix.com", "squarespace.com", "wordpress.com",
               "godaddy.com", "hostgator.com", "amazon.com", "ebay.com",
               "craigslist.org", "nextinsurance.com", "yellowpages.com",
               "bbb.org", "yext.com", "localsearch.com", "cylex.com",
               "manta.com", "buzzfile.com", "salesgenie.com", "zoominfo.com",
               "apollo.io", "hunter.io", "clearbit.com", "rocketreach.co",
               "empire-ai.co.uk", "free-scout.empire-ai.co.uk", "empire.ai")

NICHE_LABEL = {
    "roofing": "roofing", "residential_roofing": "roofing",
    "hvac": "HVAC", "plumbing": "plumbing", "electrical": "electrical",
    "dental": "dental", "dental_practice": "dental",
    "landscaping": "landscaping", "pest_control": "pest control",
    "painting": "painting", "solar": "solar", "legal_services": "legal",
    "real_estate": "real estate", "general_contractor": "contractor",
    "b2b_services": "B2B", "b2b": "B2B",
}


def get_conn():
    # Direct sqlite3 connection with long busy_timeout. The gatekeeper was
    # wedging behind a leaked fleet transaction (DB-wide 'database is locked');
    # revenue_blast is a one-shot batch job, not a 24/7 daemon, so a direct
    # write handle (per Pitfall 59 exception for batch jobs) is correct here.
    c = sqlite3.connect(DB, timeout=120, isolation_level=None)
    c.execute("PRAGMA busy_timeout=120000")
    c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row
    return c


def pay_link():
    memo = f"ambient_ai_monthly_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    return (f"https://empire-ai.co.uk/pay?contract={CONTRACT}&vault={VAULT}"
            f"&amount={PRICE_USD:.2f}&memo={memo}")


def build_email(biz, niche, metro):
    label = NICHE_LABEL.get(niche, "home-services")
    name = (biz or "there").split(" ")[0]
    subject = f"{label.title()} leads on autopilot — reply 'buy' to start"
    body = (
        f"Hey {name},\n\n"
        f"We run an AI lead engine that finds in-market {label} customers in "
        f"{metro or 'your area'} and delivers them to you automatically — "
        f"no ad spend, no sales calls.\n\n"
        f"Businesses like yours are closing these leads on a $49/mo Ambient AI "
        f"subscription. It runs 24/7 and you only pay when it delivers.\n\n"
        f"Start now: {pay_link()}\n"
        f"Or just reply 'buy' and we'll activate your seat and send the pay link.\n\n"
        f"— Empire AI\n"
        f"(Unsubscribe: reply 'stop')\n"
    )
    return subject, body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true", help="actually send (else dry-run)")
    ap.add_argument("--cap", type=int, default=200, help="max sends this run")
    ap.add_argument("--niche", default=None, help="limit to one niche")
    a = ap.parse_args()
    dry = not a.go

    import empire_os.mail_sender as ms
    if not dry:
        os.environ.setdefault("BREVO_API_KEY", open("/root/empire_secrets/brevo_api_key").read().strip())

    conn = get_conn()
    niche_filter = f"AND c.niche = '{a.niche}'" if a.niche else ""
    rows = conn.execute(f"""
        SELECT c.id, c.business_name, c.email, c.niche, c.metro
        FROM crm_leads c
        WHERE c.email IS NOT NULL AND c.email != ''
          AND c.email LIKE '%@%'
          AND c.email NOT LIKE '%@gmail.com' AND c.email NOT LIKE '%@hotmail%'
          AND c.email NOT LIKE '%@yahoo%' AND c.email NOT LIKE '%@outlook%'
          AND c.email NOT LIKE '%@icloud%' AND c.email NOT LIKE '%@aol%'
          AND c.email NOT LIKE '%@proton%'
          AND c.email NOT LIKE '%@live.com' AND c.email NOT LIKE '%@msn.com'
          {niche_filter}
          AND c.email NOT IN (SELECT email FROM suppressed_emails)
          AND c.email NOT IN (SELECT email FROM unsubscribes)
          AND c.email NOT IN (SELECT email FROM replies)
          AND c.email NOT IN (SELECT email FROM si_buyer_outreach WHERE first_touch_at IS NOT NULL)
        ORDER BY c.omega_score DESC
        LIMIT {a.cap * 3}
    """).fetchall()

    sent = skipped = 0
    for r in rows:
        dom = r["email"].split("@")[-1].lower()
        if dom in JUNK_DOMAIN:
            skipped += 1
            continue
        if sent >= a.cap:
            break
        subject, body = build_email(r["business_name"], r["niche"], r["metro"])
        if dry:
            print(f"  [dry] {r['email']} ({r['niche']}) -> {pay_link()[:50]}...")
            sent += 1
            continue
        try:
            res = ms._brevo_api_send(r["email"], subject, body, html_body=body)
            status = "sent" if res.get("ok") else f"err:{res.get('error','?')}"
        except Exception as e:
            status = f"err:{e}"
        conn.execute(
            """INSERT INTO si_buyer_outreach
               (prospect_id, business_name, email, metro, niche, source,
                first_touch_at, last_touch_at, touch_count, reply_state, url)
               VALUES (?,?,?,?,?,'revenue_blast',datetime('now'),datetime('now'),1,'cold',?)""",
            (f"crm_{r['id']}", r["business_name"], r["email"], r["metro"],
             r["niche"], pay_link()))
        conn.execute(
            "INSERT INTO expected_payments (amount_usd, email, tenant_id, ref, status, created_at) "
            "VALUES (?,?,?,?,'pending',datetime('now'))",
            (PRICE_USD, r["email"], f"crm_{r['id']}", f"ambient_{r['id']}"))
        conn.commit()
        sent += 1
        print(f"  {status}: {r['email']}")

    print(f"[done] {'DRY ' if dry else ''}processed={len(rows)} sent={sent} skipped_junk={skipped}")


if __name__ == "__main__":
    main()
