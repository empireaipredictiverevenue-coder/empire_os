"""email_verify.py — owned email verification (beats Hunter, no $0.50/verify fee).

MX lookup + SMTP RCPT TO probe. No external API. Marks crm_leads.valid_email.
"""
from __future__ import annotations
import dns.resolver
import socket
import smtplib
import re
from typing import Optional

DISPOSABLE = {
    "mailinator.com", "temp-mail.org", "guerrillamail.com", "10minutemail.com",
    "trashmail.com", "yopmail.com", "tempmail.com", "throwawaymail.com",
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _mx_hosts(domain: str) -> list[str]:
    try:
        return [str(r.exchange).rstrip(".") for r in dns.resolver.resolve(domain, "MX")]
    except Exception:
        return []


def verify(email: str) -> dict:
    email = (email or "").strip().lower()
    res = {"email": email, "valid": False, "status": "invalid", "detail": ""}
    if not EMAIL_RE.match(email):
        res["detail"] = "bad_format"; return res
    domain = email.split("@")[1]
    if domain in DISPOSABLE:
        res["status"] = "disposable"; res["detail"] = "disposable_domain"; return res
    mx = _mx_hosts(domain)
    if not mx:
        res["status"] = "no_mx"; res["detail"] = "no_mx_record"; return res
    res["mx"] = mx[0]
    # SMTP RCPT TO probe (no send)
    try:
        with smtplib.SMTP(timeout=8) as s:
            s.connect(mx[0])
            s.helo("empire-os.ai")
            s.mail("verify@empire-os.ai")
            code, _ = s.rcpt(email)
            if code in (250, 251):
                res["valid"] = True; res["status"] = "deliverable"
            else:
                res["status"] = "undeliverable"; res["detail"] = f"smtp_{code}"
    except (socket.timeout, ConnectionRefusedError, smtplib.SMTPException,
            OSError) as e:
        res["status"] = "unknown"; res["detail"] = f"smtp_error:{type(e).__name__}"
    return res


if __name__ == "__main__":
    import sys, sqlite3
    db = "/root/empire_os/empire_os.db"
    c = sqlite3.connect(db)
    rows = c.execute(
        "SELECT id,email FROM crm_leads WHERE email LIKE '%@%' "
        "AND email NOT LIKE '%@2x.avif' AND valid_email IS NULL LIMIT 50"
    ).fetchall()
    checked = 0
    for _id, em in rows:
        r = verify(em)
        c.execute("UPDATE crm_leads SET valid_email=? WHERE id=?",
                  (1 if r["valid"] else 0, _id))
        checked += 1
        print(r["email"], r["status"])
    c.commit(); c.close()
    print(f"verified {checked}")
