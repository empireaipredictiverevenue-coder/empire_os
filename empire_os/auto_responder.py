"""auto_responder — instant reply to inbound blast responses.

Trigger: insert_inbound() matched a sender to si_outbox (a blast we sent).
Flow:
  1. classify intent from subject+body (BUY / INFO / UNSUB / OTHER)
  2. BUY or OTHER -> onboard(delivery_email=sender) -> fresh BSC pay link
     -> email reply with pay link + per-lead rate, sent via Brevo API
  3. INFO -> reply with product/rate summary + buy link
  4. UNSUB -> mark consent off, no reply
Loop guards:
  - never reply to our own domains (empire-ai.co.uk, empire.co.uk, gmail of founder)
  - one auto-reply per from_email per 7 days (auto_reply_log)
  - never reply to bounce addresses (mailer-daemon, no-reply, postmaster)
All failures are swallowed + logged; inbound capture never breaks because of this.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import urllib.request
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
log = logging.getLogger("auto_responder")

OWN_DOMAINS = ("empire-ai.co.uk", "empire.co.uk")
JUNK_LOCALS = ("mailer-daemon", "no-reply", "noreply", "postmaster", "bounce", "returns")

BUY_RX = re.compile(r"\b(yes|buy|interested|price|pricing|order|want|need|how much|start|begin|deal|invoice|pay|ready|sign me|count me|send me|lead)\b", re.I)
UNSUB_RX = re.compile(r"\b(unsubscribe|remove me|stop emailing|opt.?out|not interested|stop contacting)\b", re.I)
INFO_RX = re.compile(r"\b(what|how does|tell me|more info|details|explain|who are you)\b", re.I)
SAMPLE_RX = re.compile(r"\b(sample|samples|trial|try one|see one|show me)\b", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    cnx = sqlite3.connect(DB, timeout=30)
    cnx.row_factory = sqlite3.Row
    return cnx


def ensure_schema() -> None:
    cnx = _conn()
    try:
        cnx.execute(
            """CREATE TABLE IF NOT EXISTS auto_reply_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inbox_id INTEGER,
                to_email TEXT,
                intent TEXT,
                action TEXT,
                pay_url TEXT DEFAULT '',
                ok INTEGER DEFAULT 0,
                detail TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )"""
        )
        cnx.execute("CREATE INDEX IF NOT EXISTS arl_to_idx ON auto_reply_log(to_email)")
        cnx.commit()
    finally:
        cnx.close()


ensure_schema()


def classify(subject: str, body: str) -> str:
    text = f"{subject}\n{body}"
    if UNSUB_RX.search(text):
        return "UNSUB"
    if BUY_RX.search(text):
        return "BUY"
    if INFO_RX.search(text):
        return "INFO"
    return "OTHER"


def _already_replied_recently(cnx, email: str, days: int = 7) -> bool:
    r = cnx.execute(
        "SELECT id FROM auto_reply_log WHERE lower(to_email)=? "
        "AND created_at > datetime('now', ?) LIMIT 1",
        (email.lower(), f"-{days} days"),
    ).fetchone()
    return r is not None


def _brevo_send(to_email: str, subject: str, body: str, in_reply_to: str = "", html: str = "") -> dict:
    key = open("/root/empire_secrets/brevo_api_key").read().strip()
    payload = {
        "sender": {"name": "Empire AI — Founder", "email": "founder@empire-ai.co.uk"},
        "replyTo": {"email": "founder@empire-ai.co.uk"},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body,
    }
    if html:
        payload["htmlContent"] = html
    if in_reply_to:
        payload["headers"] = {"In-Reply-To": in_reply_to}
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode(),
        headers={"api-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return {"ok": True, "messageId": json.loads(resp.read()).get("messageId", "")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


_GMAIL_RELAY_DOMAINS = ("gmail.com", "googlemail.com")


def _gmail_relay_send(to_email: str, subject: str, body: str, in_reply_to: str = "", html: str = "") -> dict:
    """Gmail SMTP relay with founder@ From. Gmail->Gmail always lands;
    Brevo->Gmail is silently dropped for this account (verified 2026-08-30).
    SPF passes: apex SPF includes _spf.google.com."""
    import smtplib, ssl
    from email.message import EmailMessage
    from email.utils import make_msgid
    try:
        pw = open("/root/empire_secrets/gmail_app_password_predictive").read().strip()
    except OSError:
        return {"ok": False, "error": "no gmail app password"}
    msg = EmailMessage()
    msg["From"] = "Empire AI — Founder <empireaipredictiverevenue@gmail.com>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Reply-To"] = "founder@empire-ai.co.uk"
    msg["Message-ID"] = make_msgid(domain="empire-ai.co.uk")
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    if html:
        msg.set_content(body)
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(body)
    try:
        s = smtplib.SMTP_SSL("smtp.gmail.com", 465,
                             context=ssl.create_default_context(), timeout=25)
        s.login("empireaipredictiverevenue@gmail.com", pw)
        s.send_message(msg)
        s.quit()
        return {"ok": True, "via": "gmail_relay"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _reply_to_buyer(to_email: str, subject: str, body: str, in_reply_to: str = "", html: str = "") -> dict:
    """Route: Gmail-addressed buyer -> Gmail relay; everyone else -> Brevo."""
    domain = to_email.rsplit("@", 1)[-1].lower()
    if domain in _GMAIL_RELAY_DOMAINS:
        r = _gmail_relay_send(to_email, subject, body, in_reply_to, html)
        if r.get("ok"):
            return r
    return _brevo_send(to_email, subject, body, in_reply_to, html)


def _buyer_reply(name: str, pay_url: str, per_lead: str) -> str:
    first = (name or "there").split()[0]
    return (
        f"Hi {first},\n\n"
        f"Great to hear — you're set up on Empire AI buyer acquisition.\n\n"
        f"YOUR PAY LINK (BSC USDT, activates instantly on settlement):\n"
        f"  {pay_url}\n\n"
        f"Rate: ${per_lead} USDT per qualified lead, exclusive to your market.\n"
        f"Leads start flowing to your seat as soon as the seat payment settles.\n\n"
        f"Questions? Just reply — founder reads everything.\n\n"
        f"— Empire AI\n"
        f"https://empire-ai.co.uk\n"
    )


def _info_reply() -> str:
    return (
        "Hi, thanks for reaching out.\n\n"
        "Empire AI sells exclusive, scored B2B leads settled in BSC USDT.\n"
        "Roofing buyer lane: $4.00 USDT per qualified lead, pay on delivery.\n\n"
        "To start buying leads now (no card, wallet only):\n"
        "  https://empire-ai.co.uk/buy-leads\n\n"
        "Reply 'yes' and we'll set up your buyer seat + pay link immediately.\n\n"
        "— Empire AI\nhttps://empire-ai.co.uk\n"
    )


def handle_inbound(inbox_id: int, from_email: str, from_name: str,
                   subject: str, body: str, message_id: str = "") -> dict:
    """Called from insert_inbound after a successful outbox match."""
    from_email = (from_email or "").strip().lower()
    try:
        if not from_email or "@" not in from_email:
            return {"ok": False, "skipped": "no_email"}
        domain = from_email.split("@")[-1]
        local = from_email.split("@")[0]
        if domain in OWN_DOMAINS or local in JUNK_LOCALS:
            return {"ok": False, "skipped": "self_or_junk"}

        intent = classify(subject, body)
        cnx = _conn()
        try:
            if _already_replied_recently(cnx, from_email):
                return {"ok": False, "skipped": "already_replied_7d"}

            if intent == "UNSUB":
                # si_prospect_consent keys on prospect_id, not email — honour
                # the unsub by flagging the outbox recipient so senders skip them.
                try:
                    cnx.execute(
                        "UPDATE si_outbox SET status='unsubscribed' "
                        "WHERE lower(to_email)=? AND status IN ('sent','queued','pending')",
                        (from_email,))
                    cnx.commit()
                except Exception:
                    pass
                cnx.execute(
                    "INSERT INTO auto_reply_log (inbox_id,to_email,intent,action,ok,detail) "
                    "VALUES (?,?,?,?,1,'unsub honoured, no reply')",
                    (inbox_id, from_email, intent, "unsub"))
                cnx.commit()
                return {"ok": True, "action": "unsub"}

            if intent == "INFO":
                from empire_os import email_templates as _t
                send = _reply_to_buyer(from_email, f"Re: {subject or 'Empire AI'}",
                                       _t.info_text(), message_id, _t.info_html())
                cnx.execute(
                    "INSERT INTO auto_reply_log (inbox_id,to_email,intent,action,ok,detail) "
                    "VALUES (?,?,?,?,?,?)",
                    (inbox_id, from_email, intent, "info_reply",
                     1 if send.get("ok") else 0, json.dumps(send)[:300]))
                cnx.commit()
                return {"ok": bool(send.get("ok")), "action": "info_reply"}

            # BUY or OTHER -> onboard + pay link
            pay_url = ""
            per_lead = "4.00"
            onboard_detail = ""
            try:
                from empire_os import auto_onboard
                res = auto_onboard.onboard(
                    name=from_name or from_email.split("@")[0],
                    niche="roofing", tier="buyer",
                    delivery_email=from_email, source="auto_responder")
                onboard_detail = json.dumps({k: v for k, v in res.items()
                                             if k in ("ok", "tenant_id", "subscription_id", "error")})[:300]
                if res.get("ok"):
                    pay_url = res.get("pay_url") or (res.get("payment") or {}).get("pay_url", "")
                    per_lead = str(res.get("per_lead_usdc") or "4.00")
            except Exception as e:
                onboard_detail = f"onboard_err:{str(e)[:150]}"

            from empire_os import email_templates as _t
            first = (from_name or from_email.split("@")[0]).split()[0]
            if pay_url:
                body_out = _t.paylink_text(first, per_lead, pay_url)
                html_out = _t.paylink_html(first, per_lead, pay_url)
                subj_out = _t.paylink_subject()
            else:
                body_out = _t.info_text()
                html_out = _t.info_html()
                subj_out = f"Re: {subject}" if subject else "Empire AI — buyer setup"

            send = _reply_to_buyer(from_email, subj_out, body_out, message_id, html_out)
            cnx.execute(
                "INSERT INTO auto_reply_log (inbox_id,to_email,intent,action,pay_url,ok,detail) "
                "VALUES (?,?,?,?,?,?,?)",
                (inbox_id, from_email, intent, "pay_link_reply" if pay_url else "fallback_info",
                 pay_url[:500], 1 if send.get("ok") else 0,
                 (onboard_detail + " | " + json.dumps(send))[:400]))
            cnx.commit()
            return {"ok": bool(send.get("ok")), "action": "pay_link_reply",
                    "pay_url": pay_url, "send": send}
        finally:
            cnx.close()
    except Exception as e:
        log.exception("auto_responder failed for inbox %s", inbox_id)
        try:
            cnx = _conn()
            cnx.execute(
                "INSERT INTO auto_reply_log (inbox_id,to_email,intent,action,ok,detail) "
                "VALUES (?,?,?, 'error', 0, ?)",
                (inbox_id, from_email, "ERR", str(e)[:300]))
            cnx.commit()
            cnx.close()
        except Exception:
            pass
        return {"ok": False, "error": str(e)[:200]}
