"""Empire OS Hub Loop — single asyncio task owning the 3 in-process ticks
that previously lived as separate systemd agents / scripts.

Replaces:
  - empire-agent-founder-outreach.service (founder_outreach.py --watch)
  - empire-agent-outreach_runner.service (outreach_runner.py)
  - enrichment_webhook.py (HTTP service)
  - watchdog.sh / loop_closure_watchdog.py (killed hub every minute)

Runs as ONE asyncio.create_task inside hub.py lifespan — when EMPIRE_INPROC_AGENTS=1.
Owns nothing but the asyncio sleep + thread dispatch. All real work goes
through the existing hub `backend` (SQLiteBackend) so the DB write path
is the same as the HTTP handlers.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

log = logging.getLogger("empire.hub_loop")

# Tunables (override via .env if needed)
ENRICH_TICK_SEC = int(os.environ.get("HUB_LOOP_ENRICH_SEC", "90"))
OUTREACH_TICK_SEC = int(os.environ.get("HUB_LOOP_OUTREACH_SEC", "300"))
HEALTH_TICK_SEC = int(os.environ.get("HUB_LOOP_HEALTH_SEC", "60"))
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "") or Path("/root/empire_secrets/brevo_api_key").read_text().strip() if Path("/root/empire_secrets/brevo_api_key").exists() else ""
ENRICH_DOMAIN_GUESS = os.environ.get("HUB_LOOP_DOMAIN_GUESS", "1") == "1"  # synthesize domain from business_name when no url
MAIL_FROM = os.environ.get("EMPIRE_MAIL_FROM", "Empire AI <founder@empire-ai.co.uk>")
MAIL_REPLY_TO = os.environ.get("EMPIRE_REPLY_TO", "founder@empire-ai.co.uk>")
STATE_PATH = Path("/run/empire-hub-loop.json")
LOG_PATH = Path("/root/empire_os/logs/hub_loop.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _emit(level: str, msg: str, **fields) -> None:
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "level": level, "msg": msg, **fields}
    try:
        with LOG_PATH.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    except Exception:
        pass
    log.log({"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}.get(level, 20), "%s %s", msg, fields)


def _db_path() -> str:
    return os.environ.get("EMPIRE_DB_PATH", "empire_os.db")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_db_path(), timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


# ── Enrichment tick ──────────────────────────────────────────────────
def _enrich_domain_guess(business_name: str, niche: str) -> str:
    """Synthesize a likely domain when no url is on file."""
    slug = "".join(ch for ch in business_name.lower() if ch.isalnum())[:30]
    return f"{slug}.com" if slug else ""


def _enrich_one(pid: str, business_name: str, url: str, niche: str) -> Optional[str]:
    """Best-effort email lookup. Returns email or None."""
    import re
    domain = ""
    if url and "." in url and " " not in url and not url.startswith("skus:"):
        domain = url.split("//")[-1].split("/")[0]
    elif ENRICH_DOMAIN_GUESS and business_name:
        domain = _enrich_domain_guess(business_name, niche)

    if not domain:
        return None

    role_prefixes = ["info", "contact", "sales", "hello", "team", "office", "support"]
    candidates = [f"{r}@{domain}" for r in role_prefixes]
    return candidates[0]


def _enrich_tick(backend) -> dict:
    """Find empty-email prospects, stamp a role email. Commits every 5 rows."""
    c = backend._conn if hasattr(backend, "conn") else None
    if c is None:
        c = backend._conn
    cur = c.cursor()
    rows = cur.execute(
        """
        SELECT prospect_id, business_name, url, niche, source
        FROM si_buyer_outreach
        WHERE (email IS NULL OR email='')
          AND business_name IS NOT NULL AND business_name != ''
          AND (touch_count IS NULL OR touch_count = 0)
        ORDER BY prospect_id
        LIMIT 25
        """
    ).fetchall()

    enriched = 0
    write_conn = _conn()  # separate connection for writes so reads don't hold locks
    write_conn.execute("PRAGMA busy_timeout=30000")
    for i, r in enumerate(rows):
        pid, bname, url, niche, source = r["prospect_id"], r["business_name"], r["url"] or "", r["niche"] or "", r["source"] or ""
        if url and url.startswith("skus:") and not bname:
            continue
        email = _enrich_one(pid, bname, url, niche)
        if not email:
            continue
        # Use separate connection; commit immediately so HTTP requests
        # landing on the hub's main tenant_store connection aren't blocked.
        try:
            write_conn.execute("UPDATE si_buyer_outreach SET email=? WHERE prospect_id=?", (email, pid))
            write_conn.commit()
        except Exception:
            write_conn.rollback()
        enriched += 1
    write_conn.close()
    return {"candidates": len(rows), "enriched": enriched}


# ── Outreach tick ────────────────────────────────────────────────────
def _outreach_tick(backend) -> dict:
    """Pull pending prospects, draft + queue to Brevo outbox."""
    c = backend._conn
    cur = c.cursor()
    rows = cur.execute(
        """
        SELECT prospect_id, business_name, email, niche, metro, url, source, score, seq_step, last_touch_at
        FROM si_buyer_outreach
        WHERE (reply_state = 'cold' OR touch_count IS NULL OR touch_count = 0)
          AND email IS NOT NULL AND email != '' AND email NOT LIKE '%@example%'
        ORDER BY (email IS NOT NULL AND email != '') DESC, score DESC
        LIMIT 10
        """
    ).fetchall()

    import re
    sent = 0
    skipped = 0
    # Separate write connection so HTTP handlers on the main tenant_store
    # connection aren't blocked by this tick's writes.
    write_conn = _conn()
    write_conn.execute("PRAGMA busy_timeout=30000")
    for r in rows:
        pid = r["prospect_id"]
        email = r["email"]
        bname = (r["business_name"] or "").strip()
        niche = r["niche"] or "your specialty"
        metro = r["metro"] or "your area"
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            skipped += 1
            continue
        # Reject emails with invalid chars in domain part (parens, commas, etc.)
        domain = email.split("@")[1] if "@" in email else ""
        if any(c in domain for c in "(),"):
            skipped += 1
            continue
        subject, body = _draft_email(bname, niche, metro)
        meta = json.dumps({"prospect_id": pid, "name": bname, "from": MAIL_FROM, "reply_to": MAIL_REPLY_TO})
        try:
            write_conn.execute(
                "INSERT INTO si_outbox (to_email, subject, body, source, meta_json, html_body) VALUES (?,?,?,?,?,?)",
                (email, subject, body, "hub_loop_outreach", meta, body),
            )
            write_conn.execute(
                "UPDATE si_buyer_outreach SET touch_count = COALESCE(touch_count,0)+1, last_touch_at = datetime('now'), reply_state='contacted' WHERE prospect_id=?",
                (pid,),
            )
            write_conn.commit()
            sent += 1
        except Exception as e:
            write_conn.rollback()
            _emit("ERROR", "outbox_insert_failed", error=str(e)[:200], prospect_id=pid)
            skipped += 1
    write_conn.close()
    return {"considered": len(rows), "sent": sent, "skipped": skipped}


def _draft_email(bname: str, niche: str, metro: str) -> tuple[str, str]:
    name = bname.split("|")[0].split(" - ")[0].strip() or "there"
    subject = f"Exclusive {niche.replace('_', ' ')} leads for {metro} — pay in USDC, no cards"
    body = (
        f"Hi {name},\n\n"
        f"We deliver fresh {niche.replace('_', ' ')} leads into {metro} daily. "
        "Pay per lead in USDC — no card, no KYC, no monthly fee. "
        "Sample is free on reply.\n\n"
        "— Phillip, Empire AI\n"
    )
    return subject, body


# ── Self-health tick ─────────────────────────────────────────────────
def _health_tick() -> dict:
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "alive": True,
        "enrich_tick_sec": ENRICH_TICK_SEC,
        "outreach_tick_sec": OUTREACH_TICK_SEC,
    }
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(rec))
    except Exception:
        pass
    return rec


# ── Loop ─────────────────────────────────────────────────────────────
async def run(backend) -> None:
    _emit("INFO", "hub_loop_started", enrich_sec=ENRICH_TICK_SEC, outreach_sec=OUTREACH_TICK_SEC, health_sec=HEALTH_TICK_SEC)

    next_enrich = time.monotonic()
    next_outreach = time.monotonic() + 30
    next_health = time.monotonic()

    while True:
        now = time.monotonic()
        try:
            if now >= next_health:
                h = await asyncio.to_thread(_health_tick)
                _emit("INFO", "health_tick", **h)
                next_health = now + HEALTH_TICK_SEC

            if now >= next_enrich:
                r = await asyncio.to_thread(_enrich_tick, backend)
                _emit("INFO", "enrich_tick", **r)
                next_enrich = now + ENRICH_TICK_SEC

            if now >= next_outreach:
                r = await asyncio.to_thread(_outreach_tick, backend)
                _emit("INFO", "outreach_tick", **r)
                next_outreach = now + OUTREACH_TICK_SEC
        except Exception as e:
            _emit("ERROR", "tick_failed", error=str(e)[:300])
            await asyncio.sleep(5)

        sleeps = [next_enrich, next_outreach, next_health]
        await asyncio.sleep(max(1.0, min(sleeps) - time.monotonic()))