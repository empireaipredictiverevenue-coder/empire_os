#!/usr/bin/env python3
"""
Empire Omega OS - Automated Outreach (Vapi + Resend)
=====================================================
AI voice calls (Vapi) + outcome-based emails (Resend)
Integrated into Empire OS v3.
"""

import os
import sys
import json
import sqlite3
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"

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
        ORDER BY omega_score DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def vapi_make_call(lead: Dict, script_config: Dict = None) -> Dict:
    """Trigger Vapi AI call to lead."""
    # Vapi API integration
    vapi_key = os.environ.get("VAPI_API_KEY", "")
    if not vapi_key:
        return {"success": False, "error": "VAPI_API_KEY not set"}
    
    phone = lead.get("phone", "").strip()
    if not phone:
        return {"success": False, "error": "No phone number"}
    
    # Vapi API call
    url = "https://api.vapi.ai/call"
    headers = {
        "Authorization": f"Bearer {os.environ.get('VAPI_API_KEY', '')}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "phoneNumber": phone,
        "assistant": {
            "firstMessage": f"Hi {lead.get('first_name', 'there')}, this is an automated call from Empire AI regarding {lead.get('company', 'your business')}. We found significant revenue opportunities on your website. Would you like to hear about them?",
            "model": {
                "provider": "openai",
                "model": "gpt-4",
                "systemPrompt": "You are a revenue optimization specialist calling businesses to help them fix revenue leaks on their website. Be helpful, not pushy. Focus on specific revenue opportunities you found."
            },
            "voice": {"provider": "11labs", "voiceId": "pNInz6obpgDQGcFmaJgB"},
        }
    }
    
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            "https://api.vapi.ai/call",
            data=data,
            headers={"Authorization": f"Bearer {os.environ.get('VAPI_API_KEY', '')}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return {"success": True, "call_id": data.get("id")}
    except Exception as e:
        return {"success": False, "error": str(e)}

def send_outreach_email(lead: Dict) -> Dict:
    """Send outcome-based email via Resend/Brevo."""
    from empire_os.mail_sender import _send
    
    email = lead.get("email", "").strip()
    if not email:
        return {"success": False, "error": "No email address"}
    
    # Outcome-based email template with ROI estimates
    company = lead.get("company", "your business")
    first_name = lead.get("first_name", "there")
    omega_score = lead.get("omega_score", 0)
    
    # Estimate revenue leak based on score
    estimated_leak = int(omega_score * 2500)  # $2500 per score point
    
    subject = f"Found ${estimated_leak:,} in revenue leaks for {lead.get('company', 'your business')}"
    
    body = f"""Hi {first_name},

We analyzed {company}'s online presence and found an estimated ${estimated_leak:,}/month in revenue leaks.

**What we found:**
• Missing conversion tracking (Google Analytics, FB Pixel)
• Slow page load speed costing leads
• No click-to-call or booking integration
• Forms not capturing all visitor info

**The fix:** Our automated system patches these gaps in under 48 hours.

Worth a 15-min call to see the exact leaks?

[View Your Revenue Report](https://empireos.ai/report/{lead.get('id', '')})

Best,
Empire AI Revenue Team

P.S. Companies at your score level ({lead.get('omega_score', 0)}/30) typically recover ${estimated_leak * 3:,}+ in the first quarter."""

    try:
        from empire_os.mail_sender import _send
        result = _send(lead.get("email", ""), subject, body)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

def trigger_lead_outreach(lead: Dict) -> Dict:
    """Trigger both Vapi call and email for a lead."""
    log("INFO", f"Starting outreach for lead {lead.get('id')}")
    
    # 1. Vapi call (30 second SLA)
    call_result = vapi_make_call(lead)
    
    # 2. Email (5 second delay)
    time.sleep(5)
    email_result = send_outreach_email(lead)
    
    # Update lead status
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE crm_leads 
        SET status = 'contacted',
            outreach_attempted = 1,
            outreach_at = ?,
            vapi_call_id = ?,
            email_sent = ?
        WHERE id = ?
    """, (datetime.now(timezone.utc).isoformat(),
          call_result.get("call_id") if call_result.get("success") else None,
          1 if email_result.get("success") else 0,
          lead["id"]))
    conn.commit()
    conn.close()
    
    return {
        "call": call_result,
        "email": email_result,
        "lead_id": lead["id"],
    }

def run_outreach_cycle(max_leads: int = 50) -> Dict:
    """Run outreach cycle for qualified leads."""
    log("INFO", f"Starting outreach cycle, max_leads={max_leads}")
    
    leads = get_qualified_leads(max_leads)
    if not leads:
        return {"contacted": 0, "message": "No qualified leads"}
    
    contacted = 0
    call_success = 0
    email_success = 0
    
    for lead in leads:
        result = trigger_lead_outreach(lead)
        
        if result["call"].get("success"):
            call_success += 1
        if result["email"].get("success"):
            email_success += 1
        if result["call"].get("success") or result["email"].get("success"):
            contacted += 1
        
        # Rate limiting - delay between leads
        time.sleep(2)
    
    result = {
        "total_qualified": len(leads),
        "contacted": contacted,
        "call_success": call_success,
        "email_success": email_success,
    }
    log("INFO", "Outreach cycle complete", **result)
    return result

if __name__ == "__main__":
    result = run_outreach_cycle(50)
    print(json.dumps(result, indent=2))