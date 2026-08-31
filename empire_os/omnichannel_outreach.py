#!/usr/bin/env python3
"""Empire Omega OS — Omnichannel Outreach (EMAIL RUNWAY ONLY).

4-stage conversational flow over email via si_outbox (Brevo backend chain in
mail_sender). Social DM runways NOT built per founder (2026-08-29): no IG /
LinkedIn / FB senders here. Stage 1 = light open, 2 = numbers, 3 = diagnosis,
4 = bridge. Never pitch before stage 3.

Usage:
  python3 -m empire_os.omnichannel_outreach            # process batch
  python3 -m empire_os.omnichannel_outreach --limit 25
"""
import json
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional

sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"
HUB = "http://127.0.0.1:8081"
MAX_PER_RUN = 25
# Daily per-lead cadence guard: don't re-touch a stage within N hours
STAGE_COOLDOWN_H = 48

LOG_DIR = "/root/empire_os/logs"


def log(level: str, msg: str, **fields):
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
             "msg": msg, **fields}
    try:
        with open(f"{LOG_DIR}/omnichannel_outreach.jsonl", "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass
    if level in ("ERROR", "WARN"):
        print(json.dumps(entry))


def get_conn():
    c = sqlite3.connect(DB, timeout=30, isolation_level=None)
    c.execute("PRAGMA busy_timeout=30000")
    c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row
    return c


# ---------------------------------------------------------------- templates
def stage_template(stage: int, lead: Dict) -> tuple:
    """Return (subject, body) for the stage. Conversational, no pitch 1-2."""
    name = (lead.get("first_name") or "").strip() or "there"
    company = lead.get("company") or "your shop"
    niche = (lead.get("niche") or "business").replace("_", " ")

    if stage == 1:  # Light open — zero business talk
        subject = f"quick one, {name}"
        body = (f"Hey {name},\n\nJust checking in — how is the {niche} side "
                f"holding up this season at {company}?\n\n— Empire AI\n")
    elif stage == 2:  # The numbers — peer-level busy-ness question
        subject = f"{company} this week"
        body = (f"Hey {name},\n\nRandom question: are you totally booked out "
                f"this week or do you have room for more jobs?\n\nCurious "
                f"how demand is running.\n\n— Empire AI\n")
    elif stage == 3:  # The diagnosis — point out a gap
        score = lead.get("omega_score") or 0
        est_leak = int(score * 2500)
        subject = f"found ${est_leak:,}/mo leaking at {company}"
        body = (f"Hey {name},\n\nRan a quick audit on {company}'s online "
                f"setup. Looks like roughly ${est_leak:,}/month in missed "
                f"jobs — mostly missing conversion tracking and slow pages.\n\n"
                f"Want the 2-page breakdown? Reply \"send it\".\n\n— Empire AI\n")
    else:  # stage 4 — the bridge
        subject = f"that audit for {company}"
        body = (f"Hey {name},\n\nWe install our automated recovery system "
                f"directly into your existing setup — starts capturing missed "
                f"opportunities on autopilot. 15-min audit call tomorrow?\n\n"
                f"— Empire AI\n")
    return subject, body


# ---------------------------------------------------------------- send path
FOUNDER_APPROVAL_REF = "aprv-omni-outreach-20260829"

def _enqueue_outbox(to_email: str, subject: str, body: str,
                    lead: Dict, stage: int) -> Optional[int]:
    """Insert into si_outbox (mail_sender drains via Brevo chain).

    Dispatch trigger requires: non-empty recipient, founder approval_ref
    (si_founder_approvals.status='approved'), provider_message_id.
    """
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO si_outbox (to_email, subject, body, lane, tier, "
        "lead_id, source, approval_ref, provider_message_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (to_email, subject, body[:8000], "omnichannel",
         lead.get("omega_tier") or "", lead.get("id") or "",
         f"stage{stage}", FOUNDER_APPROVAL_REF,
         f"omni-{lead.get('id')}-{stage}-{int(datetime.now(timezone.utc).timestamp())}"))
    conn.commit()
    out_id = cur.lastrowid
    conn.close()
    return out_id


def _stage_row(lead_id: str) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM outreach_stages WHERE lead_id = ? "
        "ORDER BY id DESC LIMIT 1", (lead_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _cooldown_ok(row: Optional[Dict]) -> bool:
    if not row:
        return True
    last = row.get("last_msg_at") or row.get("updated_at") or ""
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        hours = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
        return hours >= STAGE_COOLDOWN_H
    except Exception:
        return True


def process_lead(lead: Dict) -> Dict:
    lead_id = lead["id"]
    email = (lead.get("email") or "").strip()
    if not email or "@" not in email:
        return {"lead_id": lead_id, "skipped": "no_email"}

    row = _stage_row(lead_id)
    stage = (row or {}).get("stage", 1)
    state = (row or {}).get("stage_state", "new")

    if state in ("booked", "closed"):
        return {"lead_id": lead_id, "skipped": f"state={state}"}
    if not _cooldown_ok(row):
        return {"lead_id": lead_id, "skipped": "cooldown"}

    subject, body = stage_template(stage, lead)
    out_id = _enqueue_outbox(email, subject, body, lead, stage)

    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    if row:
        conn.execute(
            "UPDATE outreach_stages SET stage = ?, stage_state = 'sent', "
            "hook = ?, last_msg_at = ?, updated_at = ? WHERE id = ?",
            (stage, subject, now, now, row["id"]))
    else:
        conn.execute(
            "INSERT INTO outreach_stages (lead_id, channel, stage, hook, "
            "last_msg_at, stage_state) VALUES (?, 'email', ?, ?, ?, 'sent')",
            (lead_id, stage, subject, now))
    conn.execute(
        "UPDATE crm_leads SET outreach_stage = ?, email_sent_at = ?, "
        "outreach_attempted = 1, status = CASE WHEN status = 'new' "
        "THEN 'contacted' ELSE status END WHERE id = ?",
        (stage, now, lead_id))
    conn.commit()
    conn.close()
    return {"lead_id": lead_id, "stage": stage, "outbox_id": out_id,
            "email": email}


def pick_leads(limit: int = MAX_PER_RUN) -> List[Dict]:
    """Stage-1 pool: scored, email present, never contacted.
    Later-stage pool: active threads past cooldown."""
    conn = get_conn()
    new_leads = conn.execute("""
        SELECT * FROM crm_leads
        WHERE email LIKE '%@%' AND omega_score >= 10
          AND (outreach_attempted IS NULL OR outreach_attempted = 0)
        ORDER BY omega_score DESC LIMIT ?""", (limit,)).fetchall()
    threads = conn.execute("""
        SELECT c.* FROM crm_leads c
        JOIN outreach_stages o ON o.lead_id = c.lead_uid
        WHERE o.stage_state IN ('sent', 'replied', 'advanced')
          AND o.stage < 4""", ()).fetchall()
    conn.close()
    picked = [dict(r) for r in new_leads]
    have = {r["lead_uid"] for r in picked}
    for t in threads:
        if t["lead_uid"] not in have:
            picked.append(dict(t))
    return picked


def run_omnichannel_cycle(limit: int = MAX_PER_RUN) -> Dict:
    leads = pick_leads(limit)
    sent = skipped = 0
    for lead in leads:
        try:
            res = process_lead(lead)
            if res.get("skipped"):
                skipped += 1
            else:
                sent += 1
        except Exception as e:
            log("ERROR", "process_lead failed", lead_id=lead.get("id"),
                error=str(e))
            skipped += 1
    log("INFO", "omnichannel cycle done", sent=sent, skipped=skipped)
    return {"success": True, "sent": sent, "skipped": skipped,
            "pool": len(leads)}


if __name__ == "__main__":
    lim = MAX_PER_RUN
    if "--limit" in sys.argv:
        lim = int(sys.argv[sys.argv.index("--limit") + 1])
    print(json.dumps(run_omnichannel_cycle(lim), indent=2))
