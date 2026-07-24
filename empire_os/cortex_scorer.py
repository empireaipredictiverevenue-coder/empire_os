#!/usr/bin/env python3
"""
Cortex Scorer — Empire OS v3 lead intelligence layer.

Two entrypoints used by the stack:
1. INTAKE: get_niche_score(niche, metro) -> int (50-95)
   Called by crawler_runner / lead sources BEFORE posting to /v1/leads/direct
   
2. POST-ENRICH: re_score_existing(limit=500) -> updated_count
   Called by cron (every 15m) to re-score leads already in si_buyer_outreach

Both read the same atomic cache written by cortex_engine.py:
  /run/cortex_niche_scores.json  {"ts": ..., "scores": {"roofing": 82, "hvac": 75, ...}}
"""

import json, os, sqlite3, time
from pathlib import Path
from typing import Dict, Optional, Tuple

DB = "/root/empire_os/empire_os.db"
CACHE = Path("/run/cortex_niche_scores.json")
CACHE.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_SCORE = 55

def _load_cache() -> Tuple[float, Dict[str, int]]:
    try:
        if CACHE.exists():
            data = json.loads(CACHE.read_text())
            return data.get("ts", 0), data.get("scores", {})
    except Exception:
        pass
    return 0, {}

_ts, _SCORES = _load_cache()

def get_niche_score(niche: str, metro: str = "") -> int:
    """
    Return Cortex-informed score for a niche (optionally metro-specific).
    Range: 50 (cold) .. 95 (hot). Used at INTAKE to boost lead_score.
    """
    global _ts, _SCORES
    # Refresh cache if older than 60s
    if time.time() - _ts > 60:
        _ts, _SCORES = _load_cache()
    
    n = (niche or "").lower().strip()
    key = f"{metro.lower()}:{n}" if metro else n
    return _SCORES.get(key, _SCORES.get(n, DEFAULT_SCORE))


def re_score_existing(limit: int = 500) -> int:
    """
    Post-enrichment: re-score leads already in si_buyer_outreach.
    Updates lead_score column with Cortex-informed score.
    Returns number of rows updated.
    """
    _ts, scores = _load_cache()
    if not scores:
        return 0
    
    updated = 0
    with sqlite3.connect(DB) as c:
        # Find leads that need re-scoring (score < 80 or older than 24h)
        rows = c.execute(
            "SELECT prospect_id, niche, metro, lead_score "
            "FROM si_buyer_outreach "
            "WHERE lead_score < 80 OR last_touch_at < datetime('now', '-1 day') "
            "ORDER BY lead_score ASC LIMIT ?",
            (limit,)
        ).fetchall()
        
        for pid, niche, metro, old_score in rows:
            new_score = scores.get(f"{metro.lower()}:{niche.lower()}", scores.get(niche.lower(), DEFAULT_SCORE))
            if new_score != old_score:
                c.execute(
                    "UPDATE si_buyer_outreach SET lead_score=?, last_touch_at=datetime('now') WHERE prospect_id=?",
                    (new_score, pid)
                )
                updated += 1
        if updated:
            c.commit()
    return updated


# ── CLI ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse, sys
    ap = argparse.ArgumentParser()
    ap.add_argument("--niche", help="Get score for niche")
    ap.add_argument("--metro", default="", help="Metro for niche")
    ap.add_argument("--rescore", type=int, help="Re-score existing leads (limit)")
    a = ap.parse_args()
    
    if a.niche:
        print(get_niche_score(a.niche, a.metro))
    elif a.rescore:
        n = re_score_existing(a.rescore)
        print(f"Re-scored {n} leads")
    else:
        # Dump cache
        print(json.dumps({"ts": _ts, "scores": _SCORES}, indent=2))
