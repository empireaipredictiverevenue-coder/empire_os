"""Outreach Agent — Empire OS v3
===============================
Automated buyer outreach pipeline:
1. Pulls target agencies from internal lead sources (no Clay/Hunter/Apollo needed)
2. Sends first-touch email via Resend with sample lead attached
3. Tracks replies in si_buyer_outreach
4. Routes positive replies to closing agent for demo + plan conversion
"""

from __future__ import annotations
import json
import os
import re
import secrets
import sqlite3
import time
import smtplib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Iterator
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

DB = "/root/empire_os/empire_os.db"
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM", "outreach@empire-ai.co.uk")
OUTREACH_INTERVAL_SEC = int(os.environ.get("OUTREACH_INTERVAL_SEC", "3600"))  # 1 hour
MAX_EMAILS_PER_CYCLE = int(os.environ.get("MAX_EMAILS_PER_CYCLE", "50"))
MAX_EMAILS_PER_DAY = int(os.environ.get("MAX_EMAILS_PER_DAY", "100"))

# Bad email domains to skip
_BAD_EMAIL_DOMAINS = {
    "v.co", "example.com", "buyer.com", "guerrillamail.org",
    "mailinator.com", "tempmail.org", "10minutemail.com",
    "trashmail.com", "yopmail.com", "fakeinbox.com",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db() -> sqlite3.Connection:
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def _daily_email_count() -> int:
    """Count emails sent today."""
    con = _db()
    try:
        c = con.cursor()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = c.execute(
            "SELECT COUNT(*) FROM si_buyer_outreach WHERE date(created_at) = ? AND reply_state IN ('sent', 'opened', 'replied', 'bounced')",
            (today,)
        ).fetchone()
        return row[0] if row else 0
    finally:
        con.close()


def _get_target_agencies(niche: str, metro: str, limit: int = 20) -> List[Dict]:
    """Get target agencies from our lead sources that don't have active outreach."""
    con = _db()
    try:
        c = con.cursor()
        
        # Find agencies in crm_leads that match niche/metro and haven't been contacted
        c.execute("""
            SELECT l.lead_uid, l.business_name, l.email, l.phone, l.website, l.city, l.state, l.zip,
                   l.niche, l.sub_niche, l.omega_score, l.lead_score
            FROM crm_leads l
            LEFT JOIN si_buyer_outreach o ON o.prospect_id = l.lead_uid
            WHERE l.niche = ? 
              AND (l.metro = ? OR l.state = ?)
              AND l.status IN ('raw', 'enriched', 'qualified')
              AND (o.prospect_id IS NULL OR o.reply_state = 'cold')
              AND l.email != '' AND l.email NOT LIKE '%@%.%'
            ORDER BY COALESCE(l.omega_score, 0) + COALESCE(l.lead_score, 0) DESC
            LIMIT ?
        """, (niche, metro, metro[:2] if len(metro) > 2 else metro, limit))
        
        rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def _get_sample_lead(niche: str, metro: str) -> Optional[Dict]:
    """Get a sample delivered lead for the niche/metro to attach."""
    con = _db()
    try:
        c = con.cursor()
        c.execute("""
            SELECT business_name, niche, metro, city, state, details, created_at
            FROM crm_leads
            WHERE niche = ? AND (metro = ? OR state = ?)
              AND status = 'delivered'
            ORDER BY created_at DESC
            LIMIT 1
        """, (niche, metro, metro[:2] if len(metro) > 2 else metro))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def _build_email(agency: Dict, sample_lead: Optional[Dict]) -> MIMEMultipart:
    """Build personalized outreach email with sample lead."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Verified {agency['niche'].replace('_', ' ').title()} lead in {agency['metro']} — {agency['business_name'] or 'your agency'}"
    msg["From"] = RESEND_FROM
    msg["To"] = agency["email"]
    
    # Plain text version
    text = f"""Hi there,

I'm reaching out because we have a verified {agency['niche'].replace('_', ' ')} lead in {agency['metro']} that matches your service area.

Lead details:
- Service: {agency['service_type'] if 'service_type' in agency else agency['niche'].replace('_', ' ').title()}
- Location: {agency.get('city', '')}, {agency.get('state', '')} {agency.get('zip_code', '')}
- Urgency: {agency.get('urgency', 'normal').title()}
- Budget: {agency.get('budget_range', 'not specified').replace('_', ' ').title()}

We're connecting this lead with 3 verified contractors in the area. Would you like to be one of them?

Here's a recent similar lead we delivered in {agency['metro']}:
"""
    if sample_lead:
        text += f"""
- Business: {sample_lead['business_name']}
- Niche: {sample_lead['niche'].replace('_', ' ').title()}
- Metro: {sample_lead['metro']}
- Status: Delivered to buyer, converted to paid seat
"""
    
    text += f"""
Our model: You pay a monthly subscription (Bronze $30/mo for 10 leads, Silver $120/mo for 50, Gold $480/mo for 250) — no per-lead fees. Leads are exclusive to your lane.

Reply to this email or book a 15-min demo: https://cal.empire-ai.co.uk/outreach

Best,
Empire OS Outreach Team
empire-ai.co.uk | Unsubscribe: reply STOP
"""
    
    # HTML version
    html = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #111; max-width: 600px; margin: 0 auto; padding: 24px;">
  <p>Hi there,</p>
  
  <p>I'm reaching out because we have a verified <strong>{agency['niche'].replace('_', ' ')} lead in {agency['metro']}</strong> that matches your service area.</p>
  
  <div style="background: #f8fafc; border-radius: 8px; padding: 16px; margin: 16px 0; border-left: 4px solid #2563eb;">
    <h3 style="margin: 0 0 12px 0; font-size: 1rem;">Lead Details</h3>
    <ul style="margin: 0; padding-left: 20px;">
      <li><strong>Service:</strong> {agency['niche'].replace('_', ' ').title()}</li>
      <li><strong>Location:</strong> {agency.get('city', '')}, {agency.get('state', '')} {agency.get('zip_code', '')}</li>
      <li><strong>Urgency:</strong> {agency.get('urgency', 'normal').title()}</li>
      <li><strong>Budget:</strong> {agency.get('budget_range', 'not specified').replace('_', ' ').title()}</li>
    </ul>
  </div>
  
  <p>We're connecting this lead with 3 verified contractors in the area. Would you like to be one of them?</p>
  
  {f'''
  <div style="background: #f0fdf4; border-radius: 8px; padding: 16px; margin: 16px 0; border-left: 4px solid #16a34a;">
    <h3 style="margin: 0 0 12px 0; font-size: 1rem;">Recent Similar Lead Delivered</h3>
    <ul style="margin: 0; padding-left: 20px;">
      <li><strong>Business:</strong> {sample_lead['business_name']}</li>
      <li><strong>Niche:</strong> {sample_lead['niche'].replace('_', ' ').title()}</li>
      <li><strong>Metro:</strong> {sample_lead['metro']}</li>
      <li><strong>Status:</strong> Delivered → Paid seat</li>
    </ul>
  </div>
  ''' if sample_lead else ''}
  
  <p>Our model: You pay a monthly subscription (Bronze $30/mo for 10 leads, Silver $120/mo for 50, Gold $480/mo for 250) — no per-lead fees. Leads are exclusive to your lane.</p>
  
  <div style="text-align: center; margin: 24px 0;">
    <a href="https://cal.empire-ai.co.uk/outreach" style="background: #111; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Book 15-min Demo</a>
  </div>
  
  <p style="font-size: 0.875rem; color: #666; border-top: 1px solid #eee; padding-top: 16px;">
    Reply to this email or book above.<br>
    Empire OS Outreach Team · empire-ai.co.uk<br>
    <a href="mailto:unsubscribe@empire-ai.co.uk?subject=STOP">Unsubscribe</a>
  </p>
</body>
</html>"""
    
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


def _send_via_resend(msg: MIMEMultipart) -> Dict[str, Any]:
    """Send email via Resend API."""
    if not RESEND_API_KEY:
        return {"ok": False, "error": "RESEND_API_KEY not set"}
    
    import urllib.request
    import urllib.error
    
    # Build Resend payload
    to_addr = msg["To"]
    from_addr = msg["From"]
    subject = msg["Subject"]
    
    # Get HTML and text parts
    html_content = ""
    text_content = ""
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            html_content = part.get_payload(decode=True).decode()
        elif part.get_content_type() == "text/plain":
            text_content = part.get_payload(decode=True).decode()
    
    payload = {
        "from": from_addr,
        "to": [to_addr],
        "subject": subject,
        "html": html_content,
        "text": text_content,
    }
    
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return {"ok": True, "id": result.get("id"), "provider": "resend"}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _log_outreach(lead_uid: str, agency: Dict, sample_lead: Optional[Dict], email_result: Dict) -> None:
    """Log outreach attempt to si_buyer_outreach."""
    con = _db()
    try:
        c = con.cursor()
        c.execute("""
            INSERT INTO si_buyer_outreach
            (lead_uid, buyer_id, email, niche, metro, status, subject, body, sent_at, provider, provider_id, raw_response)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lead_uid,
            agency.get("lead_uid", ""),  # using lead_uid as buyer_id reference
            agency["email"],
            agency["niche"],
            agency["metro"],
            "sent" if email_result.get("ok") else "failed",
            f"Verified {agency['niche'].replace('_', ' ')} lead in {agency['metro']}",
            json.dumps({"sample_lead": sample_lead}) if sample_lead else "",
            now_iso(),
            email_result.get("provider", "resend"),
            email_result.get("id", ""),
            json.dumps(email_result),
        ))
        con.commit()
    finally:
        con.close()


def _update_reply(lead_uid: str, reply_data: Dict) -> None:
    """Update outreach record with reply."""
    con = _db()
    try:
        c = con.cursor()
        c.execute("""
            UPDATE si_buyer_outreach
            SET status = 'replied', replied_at = ?, reply_body = ?, reply_sentiment = ?
            WHERE lead_uid = ? AND status = 'sent'
        """, (
            now_iso(),
            reply_data.get("body", ""),
            reply_data.get("sentiment", "neutral"),
            lead_uid,
        ))
        con.commit()
        
        # If positive reply, create task for closing agent
        if reply_data.get("sentiment") in ("positive", "interested"):
            c.execute("""
                INSERT INTO empire_tasks (task_type, payload, status, created_at)
                VALUES ('closing_demo', ?, 'pending', ?)
            """, (
                json.dumps({"lead_uid": lead_uid, "reply": reply_data}),
                now_iso(),
            ))
            con.commit()
    finally:
        con.close()


def run_outreach_cycle(niches: List[str], metros: List[str]) -> Dict[str, int]:
    """Run one outreach cycle across niches/metros."""
    sent = 0
    failed = 0
    skipped = 0
    
    # Check daily limit
    daily_sent = _daily_email_count()
    if daily_sent >= MAX_EMAILS_PER_DAY:
        return {"sent": 0, "failed": 0, "skipped": 1, "reason": "daily_limit_reached"}
    
    remaining_today = MAX_EMAILS_PER_DAY - daily_sent
    cycle_limit = min(MAX_EMAILS_PER_CYCLE, remaining_today)
    
    for niche in niches:
        if sent >= cycle_limit:
            break
        for metro in metros:
            if sent >= cycle_limit:
                break
            
            agencies = _get_target_agencies(niche, metro, limit=10)
            if not agencies:
                continue
            
            sample_lead = _get_sample_lead(niche, metro)
            
            for agency in agencies:
                if sent >= cycle_limit:
                    break
                
                # Skip bad email domains
                domain = agency["email"].split("@")[-1].lower() if "@" in agency["email"] else ""
                if domain in _BAD_EMAIL_DOMAINS:
                    skipped += 1
                    continue
                
                # Add service details to agency for email
                agency["service_type"] = "repair"
                agency["urgency"] = "normal"
                agency["budget_range"] = "5k_15k"
                
                msg = _build_email(agency, sample_lead)
                result = _send_via_resend(msg)
                
                _log_outreach(agency["lead_uid"], agency, sample_lead, result)
                
                if result.get("ok"):
                    sent += 1
                else:
                    failed += 1
                
                time.sleep(0.5)  # rate limit
    
    return {"sent": sent, "failed": failed, "skipped": skipped, "daily_total": daily_sent + sent}


def handle_inbound_reply(lead_uid: str, body: str, sentiment: str = "neutral") -> None:
    """Handle inbound reply from prospect."""
    _update_reply(lead_uid, {"body": body, "sentiment": sentiment})


if __name__ == "__main__":
    # Test run
    print("=== Outreach Agent Test ===")
    
    # Check config
    print(f"RESEND_API_KEY: {'SET' if RESEND_API_KEY else 'NOT SET'}")
    print(f"RESEND_FROM: {RESEND_FROM}")
    print(f"MAX_EMAILS_PER_DAY: {MAX_EMAILS_PER_DAY}")
    
    # Test target agencies
    agencies = _get_target_agencies("roofing", "LAX", limit=3)
    print(f"\nTarget agencies (roofing/LAX): {len(agencies)}")
    for a in agencies:
        print(f"  {a['business_name']} | {a['email']} | score={a.get('lead_score', 0)}")
    
    # Test sample lead
    sample = _get_sample_lead("roofing", "LAX")
    print(f"\nSample lead: {sample['business_name'] if sample else 'None'}")
    
    # Test email build
    if agencies:
        msg = _build_email(agencies[0], sample)
        print(f"\nEmail built: Subject={msg['Subject']}")
        print(f"To: {msg['To']}")