#!/usr/bin/env python3
"""
empire_company_intel.py — competitor + market intelligence.

Watches what competitors are doing in each (metro, niche) so Empire OS can
find gaps to fill.

Two lenses:

1. **Lead-pipeline view** — count us vs them in each lane.
   - us = lane_leads.source = 'empire_enrich/*' or 'permits:*' (we own this)
   - them = other sources
   - 7-day rolling window

2. **Buyer-pool view** — who is competing to buy the same leads.
   - si_buyer_outreach.business_name clusters
   - their active outreach cadence (touch_count, last_touch_at)

What we emit:
  /root/feedback/company_intel.jsonl          (append-only)
  /root/feedback/company_intel_latest.json     (latest)
  /root/feedback/competitor_signals.jsonl       (one-line per signal)

Cadence: empire-company-intel.timer → empire-company-intel.service (daily).
"""
from __future__ import annotations
import os, sys, json, sqlite3, time, logging
from datetime import datetime, timezone, timedelta

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)
sys.path.insert(0, os.path.dirname(_THIS_DIR))

log = logging.getLogger("empire_company_intel")

DB = os.getenv("EMPIRE_DB", "/root/empire_os/empire_os.db")
FEED = "/root/feedback"
JSONL = os.path.join(FEED, "company_intel.jsonl")
LATEST = os.path.join(FEED, "company_intel_latest.json")
SIGNALS = os.path.join(FEED, "competitor_signals.jsonl")
MAX_JSONL_BYTES = 5 * 1024 * 1024


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(x):
    try:
        return int(x or 0)
    except Exception:
        return 0


def _lane_leads_cols() -> set[str]:
    con = _db()
    try:
        return {r[1] for r in con.execute("PRAGMA table_info(lane_leads)").fetchall()}
    finally:
        con.close()


def _buyer_cols() -> set[str]:
    con = _db()
    try:
        return {r[1] for r in con.execute("PRAGMA table_info(si_buyer_outreach)").fetchall()}
    finally:
        con.close()


def _own_sources() -> set[str]:
    """Sources owned by Empire OS — leads we generate ourselves."""
    return {
        "permits", "nyc_hpd", "chicago_311", "overpass",
        "searxng_search", "universal_scraper", "solar_intelligence",
        "storm_alerts", "court_listener", "search_api_leads",
        "empire_enrich", "fema", "sam_gov", "acris",
        "dob_violations", "hud",
    }


def _is_own_source(source: str | None) -> bool:
    if not source:
        return False
    return any(source.startswith(s) for s in _own_sources())


def _pipeline_view() -> dict:
    """Lead-pipeline: empire-sourced vs others, per (metro, niche)."""
    con = _db()
    try:
        cols = _lane_leads_cols()
        if "metro" not in cols or "niche" not in cols:
            return {"data_drift": True, "reason": "missing_metro_or_niche"}
        # Live lane_leads schema has no source column. Never issue SQL against
        # a column that schema inspection proved absent; preserve uncertainty.
        if "source" not in cols:
            rows = con.execute("""
                SELECT metro, niche, COUNT(*) AS total
                FROM lane_leads
                WHERE metro IS NOT NULL AND metro != ''
                  AND niche IS NOT NULL AND niche != ''
                GROUP BY metro, niche
                ORDER BY metro, total DESC
            """).fetchall()
            out = {}
            for r in rows:
                out.setdefault(r["metro"], {})[r["niche"]] = {
                    "total_leads_30d": _safe_int(r["total"]),
                    "empire_leads_30d": None,
                    "competing_leads_30d": None,
                    "our_supply_share_pct": None,
                    "data_drift": True,
                    "reason": "lane_leads_source_column_missing",
                }
            return {"data": out, "data_drift": True,
                    "reason": "lane_leads_source_column_missing"}
        sql = """
        SELECT metro, niche, COUNT(*) AS total,
               SUM(CASE WHEN source LIKE 'empire_enrich/%'
                         OR source LIKE 'permits:%'
                         OR source LIKE 'nyc_hpd:%'
                         OR source LIKE 'chicago_311:%'
                         OR source LIKE 'overpass:%'
                         OR source LIKE 'searxng_search:%'
                         OR source LIKE 'universal_scraper:%'
                         OR source LIKE 'solar_intelligence:%'
                         OR source LIKE 'storm_alerts:%'
                         OR source LIKE 'court_listener:%'
                         OR source LIKE 'search_api_leads:%'
                         OR source LIKE 'fema:%'
                         OR source LIKE 'sam_gov:%'
                         OR source LIKE 'acris:%'
                         OR source LIKE 'dob_violations:%'
                         OR source LIKE 'hud:%' THEN 1 ELSE 0 END) AS empire_total
        FROM lane_leads
        WHERE metro IS NOT NULL AND metro != ''
          AND niche IS NOT NULL AND niche != ''
        GROUP BY metro, niche ORDER BY metro, total DESC
        """
        rows = con.execute(sql).fetchall()
        out = {}
        for r in rows:
            total = _safe_int(r["total"])
            empire = _safe_int(r["empire_total"])
            out.setdefault(r["metro"], {})[r["niche"]] = {
                "total_leads_30d": total,
                "empire_leads_30d": empire,
                "competing_leads_30d": max(0, total - empire),
                "our_supply_share_pct": round((empire / total) * 100, 1) if total else 0.0,
            }
        return {"data": out, "data_drift": False}
    finally:
        con.close()


def _buyer_competitors() -> list:
    """Active buyers per (metro, niche). Rank by touch_count for outreach
    intensity."""
    con = _db()
    try:
        bcols = _buyer_cols()
        if not {"metro", "niche", "business_name"}.issubset(bcols):
            return []
        rows = con.execute(f"""
            SELECT metro, niche, business_name,
                   COUNT(*) AS rows_n,
                   SUM(COALESCE(touch_count, 0)) AS touch_total
            FROM si_buyer_outreach
            WHERE metro IS NOT NULL AND metro != ''
              AND niche IS NOT NULL AND niche != ''
              AND business_name IS NOT NULL AND business_name != ''
              {("AND active = 1" if "active" in bcols else "")}
            GROUP BY metro, niche, business_name
            ORDER BY touch_total DESC
            LIMIT 100
        """).fetchall()
        result = []
        for r in rows:
            entry = {
                "metro": r["metro"],
                "niche": r["niche"],
                "competitor": r["business_name"][:60],
                "outreach_touches": _safe_int(r["touch_total"]),
                "rows_in_intake": _safe_int(r["rows_n"]),
            }
            # Cold start
            entry["engagement_state"] = (
                "active" if entry["outreach_touches"] >= 3 else "warming"
            )
            result.append(entry)
        return result
    finally:
        con.close()


def _buyer_intent_signals() -> list:
    """Detect buyers who are heating up vs cooling down.

    Heating = touched in last 72h but never delivered
    Cooling = last_touch_at > 14d ago, no recent delivery
    """
    con = _db()
    try:
        bcols = _buyer_cols()
        if not {"prospect_id", "last_touch_at"}.issubset(bcols):
            return []
        cutoff_heating = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
        cutoff_cooling = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        rows = con.execute(f"""
            SELECT business_name, email, niche, metro,
                   touch_count, last_touch_at, reply_state
            FROM si_buyer_outreach
            WHERE last_touch_at > ?
              {("AND business_name IS NOT NULL AND business_name != ''" if "business_name" in bcols else "")}
            ORDER BY last_touch_at DESC
            LIMIT 30
        """, (cutoff_heating,)).fetchall()
        heating = [{
            "business": r["business_name"][:50] if r["business_name"] else "",
            "email": r["email"][:60] if "email" in bcols and r["email"] else "",
            "niche": r["niche"] if "niche" in bcols else "",
            "metro": r["metro"] if "metro" in bcols else "",
            "touches": _safe_int(r["touch_count"]) if "touch_count" in bcols else 0,
        } for r in rows]

        # Cooling
        rows2 = con.execute(f"""
            SELECT business_name, email, niche, metro,
                   touch_count, last_touch_at
            FROM si_buyer_outreach
            WHERE last_touch_at < ?
              AND reply_state IN ('cold', 'no_reply', 'unsubscribed')
              {("AND business_name IS NOT NULL AND business_name != ''" if "business_name" in bcols else "")}
            ORDER BY last_touch_at ASC
            LIMIT 30
        """, (cutoff_cooling,)).fetchall()
        cooling = [{
            "business": r["business_name"][:50] if "business_name" in bcols and r["business_name"] else "",
            "email": r["email"][:60] if "email" in bcols and r["email"] else "",
            "niche": r["niche"] if "niche" in bcols else "",
            "metro": r["metro"] if "metro" in bcols else "",
            "last_touch_at": r["last_touch_at"],
        } for r in rows2]
        return {"heating": heating, "cooling": cooling}
    finally:
        con.close()


def _write_signal(snap: dict) -> None:
    """Emit a one-line actionable signal per day."""
    sig = {
        "ts": snap["ts"],
        "msg": snap.get("summary_msg", ""),
        "heating_buyers_n": len(snap.get("intent_signals", {}).get("heating", [])),
        "cooling_buyers_n": len(snap.get("intent_signals", {}).get("cooling", [])),
    }
    os.makedirs(FEED, exist_ok=True)
    with open(SIGNALS, "a") as f:
        f.write(json.dumps(sig) + "\n")


def main() -> dict:
    t0 = time.time()
    snap = {"ts": _now(), "schema_drift_safe": True}
    try:
        snap["pipeline"] = _pipeline_view()
        snap["pipeline_data"] = snap["pipeline"].get("data", {})
        snap["competitors"] = _buyer_competitors()
        snap["intent_signals"] = _buyer_intent_signals()
        # Aggregate top-level
        snap["top_competitors_by_outreach"] = snap["competitors"][:10]
        snap["n_competitors_seen"] = len({
            (r["metro"], r["niche"], r["competitor"]) for r in snap["competitors"]
        })
        snap["duration_ms"] = round((time.time() - t0) * 1000)
        snap["summary_msg"] = (
            f"tracked {snap['n_competitors_seen']} active competitors across "
            f"{len({r['metro'] for r in snap['competitors']})} metros; "
            f"{len(snap['intent_signals']['heating'])} heating buyers; "
            f"{len(snap['intent_signals']['cooling'])} going cold"
        )
    except Exception as e:
        log.exception("company_intel failed")
        snap["error"] = str(e)[:300]

    os.makedirs(FEED, exist_ok=True)
    if os.path.exists(JSONL) and os.path.getsize(JSONL) > MAX_JSONL_BYTES:
        try:
            os.rename(JSONL, JSONL + ".1")
        except OSError:
            pass
    with open(JSONL, "a") as f:
        f.write(json.dumps(snap, default=str) + "\n")
    with open(LATEST, "w") as f:
        json.dump(snap, f, indent=2, default=str)
    _write_signal(snap)

    print(json.dumps({
        "ts": snap["ts"],
        "duration_ms": snap.get("duration_ms", 0),
        "n_competitors_seen": snap.get("n_competitors_seen"),
        "heating_count": len(snap.get("intent_signals", {}).get("heating", [])),
        "cooling_count": len(snap.get("intent_signals", {}).get("cooling", [])),
        "summary": snap.get("summary_msg"),
    }, indent=2))
    return snap


if __name__ == "__main__":
    main()
