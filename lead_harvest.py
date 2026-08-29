#!/usr/bin/env python3
"""lead_harvest.py — orchestrates EXISTING free toolchain into the BD pool.

Quality-first pipeline (all keyless / free):
  step0 market_sweep --all   -> crm_leads (real business NAMES, 42 verts x 11 metros)
  step1 serp_discovery       -> crm_leads (REAL business domains+emails via Serper)
  step2 enrich_pending       -> free waterfall fills more emails
  step3 bridge               -> crm_leads(valid, non-aggregator email) -> si_buyer_outreach
  step4 flag junk            -> synthetic (borough) emails -> email_status='junk'

crm_leads = source of truth. si_buyer_outreach = derived.
"""
from __future__ import annotations
import os, sys, subprocess, sqlite3, re
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
MAX_ENRICH_PER_RUN = 300
MAX_BRIDGE_PER_RUN = 500

# Aggregator / marketplace / job-board domains — never a real business email
AGG = ("glassdoor", "downtobid", "roofingcontractor", "yelp", "thumbtack",
       "homeadvisor", "houzz", "angi", "porch", "networx", "bbb.org",
       "linkedin", "indeed", "ziprecruiter", "monster", "facebook", "google",
       "yellowpages", "procore", "porch.com")

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

def log(m): print(f"[lead_harvest] {m}", flush=True)

def open_db():
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA busy_timeout=60000")
    return c

def run_market_sweep():
    log("step0: market_sweep --all (keyless OSM, multi-niche names)")
    subprocess.run(["/root/venv/bin/python3", "/root/empire_os/sweeps/market_sweep.py",
                    "--all", "--limit", "40"], capture_output=True, text=True, timeout=900)

def run_serp():
    from empire_os.lead_engine import serp_discovery as sd
    METROS = ["Dallas, TX", "Houston, TX", "New York, NY", "Los Angeles, CA",
              "Chicago, IL", "Atlanta, GA", "Miami, FL", "Phoenix, AZ",
              "Philadelphia, PA", "Boston, MA", "San Francisco, CA"]
    niches = list(sd.NICHE_KW.keys())
    log(f"step1: serp_discovery across {len(niches)} niches x {len(METROS)} metros")
    for n in niches:
        for m in METROS:
            try:
                sd.discover_and_score(n, m, 6)
                sd.enrich_pending(n, m, 8)
            except Exception as e:
                log(f"  serp err {n}/{m}: {e}")

def enrich_crm():
    from empire_os.agents.empire_enricher import enrich_waterfall
    c = open_db(); c.row_factory = sqlite3.Row
    rows = c.execute(
        "SELECT id, business_name, website, niche, metro FROM crm_leads "
        "WHERE (email IS NULL OR email='') AND website IS NOT NULL AND website!='' "
        "AND website NOT LIKE '%facebook.com' AND website NOT LIKE '%google.com' "
        "AND website NOT LIKE '%yelp.com' AND website NOT LIKE '%linkedin.com' "
        "LIMIT ?", (MAX_ENRICH_PER_RUN,)
    ).fetchall()
    log(f"step2: enriching {len(rows)} crm_leads (free waterfall)")
    done = 0
    for r in rows:
        try:
            res = enrich_waterfall({"company": r["business_name"] or "",
                "website": r["website"] or "",
                "domain": (r["website"] or "").replace("www.", ""),
                "industry": r["niche"], "city": r["metro"]})
            email = (res.get("email") or "").strip()
            phone = (res.get("phone") or "").strip()
            if email and not EMAIL_RE.match(email): email = ""
            if email or phone:
                c.execute("UPDATE crm_leads SET email=COALESCE(NULLIF(?,''),email), "
                          "phone=COALESCE(NULLIF(?,''),phone) WHERE id=?",
                          (email, phone, r["id"])); done += 1
        except Exception as e:
            log(f"  enrich err id={r['id']}: {e}")
    c.commit(); c.close()
    log(f"  enriched {done} rows")

def _is_agg(em):
    e = em.lower()
    return any(a in e for a in AGG)

def bridge_to_outreach():
    c = open_db()
    rows = c.execute(
        "SELECT DISTINCT business_name, email, phone, niche, metro, website FROM crm_leads "
        "WHERE email IS NOT NULL AND email!='' AND email LIKE '%@%' "
        "AND email NOT LIKE '%(%' AND email NOT LIKE '%)%'"
    ).fetchall()
    seen = set(); pending = []
    for r in rows:
        em = r[1].strip().lower()
        if not EMAIL_RE.match(em) or _is_agg(em) or em in seen:
            continue
        seen.add(em)
        pending.append((r[0], em, r[3], r[4], r[5]))
        if len(pending) >= MAX_BRIDGE_PER_RUN:
            break
    ins = 0
    for biz, em, niche, metro, web in pending:
        cur = c.execute(
            "INSERT OR IGNORE INTO si_buyer_outreach "
            "(prospect_id, business_name, email, niche, metro, url, source, reply_state, email_status) "
            "VALUES (?,?,?,?,?,?, 'crm_bridge', 'cold', 'valid')",
            (f"crm_{abs(hash(em))}", biz, em, niche, metro, web or ""))
        ins += cur.rowcount
    c.commit()
    log(f"step3: bridged {ins} new valid (non-aggregator) emails -> si_buyer_outreach")

def flag_junk():
    c = open_db()
    n = c.execute("UPDATE si_buyer_outreach SET email_status='junk' "
                  "WHERE (email_status IS NULL OR email_status='unknown') "
                  "AND (email LIKE '%(%' OR email LIKE '%)%' OR email LIKE '%na@na%')").rowcount
    v = c.execute("UPDATE si_buyer_outreach SET email_status='valid' "
                  "WHERE email_status IN ('unknown', NULL) AND last_emailed IS NOT NULL "
                  "AND email NOT LIKE '%(%' AND email NOT LIKE '%)%'").rowcount
    c.commit()
    log(f"step4: flagged junk={n}, promoted valid={v}")

def main():
    run_market_sweep()
    run_serp()
    enrich_crm()
    bridge_to_outreach()
    flag_junk()
    c = open_db()
    tot = c.execute("SELECT COUNT(*) FROM si_buyer_outreach WHERE email_status='valid'").fetchone()[0]
    uniq = c.execute("SELECT COUNT(DISTINCT email) FROM si_buyer_outreach WHERE email_status='valid'").fetchone()[0]
    log(f"DONE — si_buyer_outreach valid: {tot} rows / {uniq} unique deliverable")
    c.close()

if __name__ == "__main__":
    main()
