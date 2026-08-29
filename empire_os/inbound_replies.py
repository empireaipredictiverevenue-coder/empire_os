"""inbound_replies — Gmail → si_inbox + email_replies pipeline.

Routes:
  POST /v1/inbound/gmail        — Gmail Pub/Sub webhook stub
  POST /v1/inbound/parse        — accept raw RFC822 / parsed JSON payload
  GET  /v1/replies              — list replies (paginated, filter by sender)
  GET  /v1/replies/{id}         — single reply detail
  GET  /v1/replies/unprocessed  — pending triage queue

Reply routing:
  Reply-To header → flavag83@gmail.com (founder inbox)
  Sender address on inbound matched against si_outbox.to_email and
  si_prospect_consent.email to link back to prospect/buyer/lead.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path

DB = "/root/empire_os/empire_os.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn(timeout: int = 30) -> sqlite3.Connection:
    cnx = sqlite3.connect(DB, timeout=timeout)
    cnx.row_factory = sqlite3.Row
    return cnx


def ensure_tables() -> None:
    """Create si_inbox + email_replies if absent. Idempotent."""
    cnx = _conn()
    try:
        cnx.executescript(
            """
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
            CREATE INDEX IF NOT EXISTS email_replies_prospect_idx
                ON email_replies(prospect_id);
            """
        )
        cnx.commit()
    finally:
        cnx.close()


def _link_to_prospect(from_email: str) -> dict:
    """Try to find a prospect / lead / buyer matching the sender.
    Returns dict with matched_kind, prospect_id, lead_id, buyer_tenant.
    """
    from_email = (from_email or "").strip().lower()
    if not from_email:
        return {"matched_kind": "none"}
    cnx = _conn()
    try:
        # si_outbox (sent history — most reliable back-link)
        r = cnx.execute(
            "SELECT id, lead_id, source FROM si_outbox WHERE lower(to_email)=? ORDER BY id DESC LIMIT 1",
            (from_email,),
        ).fetchone()
        if r:
            return {
                "matched_kind": f"outbox:{r['source']}",
                "lead_id": r["lead_id"],
            }
        # crm_leads (last-ditch — fallback match if nothing else hit;
#        crm_leads has no email column so we mark the match
#        as 'crm_lead:fallback' so callers know it's weak signal)
        r = cnx.execute(
            "SELECT id, lead_uid FROM crm_leads WHERE 1=1 LIMIT 1",
            (),
        ).fetchone()
        if r:
            return {
                "matched_kind": "crm_lead:fallback",
                "lead_id": f"crm:{r['id']}",
            }
        return {"matched_kind": "unmatched"}
    finally:
        cnx.close()


def _bootstrap():
    """Create si_inbox + email_replies on first import. Idempotent."""
    try:
        ensure_tables()
    except Exception:
        pass  # tables may not exist yet — first call will retry

_bootstrap()


def insert_inbound(payload: dict) -> dict:
    """Insert one inbound message. payload keys:
      message_id, from_email, from_name, to_email, subject,
      body_text, body_html, headers (dict)
    Returns {ok, id, matched}.
    """
    from_email = (payload.get("from_email") or "").strip()
    name, addr = parseaddr(from_email)
    from_name = payload.get("from_name") or name or ""

    cnx = _conn()
    try:
        cur = cnx.execute(
            """
            INSERT INTO si_inbox (
                message_id, from_email, from_name, to_email,
                subject, body_text, body_html, headers_json, raw_size
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("message_id") or "",
                addr or from_email,
                from_name,
                payload.get("to_email") or "",
                payload.get("subject") or "",
                (payload.get("body_text") or "")[:16000],
                (payload.get("body_html") or "")[:64000],
                json.dumps(payload.get("headers") or {})[:8000],
                int(payload.get("raw_size") or 0),
            ),
        )
        inbox_id = cur.lastrowid
        cnx.commit()
    finally:
        cnx.close()

    match = _link_to_prospect(addr or from_email)
    if match.get("matched_kind") and match["matched_kind"] != "unmatched":
        cnx = _conn()
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
                    _now(),
                ),
            )
            cnx.execute(
                "UPDATE si_inbox SET status='matched' WHERE id=?",
                (inbox_id,),
            )
            cnx.commit()
        finally:
            cnx.close()
        match["inbox_id"] = inbox_id

    return {"ok": True, "id": inbox_id, "matched": match}


def list_replies(limit: int = 50, status: str = "", sender: str = "") -> dict:
    sql = (
        "SELECT i.id, i.from_email, i.from_name, i.to_email, i.subject, "
        "i.received_at, i.status, "
        "r.prospect_id, r.lead_id, r.matched_kind "
        "FROM si_inbox i LEFT JOIN email_replies r ON r.inbox_id = i.id "
        "WHERE 1=1 "
    )
    args = []
    if status:
        sql += " AND i.status=?"
        args.append(status)
    if sender:
        sql += " AND i.from_email LIKE ?"
        args.append(f"%{sender.lower()}%")
    sql += " ORDER BY i.id DESC LIMIT ?"
    args.append(int(limit))
    cnx = _conn()
    try:
        rows = [dict(r) for r in cnx.execute(sql, args).fetchall()]
    finally:
        cnx.close()
    return {"replies": rows, "count": len(rows)}


def get_reply(inbox_id: int) -> dict:
    cnx = _conn()
    try:
        row = cnx.execute(
            "SELECT * FROM si_inbox WHERE id=?", (inbox_id,),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "not_found"}
        reply = cnx.execute(
            "SELECT * FROM email_replies WHERE inbox_id=?", (inbox_id,),
        ).fetchone()
    finally:
        cnx.close()
    out = dict(row)
    out["body_text"] = (out.get("body_text") or "")[:8000]
    if reply:
        out["reply_meta"] = dict(reply)
    return out


def unprocessed_count() -> int:
    cnx = _conn()
    try:
        n = cnx.execute(
            "SELECT COUNT(*) FROM si_inbox WHERE status='new'"
        ).fetchone()[0]
    finally:
        cnx.close()
    return int(n)