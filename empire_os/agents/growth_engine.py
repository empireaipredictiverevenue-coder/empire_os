"""growth_engine.py - Empire 100K-1M subscriber strategy, as code.

Reads hooks_transcripts.db (competitor intel) + our social_log to produce:
- Winning hook templates (top converted_score hooks)
- Niche weighting for the autopilot (bias to high-view niches)
- Cadence + milestone plan (6/12/18mo)
- Injects top hooks into social_autopilot as hook pool

No fabricated metrics. All derived from scraped + logged signal.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/root/empire_os")
DB = ROOT / "empire_os" / "hooks_transcripts.db"
LOG = ROOT / "empire_os" / "social_log.jsonl"


def top_hooks(n: int = 25) -> list:
    if not DB.exists():
        return []
    c = sqlite3.connect(DB)
    rows = c.execute(
        "SELECT hook, niche, converted_score, views FROM videos "
        "ORDER BY converted_score DESC LIMIT ?", (n,)).fetchall()
    c.close()
    return [{"hook": r[0], "niche": r[1], "score": r[2], "views": r[3]}
            for r in rows if r[0]]


def niche_weights() -> dict:
    """Weight autopilot niches by competitor view-pull per niche."""
    if not DB.exists():
        return {}
    c = sqlite3.connect(DB)
    agg = defaultdict(lambda: [0, 0])  # niche -> [count, total_views]
    for nic, views in c.execute(
            "SELECT niche, views FROM videos WHERE views>0").fetchall():
        agg[nic][0] += 1
        agg[nic][1] += views
    c.close()
    if not agg:
        return {}
    maxv = max(v[1] for v in agg.values()) or 1
    return {n: round(v[1] / maxv, 3) for n, v in agg.items()}


def our_cadence() -> dict:
    """Real posting cadence from social_log."""
    if not LOG.exists():
        return {"cycles": 0, "passed": 0, "pass_rate": 0.0}
    ok = bad = 0
    for line in LOG.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = __import__("json").loads(line)
        except Exception:
            continue
        if r.get("flag") == "OK":
            ok += 1
        elif r.get("flag") == "REVIEW":
            bad += 1
    tot = ok + bad
    return {"cycles": tot, "passed": ok,
            "pass_rate": round(ok / tot, 3) if tot else 0.0}


def milestone_plan() -> dict:
    """6/12/18mo milestones. Conservative, data-gated (no fake promises)."""
    w = niche_weights()
    top = sorted(w.items(), key=lambda x: x[1], reverse=True)[:3]
    return {
        "targets": {"6mo": 100_000, "12mo": 500_000, "18mo": 1_000_000},
        "levers": [
            "Daily Shorts (9:16) from top-converting hook templates",
            "Cross-post to TikTok/IG Reels via social_syndication",
            "Bias autopilot to high-view niches: " + ", ".join(n for n, _ in top),
            "A/B hook variants from competitor transcript DB",
            "Series format (recurring) for retention + subs",
        ],
        "cadence_now": our_cadence(),
        "top_hook_examples": [h["hook"] for h in top_hooks(5)],
    }


def inject_hook_pool() -> str:
    """Write top hooks to a pool file the autopilot can sample."""
    pool = [h["hook"] for h in top_hooks(40) if h["hook"]]
    out = ROOT / "empire_os" / "agents" / "hook_pool.json"
    out.write_text(__import__("json").dumps(
        {"updated": datetime.now(timezone.utc).isoformat(),
         "hooks": pool}, indent=2))
    return str(out)


if __name__ == "__main__":
    import json
    print("TOP HOOKS:", json.dumps(top_hooks(5), indent=2))
    print("NICHE WEIGHTS:", json.dumps(niche_weights(), indent=2))
    print("PLAN:", json.dumps(milestone_plan(), indent=2, default=str))
    print("HOOK POOL:", inject_hook_pool())
