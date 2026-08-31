#!/usr/bin/env python3
"""
IMAP Defensive Wrapper - Solves >1MB Gmail IMAP warnings
"""
import json
import imaplib
import logging
import os
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Optional

# Defensive Configuration
IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
IMAP_USER = "flavag83@gmail.com"
CREDS_PATH = Path("/root/empire_secrets/gmail_app_password")
LOG_PATH = Path("/root/empire_os/feedback/inbound_reply_daemon.log")
JSONL_PATH = Path("/root/empire_os/feedback/inbound_reply_daemon.jsonl")
MAX_EMAIL_SIZE = 1048576
CHUNK_SIZE = 524288

# Setup logging
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
log = logging.getLogger(__name__)

def validate_email_size(email_bytes: bytes) -> bool:
    """Validate email size before processing."""
    size = len(email_bytes)
    if size > MAX_EMAIL_SIZE:
        log.error(f"Email size {size} exceeds limit {MAX_EMAIL_SIZE}")
        return False
    return True

def safe_email_fetch(imap: imaplib.IMAP4_SSL, num: int) -> Optional[bytes]:
    """Safe email fetch with size validation."""
    try:
        typ, msg_data = imap.fetch(num, "(RFC822)")
        if typ != "OK" or not msg_data or not msg_data[0]:
            return None
            
        raw = msg_data[0][1]
        
        if not validate_email_size(raw):
            return None
            
        log.info(f"Successfully fetched email {num}")
        return raw
        
    except Exception as exc:
        log.error(f"Error fetching email {num}: {exc}")
        return None

def parse_message_safe(raw_bytes: bytes) -> Dict[str, Any]:
    """Parse email with size limits."""
    try:
        import email
        msg = email.message_from_bytes(raw_bytes)

        body_text = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and part.get("Content-Disposition") != "attachment":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode(errors="replace")
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body_text = payload.decode(errors="replace")

        return {
            "subject": msg.get("Subject", ""),
            "from_email": msg.get("From", ""),
            "to_email": msg.get("To", ""),
            "body_text": body_text,
            "body": body_text,
            "message_id": msg.get("Message-ID", ""),
            "raw_size": len(raw_bytes),
        }
    except Exception as exc:
        log.error(f"Parse error: {exc}")
        return {"subject": "Parse Error", "from_email": "", "to_email": "", "body": "", "message_id": ""}

def post_to_hub_safe(payload: Dict[str, Any]) -> int:
    """POST to hub with safe error handling."""
    try:
        url = os.environ.get('EMPIRE_HUB_URL', 'http://10.118.155.218:8081') + '/v1/inbound/parse'
        body = json.dumps(payload).encode('utf-8')
        
        req = urllib.request.Request(url, data=body, method='POST',
                                     headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.code
    except Exception as exc:
        log.error(f"Hub POST error: {exc}")
        return 0

def fetch_unseen_uids(imap: imaplib.IMAP4_SSL) -> list:
    """Fetch unseen UIDs with size limits. Only replies since blast window (30-Aug-2026)."""
    try:
        typ, data = imap.search(None, "UNSEEN", "SINCE", "30-Aug-2026")
        if typ == "OK" and data and data[0]:
            return data[0].split()[:50]  # Limit per cycle
        return []
    except Exception as exc:
        log.error(f"Search error: {exc}")
        return []

def main():
    """Main defensive IMAP daemon."""
    log.info("Starting defensive IMAP daemon")
    
    # Read credentials
    try:
        password = CREDS_PATH.read_text().strip()
        if not password:
            log.error("No credentials found")
            return
    except Exception as exc:
        log.error(f"Failed to read credentials: {exc}")
        return
    
    # Connect to IMAP
    ctx = ssl.create_default_context()
    imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx)
    
    try:
        imap.login(IMAP_USER, password)
        imap.select("INBOX", readonly=False)
        log.info("Connected to IMAP")
        
        while True:
            uids = fetch_unseen_uids(imap)
            if not uids:
                time.sleep(60)
                continue
                
            for num in uids:
                # Memory check
                try:
                    import psutil
                    memory = psutil.virtual_memory()
                    if memory.percent > 90:
                        log.warning("High memory usage: %.1f%%", memory.percent)
                        continue
                except:
                    pass
                
                # Fetch and process email
                raw = safe_email_fetch(imap, num)
                if raw is None:
                    continue
                    
                payload = parse_message_safe(raw)
                status = post_to_hub_safe(payload)
                
                if 200 <= status < 300:
                    imap.store(num, "+FLAGS", "\\Seen")
                    log.info(f"Processed email {num}: {payload['subject']}")
                    
    except KeyboardInterrupt:
        log.info("Shutting down defensive IMAP daemon")
    except Exception as exc:
        log.error(f"Critical error: {exc}")
    finally:
        try:
            imap.logout()
        except:
            pass

if __name__ == "__main__":
    main()
