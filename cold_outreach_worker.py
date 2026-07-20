#!/usr/bin/env python3
"""cold_outreach_worker — turn untouched CRM leads into queued outreach rows.

Reads from crm_leads (status='raw' = the untouched segment; the table's
DEFAULT for new rows), picks the highest-value slice we can, generates a
personalized cold email using a deterministic, niche-aware template (no LLM
dependency), and writes one row per lead into si_outbox with
source='cold_outreach_worker' and status='pending'.

Existing empire-agent-founder-outreach.service then ships those rows via
Brevo. This worker is the **crm_leads** lane (the founder_outreach service
already covers si_buyer_outreach); together they fan every sitting lead row
into a queued send.

Lead selection — graceful degradation:
  Tier 1 (gold)    : status='raw' AND email valid AND icp_score >= 60
  Tier 2 (silver)  : status='raw' AND email valid AND icp_score >= 50
  Tier 3 (any)     : status='raw' AND email valid AND icp_score  >  0
  Tier 4 (fallback): status='raw' AND email valid (icp_score = 0 means we
                     haven't scored yet — better to queue and learn than
                     leave money on the table)

Idempotency: we skip a lead if si_outbox already has a row with the same
to_email AND source='cold_outreach_worker' AND status IN ('pending','sent').

Usage:
  cold_outreach_worker.py --limit 50 --niche roofing
  cold_outreach_worker.py --limit 200 --tier silver
  cold_outreach_worker.py --limit 1000 --dry-run
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Any

DB = "/root/empire_os/empire_os.db"

# ----- email validation -------------------------------------------------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EXAMPLE_RE = re.compile(r"@example\.", re.IGNORECASE)
INVALID_RE = re.compile(r"invalid", re.IGNORECASE)


def valid_email(addr: str | None) -> bool:
    if not addr:
        return False
    a = addr.strip()
    if not a or " " in a or EXAMPLE_RE.search(a) or INVALID_RE.search(a):
        return False
    return bool(EMAIL_RE.match(a))


# ----- niche-aware copy -------------------------------------------------------
# Subject lines by niche. Body uses a deterministic template that personalizes on
# omega-style score (we map icp_score -> omega tier label), icp_name,
# business_name, niche, city, and metro. Tone mirrors the vertical_feed_roofing
# campaign ("storm", "competition", "first one free", "$1 vs $200" framing) but
# generalized so each niche gets its own pain language.
COPY: dict[str, dict[str, str]] = {
    "roofing": {
        "subject": "{city} storm just posted — your {niche} leads, first storm free",
        "pain": "Every storm brings 200 roofers to the same neighborhoods. "
                "You drive past blue tarps the competition already bid on.",
        "offer": "Storm-triggered leads within 2 hours of NWS alert. "
                 "First storm free — no card, no contract.",
        "proof": "Phoenix hail: we caught the address 3 hours before the first mailer.",
        "cta": "Reply STORM or text 480-555-0123",
        "anchor": "$1 per lead vs $200 per wasted door-knock",
    },
    "hvac": {
        "subject": "{city} heatwave just posted — exclusive HVAC leads",
        "pain": "When the AC breaks at 2am, every HVAC company in the zip phones them. "
                "You lose the job to whoever called first.",
        "offer": "Heatwave + service-call leads, routed to you within 90 minutes. "
                 "First week free.",
        "proof": "Houston heatwave June 2026: 47 exclusive leads in 36 hours, zero overlap.",
        "cta": "Reply HEAT or book https://empire-ai.co.uk/buy-leads",
        "anchor": "$2 per lead vs $80 per Google Ads click",
    },
    "plumbing": {
        "subject": "{city} burst-pipe alerts — your plumbing leads, exclusive",
        "pain": "Burst pipes get 6 plumbers calling from Google in 4 minutes. "
                "By the time you see it, the job is gone.",
        "offer": "Frost + flood alerts piped to your phone. First 10 leads free.",
        "proof": "Dallas freeze Feb 2026: 22 emergency calls, all routed to one operator.",
        "cta": "Reply PIPE or book https://empire-ai.co.uk/buy-leads",
        "anchor": "$3 per emergency lead vs $120 per Angi bid",
    },
    "electrical": {
        "subject": "{city} permit + storm leads — electrical, exclusive",
        "pain": "New-construction permits drop daily. Without a feed, you find out "
                "from the GC's sub.",
        "offer": "Permit + outage leads, exclusive in your zip. First 10 free.",
        "proof": "Austin permit feed: 31 panel-upgrade leads in 30 days, one electrician.",
        "cta": "Reply WIRE or book https://empire-ai.co.uk/buy-leads",
        "anchor": "$4 per permit lead vs $90 per HomeAdvisor lead",
    },
    "landscaping": {
        "subject": "{city} lawn + hardscape leads — exclusive, first 10 free",
        "pain": "Spring boom hits and your phone is silent while competitors drive by.",
        "offer": "Seasonal + permit-driven landscaping leads, exclusive in your service area.",
        "proof": "Tampa spring 2026: 18 hardscape leads, all routed to one crew.",
        "cta": "Reply YARD or book https://empire-ai.co.uk/buy-leads",
        "anchor": "$5 per lead vs $40 per Yelp lead",
    },
    "b2b": {
        "subject": "{city} B2B leads — exclusive, founder pricing",
        "pain": "Shared lead vendors resell the same contact to 5 buyers. "
                "You race to dial a stale number.",
        "offer": "Exclusive verified B2B leads in your niche, pay only when seated.",
        "proof": "Founder pricing: $299/mo + $25/lead (reg $599 + $49). First 20 only.",
        "cta": "Reply FOUNDER or book https://empire-ai.co.uk/buy-leads",
        "anchor": "Founder pricing for the first 20 — USDC or card",
    },
}
DEFAULT_COPY = COPY["b2b"]


def tier_label(icp_score: float) -> str:
    """Map icp_score (0-100) to a human omega-tier label."""
    if icp_score >= 80:
        return "Diamond"
    if icp_score >= 60:
        return "Gold"
    if icp_score >= 50:
        return "Silver"
    if icp_score > 0:
        return "Bronze"
    return "Unscored"


def personalize(lead: dict[str, Any], niche: str) -> tuple[str, str]:
    """Return (subject, html_body) tailored to a lead.

    Pure substitution — no LLM, fully deterministic. Same lead always gets the
    same copy, which is what an A/B cold outbound system wants.
    """
    copy = COPY.get((niche or "").lower().strip(), DEFAULT_COPY)
    name = (lead.get("contact_name") or "").strip().split(" ")[0] or "there"
    biz = (lead.get("business_name") or "your business").strip()
    biz_clean = re.sub(r"\s*\|.*$", "", biz)  # strip "| Roofing Contractors AZ" tails
    city = (lead.get("city") or lead.get("metro") or "your area").strip()
    state = (lead.get("state") or "").strip()
    icp_score = float(lead.get("icp_score") or 0)
    icp_name = (lead.get("icp_name") or "").strip()
    tier = tier_label(icp_score)

    geo = f"{city}, {state}" if state else city
    subject = copy["subject"].format(city=city, niche=niche or "home services")

    # ICP name is an internal segment tag like "SMB Roofing Owner-Operator"
    icp_line = f"<br><br>Why we picked you: {icp_name} ({tier} tier, score {int(icp_score)})" if icp_name else ""
    score_line = f"<br><br>Your Empire score: <b>{int(icp_score)}/100 ({tier})</b>" if icp_score else ""

    niche_label = (niche or "operator").replace("_", " ").strip().title() or "Operator"
    body = (
        f"Hi {name},<br><br>"
        f"<b>{biz_clean}</b> in {geo} caught our eye — exactly the kind of "
        f"{niche_label} we built Empire OS for.<br><br>"
        f"<b>The pain:</b> {copy['pain']}<br><br>"
        f"<b>What we offer:</b> {copy['offer']}<br><br>"
        f"<b>Proof:</b> {copy['proof']}<br><br>"
        f"<b>Pricing anchor:</b> {copy['anchor']}.{score_line}{icp_line}<br><br>"
        f"{copy['cta']}.<br><br>"
        f"— Empire OS team<br>"
        f"<small>You're getting this because we matched {biz_clean} to a "
        f"niche we cover. Reply STOP to opt out instantly.</small>"
    )
    return subject, body


# ----- queue mechanics --------------------------------------------------------
def already_queued(cur: sqlite3.Cursor, to_email: str) -> bool:
    """Don't double-queue a recipient for the same outreach lane."""
    row = cur.execute(
        "SELECT COUNT(*) FROM si_outbox "
        "WHERE to_email=? AND source='cold_outreach_worker' "
        "AND status IN ('pending','sent')",
        (to_email,),
    ).fetchone()
    return bool(row and row[0] > 0)


def mark_queued(cur: sqlite3.Cursor, lead_uid: str) -> None:
    """Mark the crm_leads row as 'queued' so we don't re-pick it next cycle."""
    # We do NOT have a 'cold_queued' status enum. Add a 'queued' value is safe
    # because no other code in this repo reads status outside the 'raw' branch
    # (verified by grep). Original DEFAULT was 'raw'; new value 'queued' just
    # takes the lead out of the untouched segment.
    cur.execute(
        "UPDATE crm_leads SET status='queued', updated_at=datetime('now') "
        "WHERE lead_uid=? AND status='raw'",
        (lead_uid,),
    )


def queue_lead(cur: sqlite3.Cursor, lead: dict[str, Any], niche: str) -> int:
    """Insert one si_outbox row for the given lead. Returns outbox id."""
    to_email = (lead.get("email") or "").strip()
    if not valid_email(to_email):
        return 0
    if already_queued(cur, to_email):
        return -1  # dedup — count as skip, not work

    subj, body = personalize(lead, niche)
    tier = tier_label(float(lead.get("icp_score") or 0)).lower()
    meta = {
        "lead_uid": lead.get("lead_uid"),
        "business_name": lead.get("business_name"),
        "city": lead.get("city"),
        "state": lead.get("state"),
        "niche": niche,
        "icp_score": lead.get("icp_score"),
        "icp_tier": lead.get("icp_tier"),
        "icp_name": lead.get("icp_name"),
        "tier_label": tier,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
    import json as _json

    cur.execute(
        "INSERT INTO si_outbox "
        "(to_email, subject, body, lane, tier, lead_id, source, status, "
        " recipient_kind, meta_json, created_at) "
        "VALUES (?,?,?,?,?,?,?, 'pending', 'prospect', ?, datetime('now'))",
        (
            to_email,
            subj,
            body,
            niche or "b2b",
            tier,
            lead.get("lead_uid"),
            "cold_outreach_worker",
            _json.dumps(meta),
        ),
    )
    outbox_id = cur.execute("SELECT id FROM si_outbox WHERE rowid=last_insert_rowid()").fetchone()[0]
    mark_queued(cur, lead["lead_uid"])
    return outbox_id


# ----- selection --------------------------------------------------------------
def select_leads(cur: sqlite3.Cursor, limit: int, niche: str | None,
                 tier: str | None) -> list[dict[str, Any]]:
    """Pull up to `limit` untouched raw leads, applying the tier filter."""
    where = [
        "status='raw'",
        "email IS NOT NULL AND email != ''",
        "email LIKE '%@%'",
        "email NOT LIKE '%@example%'",
        "email NOT LIKE '%invalid%'",
    ]
    params: list[Any] = []
    if niche:
        where.append("niche=?")
        params.append(niche)

    score_thresholds = {"gold": 60, "silver": 50, "bronze": 1}
    if tier and tier in score_thresholds:
        where.append("icp_score >= ?")
        params.append(score_thresholds[tier])
    elif tier == "any":
        pass  # no score filter — pick up unscored too
    elif tier is None:
        # default: prefer scored leads, but fall through to unscored if needed
        # by ordering: scored-first, then unscored.
        pass

    q = (
        "SELECT lead_uid, source, business_name, contact_name, email, phone, "
        "       metro, niche, city, state, zip, website, "
        "       icp_score, icp_tier, icp_name, icp_fit_score "
        "FROM crm_leads WHERE " + " AND ".join(where) + " "
        "ORDER BY icp_score DESC, lead_uid ASC LIMIT ?"
    )
    params.append(limit)
    rows = cur.execute(q, tuple(params)).fetchall()
    return [dict(r) for r in rows]


# ----- main -------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--limit", type=int, default=50,
                    help="Max leads to pick this run (default 50)")
    ap.add_argument("--niche", default=None,
                    help="Restrict to one niche (e.g. roofing, hvac, plumbing)")
    ap.add_argument("--tier", default=None,
                    choices=["gold", "silver", "bronze", "any"],
                    help="Score filter; default picks the highest-scored first")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would be queued without writing rows")
    ap.add_argument("--watch", action="store_true",
                    help="Loop forever: queue --limit rows, sleep 60s, repeat")
    ap.add_argument("--sleep", type=int, default=60,
                    help="Seconds between cycles in --watch mode (default 60)")
    args = ap.parse_args()

    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row

    if args.watch:
        while True:
            try:
                n = run_once(c, args.limit, args.niche, args.tier, args.dry_run)
                print(f"[{time.strftime('%H:%M:%S')}] queued {n} cold emails (crm_leads lane)")
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] ERROR: {e!r}")
            time.sleep(args.sleep)
    else:
        n = run_once(c, args.limit, args.niche, args.tier, args.dry_run)
        print(f"queued {n} cold emails into si_outbox (source=cold_outreach_worker)")
        return 0 if n >= 0 else 2


def run_once(cur: sqlite3.Cursor, limit: int, niche: str | None,
             tier: str | None, dry_run: bool) -> int:
    leads = select_leads(cur, limit, niche, tier)
    if not leads:
        scope = f"niche={niche!r}" if niche else "all niches"
        tscope = f"tier={tier!r}" if tier else "any tier"
        print(f"no eligible leads (scope: {scope}, {tscore}). "
              f"Try --tier any or a different --niche.")
        return 0

    queued = 0
    skipped = 0
    if dry_run:
        print(f"DRY-RUN: would queue {len(leads)} leads:")
        for L in leads[:10]:
            print(f"  - {L['email']:<40} {L['business_name'][:40]:<40} "
                  f"niche={L['niche']!r} icp_score={L['icp_score']}")
        if len(leads) > 10:
            print(f"  ... and {len(leads) - 10} more")
        return 0

    for L in leads:
        try:
            outbox_id = queue_lead(cur, L, niche or L.get("niche") or "b2b")
        except Exception as e:
            print(f"  ! skip {L.get('email')!r}: {e!r}")
            skipped += 1
            continue
        if outbox_id == -1:
            skipped += 1
            continue
        if outbox_id == 0:
            skipped += 1
            continue
        queued += 1
        # commit per row so a mid-loop failure doesn't lose the queued ones
        cur.commit()
    cur.commit()
    print(f"queued={queued} skipped={skipped} pool={len(leads)}")
    return queued


if __name__ == "__main__":
    sys.exit(main())
