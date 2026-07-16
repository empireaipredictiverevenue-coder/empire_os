"""Empire CRM — Full lead management, enrichment, and AI qualification.

Tables:
  crm_leads         — Unified lead record with enriched fields
  crm_activities    — Notes, calls, emails, touchpoints
  crm_pipeline      — Pipeline stage definitions
  crm_lead_pipeline — Current pipeline stage per lead
  crm_tags          — Tag/label definitions
  crm_lead_tags     — Many-to-many lead/tag
  crm_enrichment_log — Track enrichment sources queried per lead

Scoring: Uses omega_score (inherited from lane_leads) + enrichment-derived
signals + optional AI re-scoring via configurable weight sets.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("empire_crm")

# ── Schema ──────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS crm_leads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_uid        TEXT    UNIQUE NOT NULL,          -- stable external id (lane_leads.prospect_id or auto)
    source          TEXT    DEFAULT 'import',
    business_name   TEXT    DEFAULT '',
    contact_name    TEXT    DEFAULT '',
    email           TEXT    DEFAULT '',
    phone           TEXT    DEFAULT '',
    metro           TEXT    DEFAULT '',
    niche           TEXT    DEFAULT '',
    sub_niche       TEXT    DEFAULT '',
    street          TEXT    DEFAULT '',
    city            TEXT    DEFAULT '',
    state           TEXT    DEFAULT '',
    zip             TEXT    DEFAULT '',
    website         TEXT    DEFAULT '',
    social_links    TEXT    DEFAULT '[]',             -- JSON array
    employee_count  INTEGER DEFAULT 0,
    revenue_est     INTEGER DEFAULT 0,               -- estimated annual revenue
    year_founded    INTEGER DEFAULT 0,
    bbb_rating      TEXT    DEFAULT '',
    license_no      TEXT    DEFAULT '',
    license_state   TEXT    DEFAULT '',
    omega_score     REAL    DEFAULT 0,
    omega_tier      TEXT    DEFAULT '',
    enrichment_score REAL   DEFAULT 0,               -- 0-100 completeness score
    status          TEXT    DEFAULT 'raw',            -- raw / qualifying / qualified / assigned / contacted / converted / dead
    owner           TEXT    DEFAULT '',               -- assigned user/contractor
    notes           TEXT    DEFAULT '',
    tags_json       TEXT    DEFAULT '[]',
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now'))
);

CREATE INDEX IF NOT EXISTS idx_crm_leads_status ON crm_leads(status);
CREATE INDEX IF NOT EXISTS idx_crm_leads_niche  ON crm_leads(niche);
CREATE INDEX IF NOT EXISTS idx_crm_leads_metro  ON crm_leads(metro);
CREATE INDEX IF NOT EXISTS idx_crm_leads_score  ON crm_leads(omega_score DESC);

CREATE TABLE IF NOT EXISTS crm_activities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id     INTEGER NOT NULL REFERENCES crm_leads(id),
    act_type    TEXT    NOT NULL,        -- note / call / email / sms / enrichment / system
    summary     TEXT    DEFAULT '',
    detail      TEXT    DEFAULT '',      -- markdown or JSON
    actor       TEXT    DEFAULT 'system',
    occurred_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now')),
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now'))
);

CREATE INDEX IF NOT EXISTS idx_crm_act_lead ON crm_activities(lead_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS crm_pipeline_stages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    UNIQUE NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    color       TEXT    DEFAULT '#6b7280',
    default_for TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS crm_lead_pipeline (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id     INTEGER NOT NULL REFERENCES crm_leads(id),
    stage_id    INTEGER NOT NULL REFERENCES crm_pipeline_stages(id),
    entered_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now')),
    exited_at   TEXT,
    UNIQUE(lead_id, stage_id)
);

CREATE TABLE IF NOT EXISTS crm_tags (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT    UNIQUE NOT NULL,
    color   TEXT    DEFAULT '#6b7280'
);

CREATE TABLE IF NOT EXISTS crm_lead_tags (
    lead_id INTEGER NOT NULL REFERENCES crm_leads(id),
    tag_id  INTEGER NOT NULL REFERENCES crm_tags(id),
    PRIMARY KEY (lead_id, tag_id)
);

CREATE TABLE IF NOT EXISTS crm_enrichment_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id     INTEGER NOT NULL REFERENCES crm_leads(id),
    source      TEXT    NOT NULL,
    status      TEXT    NOT NULL,        -- success / skipped / failed
    fields_found INTEGER DEFAULT 0,
    detail      TEXT    DEFAULT '',
    ran_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now'))
);
"""


def ensure_schema(backend) -> None:
    """Create all CRM tables if they don't exist. Idempotent."""
    backend.executescript(SCHEMA_SQL)
    # Seed default pipeline stages
    stages = [
        ("raw", 0, "#6b7280", "imported"),
        ("qualifying", 1, "#f59e0b", ""),
        ("qualified", 2, "#10b981", ""),
        ("assigned", 3, "#3b82f6", ""),
        ("contacted", 4, "#8b5cf6", ""),
        ("converted", 5, "#059669", ""),
        ("dead", 6, "#ef4444", ""),
    ]
    for name, order, color, default_for in stages:
        try:
            backend.execute(
                "INSERT OR IGNORE INTO crm_pipeline_stages (name, sort_order, color, default_for) VALUES (?, ?, ?, ?)",
                (name, order, color, default_for),
            )
        except Exception:
            pass
    backend.commit()
    logger.info("CRM schema ensured")


# ── Data classes ────────────────────────────────────────────────────


@dataclass
class CrmLead:
    id: int = 0
    lead_uid: str = ""
    source: str = "import"
    business_name: str = ""
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    metro: str = ""
    niche: str = ""
    sub_niche: str = ""
    street: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    website: str = ""
    social_links: list = field(default_factory=list)
    employee_count: int = 0
    revenue_est: int = 0
    year_founded: int = 0
    bbb_rating: str = ""
    license_no: str = ""
    license_state: str = ""
    omega_score: float = 0.0
    omega_tier: str = ""
    enrichment_score: float = 0.0
    status: str = "raw"
    owner: str = ""
    notes: str = ""
    tags_json: str = "[]"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["social_links"] = self.social_links if isinstance(self.social_links, list) else json.loads(self.social_links)
        d["tags"] = json.loads(self.tags_json) if isinstance(self.tags_json, str) else self.tags_json
        return d


@dataclass
class CrmActivity:
    id: int = 0
    lead_id: int = 0
    act_type: str = "note"
    summary: str = ""
    detail: str = ""
    actor: str = "system"
    occurred_at: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ── Lead CRUD ───────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%f")


def import_from_lane_leads(backend) -> dict:
    """Import all lane_leads into CRM. Idempotent (upserts by lead_uid)."""
    rows = backend.execute(
        "SELECT id, lane_id, prospect_id, status, omega_score, omega_tier, notes, niche "
        "FROM lane_leads"
    ).fetchall()
    imported = 0
    skipped = 0
    for row in rows:
        pid = row["prospect_id"] or f"lane_{row['id']}"
        existing = backend.execute(
            "SELECT id FROM crm_leads WHERE lead_uid = ?", (pid,)
        ).fetchone()
        if existing:
            skipped += 1
            continue
        now = _now()
        backend.execute(
            """INSERT INTO crm_leads
               (lead_uid, source, niche, omega_score, omega_tier, notes, status, created_at, updated_at)
               VALUES (?, 'lane_leads', ?, ?, ?, ?, 'raw', ?, ?)""",
            (pid, row["niche"] or "", float(row["omega_score"] or 0),
             row["omega_tier"] or "", row["notes"] or "", now, now),
        )
        # Log activity
        backend.execute(
            "INSERT INTO crm_activities (lead_id, act_type, summary, actor) VALUES (?, 'system', 'Imported from lane_leads', 'crm')",
            (backend.execute("SELECT last_insert_rowid()").fetchone()[0],),
        )
        imported += 1
    backend.commit()
    # Update enriched records from si_buyer_outreach where possible
    updated = 0
    br = backend.execute(
        "SELECT prospect_id, business_name, email, phone, metro, niche FROM si_buyer_outreach"
    ).fetchall()
    for r in br:
        if not r["prospect_id"]:
            continue
        c = backend.execute(
            "SELECT id, business_name, email, phone FROM crm_leads WHERE lead_uid = ?",
            (r["prospect_id"],),
        ).fetchone()
        if c and (not c["business_name"] or not c["email"]):
            updates = []
            params = []
            if r["business_name"] and not c["business_name"]:
                updates.append("business_name = ?")
                params.append(r["business_name"])
            if r["email"] and not c["email"]:
                updates.append("email = ?")
                params.append(r["email"])
            if r["phone"] and not c["phone"]:
                updates.append("phone = ?")
                params.append(r["phone"])
            if r["metro"] and not c["metro"]:
                updates.append("metro = ?")
                params.append(r["metro"])
            if updates:
                params.append(r["prospect_id"])
                backend.execute(
                    f"UPDATE crm_leads SET {', '.join(updates)} WHERE lead_uid = ?",
                    tuple(params),
                )
                updated += 1
    if updated:
        backend.commit()
    return {"imported": imported, "skipped": skipped, "enriched_from_outreach": updated}


def list_leads(
    backend,
    status: Optional[str] = None,
    niche: Optional[str] = None,
    metro: Optional[str] = None,
    omega_min: Optional[float] = None,
    query: Optional[str] = None,
    enrich_min: Optional[float] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Filterable lead listing with pagination."""
    where = ["1=1"]
    params: list = []
    if status:
        where.append("c.status = ?")
        params.append(status)
    if niche:
        where.append("c.niche = ?")
        params.append(niche)
    if metro:
        where.append("c.metro = ?")
        params.append(metro)
    if omega_min is not None:
        where.append("c.omega_score >= ?")
        params.append(omega_min)
    if enrich_min is not None:
        where.append("c.enrichment_score >= ?")
        params.append(enrich_min)
    if query:
        where.append("(c.business_name LIKE ? OR c.contact_name LIKE ? OR c.email LIKE ? OR c.phone LIKE ?)")
        q = f"%{query}%"
        params.extend([q, q, q, q])

    # Count
    cnt = backend.execute(
        f"SELECT COUNT(*) AS total FROM crm_leads c WHERE {' AND '.join(where)}",
        tuple(params),
    ).fetchone()["total"]

    # Fetch
    rows = backend.execute(
        f"SELECT c.*, COALESCE(a.activity_count, 0) AS activity_count FROM crm_leads c "
        f"LEFT JOIN (SELECT lead_id, COUNT(*) AS activity_count FROM crm_activities GROUP BY lead_id) a "
        f"ON c.id = a.lead_id "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY c.omega_score DESC, c.created_at DESC "
        f"LIMIT ? OFFSET ?",
        tuple(params + [limit, offset]),
    ).fetchall()

    leads = [_row_to_lead(r) for r in rows]
    return {"total": cnt, "limit": limit, "offset": offset, "leads": leads}


def get_lead(backend, lead_id: int) -> dict:
    """Single lead with activities and current pipeline stage."""
    row = backend.execute(
        "SELECT c.*, COALESCE(a.activity_count, 0) AS activity_count FROM crm_leads c "
        "LEFT JOIN (SELECT lead_id, COUNT(*) AS activity_count FROM crm_activities GROUP BY lead_id) a "
        "ON c.id = a.lead_id "
        "WHERE c.id = ?", (lead_id,)
    ).fetchone()
    if not row:
        raise ValueError(f"Lead id={lead_id} not found")

    lead = _row_to_lead(row)

    # Activities
    activities = [
        dict(r) for r in backend.execute(
            "SELECT * FROM crm_activities WHERE lead_id = ? ORDER BY occurred_at DESC LIMIT 50",
            (lead_id,),
        ).fetchall()
    ]

    # Current pipeline stage
    stage = backend.execute(
        "SELECT ps.* FROM crm_lead_pipeline lp "
        "JOIN crm_pipeline_stages ps ON lp.stage_id = ps.id "
        "WHERE lp.lead_id = ? AND lp.exited_at IS NULL "
        "ORDER BY lp.entered_at DESC LIMIT 1",
        (lead_id,),
    ).fetchone()

    return {
        "lead": lead,
        "activities": activities,
        "current_stage": dict(stage) if stage else None,
    }


def update_lead(
    backend,
    lead_id: int,
    updates: dict,
    actor: str = "user",
) -> dict:
    """Update lead fields. Logs changes as activities."""
    row = backend.execute("SELECT * FROM crm_leads WHERE id = ?", (lead_id,)).fetchone()
    if not row:
        raise ValueError(f"Lead id={lead_id} not found")

    now = _now()
    setters = ["updated_at = ?"]
    params: list = [now]
    changed = []

    allowed = {
        "status", "owner", "notes", "business_name", "contact_name",
        "email", "phone", "metro", "niche", "sub_niche",
        "street", "city", "state", "zip", "website", "license_no",
        "license_state", "omega_score", "omega_tier", "tags_json",
    }

    for key, val in updates.items():
        if key not in allowed:
            continue
        old = row[key]
        if str(old) != str(val):
            setters.append(f"{key} = ?")
            params.append(val)
            changed.append(f"{key}: {old} → {val}")

    if not changed:
        return get_lead(backend, lead_id)

    params.append(lead_id)
    backend.execute(
        f"UPDATE crm_leads SET {', '.join(setters)} WHERE id = ?",
        tuple(params),
    )
    backend.commit()

    if changed:
        backend.execute(
            "INSERT INTO crm_activities (lead_id, act_type, summary, detail, actor, occurred_at) "
            "VALUES (?, 'system', ?, ?, ?, ?)",
            (lead_id, f"Updated {len(changed)} field(s)", "; ".join(changed[:10]), actor, now),
        )
        backend.commit()

    return get_lead(backend, lead_id)


def add_activity(backend, lead_id: int, act_type: str, summary: str, detail: str = "", actor: str = "user") -> dict:
    """Add a note/call/email/sms activity to a lead."""
    row = backend.execute("SELECT id FROM crm_leads WHERE id = ?", (lead_id,)).fetchone()
    if not row:
        raise ValueError(f"Lead id={lead_id} not found")
    now = _now()
    backend.execute(
        "INSERT INTO crm_activities (lead_id, act_type, summary, detail, actor, occurred_at) VALUES (?, ?, ?, ?, ?, ?)",
        (lead_id, act_type, summary, detail, actor, now),
    )
    backend.commit()
    return {"ok": True, "activity_id": backend.execute("SELECT last_insert_rowid()").fetchone()[0]}


def set_pipeline_stage(backend, lead_id: int, stage_name: str, actor: str = "user") -> dict:
    """Move lead to a pipeline stage. Exits previous stage, enters new one."""
    row = backend.execute("SELECT id FROM crm_leads WHERE id = ?", (lead_id,)).fetchone()
    if not row:
        raise ValueError(f"Lead id={lead_id} not found")
    stage = backend.execute(
        "SELECT id, name FROM crm_pipeline_stages WHERE name = ?", (stage_name,)
    ).fetchone()
    if not stage:
        raise ValueError(f"Pipeline stage '{stage_name}' not found")

    now = _now()
    # Exit current active stage
    backend.execute(
        "UPDATE crm_lead_pipeline SET exited_at = ? WHERE lead_id = ? AND exited_at IS NULL",
        (now, lead_id),
    )
    # Enter new stage
    backend.execute(
        "INSERT INTO crm_lead_pipeline (lead_id, stage_id, entered_at) VALUES (?, ?, ?)",
        (lead_id, stage["id"], now),
    )
    # Update lead status to match
    backend.execute(
        "UPDATE crm_leads SET status = ?, updated_at = ? WHERE id = ?",
        (stage_name, now, lead_id),
    )
    backend.commit()
    backend.execute(
        "INSERT INTO crm_activities (lead_id, act_type, summary, actor, occurred_at) VALUES (?, 'system', ?, ?, ?)",
        (lead_id, f"Moved to pipeline stage: {stage_name}", actor, now),
    )
    backend.commit()
    return {"ok": True, "stage": stage_name}


def get_pipeline_summary(backend) -> dict:
    """Return lead counts per pipeline stage + totals."""
    stages = backend.execute(
        "SELECT * FROM crm_pipeline_stages ORDER BY sort_order"
    ).fetchall()
    results = []
    total = 0
    for s in stages:
        cnt = backend.execute(
            "SELECT COUNT(*) AS cnt FROM crm_leads WHERE status = ?", (s["name"],)
        ).fetchone()["cnt"]
        results.append({"stage": s["name"], "count": cnt, "color": s["color"]})
        total += cnt
    return {"stages": results, "total": total}


def get_lead_counts(backend) -> dict:
    """Real lead inventory across Empire OS lead tables.
    Drives the marketing sweep + delivery engine (was 500 -> total 0)."""
    def _c(t):
        try:
            return backend.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
        except Exception:
            return 0
    lane = _c("lane_leads")
    outreach = _c("si_buyer_outreach")
    crm = _c("crm_leads")
    total = lane + outreach + crm
    by_status = {}
    try:
        for st, n in backend.execute(
            "SELECT COALESCE(status,'unknown') AS s, COUNT(*) AS c FROM lane_leads GROUP BY s"
        ).fetchall():
            by_status[st] = n
    except Exception:
        pass
    return {
        "total": total,
        "by_table": {"lane_leads": lane, "si_buyer_outreach": outreach, "crm_leads": crm},
        "by_status": by_status,
        "pending": by_status.get("pending", 0) + by_status.get("new", 0),
        "delivered": by_status.get("delivered", 0),
    }


def batch_update_status(backend, lead_ids: list[int], status: str, actor: str = "user") -> dict:
    """Bulk update lead statuses."""
    now = _now()
    count = 0
    for lid in lead_ids:
        try:
            set_pipeline_stage(backend, lid, status, actor)
            count += 1
        except ValueError:
            pass
    return {"ok": True, "updated": count}


# ── Helpers ─────────────────────────────────────────────────────────


def _row_to_lead(row: sqlite3.Row) -> dict:
    d = dict(row)
    # Parse JSON fields
    for jf in ("social_links", "tags_json"):
        if isinstance(d.get(jf), str):
            try:
                d[jf.replace("_json", "") if jf == "tags_json" else jf] = json.loads(d[jf])
            except (json.JSONDecodeError, TypeError):
                d[jf] = []
    if "tags_json" in d:
        d["tags"] = json.loads(d.pop("tags_json")) if isinstance(d["tags_json"], str) else d.pop("tags_json")
    return d
