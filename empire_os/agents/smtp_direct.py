"""
Standalone SMTP email sender — zero external deps, zero API keys.
Uses direct SMTP to any provider (Gmail, Mailgun, SendGrid, custom).
Drop-in replacement for Resend in outreach_runner.
"""
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional, Tuple
import logging

log = logging.getLogger(__name__)

# Load .env for SMTP creds
def _load_env():
    env_path = Path("/root/empire_os/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

# Config via env (set once in .env)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")          # full email
SMTP_PASS = os.environ.get("SMTP_PASS", "")          # app password or API key
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)   # "Name <email@domain>"
SMTP_TLS = os.environ.get("SMTP_TLS", "true").lower() == "true"
SMTP_TIMEOUT = int(os.environ.get("SMTP_TIMEOUT", "15"))

# Optional: rate limiting (emails per minute)
SMTP_RATE_LIMIT = int(os.environ.get("SMTP_RATE_LIMIT", "30"))


def send_email(
    to: str,
    subject: str,
    body: str,
    from_addr: Optional[str] = None,
    reply_to: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Tuple[bool, str]:
    """
    Send a plain-text email via direct SMTP.
    Returns (success, info_string).
    """
    _load_env()  # reload in case .env changed
    
    if not SMTP_USER or not SMTP_PASS:
        return False, "SMTP credentials not configured (SMTP_USER/SMTP_PASS)"
    
    if not to or "@" not in to:
        return False, f"invalid recipient: {to}"
    
    from_addr = from_addr or SMTP_FROM
    if not from_addr:
        return False, "no from address"
    
    try:
        # Build message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to
        if reply_to:
            msg["Reply-To"] = reply_to
        
        # Add metadata as custom headers
        if metadata:
            for k, v in metadata.items():
                msg[f"X-Empire-{k}"] = str(v)
        
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        # Connect & send
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
            server.ehlo()
            if SMTP_TLS:
                server.starttls(context=context)
                server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        
        return True, f"sent via {SMTP_HOST}:{SMTP_PORT}"
    
    except smtplib.SMTPAuthenticationError as e:
        return False, f"auth failed: {e}"
    except smtplib.SMTPRecipientsRefused as e:
        return False, f"recipient refused: {e}"
    except smtplib.SMTPSenderRefused as e:
        return False, f"sender refused: {e}"
    except smtplib.SMTPDataError as e:
        return False, f"data error: {e}"
    except smtplib.SMTPConnectError as e:
        return False, f"connection failed: {e}"
    except Exception as e:
        return False, f"error: {type(e).__name__}: {e}"


def test_connection() -> Tuple[bool, str]:
    """Test SMTP connection without sending."""
    _load_env()
    if not SMTP_USER or not SMTP_PASS:
        return False, "SMTP credentials not configured"
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            if SMTP_TLS:
                server.starttls(context=context)
                server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
        return True, f"connected to {SMTP_HOST}:{SMTP_PORT}"
    except Exception as e:
        return False, f"connection test failed: {e}"


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        ok, msg = test_connection()
        print(f"{'OK' if ok else 'FAIL'}: {msg}")
        sys.exit(0 if ok else 1)
    
    # Quick send test: python smtp_direct.py "to@test.com" "Subject" "Body"
    if len(sys.argv) >= 4:
        to, subject, body = sys.argv[1], sys.argv[2], sys.argv[3]
        ok, msg = send_email(to, subject, body)
        print(f"{'OK' if ok else 'FAIL'}: {msg}")
        sys.exit(0 if ok else 1)
    
    print("Usage:")
    print("  Test connection: python smtp_direct.py test")
    print("  Send email:      python smtp_direct.py to@domain.com 'Subject' 'Body'")