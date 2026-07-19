#!/usr/bin/env python3
"""
predictive_router.py — PREDICTIVE TREND ROUTER (real).

Reads last30days artifacts (real market signal from Reddit/HN/Polymarket/
GitHub/Jobs) and detects HOT niches/keywords by engagement velocity. Hot
targets are written to the `hot_targets` table, which the strategy loop
(strategy_rank / rent / rolling_stones) consumes to prioritize which leads
to route + which articles to spin next.

This is the REAL version of the blueprint's predictive_router.py — it talks to
our live SQLite + last30days artifacts, NOT a fictional
hub.predictivecloud.empire endpoint.

Velocity model: each artifact's per-source candidates carry engagement
(points/comments). We sum engagement per topic, normalize, and flag topics
above the adaptive threshold as HOT.
"""
import os, sys, json, time, glob, sqlite3, logging
sys.path.insert(0, os.path.dirname(__file__))

log = logging.getLogger("predictive_router")
FEED = "/root/feedback"
DB = os.getenv("EMPIRE_DB", "/root/empire_os/empire_os.db")
VELOCITY_THRESHOLD = float(os.getenv("VELOCITY_THRESHOLD", "50"))


def _db():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS hot_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT, niche TEXT, velocity REAL,
        source TEXT, ts REAL, routed INTEGER DEFAULT 0)""")
    return c


def _engagement_of(item: dict) -> int:
    eng = item.get("engagement", {})
    if isinstance(eng, dict):
        # real last30days engine schema
        return int(eng.get("score", 0) or 0) + int(eng.get("num_comments", 0) or 0)
    return int(eng or 0)


def scan_artifacts() -> list:
    """Return list of hot-target dicts from all last30days artifacts."""
    hots = []
    for f in glob.glob(f"{FEED}/last30days_*.jsonl"):
        if "runs" in f:
            pass
        try:
            with open(f) as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    data = r.get("data") or {}
                    topic = r.get("topic", "")
                    if not isinstance(data, dict):
                        continue
                    # real engine shape: candidates under "results" (list)
                    candidates = data.get("results") or []
                    if not isinstance(candidates, list):
                        candidates = []
                    # also accept legacy per-source lists
                    if not candidates:
                        for src, rows in data.items():
                            if isinstance(rows, list):
                                candidates.extend(rows)
                    total_eng = 0
                    for it in candidates:
                        if not isinstance(it, dict):
                            continue
                        total_eng += _engagement_of(it)
                        if _engagement_of(it) >= VELOCITY_THRESHOLD:
                            hots.append({
                                "keyword": it.get("title", topic)[:120],
                                "niche": topic,
                                "velocity": float(_engagement_of(it)),
                                "source": it.get("source", "unknown"),
                                "ts": r.get("ts", time.time()),
                            })
                    if total_eng >= VELOCITY_THRESHOLD * 2:
                        hots.append({
                            "keyword": topic, "niche": topic,
                            "velocity": float(total_eng), "source": "aggregate",
                            "ts": r.get("ts", time.time()),
                        })
        except Exception:
            continue
    return hots


def run(dry_run: bool = False) -> dict:
    hots = scan_artifacts()
    # de-dup by keyword, keep highest velocity
    seen = {}
    for h in hots:
        k = h["keyword"]
        if k not in seen or h["velocity"] > seen[k]["velocity"]:
            seen[k] = h
    hots = sorted(seen.values(), key=lambda x: -x["velocity"])
    if not dry_run:
        c = _db()
        for h in hots:
            c.execute(
                "INSERT INTO hot_targets (keyword,niche,velocity,source,ts) "
                "VALUES (?,?,?,?,?)",
                (h["keyword"], h["niche"], h["velocity"], h["source"], h["ts"]))
        c.commit()
    return {"hot_count": len(hots), "top": hots[:5]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    print(json.dumps(run(dry_run=a.dry), indent=2))
