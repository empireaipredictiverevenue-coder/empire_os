#!/usr/bin/env python3
"""lead_harvest.py — orchestrates the EXISTING free toolchain into the BD pool.

Pipeline (all keyless / free):
  1. market_sweep.py --all   -> crm_leads (real businesses, 42 verticals x 11 metros)
  2. empire_enricher.enrich_waterfall -> fills crm_leads.email/phone (free)
  3. bridge crm_leads(valid email) -> si_buyer_outreach (dedup by email)
  4. flag synthetic junk in si_buyer_outreach (skip in outreach)

Runs in container (needs empire_os pkg + hub at 127.0.0.1:8081).
"""
from __future__ import annotations
import os, sys, subprocess, sqlite3, re
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
MAX_ENRICH_PER_RUN = 300   # free + bounded; accumulates nightly
MAX_BRIDGE_PER_RUN = 500

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

def log(m): print(f"[lead_harvest] {m}", flush=True)

def open_db():
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA busy_timeout=60000")
    return c

def run_market_sweep():
    log("step1: market_sweep --all (keyless OSM, multi-niche)")
    r = subprocess.run(
        ["/root/venv/bin/python3", "/root/empire_os/sweeps/market_sweep.py", "--all", "--limit", "60"],
        capture_output=True, text=True, timeout=900)
    for line in r.stdout.splitlines()[-6:]:
        log("  " + line)
    if r.returncode != 0:
        log(f"  market_sweep rc={r.returncode}: {r.stderr[-300:]}")

def enrich_crm():
    from empire_os.agents.empire_enricher import enrich_waterfall
    c = open_db(); c.row_factory = sqlite3.Row
    rows = c.execute(
        "SELECT id, business_name, website, niche, metro FROM crm_leads "
        "WHERE (email IS NULL OR email='') "
        "AND website IS NOT NULL AND website!='' "
        "AND website NOT LIKE '%facebook.com' AND website NOT LIKE '%google.com' "
        "AND website NOT LIKE '%yelp.com' AND website NOT LIKE '%angi.com' "
        "AND website NOT LIKE '%thumbtack.com' AND website NOT LIKE '%yellowpages.com' "
        "AND website NOT LIKE '%bbb.org' AND website NOT LIKE '%linkedin.com' "
        "AND website NOT LIKE '%indeed.com' LIMIT ?", (MAX_ENRICH_PER_RUN,)
    ).fetchall()
    log(f"step2: enriching {len(rows)} crm_leads (free waterfall)")
    done = 0
    for r in rows:
        try:
            res = enrich_waterfall({
                "company": r["business_name"] or "",
                "website": r["website"] or "",
                "domain": (r["website"] or "").replace("www.", ""),
                "industry": r["niche"], "city": r["metro"],
            })
            email = (res.get("email") or "").strip()
            phone = (res.get("phone") or "").strip()
            if email and not EMAIL_RE.match(email):
                email = ""
            if email or phone:
                c.execute("UPDATE crm_leads SET email=COALESCE(NULLIF(?,''),email), "
                          "phone=COALESCE(NULLIF(?,''),phone) WHERE id=?",
                          (email, phone, r["id"]))
                done += 1
        except Exception as e:
            log(f"  enrich err id={r['id']}: {e}")
    c.commit(); c.close()
    log(f"  enriched {done} rows with contact info")

def bridge_to_outreach():
    c = open_db()
    # crm_leads rows with a valid email not yet in si_buyer_outreach
    rows = c.execute(
        "SELECT business_name, email, phone, niche, metro, website FROM crm_leads "
        "WHERE email IS NOT NULL AND email!='' AND email LIKE '%@%' "
        "AND email NOT LIKE '%(%' AND email NOT LIKE '%)%' "
        f"AND email IN (SELECT email FROM crm_leads WHERE email LIKE '%@%' GROUP BY email) "
        "LIMIT ?", (MAX_BRIDGE_PER_RUN,)
    ).fetchall()
    # dedup by email within batch
    seen = set(); pending = []
    for r in rows:
        em = r["email"].strip().lower()
        if not EMAIL_RE.match(em) or em in seen:
            continue
        seen.add(em)
        pending.append((r["business_name"], em, r["niche"], r["metro"], r["website"]))
    ins = 0
    for biz, em, niche, metro, web in pending:
        cur = c.execute(
            "INSERT OR IGNORE INTO si_buyer_outreach "
            "(prospect_id, business_name, email, niche, metro, website, reply_state, email_status, created_at) "
            "VALUES (?,?,?,?,?,?, 'cold', 'valid', ?)",
            (f"crm_{abs(hash(em))}", biz, em, niche, metro, web,
             datetime.now(timezone.utc).isoformat()))
        ins += cur.rowcount
    c.commit()
    log(f"step3: bridged {ins} new valid emails crm_leads -> si_buyer_outreach")

def flag_junk():
    c = open_db()
    n = c.execute("UPDATE si_buyer_outreach SET email_status='junk' "
                  "WHERE email_status IS NULL OR email_status='unknown' "
                  "AND (email LIKE '%(%' OR email LIKE '%)%' OR email LIKE '%na@na%')").rowcount
    # mark anything already sent as valid
    v = c.execute("UPDATE si_buyer_outreach SET email_status='valid' "
                  "WHERE email_status IN ('unknown', NULL) AND last_emailed IS NOT NULL "
                  "AND email NOT LIKE '%(%' AND email NOT LIKE '%)%'").rowcount
    c.commit()
    log(f"step4: flagged junk={n}, promoted valid={v}")

def main():
    run_market_sweep()
    enrich_crm()
    bridge_to_outreach()
    flag_junk()
    c = open_db()
    tot = c.execute("SELECT COUNT(*) FROM si_buyer_outreach WHERE email_status='valid'").fetchone()[0]
    uniq = c.execute("SELECT COUNT(DISTINCT email) FROM si_buyer_outreach "
                     "WHERE email_status='valid'").fetchone()[0]
    log(f"DONE — si_buyer_outreach valid pool: {tot} rows / {uniq} unique deliverable")
    c.close()

if __name__ == "__main__":
    main()
