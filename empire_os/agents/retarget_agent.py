"""Retargeting agent (Phase 1).

Pulls leads who clicked or replied but haven't paid, enqueues a relationship
follow-up via si_outbox (Brevo). Runs as a tick; safe to call repeatedly.
"""
import sqlite3, json, datetime as _dt

DB = "/root/empire_os/empire_os.db"
FROM = "Empire OS <founder@empire-ai.co.uk>"


def _conn():
    c = sqlite3.connect(DB, timeout=20)
    c.execute("PRAGMA busy_timeout=20000")
    return c


def pending_buyers() -> list:
    """Buyers who engaged (clicked/replied) but not paid."""
    c = _conn()
    rows = c.execute(
        """SELECT DISTINCT e.email, e.campaign
           FROM email_events e
           LEFT JOIN unsubscribes u ON u.email = e.email
           WHERE e.event IN ('click','open','reply')
             AND u.email IS NULL
             AND e.email NOT IN (
               SELECT to_email FROM si_outbox WHERE source='retarget' AND status='sent'
             )"""
    ).fetchall()
    c.close()
    return rows


def tick_once() -> int:
    engaged = pending_buyers()
    if not engaged:
        return 0
    c = _conn()
    sent = 0
    for email, campaign in engaged:
        subject = "Empire OS — quick question on your lane"
        body = (
            f"<p>Hi,</p>"
            f"<p>You opened our note about your dedicated lead lane. "
            f"No rush — most operators activate within a week of seeing their "
            f"first sample lead.</p>"
            f"<p>Want me to send you 3 live samples for your niche so you can "
            f"see the quality before funding?</p>"
            f"<p style='margin:18px 0'><a href='https://empire-ai.co.uk/pay/"
            f"retarget:{email[:8]}' "
            f"style='background:#39ff88;color:#050810;padding:12px 20px;"
            f"border-radius:10px;font-weight:700;text-decoration:none'>"
            f"See activation &amp; samples</a></p>"
        )
        meta = json.dumps({"campaign": campaign, "kind": "retarget"})
        try:
            c.execute(
                """INSERT INTO si_outbox (to_email, subject, body, html_body,
                   lane, tier, source, status, recipient_kind, meta_json)
                   VALUES (?,?,?,?, 'general','GOLD','retarget','pending','buyer',?)""",
                (email, subject, body, body, meta))
            sent += 1
        except Exception:
            pass
    c.commit(); c.close()
    return sent


if __name__ == "__main__":
    print("retargeted:", tick_once())
