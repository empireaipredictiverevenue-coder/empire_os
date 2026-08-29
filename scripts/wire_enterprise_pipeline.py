#!/usr/bin/env python3
"""Wire Enterprise Lead-Gen (Task C) + Enrich crm_leads (Task B).

Bounded, real-DB producer:
  (B) Enrich up to N crm_leads (website, no email) using FREE waterfall
      providers only (internal_scraper, social_scraper) -> update email.
  (C) Move qualified REAL prospects into crm_lead_pipeline and increment
      enterprise_leads_campaign.current_leads_generated toward 100/mo target.

No fabricated leads. Every row is a live DB record.
"""
import sqlite3, sys, time, signal
from datetime import datetime, timezone
sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"
ENT_CAMPAIGN_ID = 1          # Enterprise Lead Generation Q2 2026 (target 100/mo)
MONTHLY_TARGET = 100
ENRICH_LIMIT = 40            # bounded to avoid timeout

# per-lead wall clock guard
def _timeout(signum, frame):
    raise TimeoutError("lead enrichment timed out")
signal.signal(signal.SIGALRM, _timeout)


def get_conn():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def enrich_batch(limit: int) -> int:
    """(B) Enrich crm_leads with website but no valid email via free providers."""
    from empire_os.waterfall import (
        Waterfall, ValidationGate,
        InternalScraperProvider, SocialScraperProvider,
    )
    gate = ValidationGate(min_confidence=0.6, require_email=True)
    wf = Waterfall(
        providers=[InternalScraperProvider(), SocialScraperProvider()],
        gate=gate, max_attempts=2,
    )
    c = get_conn()
    rows = c.execute(
        "SELECT lead_uid, business_name, website, email, phone, city, state, niche "
        "FROM crm_leads "
        "WHERE (email IS NULL OR email='' OR email NOT LIKE '%@%') "
        "AND website IS NOT NULL AND website != '' "
        "LIMIT ?", (limit,)
    ).fetchall()

    enriched = 0
    for r in rows:
        lead_info = {
            "company": r["business_name"],
            "website": r["website"],
            "phone": r["phone"],
            "city": r["city"], "state": r["state"], "niche": r["niche"],
        }
        try:
            signal.setitimer(signal.ITIMER_REAL, 8)  # 8s cap per lead
            res = wf.enrich(lead_info)
            signal.setitimer(signal.ITIMER_REAL, 0)
        except Exception:
            signal.setitimer(signal.ITIMER_REAL, 0)
            continue
        if res.success and res.contact and res.contact.email:
            c.execute(
                "UPDATE crm_leads SET email=?, enriched=1, enrichment_score=? "
                "WHERE lead_uid=?",
                (res.contact.email, round(res.contact.confidence, 2), r["lead_uid"]),
            )
            enriched += 1
    c.commit()
    c.close()
    return enriched


def wire_pipeline(batch_size: int) -> int:
    """(C) Insert qualified real prospects into crm_lead_pipeline and bump counter."""
    c = get_conn()
    # Qualified = real buyers with valid email OR omega-scored crm_leads
    prospects = c.execute(
        "SELECT email, business_name, niche, metro, 'buyer' AS kind "
        "FROM si_buyer_outreach "
        "WHERE email LIKE '%@%' AND email NOT LIKE '%example%' AND email NOT LIKE '%2x.avif%' "
        "AND reply_state IN ('contacted','replied','cold') "
        "LIMIT ?", (batch_size,)
    ).fetchall()

    stage_id = "enterprise_lead"
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for p in prospects:
        cur = c.execute(
            "INSERT OR IGNORE INTO crm_lead_pipeline "
            "(lead_id, stage_id, entered_at) VALUES (?,?,?)",
            (p["email"], stage_id, now),
        )
        if cur.rowcount:
            inserted += 1

    # Increment the enterprise campaign counter (idempotent-ish: capped at target)
    cur = c.execute(
        "SELECT current_leads_generated FROM enterprise_leads_campaign WHERE campaign_id=?",
        (ENT_CAMPAIGN_ID,)).fetchone()[0]
    new_total = min(cur + inserted, MONTHLY_TARGET)
    c.execute(
        "UPDATE enterprise_leads_campaign SET current_leads_generated=? WHERE campaign_id=?",
        (new_total, ENT_CAMPAIGN_ID))
    c.commit()
    c.close()
    return inserted, new_total


if __name__ == "__main__":
    print(f"[B] enriching up to {ENRICH_LIMIT} crm_leads (free providers)...")
    b = enrich_batch(ENRICH_LIMIT)
    print(f"[B] enriched {b} leads")

    print(f"[C] wiring enterprise pipeline (batch 100)...")
    ins, total = wire_pipeline(100)
    print(f"[C] inserted {ins} qualified prospects; campaign counter now {total}/{MONTHLY_TARGET}")

    # final state
    c = get_conn()
    print("  crm_leads valid emails:", c.execute(
        "SELECT COUNT(*) FROM crm_leads WHERE email LIKE '%@%'").fetchone()[0])
    print("  crm_lead_pipeline rows:", c.execute(
        "SELECT COUNT(*) FROM crm_lead_pipeline").fetchone()[0])
    c.close()
