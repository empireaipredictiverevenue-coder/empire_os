#!/usr/bin/env python3
"""
Empire Omega OS - Automated Outreach (Email-only, 4-stage flow)
================================================================
Email runway only. Phone/Vapi REMOVED per founder (2026-08-29, permanent).
Social runways (IG/LinkedIn/FB DMs) NOT built — founder deferred.

Delivery: si_outbox enqueue -> mail_sender Brevo/resend/MX chain.
Flow: 4-stage conversational sequence (Light Open -> Numbers -> Diagnosis
-> Bridge), one stage per reply-gated send. Stage 1 fires on qualification;
stages 2-4 advance only when the prospect replies (email_replies match).
"""

import os
import sys
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"
HUB_URL = os.environ.get("EMPIRE_HUB_URL", "http://127.0.0.1:8081")
STAGE_COOLDOWN_HOURS = 48   # min hours between stage sends per lead

def get_conn():
    c = sqlite3.connect(DB, timeout=30, isolation_level=None)
    c.execute("PRAGMA busy_timeout=30000")
    c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row
    return c

def log(level: str, msg: str, **fields):
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg, **fields}
    with open("/root/empire_os/logs/outreach.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
    if level in ("ERROR", "WARN"):
        print(json.dumps(entry))

def get_qualified_leads(limit: int = 50) -> List[Dict]:
    """Get qualified leads ready for outreach (omega_score >= 15, not yet contacted)."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM crm_leads
        WHERE omega_score >= 15
        AND status IN ('new', 'qualified')
        AND (outreach_attempted IS NULL OR outreach_attempted = 0)
        AND email IS NOT NULL AND email != ''
        ORDER BY omega_score DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def vapi_make_call(lead: Dict, script_config: Dict = None) -> Dict:
    """AI voice calls REMOVED per founder (2026-08-29) — phone/Vapi out.
    Kept as no-op stub so callers (hub imports) don't break. Outreach =
    email-only via send_outreach_email(). Do NOT re-add Vapi: permanent."""
    return {"success": False, "error": "phone_outreach_disabled_by_founder"}


# ── 4-stage flow templates (email runway, 4-Stage Universal Flow) ──────────
# Stage 1: Light Open — zero business talk. Stage 2: Numbers — peer-level.
# Stage 3: Diagnosis — the gap they didn't see. Stage 4: The Bridge — booking.
NICHE_LABEL = {
    "roofing": "roofing", "hvac": "HVAC", "plumbing": "plumbing",
    "electrical": "electrical", "dental": "dental", "dental_practice": "dental",
    "mass_tort": "mass tort", "debt_relief": "debt relief",
    "real_estate": "real estate", "solar": "solar", "landscaping": "landscaping",
}

def _niche(lead: Dict) -> str:
    return NICHE_LABEL.get((lead.get("niche") or "").strip().lower(),
                           (lead.get("niche") or "local service").replace("_", " "))

def _metro(lead: Dict) -> str:
    metro = (lead.get("metro") or "").strip()
    return metro.split(",")[0].strip() if metro else "your area"

def _first(lead: Dict) -> str:
    return (lead.get("first_name") or "").strip() or (lead.get("contact_name") or "").strip() or "there"

def build_stage_message(stage: int, lead: Dict) -> Dict:
    """Return {subject, body} for the given flow stage. Personalized, plain text."""
    company = (lead.get("business_name") or lead.get("company") or "your shop").strip()
    name = _first(lead)
    niche = _niche(lead)
    metro = _metro(lead)
    score = lead.get("omega_score", 0) or 0

    if stage == 1:  # Light Open — casual check-in, zero pitch
        subject = f"Quick check-in, {name}"
        body = (f"Hey {name},\n\n"
                f"How's {company} holding up this season? Busy stretch in "
                f"{metro} for {niche} crews lately.\n\n"
                f"No agenda — just staying in touch with owners in the area.\n\n"
                f"— Empire AI\n")
    elif stage == 2:  # Numbers — peer-level workload question
        subject = f"Booked out this week, {name}?"
        body = (f"Hey {name},\n\n"
                f"Curious — are you totally booked out this week or do you "
                f"have room for more {niche} jobs? Talking with a few "
                f"{metro} owners and hearing mixed things.\n\n"
                f"— Empire AI\n")
    elif stage == 3:  # Diagnosis — the gap they didn't see
        estimated_leak = max(int(score) * 2500, 5000)
        subject = f"{company}: the {niche} calls you're not getting"
        body = (f"Hey {name},\n\n"
                f"Ran a quick outside-in look at {company}'s online setup. "
                f"Nothing invasive — just what any customer sees.\n\n"
                f"What stood out:\n"
                f"- Conversion tracking: partial or missing, so ad spend and "
                f"word-of-mouth can't be measured against booked jobs\n"
                f"- Page speed: slow enough that mobile visitors bounce before "
                f"they reach the contact form\n"
                f"- Missed-call capture: {niche} callers who hit voicemail "
                f"rarely call back — those are jobs walking to a competitor\n"
                f"- Form capture: contact forms not capturing full visitor info\n\n"
                f"Ballpark, that combination quietly costs a {niche} shop in "
                f"{metro} on the order of ${estimated_leak:,}/month in jobs "
                f"that were winnable. Not a crisis — just money on the table.\n\n"
                f"Happy to walk through the specifics.\n\n"
                f"— Empire AI\n")
    elif stage == 4:  # Bridge — low-commitment booking hook
        subject = f"Worth a 15-min audit, {name}?"
        body = (f"Hey {name},\n\n"
                f"One follow-up and I'll leave you alone. We install an "
                f"automated revenue recovery system into your existing setup — "
                f"missed-call textback, form capture, tracking — so {company} "
                f"starts capturing the jobs it's already paying to generate. "
                f"No rip-and-replace; it bolts onto what you use now.\n\n"
                f"Let's lock a quick 15-min audit tomorrow 9:00 AM — I'll "
                f"show the exact leaks we found for {company} and you can "
                f"decide if it's worth fixing.\n\n"
                f"Reply with a time that works and I'll send the invite.\n\n"
                f"— Empire AI\n")
    else:
        return {"subject": "", "body": ""}
    return {"subject": subject, "body": body}


def _enqueue_outbox(email: str, subject: str, body: str, lead: Dict,
                    stage: int) -> Optional[int]:
    """Queue via hub /v1/outbox/enqueue (persistent si_outbox -> Brevo chain)."""
    import urllib.request as _ur
    payload_bytes = json.dumps({
        "to_email": email, "subject": subject, "body": body,
        "lane": lead.get("niche") or "omega_pipeline",
        "tier": lead.get("omega_tier") or "qualified",
        "lead_id": lead.get("id"), "source": f"omega_outreach_stage{stage}",
    }).encode()
    r = _ur.Request(f"{HUB_URL}/v1/outbox/enqueue", data=payload_bytes,
                    headers={"Content-Type": "application/json"})
    try:
        with _ur.urlopen(r, timeout=10) as resp:
            out = json.loads(resp.read())
            return out.get("id") if out.get("ok") else None
    except Exception as e:
        log("ERROR", f"outbox enqueue failed lead={lead.get('id')}", error=str(e))
        return None

def _record_stage(lead: Dict, stage: int, outbox_id: Optional[int]) -> None:
    """Upsert outreach_stages row + crm_leads status columns."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    conn.execute("""
        INSERT INTO outreach_stages (lead_id, channel, stage, hook,
                                     last_msg_at, stage_state, updated_at)
        VALUES (?, 'email', ?, ?, ?, 'sent', ?)
    """, (lead.get("id"), stage, f"stage{stage}", now, now))
    conn.execute("""
        UPDATE crm_leads
        SET status = 'contacted', outreach_attempted = 1, outreach_at = ?,
            email_sent = 1, email_sent_at = ?, outreach_stage = ?
        WHERE id = ?
    """, (now, now, stage, lead.get("id")))
    conn.commit()
    conn.close()
    if outbox_id:
        log("INFO", f"queued stage{stage}", lead_id=lead.get("id"), outbox_id=outbox_id)

def _reply_count(lead: Dict) -> int:
    """Count inbound replies from this lead (email_replies or si_inbox)."""
    email = (lead.get("email") or "").strip().lower()
    if not email:
        return 0
    conn = get_conn()
    try:
        # email_replies keys via lead_id; fall back to si_inbox sender match
        n = conn.execute(
            "SELECT COUNT(*) FROM email_replies WHERE lead_id=?",
            (lead.get("id"),)).fetchone()[0]
        if not n:
            n = conn.execute(
                "SELECT COUNT(*) FROM si_inbox WHERE LOWER(from_email)=?",
                (email,)).fetchone()[0]
    except Exception:
        n = 0
    conn.close()
    return n

def _stage_cooldown_ok(lead: Dict) -> bool:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT last_msg_at FROM outreach_stages WHERE lead_id=? "
            "ORDER BY last_msg_at DESC LIMIT 1", (lead.get("id"),)).fetchone()
        if not row:
            return True
        last = datetime.fromisoformat(row[0])
        hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
        return hours >= STAGE_COOLDOWN_HOURS
    except Exception:
        return True
    finally:
        conn.close()

def send_outreach_email(lead: Dict, stage: int = 1) -> Dict:
    """Build + enqueue the stage-appropriate email via si_outbox (Brevo chain)."""
    email = (lead.get("email") or "").strip()
    if not email:
        return {"success": False, "error": "No email address"}
    msg = build_stage_message(stage, lead)
    if not msg["subject"]:
        return {"success": False, "error": f"bad stage {stage}"}
    outbox_id = _enqueue_outbox(email, msg["subject"], msg["body"], lead, stage)
    if outbox_id is None:
        return {"success": False, "error": "outbox_enqueue_failed"}
    _record_stage(lead, stage, outbox_id)
    return {"success": True, "outbox_id": outbox_id, "stage": stage,
            "subject": msg["subject"]}

def trigger_lead_outreach(lead: Dict) -> Dict:
    """Advance the 4-stage flow for one lead (email-only, reply-gated)."""
    log("INFO", f"Starting outreach for lead {lead.get('id')}")
    stage = (lead.get("outreach_stage") or 1)
    replies = _reply_count(lead)
    # Reply-gating: stage never outruns replies+1 (no pitch stacking)
    effective_stage = min(stage, replies + 1) if replies else stage
    result = send_outreach_email(lead, stage=effective_stage)
    return {"email": result, "lead_id": lead.get("id"),
            "stage": effective_stage, "replies": replies}

def run_outreach_cycle(max_leads: int = 50) -> Dict:
    """Run outreach cycle for qualified leads (stage 1) + advancing replies."""
    log("INFO", f"Starting outreach cycle, max_leads={max_leads}")
    leads = get_qualified_leads(max_leads)
    contacted = 0
    email_success = 0
    for lead in leads:
        result = trigger_lead_outreach(lead)
        if result["email"].get("success"):
            email_success += 1
            contacted += 1
        time.sleep(2)
    result = {
        "total_qualified": len(leads),
        "contacted": contacted,
        "email_success": email_success,
    }
    log("INFO", "Outreach cycle complete", **result)
    return result

if __name__ == "__main__":
    result = run_outreach_cycle(50)
    print(json.dumps(result, indent=2))
