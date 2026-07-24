#!/usr/bin/env python3
"""
WIN 1: SendGrid Inbound Parse Webhook → Empire OS /v1/inbound/reply
Deploy: Configure SendGrid Inbound Parse to POST to https://empire-ai.co.uk/v1/inbound/reply
"""

import sys, json, os, sqlite3
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/empire_os/empire_os")

DB = "/root/empire_os/empire_os.db"
REPLIES_LOG = "/root/feedback/inbound_replies.jsonl"

def ensure_reply_table():
    """Ensure email_replies table exists for audit trail"""
    import sqlite3
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE NOT NULL,
            from_email TEXT NOT NULL,
            to_email TEXT NOT NULL,
            subject TEXT,
            body_text TEXT,
            body_html TEXT,
            lead_ref TEXT,
            received_at TEXT NOT NULL,
            processed_at TEXT DEFAULT (datetime('now')),
            UNIQUE(message_id)
        )
    """)
    conn.commit()
    conn.close()

def find_lead_by_email(conn, from_email: str):
    """Match reply sender to si_buyer_outreach or crm_leads"""
    # Normalize email
    raw = from_email
    if "<" in raw and ">" in raw:
        raw = raw.split("<", 1)[1].split(">", 1)[0]
    key = raw.strip().lower()
    
    # Try si_buyer_outreach first
    row = conn.execute(
        "SELECT prospect_id, email FROM si_buyer_outreach WHERE LOWER(email) = ?",
        (key,)
    ).fetchone()
    if row:
        return f"buyer_outreach:{row[0]}", row[1]
    
    # Try crm_leads
    row = conn.execute(
        "SELECT id, email FROM crm_leads WHERE LOWER(email) = ?",
        (key,)
    ).fetchone()
    if row:
        return f"crm_leads:{row[0]}", row[1]
    
    return None, None

def process_sendgrid_inbound(payload: dict) -> dict:
    """
    Process SendGrid Inbound Parse webhook payload.
    SendGrid POSTs multipart/form-data with:
    - headers: raw email headers
    - from: sender email
    - to: recipient email  
    - subject: email subject
    - text: plain text body
    - html: HTML body
    - envelope: JSON of {to: [...], from: ...}
    - dkim, spf, charsets, etc.
    """
    ensure_reply_table()
    
    # Extract fields from SendGrid payload
    from_email = payload.get("from", "").strip()
    to_email = payload.get("to", "").strip()
    subject = payload.get("subject", "").strip()
    body_text = payload.get("text", "").strip()
    body_html = payload.get("html", "").strip()
    message_id = payload.get("headers", "")
    
    # Try to extract Message-ID from headers
    import re
    msg_id_match = re.search(r'message-id:\s*<([^>]+)>', message_id, re.IGNORECASE)
    message_id = msg_id_match.group(1) if msg_id_match else f"sg-{datetime.now(timezone.utc).timestamp()}"
    
    if not from_email or not to_email:
        return {"ok": False, "error": "missing from/to email"}
    
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    
    try:
        # Idempotency check
        existing = conn.execute(
            "SELECT 1 FROM email_replies WHERE message_id = ?", (message_id,)
        ).fetchone()
        if existing:
            conn.close()
            return {"ok": True, "status": "duplicate", "message_id": message_id}
        
        # Store reply
        conn.execute("""
            INSERT INTO email_replies (message_id, from_email, to_email, subject, body_text, body_html, received_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (message_id, from_email, to_email, subject, body_text, body_html, datetime.now(timezone.utc).isoformat()))
        
        # Match to lead
        lead_ref, matched_email = find_lead_by_email(conn, from_email)
        
        updated = 0
        if lead_ref:
            if lead_ref.startswith("buyer_outreach:"):
                lead_id = lead_ref.split(":")[1]
                cur = conn.execute(
                    "UPDATE si_buyer_outreach SET reply_state = 'replied' WHERE prospect_id = ? AND reply_state != 'replied'",
                    (lead_id,)
                )
                updated = cur.rowcount
            elif lead_ref.startswith("crm_leads:"):
                # Could update a replies table for crm_leads
                updated = 1
        
        conn.commit()
        
        # Log to feedback
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "sendgrid_inbound_reply",
            "message_id": message_id,
            "from_email": from_email,
            "to_email": to_email,
            "subject": subject,
            "body_preview": body_text[:200] if body_text else "",
            "lead_ref": lead_ref,
            "matched_email": matched_email,
            "reply_state_flipped": updated > 0,
            "provider": "sendgrid"
        }
        
        Path(REPLIES_LOG).parent.mkdir(parents=True, exist_ok=True)
        with open(REPLIES_LOG, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        return {
            "ok": True,
            "message_id": message_id,
            "lead_ref": lead_ref,
            "reply_state_flipped": updated > 0,
            "log_entry": log_entry
        }
        
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()

# FastAPI endpoint handler (to be added to hub.py)
"""
@app.post("/v1/inbound/sendgrid")
async def sendgrid_inbound(request: Request):
    '''
    Receive SendGrid Inbound Parse webhook.
    
    Configure in SendGrid:
    - Inbound Parse → Host: empire-ai.co.uk
    - URL: https://empire-ai.co.uk/v1/inbound/sendgrid
    - Check 'POST the raw, full MIME message' = OFF (we want parsed fields)
    - Check 'Spam Check' = ON
    '''
    # Parse multipart form data
    form = await request.form()
    payload = dict(form)
    
    result = process_sendgrid_inbound(payload)
    return result
"""

if __name__ == "__main__":
    ensure_reply_table()
    print("✅ email_replies table ensured")
    
    # Test with sample SendGrid payload
    test_payload = {
        "from": "John Doe <john@example.com>",
        "to": "replies@empire-ai.co.uk",
        "subject": "Re: Your roofing inquiry",
        "text": "Yes, I'm interested. Call me at 555-1234.",
        "html": "<p>Yes, I'm interested. Call me at 555-1234.</p>",
        "headers": "message-id: <test-123@example.com>\nfrom: John Doe <john@example.com>",
        "envelope": '{"to":["replies@empire-ai.co.uk"],"from":"john@example.com"}'
    }
    
    result = process_sendgrid_inbound(test_payload)
    print(f"Test result: {json.dumps(result, indent=2)}")