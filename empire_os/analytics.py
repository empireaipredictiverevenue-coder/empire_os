"""Empire OS outbound analytics — click / open / reply capture + retargeting.

Uses the EXISTING tracking tables (no schema conflicts):
  - link_redirects(token, target, source, created_at)  -> real destination per token
  - lead_links(token, lead_uid, buyer_email, created_at, clicks)
  - lead_clicks(id, token, email, url, source, ip, user_agent, clicked_at)
  - email_replies(id, inbox_id, prospect_id, lead_id, buyer_tenant, matched_kind, sentiment, summary, processed_at)
  - email_opens(outbox_id, to_email, opened_at, ip)
  - retarget_queue(to_email, stage, last_touch, next_touch, status)
"""
import sqlite3
import os
import json
import uuid

DB = os.environ.get("EMPIRE_DB", "/root/empire_os/empire_os.db")


def _c():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA busy_timeout=30000")
    c.execute("PRAGMA journal_mode=WAL")
    return c


def ensure_tables():
    # All tables already exist in prod DB; this is a safe no-op for parity/tests.
    c = _c()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS link_redirects (
            token TEXT PRIMARY KEY, target TEXT, source TEXT, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS email_opens (
            open_id TEXT PRIMARY KEY, outbox_id INTEGER,
            to_email TEXT, opened_at TEXT DEFAULT (datetime('now')), ip TEXT
        );
        CREATE TABLE IF NOT EXISTS retarget_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT, to_email TEXT, stage TEXT,
            last_touch TEXT, next_touch TEXT, status TEXT DEFAULT 'pending'
        );
        """
    )
    c.commit()
    c.close()


def cloak_link(outbox_id, to_email, target_url, source="outbound"):
    """Register a cloaked /l/ link. Stores target in link_redirects + lead_links."""
    token = uuid.uuid4().hex[:12]
    c = _c()
    c.execute(
        "INSERT OR REPLACE INTO link_redirects (token, target, source, created_at) "
        "VALUES (?,?,?,datetime('now'))",
        (token, target_url, source),
    )
    c.execute(
        "INSERT OR REPLACE INTO lead_links "
        "(token, lead_uid, buyer_email, created_at, clicks) VALUES (?,?,?,datetime('now'),0)",
        (token, str(outbox_id), to_email),
    )
    c.commit()
    c.close()
    return f"https://empire-ai.co.uk/l/{token}"


def resolve_redirect(token):
    c = _c()
    row = c.execute(
        "SELECT target FROM link_redirects WHERE token=?", (token,)
    ).fetchone()
    c.close()
    return row[0] if row else None


def track_open(outbox_id, to_email, ip=""):
    oid = uuid.uuid4().hex[:12]
    c = _c()
    c.execute(
        "INSERT INTO email_opens (open_id, outbox_id, to_email, ip) VALUES (?,?,?,?)",
        (oid, outbox_id, to_email, ip),
    )
    c.commit()
    c.close()


def capture_reply(to_email, source="inbound", snippet=""):
    c = _c()
    c.execute(
        "INSERT INTO email_replies "
        "(inbox_id, prospect_id, lead_id, buyer_tenant, matched_kind, sentiment, summary, processed_at) "
        "VALUES (NULL,?,?,?,?,?,?, datetime('now'))",
        ("", "", to_email, source, "positive", snippet),
    )
    c.commit()
    c.close()


def retarget_segment(min_touches=1, max_touches=3):
    c = _c()
    replied = {r[0] for r in c.execute(
        "SELECT DISTINCT buyer_tenant FROM email_replies WHERE buyer_tenant != ''")}
    clicked = {r[0] for r in c.execute("SELECT DISTINCT email FROM lead_clicks WHERE email != ''")}
    rows = c.execute(
        "SELECT email, business_name, niche, touch_count, last_touch_at "
        "FROM si_buyer_outreach WHERE reply_state IN ('contacted','cold') "
        "AND touch_count BETWEEN ? AND ?",
        (min_touches, max_touches),
    ).fetchall()
    c.close()
    out = []
    for r in rows:
        email = r[0]
        out.append({
            "email": email, "business_name": r[1], "niche": r[2],
            "touch_count": r[3], "last_touch_at": r[4],
            "has_replied": email in replied, "has_clicked": email in clicked,
            "engaged": (email in replied) or (email in clicked),
        })
    return out


def summary():
    c = _c()
    s = {
        "clicks": c.execute("SELECT COUNT(*) FROM lead_clicks").fetchone()[0],
        "opens": c.execute("SELECT COUNT(*) FROM email_opens").fetchone()[0],
        "replies": c.execute(
            "SELECT COUNT(*) FROM email_replies WHERE buyer_tenant != ''").fetchone()[0],
        "clickers": c.execute(
            "SELECT COUNT(DISTINCT email) FROM lead_clicks WHERE email != ''").fetchone()[0],
        "repliers": c.execute(
            "SELECT COUNT(DISTINCT buyer_tenant) FROM email_replies WHERE buyer_tenant != ''").fetchone()[0],
    }
    c.close()
    return s


if __name__ == "__main__":
    ensure_tables()
    print("analytics tables ok:", json.dumps(summary()))
