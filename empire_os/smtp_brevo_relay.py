"""
smtp_brevo_relay.py — minimal self-hosted SMTP relay (host side).

Listens on 0.0.0.0:2525, receives messages from Listmonk (container), and
forwards them to Brevo's transactional API (our working outbound path).
Keeps bulk nurture fully self-hosted — no external SMTP creds needed.

Env:
  BREVO_API_KEY  (file path or value) — default /root/empire_secrets/brevo_api_key
  RELAY_HOST     bind host  (default 0.0.0.0)
  RELAY_PORT     bind port  (default 2525)
  BREVO_FROM     From address for outbound (default growth@empire-ai.co.uk)
"""
import os, sys, asyncio, json, urllib.request
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import Envelope

BREVO_KEY = os.getenv("BREVO_API_KEY", open("/root/empire_secrets/brevo_api_key").read().strip())
BREVO_FROM = os.getenv("BREVO_FROM", "growth@empire-ai.co.uk")
LISTMONK_IP = os.getenv("LISTMONK_IP", "10.118.155.153")


def _send_brevo(rcpt, subject, body, html=True):
    payload = {
        "sender": {"name": "Empire AI", "email": BREVO_FROM},
        "to": [{"email": r} for r in rcpt],
        "subject": subject,
    }
    if html:
        payload["htmlContent"] = body
    else:
        payload["textContent"] = body
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode(),
        headers={"api-key": BREVO_KEY, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


class BrevoHandler:
    async def handle_DATA(self, server, session, envelope: Envelope):
        peer = session.peer[0]
        # accept from listmonk container + host localhost (relay is internal-only)
        if peer not in (LISTMONK_IP, "127.0.0.1", "::1"):
            return "550 relay denied"
        msg = envelope.content.decode("utf-8", "replace")
        rcpt = envelope.rcpt_tos
        # handle CRLF and LF; split headers from body
        if "\r\n\r\n" in msg:
            headers, _, body = msg.partition("\r\n\r\n")
        else:
            headers, _, body = msg.partition("\n\n")
        body = body.strip()
        subject = ""
        content_type = "text/plain"
        for line in headers.splitlines():
            if line.lower().startswith("subject:"):
                subject = line.split(":", 1)[1].strip()
            if line.lower().startswith("content-type:"):
                content_type = line.split(":", 1)[1].strip()
        is_html = "html" in content_type
        payload = {
            "sender": {"name": "Empire AI", "email": BREVO_FROM},
            "to": [{"email": r} for r in rcpt],
            "subject": subject or "(no subject)",
        }
        if is_html:
            payload["htmlContent"] = body
            payload["textContent"] = body
        else:
            payload["textContent"] = body
            payload["htmlContent"] = f"<pre>{body}</pre>"
        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=json.dumps(payload).encode(),
            headers={"api-key": BREVO_KEY, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                status, resp = r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            status, resp = e.code, e.read().decode()[:200]
        if status == 201:
            return "250 OK queued via Brevo"
        return f"451 Brevo error {status}: {resp}"


def main():
    host = os.getenv("RELAY_HOST", "0.0.0.0")
    port = int(os.getenv("RELAY_PORT", "2525"))
    ctrl = Controller(BrevoHandler(), hostname=host, port=port)
    ctrl.start()
    print(f"[smtp-relay] listening on {host}:{port}, forwarding to Brevo API")
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        ctrl.stop()


if __name__ == "__main__":
    main()
