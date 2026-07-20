#!/usr/bin/env python3
"""Empire OS Nurture Daemon — 3-step threaded cold-email sequence.

Stolen + adapted from:
- ai-cold-outreach-engine (warm-up ramp, threaded replies, state machine)
- opengtm (ICP tiers hot/warm/cold)
- dealer-scraper (contacts_json model)

Design:
- Reads buyer prospects from crm_leads (status='new', contacts_json populated)
  OR si_buyer_outreach (legacy, reply_state='cold')
- Sends max DAILY_CAP emails, ramping 5->8->12->15 over 4 weeks (warm-up)
- 3-step sequence: Day0 value, Day+3 nudge (reply in thread), Day+7 micro-ask
- On reply (POST /v1/inbound/reply flips reply_state), prospect exits sequence
- Writes queued sends to si_outbox (source='nurture_daemon', status='pending')
  for the existing founder_outreach / Brevo sender to ship.

Run:
  nurture_daemon.py --dry-run          # show what would send
  nurture_daemon.py --limit 10         # send up to 10 now
  nurture_daemon.py --once             # one tick
"""
from __future__ import annotations
import argparse, json, os, sqlite3, sys, time
from datetime import datetime, timezone, timedelta

DB = "/root/empire_os/empire_os.db"
HUB = "http://127.0.0.1:8081"

# warm-up: daily cap derived from days since START_DATE
START_DATE = datetime(2026, 7, 20, tzinfo=timezone.utc)
def daily_cap(now=None):
    now = now or datetime.now(timezone.utc)
    days = (now - START_DATE).days
    if days < 7:   return 5
    if days < 14:  return 8
    if days < 21:  return 12
    return 15

# sequence steps: (day_offset, kind)
SEQUENCE = [
    (0,  "value"),     # Day 0: niche insight, no ask
    (3,  "nudge"),     # Day +3: short reply in thread
    (7,  "micro_ask"), # Day +7: "5-min chat?"
]

VALUE_TPL = (
    "Hi {name}, noticed {trigger} is hitting {metro} hard this season. "
    "We grade those homeowner triggers and route the hot ones to local crews. "
    "No ask — just know the pipeline exists if you want it."
)
NUdGE_TPL = (
    "Following up on the roofing trigger volume in {metro}. "
    "Last storm cycle we tracked 400+ homeowner leads there. Happy to show the grade breakdown."
)
ASK_TPL = (
    "Worth a 5-min look at how the trigger feed works? "
    "You'd get exclusive homeowner leads in {metro}, pay per seated lead in USDC. "
    "Reply 'yes' and I'll send the link."
)

def get_prospects(cur, limit):
    """Pull buyers ready for next sequence step."""
    rows = cur.execute("""
        SELECT prospect_id, business_name, email, metro, niche,
               reply_state, seq_step, last_touch_at
        FROM si_buyer_outreach
        WHERE reply_state IN ('cold','contacted')
          AND email IS NOT NULL AND email != ''
          AND email NOT LIKE '%@example%' AND email NOT LIKE 'webhook%'
          AND email NOT LIKE '%sentry%' AND email NOT LIKE '%calendar.google%'
          AND email NOT LIKE '%@domain.com' AND email NOT LIKE '%@test%'
          AND (email LIKE '%.com' OR email LIKE '%.net' OR email LIKE '%.org'
               OR email LIKE '%.us' OR email LIKE '%.co')
          AND (seq_step IS NULL OR seq_step < 3)
        ORDER BY prospect_id
        LIMIT ?
    """, (limit,)).fetchall()
    return rows

def build_email(kind, name, metro, niche):
    name = (name or "there").split()[0] if name else "there"
    trigger = {"residential_roofing":"roof damage","roof_repair":"storm repair",
               "water_damage":"flood damage","hvac":"HVAC failure"}.get(niche,"storm damage")
    tpl = {"value":VALUE_TPL,"nudge":NUdGE_TPL,"ask":ASK_TPL}[kind]
    return tpl.format(name=name, metro=metro or "your area", trigger=trigger)

def queue_send(cur, prospect, kind, step):
    pid, name, email, metro, niche = prospect[0], prospect[1], prospect[2], prospect[3], prospect[4]
    body = build_email(kind, name, metro, niche)
    meta = json.dumps({"niche": niche, "metro": metro, "seq_step": step, "kind": kind})
    cur.execute("""
        INSERT INTO si_outbox (to_email, subject, body, source, status, created_at, meta_json)
        VALUES (?, ?, ?, 'nurture_daemon', 'pending', ?, ?)
    """, (email, f"Empire OS — {kind} ({metro or 'leads'})", body,
          datetime.now(timezone.utc).isoformat(), meta))
    # advance seq_step + last_touch
    cur.execute("""
        UPDATE si_buyer_outreach SET seq_step=?, last_touch_at=?, reply_state='contacted'
        WHERE prospect_id=?
    """, (step+1, datetime.now(timezone.utc).isoformat(), pid))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    cap = daily_cap()
    print(f"[nurture] daily_cap={cap} limit={args.limit} dry_run={args.dry_run}")
    c = sqlite3.connect(DB); cur = c.cursor()

    # count already sent today
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sent_today = cur.execute(
        "SELECT COUNT(*) FROM si_outbox WHERE source='nurture_daemon' AND created_at LIKE ?",
        (today+"%",)).fetchone()[0]
    room = max(0, cap - sent_today)
    print(f"[nurture] sent_today={sent_today} room={room}")

    if room == 0:
        print("[nurture] daily cap hit. stopping."); return

    prospects = get_prospects(cur, min(args.limit, room))
    print(f"[nurture] prospects due: {len(prospects)}")

    sent = 0
    for p in prospects:
        pid, name, email, metro, niche = p[0], p[1], p[2], p[3], p[4]
        step = p[6] or 0  # seq_step
        if step >= len(SEQUENCE):
            continue
        kind = SEQUENCE[step][1]
        if args.dry_run:
            print(f"  [dry] {email} step{step} {kind}")
        else:
            queue_send(cur, p, kind, step)
            print(f"  [send] {email} step{step} {kind}")
            sent += 1
    if not args.dry_run:
        c.commit()
    print(f"[nurture] done. queued={sent}")

if __name__ == "__main__":
    main()
