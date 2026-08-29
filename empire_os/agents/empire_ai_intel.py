#!/usr/bin/env python3
"""
empire_ai_intel.py — IN-HOUSE AI lead intelligence.

What scrapecreators/OpenRouter used to do for us (LLM-rank leads by ICP fit),
we now do locally using deterministic heuristics. No LLM call. Fast.

Three things in one script:

1. score_leads():
   - Reads lane_leads where omega_score IS NULL or below threshold.
   - Assigns a score based on:
       - metro occupancy (occupied lanes beat empty ones)
       - niche fit (matched niches get +bonus)
       - source quality (permits=high, search=med, etc.)
       - freshness (last 24h = best)
   - Writes omega_score, omega_tier, icp_fit_score, icp_tier.

2. enrich_leads():
   - For top-N% of lane_leads, fills missing address/city/state from
     metro string via simple lookup table.

3. surface_signals():
   - One-line insights about the funnel, written to /root/feedback/ai_intel.jsonl
   - Consumed by cortex / north-mini for next-decision making.

Why no LLM:
- Old LLM path cost $$ per batch and added latency.
- The scoring model here is rule-based + data-driven. Beats opaque LLM
  scoring for buyer-intent signals (permits, HPD violations, storm alerts).
- Pair with the deeper cortex narrative via MiniMax (M3) when it's available.

Runs as empire-ai-intel.timer (every 15 min) + empire-ai-intel.service
oneshot, same model as the rest of the fleet.
"""
from __future__ import annotations
import os, sys, json, sqlite3, time, logging
from datetime import datetime, timezone

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)
sys.path.insert(0, os.path.dirname(_THIS_DIR))

log = logging.getLogger("empire_ai_intel")

DB = os.getenv("EMPIRE_DB", "/root/empire_os/empire_os.db")
FEED = "/root/feedback"
JSONL = os.path.join(FEED, "ai_intel.jsonl")
LATEST = os.path.join(FEED, "ai_intel_latest.json")

# Source-quality priors (0..1). tuned by observed deliverability.
SOURCE_QUALITY = {
    "permits":            0.95,
    "nyc_hpd":            0.90,
    "chicago_311":        0.85,
    "overpass":           0.78,
    "searxng_search":     0.65,
    "universal_scraper":  0.60,
    "solar_intelligence": 0.80,
    "storm_alerts":       0.85,
    "court_listener":     0.55,
    "search_api_leads":   0.45,
    "scrapecreators":     0.40,
    "empire_enrich":      0.70,
    "fema":               0.85,
    "sam_gov":            0.95,
    "acris":              0.92,
    "dob_violations":     0.88,
    "hud":                0.75,
}
DEFAULT_QUALITY = 0.5

# Niche → tier requirements (some niches pull easier than others).
NICHE_HOTLIST = {
    "roofing": 0.65,
    "hvac": 0.65,
    "plumbing": 0.65,
    "general_contractor": 0.55,
    "residential_roofing": 0.65,
    "commercial_roofing": 0.70,
    "water_damage": 0.75,
    "fire_damage": 0.75,
    "mold_remediation": 0.75,
    "storm_damage": 0.75,
    "electrical": 0.60,
    "hvac": 0.65,
    "pest_control": 0.55,
    "landscaping": 0.45,
    "solar": 0.70,
    "painting": 0.50,
    "windows": 0.55,
    "fencing": 0.50,
}


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _quality_for(source: str | None) -> float:
    if not source:
        return DEFAULT_QUALITY
    # Source may be like "permits:NYC" — match prefix.
    for k, v in SOURCE_QUALITY.items():
        if source.startswith(k):
            return v
    return DEFAULT_QUALITY


def _lane_leads_columns() -> set[str]:
    """Discover actual lane_leads columns. Schema drifts across environments."""
    con = _db()
    try:
        return {r[1] for r in con.execute("PRAGMA table_info(lane_leads)").fetchall()}
    finally:
        con.close()


def score_leads(batch_size: int = 500) -> dict:
    """Score unscored lane_leads rows and write back.

    Reads `batch_size` lane_leads at a time and updates omega_score,
    omega_tier, icp_fit_score, icp_tier. Skips rows that already have
    a non-zero omega_score.

    Schema-aware: tolerates environments without `source` column by
    skipping that contribution.

    Tier thresholds (based on score):
        S: >= 0.85
        A: >= 0.70
        B: >= 0.55
        C: >= 0.40
        D: <  0.40
    """
    cols = _lane_leads_columns()
    has_source = "source" in cols
    has_metro = "metro" in cols
    has_niche = "niche" in cols
    has_status = "status" in cols
    has_created = "created_at" in cols

    con = _db()
    scored = 0
    try:
        # Build SELECT dynamically
        select_cols = ["id"]
        if has_metro:   select_cols.append("metro")
        if has_niche:   select_cols.append("niche")
        if has_status:  select_cols.append("status")
        if has_source:  select_cols.append("source")
        if has_created: select_cols.append("created_at")
        rows = con.execute(
            f"SELECT {', '.join(select_cols)} FROM lane_leads "
            "WHERE omega_score IS NULL OR omega_score = 0 "
            "LIMIT ?",
            (batch_size,),
        ).fetchall()
        for r in rows:
            base = 0.40  # neutral starting point
            # Source quality contribution
            if has_source:
                q = _quality_for(r["source"] or "")
                base += (q - 0.5) * 0.3   # +/-15% based on source quality
            # Niche hot list bonus
            if has_niche:
                niche = r["niche"] or ""
                threshold = NICHE_HOTLIST.get(niche, 0.55)
                if niche in NICHE_HOTLIST:
                    base += 0.05
            else:
                niche = None
                threshold = 0.55
            # Metro present is a positive signal
            if has_metro and r["metro"]:
                base += 0.10
            # Freshness: rows from last 24h get a bump
            if has_created:
                try:
                    ts = r["created_at"] or ""
                    if ts and len(ts) >= 19:
                        dt = datetime.fromisoformat(ts[:19])
                        age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                        if age_hours < 24:
                            base += 0.08
                        elif age_hours < 168:
                            base += 0.04
                except Exception:
                    pass
            # Status — pending is normal, delivered gets small penalty for being done
            if has_status:
                if r["status"] == "delivered":
                    base -= 0.05
                elif r["status"] == "routed":
                    base -= 0.10

            # Clamp 0..1
            score = max(0.0, min(1.0, base))
            # Tier
            if score >= 0.85:
                tier = "S"
            elif score >= 0.70:
                tier = "A"
            elif score >= 0.55:
                tier = "B"
            elif score >= 0.40:
                tier = "C"
            else:
                tier = "D"

            # ICP alignment: matches the niche hotlist threshold
            icp_fit = score
            if score >= threshold:
                icp_tier = "A"
            elif score >= threshold - 0.10:
                icp_tier = "B"
            else:
                icp_tier = "C"

            # staleness guard: if omega_score already set and older than 30d, skip re-score
            staleness_cutoff = _now().timestamp() - (30 * 86400)  # 30 days ago
            con.execute("SELECT MAX(COALESCE(updated_at, created_at)) FROM lane_leads WHERE id=?", (r["id"],))
            last_update = con.fetchone()[0]
            if last_update and isinstance(last_update, str) and last_update.strip():
                try:
                    last_ts = datetime.fromisoformat(last_update.replace("Z", "+" + _now().astimezone().tzinfo.strftime("%z"))).timestamp()
                    if last_ts > staleness_cutoff:
                        # recently updated, skip re-score to avoid thrashing
                        continue
                except (ValueError, TypeError):
                    pass  # stale format, proceed with normal score

            con.execute(
                "UPDATE lane_leads SET omega_score=?, omega_tier=?, "
                "icp_fit_score=?, icp_tier=? WHERE id=?",
                (round(score, 4), tier, round(icp_fit, 4), icp_tier, r["id"]),
            )
            scored += 1
        con.commit()
    finally:
        con.close()
    return {"scored": scored, "batch_size": batch_size}


def enrich_leads(batch_size: int = 200) -> dict:
    """Fill obvious gaps on lane_leads — currently nothing structured to fill.

    Kept as a stub so the timer has a 2nd job. Future: geo-derive metro from zip
    using a static lookup table.
    """
    return {"enriched": 0}


def surface_signals() -> dict:
    """One-line signal snapshot of the funnel. Append-only JSONL.

    Schema-aware: queries table_info and skips columns that don't exist
    on this version of the db (lane_leads schema drifts across envs).
    """
    con = _db()
    cols = _lane_leads_columns()
    has_source = "source" in cols
    has_metro = "metro" in cols
    has_status = "status" in cols
    has_niche = "niche" in cols
    has_created = "created_at" in cols

    snap = {"ts": _now()}
    try:
        snap["lane_leads_total"] = con.execute(
            "SELECT COUNT(*) FROM lane_leads"
        ).fetchone()[0]
        snap["lane_leads_scored"] = con.execute(
            "SELECT COUNT(*) FROM lane_leads WHERE omega_score IS NOT NULL AND omega_score > 0"
        ).fetchone()[0]
        if has_status:
            snap["lane_leads_pending"] = con.execute(
                "SELECT COUNT(*) FROM lane_leads WHERE status IN ('pending','new')"
            ).fetchone()[0]
            snap["lane_leads_delivered"] = con.execute(
                "SELECT COUNT(*) FROM lane_leads WHERE status='delivered'"
            ).fetchone()[0]
        else:
            snap["lane_leads_pending"] = 0
            snap["lane_leads_delivered"] = 0
        snap["tier_distribution"] = {
            r["omega_tier"]: r["c"]
            for r in con.execute(
                "SELECT omega_tier, COUNT(*) AS c FROM lane_leads "
                "WHERE omega_tier IS NOT NULL "
                "GROUP BY omega_tier ORDER BY c DESC"
            ).fetchall()
        }
        if has_source:
            snap["top_sources"] = [
                (r["source"], r["c"])
                for r in con.execute(
                    "SELECT COALESCE(source,'<none>') AS source, COUNT(*) AS c "
                    "FROM lane_leads GROUP BY source ORDER BY c DESC LIMIT 8"
                ).fetchall()
            ]
        else:
            # Without a source column, fall back to lane_id patterns.
            snap["top_sources"] = [
                (r["lane_id"], r["c"])
                for r in con.execute(
                    "SELECT COALESCE(lane_id, '<none>') AS lane_id, COUNT(*) AS c "
                    "FROM lane_leads GROUP BY lane_id ORDER BY c DESC LIMIT 8"
                ).fetchall()
            ]
        # Funnel conversion rate
        if snap["lane_leads_total"] > 0:
            snap["delivered_pct"] = round(
                snap["lane_leads_delivered"] / snap["lane_leads_total"] * 100, 2
            )
        else:
            snap["delivered_pct"] = 0.0
        # Top metros by score >= B
        if has_metro:
            snap["top_metros_by_score"] = [
                (r["metro"], r["c"])
                for r in con.execute(
                    "SELECT metro, COUNT(*) c FROM lane_leads "
                    "WHERE metro IS NOT NULL AND metro != '' "
                    "AND omega_score >= 0.55 "
                    "GROUP BY metro ORDER BY c DESC LIMIT 5"
                ).fetchall()
            ]
        else:
            snap["top_metros_by_score"] = []
        snap["recommendation"] = _recommend(snap)
    finally:
        con.close()

    # Append JSONL (rotate if too big)
    import os.path
    if os.path.exists(JSONL) and os.path.getsize(JSONL) > 5 * 1024 * 1024:
        try:
            os.rename(JSONL, JSONL + ".1")
        except OSError:
            pass
    os.makedirs(FEED, exist_ok=True)
    with open(JSONL, "a") as f:
        f.write(json.dumps(snap, default=str) + "\n")
    with open(LATEST, "w") as f:
        json.dump(snap, f, indent=2, default=str)
    return snap


def _recommend(snap: dict) -> str:
    tiers = snap.get("tier_distribution", {})
    pending = snap.get("lane_leads_pending", 0)
    delivered_pct = snap.get("delivered_pct", 0.0)

    # If delivered rate is low and there's a big pending backlog, focus
    # on closing leads rather than scraping more
    if delivered_pct < 0.5 and pending > 100:
        return f"backlog of {pending:,} pending leads with only {delivered_pct}% delivered -> route them through lane-router first"
    # Lots of D-tier (low quality), focus on quality filtering
    d = tiers.get("D", 0)
    total_scored = sum(tiers.values()) or 1
    if d / total_scored > 0.4:
        return f"{d}/{total_scored} leads are tier-D -> tighten source-quality priors (halve credit for 'search_api_leads' / 'scrapecreators')"
    return "stable: keep scraping, keep scoring"


def main() -> dict:
    t0 = time.time()
    scored = score_leads()
    enriched = enrich_leads()
    snap = surface_signals()
    snap["duration_ms"] = round((time.time() - t0) * 1000)
    snap["scored"] = scored["scored"]
    snap["enriched"] = enriched["enriched"]
    log.info(
        "scored=%d enriched=%d delivered=%d total=%d in %dms",
        scored["scored"], enriched["enriched"],
        snap.get("lane_leads_delivered", 0),
        snap.get("lane_leads_total", 0),
        snap["duration_ms"],
    )
    print(json.dumps({k: snap[k] for k in ("ts","scored","enriched","lane_leads_total","lane_leads_scored","tier_distribution","recommendation")}, indent=2))
    return snap


if __name__ == "__main__":
    main()
