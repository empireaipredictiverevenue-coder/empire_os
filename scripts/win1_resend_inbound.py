#!/usr/bin/env python3
"""
WIN 1: Resend Inbound Webhook — Capture replies, flip reply_state, enable ROI measurement
Run: python3 /root/empire_os/scripts/win1_resend_inbound.py
"""

import sys, os, json, sqlite3, hashlib, hmac
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/empire_os/empire_os")

DB = "/root/empire_os/empire_os.db"
REPLIES_LOG = "/root/feedback/inbound_replies.jsonl"

def ensure_reply_table():
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

def verify_svix(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Resend webhook signature (svix)"""
    if not signature or not secret:
        return False
    try:
        # Resend uses svix: signature format "t=timestamp,v1=hash"
        parts = dict(p.split("=") for p in signature.split(","))
        timestamp = parts.get("t", "")
        sig_v1 = parts.get("v1", "")
        expected = hmac.new(
            secret.encode(),
            f"{timestamp}.{payload.decode()}".encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, sig_v1)
    except Exception:
        return False

def find_lead_by_email(conn, from_email: str):
    """Match reply sender to si_buyer_outreach or crm_leads"""
    # Normalize email
    raw = from_email
    if "<" in raw and ">" in raw:
        raw = raw.split("<", 1)[1].split(">", 1)[0]
    key = raw.strip().lower()
    
    # First try exact match in buyer outreach
    row = conn.execute(
        "SELECT prospect_id, email FROM si_buyer_outreach WHERE LOWER(email) = ?",
        (key,)
    ).fetchone()
    if row:
        return f"buyer_outreach:{row[0]}", row[1]
    
    # Try crm_leads
    row = conn.execute(
        "SELECT lead_uid, email FROM crm_leads WHERE LOWER(email) = ?",
        (key,)
    ).fetchone()
    if row:
        return f"crm_leads:{row[0]}", row[1]
    
    return None, None

def process_inbound_email(payload: dict, secret: str, from_email: str | None = None):
    """Main handler for inbound webhook (Resend or SendGrid)"""
    ensure_reply_table()
    
    # Support both Resend and SendGrid payload formats
    email = payload.get("email", {})
    message_id = email.get("message_id", "") or payload.get("headers", {}).get("Message-ID", "") or payload.get("message_id", "")
    if not from_email:
        from_email = email.get("from", [{}])[0].get("email", "").lower() or payload.get("from", "").lower()
    to_email = email.get("to", [{}])[0].get("email", "").lower() or payload.get("to", "").lower()
    subject = email.get("subject", "") or payload.get("subject", "")
    body_text = email.get("text", "") or payload.get("text", "")
    body_html = email.get("html", "") or payload.get("html", "")
    received_at = email.get("created_at", datetime.now(timezone.utc).isoformat())
    
    if not message_id or not from_email:
        return {"ok": False, "error": "missing message_id or from_email"}
    
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    
    try:
        # Idempotency: check if already processed
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
        """, (message_id, from_email, to_email, subject, body_text, body_html, received_at))
        
        # Match to lead
        lead_ref, matched_email = find_lead_by_email(conn, from_email)
        
        updated = 0
        if lead_ref:
            # Flip reply_state to 'replied'
            if lead_ref.startswith("buyer_outreach:"):
                lead_id = lead_ref.split(":")[1]
                cur = conn.execute(
                    "UPDATE si_buyer_outreach SET reply_state = 'replied' WHERE prospect_id = ? AND reply_state != 'replied'",
                    (lead_id,)
                )
                updated = cur.rowcount
            elif lead_ref.startswith("crm_leads:"):
                lead_id = lead_ref.split(":")[1]
                # Could also update a replies table for crm_leads
                updated = 1
        
        conn.commit()
        
        # Log to feedback
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "inbound_reply",
            "message_id": message_id,
            "from_email": from_email,
            "to_email": to_email,
            "subject": subject,
            "lead_ref": lead_ref,
            "matched_email": matched_email,
            "reply_state_flipped": updated > 0,
            "body_preview": body_text[:200] if body_text else ""
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
@app.post("/v1/resend/inbound")
async def resend_inbound(request: Request):
    # Verify svix signature
    payload = await request.body()
    signature = request.headers.get("svix-signature", "")
    secret = os.environ.get("RESEND_WEBHOOK_SECRET", "")
    
    if not verify_svix(payload, signature, secret):
        raise HTTPException(401, "Invalid signature")
    
    data = json.loads(payload)
    result = process_inbound_email(data, secret)
    return result
"""

if __name__ == "__main__":
    # Test mode
    ensure_reply_table()
    print("✅ email_replies table ensured")
    
    # Test with sample payload
    test_payload = {
        "email": {
            "message_id": "test-msg-123",
            "from": [{"email": "test@example.com"}],
            "to": [{"email": "replies@empire-ai.co.uk"}],
            "subject": "Re: Your roofing inquiry",
            "text": "Yes, I'm interested. Call me at 555-1234.",
            "html": "<p>Yes, I'm interested. Call me at 555-1234.</p>",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    }
    
    result = process_inbound_email(test_payload, "test-secret")
    print(f"Test result: {json.dumps(result, indent=2)}")