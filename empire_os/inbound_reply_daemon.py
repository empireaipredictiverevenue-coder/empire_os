#!/usr/bin/env python3
"""inbound_reply_daemon — IMAP/Gmail inbound reply poller for Empire OS.

Polls Gmail (IMAP) for replies to our outreach emails, parses them,
stores in si_inbox + email_replies, links to prospect/lead/buyer.
"""

from __future__ import annotations
import imaplib
import email
import sqlite3
import os
import time
import logging
from datetime import datetime, timezone
from email.utils import parseaddr
from email.header import decode_header

# ── Config ──────────────────────────────────────────────────────────────
IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
IMAP_USER = os.environ.get("IMAP_USER", "flavag83@gmail.com")
IMAP_PASS = os.environ.get("IMAP_PASS", "")  # App password
DB = os.environ.get("EMPIRE_DB", "/root/empire_os/empire_os.db")
POLL_INTERVAL = int(os.environ.get("IMAP_POLL_INTERVAL", "60"))  # seconds
SEEN_FILE = "/root/empire_os/feedback/imap_seen_uids.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("inbound_reply_daemon")

# ── DB helpers ──────────────────────────────────────────────────────────
def _conn(timeout: int = 30) -> sqlite3.Connection:
    cnx = sqlite3.connect("/root/empire_os/empire_os.db", timeout=timeout)
    cnx.row_factory = sqlite3.Row
    return cnx

def ensure_tables():
    cnx = sqlite3.connect("/root/empire_os/empire_os.db", timeout=30)
    try:
        cnx.executescript("""
            CREATE TABLE IF NOT EXISTS si_inbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                from_email TEXT,
                from_name TEXT,
                to_email TEXT,
                subject TEXT,
                body_text TEXT,
                body_html TEXT,
                headers_json TEXT,
                raw_size INTEGER,
                received_at TEXT DEFAULT (datetime('now')),
                status TEXT DEFAULT 'new'
            );
            CREATE INDEX IF NOT EXISTS si_inbox_from_idx ON si_inbox(from_email);
            CREATE INDEX IF NOT EXISTS si_inbox_status_idx ON si_inbox(status);

            CREATE TABLE IF NOT EXISTS email_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inbox_id INTEGER REFERENCES si_inbox(id),
                prospect_id TEXT,
                lead_id TEXT,
                buyer_tenant TEXT,
                matched_kind TEXT,
                sentiment TEXT,
                summary TEXT,
                processed_at TEXT,
                UNIQUE(inbox_id)
            );
            CREATE INDEX IF NOT EXISTS email_replies_prospect_idx ON email_replies(prospect_id);
        """)
        cnx.commit()
    finally:
        cnx.close()

def _now():
    return datetime.now(timezone.utc).isoformat()

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        f.write("\n".join(sorted(seen)))

def decode_mime_words(s):
    if not s:
        return ""
    parts = decode_header(s)
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(enc or "utf-8", errors="ignore"))
        else:
            decoded.append(part)
    return "".join(decoded)

def link_to_prospect(from_email: str):
    from_email = (from_email or "").strip().lower()
    if not from_email:
        return {"matched_kind": "none"}
    cnx = sqlite3.connect("/root/empire_os/empire_os.db", timeout=30)
    try:
        r = cnx.execute(
            "SELECT id, lead_id, source FROM si_outbox WHERE lower(to_email)=? ORDER BY id DESC LIMIT 1",
            (from_email,),
        ).fetchone()
        if r:
            return {"matched_kind": f"outbox:{r['source']}", "lead_id": r["lead_id"]}
        r = cnx.execute(
            "SELECT id, lead_uid FROM crm_leads WHERE 1=1 LIMIT 1",
        ).fetchone()
        if r:
            return {"matched_kind": "crm_lead:fallback", "lead_id": f"crm:{r['id']}"}
        return {"matched_kind": "unmatched"}
    finally:
        cnx.close()

def store_inbound(msg_id, from_email, from_name, to_email, subject, body_text, body_html, headers):
    cnx = sqlite3.connect("/root/empire_os/empire_os.db", timeout=30)
    try:
        cur = cnx.execute(
            """
            INSERT INTO si_inbox (
                message_id, from_email, from_name, to_email,
                subject, body_text, body_html, headers_json, raw_size
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg_id or "",
                from_email,
                from_name,
                to_email,
                subject or "",
                (body_text or "")[:16000],
                (body_html or "")[:64000],
                "{}",
                0,
            ),
        )
        inbox_id = cur.lastrowid
        cnx.commit()
        return inbox_id
    finally:
        cnx.close()

def link_reply(inbox_id, from_email):
    match = link_to_prospect(from_email)
    if match.get("matched_kind") and match["matched_kind"] != "unmatched":
        cnx = sqlite3.connect("/root/empire_os/empire_os.db", timeout=30)
        try:
            cnx.execute(
                """
                INSERT OR IGNORE INTO email_replies (
                    inbox_id, prospect_id, lead_id, buyer_tenant,
                    matched_kind, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    inbox_id,
                    match.get("prospect_id"),
                    match.get("lead_id"),
                    match.get("buyer_tenant"),
                    match["matched_kind"],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            cnx.execute(
                "UPDATE si_inbox SET status='matched' WHERE id=?",
                (inbox_id,),
            )
            cnx.commit()
        finally:
            cnx.close()

def fetch_unseen(imap):
    imap.select("INBOX")
    typ, data = imap.search(None, "UNSEEN")
    if typ != "OK":
        return []
    return data[0].split()

def parse_email(imap, uid):
    typ, msg_data = imap.fetch(uid, "(RFC822)")
    if typ != "OK" or not msg_data:
        return None
    raw = msg_data[0][1]
    msg = email.message_from_bytes(raw)
    msg_id = msg.get("Message-ID", "")
    from_header = msg.get("From", "")
    from_name, from_email = parseaddr(from_header)
    to_email = msg.get("To", "")
    subject = decode_mime_words(msg.get("Subject", ""))
    
    body_text = ""
    body_html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in disp:
                body_text = part.get_payload(decode=True).decode(errors="ignore")
            elif ctype == "text/html" and "attachment" not in disp:
                body_html = part.get_payload(decode=True).decode(errors="ignore")
    else:
        ctype = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            if ctype == "text/html":
                body_html = payload.decode(errors="ignore")
            else:
                body_text = payload.decode(errors="ignore")
    
    return {
        "uid": uid.decode() if isinstance(uid, bytes) else uid,
        "message_id": msg_id,
        "from_email": from_email,
        "from_name": from_name,
        "to_email": to_email,
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
    }

# ── Main loop ───────────────────────────────────────────────────────────
def main():
    ensure_tables()
    os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)
    seen = load_seen()
    
    log.info("Starting inbound reply daemon...")
    
    while True:
        try:
            imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
            imap.login(IMAP_USER, IMAP_PASS)
            log.info("IMAP connected")
            
            unseen = fetch_unseen(imap)
            log.info(f"Found {len(unseen)} unseen messages")
            
            for uid in unseen:
                uid_str = uid.decode() if isinstance(uid, bytes) else uid
                if uid_str in seen:
                    continue
                
                parsed = parse_email(imap, uid)
                if not parsed:
                    seen.add(uid_str)
                    continue
                
                # Store inbox
                inbox_id = store_inbound(
                    parsed["message_id"],
                    parsed["from_email"],
                    parsed["from_name"],
                    parsed["to_email"],
                    parsed["subject"],
                    parsed["body_text"],
                    parsed["body_html"],
                    {},
                )
                
                # Link to prospect/lead
                link_reply(inbox_id, parsed["from_email"])
                
                seen.add(uid_str)
                log.info(f"Processed inbound from {parsed['from_email']} -> inbox_id={inbox_id}")
            
            save_seen(seen)
            imap.logout()
            
        except Exception as e:
            log.exception(f"Daemon error: {e}")
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
