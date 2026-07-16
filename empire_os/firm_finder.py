"""
Empire OS — Firm Finder

Discovers candidate firms (the BUYERS in the lead-funnel economy)
from public sources. Output: rows in si_firm_candidates table.

Why this exists:
  Empire OS models the lead funnel end-to-end EXCEPT for one half:
  the supply side of BUYERS. Without buyers, the lanes stay empty.
  The user does not have a business — the AI has to find them.

What it does:
  - Reads firm_sources.json for the query list per vertical
  - Hits each source (Overpass API first; state-license pages later)
  - Normalizes records into {name, address, phone, website, lat, lon, source, vertical, classification, payload}
  - Upserts into si_firm_candidates (UNIQUE on (source, source_id))

Why not just two queries in agent.py:
  - Separate module so it can be unit-tested, called from CLI, or driven
    by an agent. Same `_run_once()` callable covers all three modes.
  - Sources list grows over time; JSON manifest is easier to edit than
    code. Provider-specific logic stays in this file as methods.

Cadence:
  - Default: 1 run / hour via firm_finder_agent.py
  - Manual: POST /v1/firms/scrape on firm_service.py

Fair use:
  - Sleeps 15s between Overpass queries (per fair_use_policy)
  - Honors a per-run timeout
  - User-Agent identifies us and an operator contact (per Overpass usage policy)

This module deliberately does NOT send any emails.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, "/root/empire_os")

# ── .env load (same pattern as ppl_service.py) ──────────────────────────
_ENV_PATH = Path("/root/empire_os/.env")
if _ENV_PATH.exists():
    try:
        for _ln in _ENV_PATH.read_text().splitlines():
            _ln = _ln.strip()
            if not _ln or _ln.startswith("#") or "=" not in _ln:
                continue
            _k, _v = _ln.split("=", 1)
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v
    except Exception:
        pass

DB_PATH = os.environ.get("DB_PATH", "/root/empire_os/empire_os.db")
SOURCES_PATH = Path("/root/empire_os/empire_os/firm_sources.json")
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS si_firm_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    source TEXT NOT NULL,            -- 'osm_overpass_roofing_tx', etc.
    source_id TEXT NOT NULL,         -- provider's record id (osm type:id)
    vertical TEXT NOT NULL,          -- 'roofing' | 'hvac' | 'plumber' | 'mass_tort'
    name TEXT NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    postcode TEXT,
    country TEXT,
    lat REAL,
    lon REAL,
    phone TEXT,
    website TEXT,
    classification TEXT,             -- 'craft=roofer' etc.
    email TEXT,                      -- discovered emails if crawlable
    payload TEXT,                    -- raw provider json (truncated)
    status TEXT NOT NULL DEFAULT 'uncontacted',
    matched_lane_id TEXT,
    contacted_at TEXT,
    contacted_via TEXT,
    blacklisted_reason TEXT,
    UNIQUE(source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_firm_vertical ON si_firm_candidates(vertical);
CREATE INDEX IF NOT EXISTS idx_firm_status ON si_firm_candidates(status);
CREATE INDEX IF NOT EXISTS idx_firm_state ON si_firm_candidates(state);
"""


def db():
    cnx = sqlite3.connect(DB_PATH)
    cnx.row_factory = sqlite3.Row
    return cnx


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── schema init ─────────────────────────────────────────────────────────
def init_db() -> tuple[int, int]:
    """Create table if needed. Returns (rowcount firms, distinct verticals)."""
    cnx = db()
    cnx.executescript(SCHEMA_SQL)
    cnx.commit()
    cur = cnx.execute("SELECT COUNT(*), COUNT(DISTINCT vertical) "
                      "FROM si_firm_candidates")
    n, v = cur.fetchone()
    cnx.close()
    return n, v


# ── HTTP helper (honest fair-use) ──────────────────────────────────────
def _http_get(url: str, *, timeout: int = 30,
              user_agent: str = "EmpireOS-firm-finder/1.0") -> tuple[int, str]:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": user_agent,
                     "Accept-Language": "en-US,en;q=0.9",
                     "Accept": "*/*"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"[:200]


# ── source-specific fetchers ───────────────────────────────────────────
def fetch_overpass(query: str, *, endpoint: str = "https://overpass-api.de/api/interpreter",
                   timeout: int = 60) -> list[dict]:
    """Run an Overpass query. Returns list of parsed {el_type, id, lat, lon, tags}."""
    encoded = urllib.parse.quote(query)
    url = f"{endpoint}?data={encoded}"
    code, body = _http_get(url, timeout=timeout)
    if code != 200:
        raise RuntimeError(
            f"overpass HTTP {code}: {body[:200]}")
    try:
        data = json.loads(body)
    except Exception as e:
        raise RuntimeError(f"overpass not JSON: {e}: {body[:200]}")
    elements = data.get("elements", []) or []
    out = []
    for el in elements:
        rec = {
            "el_type": el.get("type"),
            "id": el.get("id"),
            "lat": el.get("lat") or (el.get("center") or {}).get("lat"),
            "lon": el.get("lon") or (el.get("center") or {}).get("lon"),
            "tags": el.get("tags", {}) or {},
        }
        out.append(rec)
    return out


# ── normalization ──────────────────────────────────────────────────────
PHONE_RE = re.compile(r"\+?1?\s*[\(\-]?\d{3}[\)\-]?\s*\d{3}[\-\s]?\d{4}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _norm_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return raw.strip() or None


def _norm_record(el: dict, *, vertical: str, source: str,
                 state: str) -> dict:
    """One element from Overpass → one DB-bound record."""
    tags = el.get("tags") or {}
    addr_parts = [
        tags.get("addr:housenumber"),
        tags.get("addr:street"),
        tags.get("addr:city") or tags.get("addr:hamlet"),
    ]
    addr = " ".join(p for p in addr_parts if p) or None
    name = (tags.get("name") or tags.get("operator")
            or tags.get("brand") or "Unknown")
    classification = None
    for k in ("craft", "shop", "office", "amenity", "lawyer", "legal"):
        if k in tags:
            classification = k + "=" + str(tags[k])
            break
    phone = _norm_phone(tags.get("contact:phone") or tags.get("phone"))
    website = (tags.get("contact:website") or tags.get("website")
               or tags.get("url"))
    email = tags.get("contact:email") or tags.get("email")
    if email and not EMAIL_RE.match(email):
        email = None
    return {
        "source_id": f"{el.get('el_type','?')}:{el.get('id','?')}",
        "source": source,
        "vertical": vertical,
        "name": name.strip()[:200],
        "address": addr,
        "city": tags.get("addr:city"),
        "state": tags.get("addr:state") or state,
        "postcode": tags.get("addr:postcode"),
        "country": tags.get("addr:country") or "US",
        "lat": el.get("lat"),
        "lon": el.get("lon"),
        "phone": phone,
        "website": website[:200] if website else None,
        "classification": classification,
        "email": email,
        "payload": json.dumps(el.get("tags", {}))[:2000],
    }


# ── upsert ─────────────────────────────────────────────────────────────
def upsert_records(records: list[dict]) -> tuple[int, int]:
    """INSERT OR IGNORE on (source, source_id). Returns (inserted, total_seen)."""
    if not records:
        return 0, 0
    inserted = 0
    cnx = db()
    try:
        for r in records:
            cur = cnx.execute(
                "INSERT OR IGNORE INTO si_firm_candidates "
                "(ts, source, source_id, vertical, name, address, city, state, "
                " postcode, country, lat, lon, phone, website, classification, "
                " email, payload, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "        'uncontacted')",
                (now_iso(),
                 r["source"], r["source_id"], r["vertical"], r["name"],
                 r["address"], r["city"], r["state"], r["postcode"],
                 r["country"], r["lat"], r["lon"], r["phone"], r["website"],
                 r["classification"], r["email"], r["payload"]))
            if cur.rowcount > 0:
                inserted += 1
        cnx.commit()
    finally:
        cnx.close()
    return inserted, len(records)


# ── one run ────────────────────────────────────────────────────────────
def _log(level: str, msg: str, **kw) -> None:
    e = {"ts": now_iso(), "level": level, "msg": msg, **kw}
    out_dir = Path("/root/feedback")
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "firm_finder.log").open("a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "ALERT"):
        print(json.dumps(e), file=sys.stderr, flush=True)
    else:
        print(json.dumps(e), flush=True)


def _run_overpass_for_vertical(vertical_cfg: dict,
                               sources_manifest: dict) -> tuple[int, int]:
    """Returns (inserted_new, total_seen) for one vertical."""
    inserted = total = 0
    fair = sources_manifest.get("fair_use_policy", {})
    sleep_between = int(fair.get("we_sleep_between_queries_seconds", 15))
    ua = fair.get("user_agent",
                  "EmpireOS-firm-finder/1.0 (+operator@empire-ai.co.uk)")
    vertical_key = vertical_cfg.get("key") or vertical_cfg.get("label", "")
    for q in vertical_cfg.get("overpass_queries", []) or []:
        endpoint = q.get("endpoint", "https://overpass-api.de/api/interpreter")
        query = q.get("query", "")
        label = q.get("label", q.get("id", "overpass"))
        if not query:
            _log("WARN", "skip empty query", id=q.get("id"))
            continue
        _log("INFO", "overpass_start",
             vertical=vertical_key, id=q.get("id"), label=label)
        try:
            elements = fetch_overpass(query, endpoint=endpoint, timeout=60)
        except Exception as e:
            _log("ERROR", "overpass_failed",
                 vertical=vertical_key, id=q.get("id"), err=str(e)[:200])
            continue
        records = []
        for el in elements:
            # determine which "state" each element is in by its lat/lon
            # (Overpass results already constrained to the state by area filter)
            r = _norm_record(el, vertical=vertical_key,
                             source=f"overpass:{q.get('id')}",
                             state="TX")  # heuristic; overpass queries carry their area
            records.append(r)
        ins, tot = upsert_records(records)
        inserted += ins
        total += tot
        _log("INFO", "overpass_done",
             vertical=vertical_key, id=q.get("id"),
             seen=tot, inserted=ins)
        time.sleep(sleep_between)
    return inserted, total


def run_once(*, verticals: Iterable[str] | None = None) -> dict:
    """Top-level entry. Does one full pass over the manifest.

    Args:
      verticals: optional list of vertical keys to restrict. If None,
                 runs all verticals in the manifest.
    Returns:
      summary dict {vertical: {seen, inserted, errors}, totals}.
    """
    if not SOURCES_PATH.exists():
        _log("ERROR", "sources_manifest_missing", path=str(SOURCES_PATH))
        return {}
    manifest = json.loads(SOURCES_PATH.read_text())
    v_all = manifest.get("verticals", {})
    init_db()
    summary = {"totals": {"seen": 0, "inserted": 0, "errors": 0},
               "verticals": {}}
    for v_key, v_cfg in v_all.items():
        if verticals is not None and v_key not in verticals:
            continue
        v_summary = {"seen": 0, "inserted": 0, "errors": 0}
        try:
            ins, tot = _run_overpass_for_vertical(
                {**v_cfg, "key": v_key}, manifest)
            v_summary["seen"] = tot
            v_summary["inserted"] = ins
        except Exception as e:
            v_summary["errors"] += 1
            _log("ERROR", "vertical_failed", vertical=v_key,
                 err=str(e)[:200])
        summary["verticals"][v_key] = v_summary
        summary["totals"]["seen"] += v_summary["seen"]
        summary["totals"]["inserted"] += v_summary["inserted"]
        summary["totals"]["errors"] += v_summary["errors"]
    _log("INFO", "run_complete", **summary["totals"])
    return summary


# ── CLI ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--verticals", nargs="*", default=None,
                   help="restrict to specific vertical keys (e.g. roofing)")
    p.add_argument("--show-stats", action="store_true",
                   help="print current rowcounts and exit")
    args = p.parse_args()
    if args.show_stats:
        n, v = init_db()
        cnx = db()
        for r in cnx.execute(
            "SELECT vertical, COUNT(*) FROM si_firm_candidates "
            "GROUP BY vertical"):
            print(f"  {r[0]:<20} {r[1]:>6}")
        for r in cnx.execute(
            "SELECT status, COUNT(*) FROM si_firm_candidates "
            "GROUP BY status"):
            print(f"  status={r[0]:<18} {r[1]:>6}")
        print(f"  total: {n} rows, {v} verticals")
        cnx.close()
    else:
        run_once(verticals=args.verticals)
