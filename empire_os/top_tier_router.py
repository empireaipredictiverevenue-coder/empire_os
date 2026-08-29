"""
Empire OS v3 — Top-Tier pre-qualified contractor lead endpoint.

Only HOT/WARM leads from the Qualifier land here. Stored in SQLite
(top_tier_contractors) keyed by license_no/name so top-tier buyers pull
a clean, vetted feed.
"""
from __future__ import annotations
import os, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()
DB = os.environ.get("TOP_TIER_DB", "/root/empire_os/empire_os/top_tier_contractors.db")
Path(DB).parent.mkdir(parents=True, exist_ok=True)


def _conn():
    return sqlite3.connect(DB, timeout=30)


def _ensure():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS top_tier_contractors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, phone TEXT, email TEXT, website TEXT,
            state TEXT, city TEXT, license_no TEXT, license_status TEXT,
            niche TEXT, geo TEXT, tier TEXT, source TEXT,
            score INTEGER, scraped_at TEXT, created_at TEXT
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tt_lic ON top_tier_contractors(license_no)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tt_tier ON top_tier_contractors(tier)")


@router.get("/top-tier/stats")
async def stats():
    _ensure()
    with _conn() as c:
        cur = c.execute("SELECT tier, COUNT(*) FROM top_tier_contractors GROUP BY tier")
        rows = cur.fetchall()
    return {"ok": True, "by_tier": {t: n for t, n in rows}}


@router.post("/contractors/top-tier")
async def receive_top_tier(req: Request):
    _ensure()
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "bad_json"}, status_code=400)
    if isinstance(body, list):
        leads = body
    elif isinstance(body, dict) and "lead" in body:
        leads = [body["lead"]]
    else:
        leads = [body]
    n = 0
    with _conn() as c:
        for l in leads:
            tier = (l.get("tier") or "").upper()
            if tier not in ("HOT", "WARM"):
                continue
            c.execute("""INSERT INTO top_tier_contractors
                (name,phone,email,website,state,city,license_no,license_status,
                 niche,geo,tier,source,score,scraped_at,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (l.get("name"), l.get("phone"), l.get("email"), l.get("website"),
                 l.get("state"), l.get("city"), l.get("license_no"),
                 l.get("license_status"), l.get("niche"), l.get("geo"),
                 tier, l.get("source"), l.get("score"), l.get("scraped_at"),
                 datetime.now(timezone.utc).isoformat()))
            n += 1
    return {"ok": True, "stored": n}
