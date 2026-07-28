#!/usr/bin/env python3
"""Empire OS Nurture Daemon — 3-step cold-email sequence, human-written.

Rules:
- Grade 6-7 reading level (short sentences, simple words)
- No AI garbage: no "hope you're well", "reaching out", "touching base"
- No "I noticed", "I saw", "just checking in"
- Real human voice: direct, specific, one clear ask
- Uses Empire OS dark-branded HTML template
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
    return 30  # bumped to 30/day once warmed up — Brevo free = 300/day

# sequence steps: (day_offset, kind)
SEQUENCE = [
    (0,  "value"),     # Day 0: useful insight, no ask
    (3,  "nudge"),     # Day +3: short follow-up in thread
    (7,  "ask"),       # Day +7: one clear micro-ask
]

# Grade 6-7 templates — short sentences, simple words, no fluff
VALUE_TPL = (
    "Roof damage spikes in {metro} every storm season. "
    "We track the addresses. We grade the leads. "
    "You get the hot ones. No cost to look."
)
NUDGE_TPL = (
    "Last storm cycle we saw 400+ roof leads in {metro}. "
    "Most went cold because nobody called fast enough. "
    "Want the list?"
)
ASK_TPL = (
    "5-minute call. I'll show you the feed. "
    "You pay per seated lead in USDC. "
    "Reply 'yes' and I'll send the link."
)

# Load branded HTML template
TEMPLATE_PATH = "/root/empire_os/email_templates/founder_pricing_dark.html"
with open(TEMPLATE_PATH) as f:
    HTML_TEMPLATE = f.read()

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

def build_text(kind, name, metro, niche):
    name = (name or "there").split()[0] if name else "there"
    trigger = {"residential_roofing":"roof damage","roof_repair":"storm repair",
               "water_damage":"flood damage","hvac":"HVAC failure"}.get(niche, "storm damage")
    tpl = {"value":VALUE_TPL, "nudge":NUDGE_TPL, "ask":ASK_TPL}[kind]
    return tpl.format(name=name, metro=metro or "your area", trigger=trigger)

def build_html(kind, name, metro, niche):
    """Wrap plain text in branded HTML template."""
    text = build_text(kind, name, metro, niche)
    # Simple conversion: line breaks to <br>, keep it clean
    html_body = text.replace("\n", "<br>")
    return HTML_TEMPLATE.format(
        business_name=name or "there",
        business_short=(name or "lead").lower().replace(" ", "")[:20],
        city=metro or "your city",
        niche=niche or "home services",
        custom_body=html_body
    )

def queue_send(cur, prospect, kind, step):
    pid, name, email, metro, niche = prospect[0], prospect[1], prospect[2], prospect[3], prospect[4]
    text_body = build_text(kind, name, metro, niche)
    html_body = build_html(kind, name, metro, niche)
    meta = json.dumps({"niche": niche, "metro": metro, "seq_step": step, "kind": kind})
    cur.execute("""
        INSERT INTO si_outbox (to_email, subject, body, source, status, created_at, meta_json)
        VALUES (?, ?, ?, 'nurture_daemon', 'pending', ?, ?)
    """, (email, f"Empire OS — {kind} ({metro or 'leads'})", text_body,
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
    ap.add_argument("--watch", action="store_true",
                    help="Continuous loop: tick every N seconds, exit on cap.")
    ap.add_argument("--interval", type=int, default=300,
                    help="Seconds between ticks when --watch is set.")
    args = ap.parse_args()

    if args.watch:
        # Long-lived daemon mode. Auto-enroll cold prospects every 6h,
        # then tick the nurture queue every --interval seconds.
        _run_watch(args)
        return

    _run_once(args)


def _run_watch(args):
    """Continuous: enroll every 6h, tick every interval until daily cap."""
    print(f"[nurture] watching: enroll every 6h, tick every {args.interval}s")
    last_enroll = 0
    while True:
        # Auto-enroll cold prospects every 6h
        if time.time() - last_enroll > 6 * 3600:
            try:
                sys.path.insert(0, "/root/empire_os")
                from empire_os.nurture_enroll import run as enroll_run
                r = enroll_run()
                print(f"[nurture-enroll] {r}")
            except Exception as e:
                print(f"[nurture-enroll] error: {e}")
            last_enroll = time.time()
        # Tick
        _run_once(args)
        # If cap was hit, sleep longer (next day)
        time.sleep(args.interval)


def _run_once(args):

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
        print("[nurture] daily cap hit. stopping.")
        return

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
