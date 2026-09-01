"""
free_traffic_analytics.py — Empire OS free-traffic analytics dashboard.

Pulls live AEO/organic performance from the hub and prints a report:
  - per-niche impressions / clicks / conversions (via /v1/aeo/conversions)
  - traffic SOURCE breakdown (via aeo_events.ref_code = referrer/source)
  - indexed page count (via /v1/aeo/pages)

The aeo_events table lives INSIDE the empire-hub container (separate SQLite),
so the source breakdown is read via `incus exec empire-hub`.

Run:
  python3 free_traffic_analytics.py [--days 30] [--json]
Serve (optional): the same data is available at /v1/aeo/conversions on the hub.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, urllib.request
from datetime import datetime, timezone

HUB = "https://empire-ai.co.uk"
HUB_CT = "empire-hub"
DB_IN_CT = "/root/empire_os/empire_os.db"   # path inside empire-hub container


def _ct_db(sql: str):
    """Run SQL against the hub container's SQLite DB (analytics lives there)."""
    out = subprocess.run(
        ["incus", "exec", HUB_CT, "--", "sqlite3", "-json", DB_IN_CT, sql],
        capture_output=True, text=True, timeout=30,
    )
    if out.returncode != 0:
        return []
    try:
        return json.loads(out.stdout or "[]")
    except json.JSONDecodeError:
        return []


def conversions(days: int) -> dict:
    rows = _ct_db(
        "SELECT niche, event_type, COUNT(*) AS count FROM aeo_events "
        f"WHERE ts >= datetime('now', '-{days} days') "
        "GROUP BY niche, event_type;"
    )
    by_niche = {}
    for r in rows:
        by_niche.setdefault(r["niche"], {})[r["event_type"]] = {"count": r["count"]}
    return {"days": days, "by_niche": by_niche}


def pages() -> dict:
    # pages are served from /srv/aeo filesystem, not the aeo_pages table
    out = subprocess.run(
        ["incus", "exec", HUB_CT, "--", "bash", "-c",
         "ls -d /srv/aeo/*/ 2>/dev/null | wc -l"],
        capture_output=True, text=True, timeout=20,
    )
    try:
        return {"count": int(out.stdout.strip() or 0)}
    except ValueError:
        return {"count": 0}


def source_breakdown(days: int) -> dict:
    rows = _ct_db(
        "SELECT COALESCE(NULLIF(ref_code,''),'direct') AS source, "
        "event_type, COUNT(*) AS count FROM aeo_events "
        f"WHERE ts >= datetime('now', '-{days} days') "
        "GROUP BY source, event_type ORDER BY count DESC;"
    )
    return {"rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    conv = conversions(a.days)
    pg = pages()
    src = source_breakdown(a.days)

    if a.json:
        print(json.dumps({"conversions": conv, "pages": pg, "sources": src}, indent=2))
        return

    print(f"\n=== EMPIRE FREE TRAFFIC ANALYTICS ({a.days}d) @ "
          f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}Z ===\n")

    # per-niche
    print("PER-NICHE (impressions / clicks / conversions):")
    bn = conv.get("by_niche", {})
    for niche, evs in sorted(bn.items(), key=lambda kv: -sum(
            v.get("count", 0) for v in kv[1].values())):
        parts = {k: v.get("count", 0) for k, v in evs.items()}
        imp = parts.get("impression", 0)
        clk = parts.get("click", 0)
        conv_n = parts.get("conversion", 0)
        print(f"  {niche:22} imp={imp:4}  clk={clk:3}  conv={conv_n:3}")

    # source
    print("\nTRAFFIC SOURCE (referrer / channel):")
    for r in src.get("rows", []):
        print(f"  {r['source']:24} {r['event_type']:12} {r['count']:4}")

    # indexed pages
    n_pages = pg.get("count", 0)
    print(f"\nIndexed AEO pages served: {n_pages}")
    tot_imp = sum(v.get("impression", {}).get("count", 0)
                  for v in bn.values())
    print(f"Total impressions ({(a.days)}d): {tot_imp}")


if __name__ == "__main__":
    main()
