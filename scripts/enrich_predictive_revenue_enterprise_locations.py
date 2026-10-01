from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

from empire_os.predictive_revenue_enterprise_location import enrich_candidate_location
from empire_os.search_fabric.site_probe import probe_site

POOL = Path("runtime/predictive_revenue/enterprise_pool_latest.json")
OUT = Path("runtime/predictive_revenue/enterprise_location_enrichment_latest.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    root = Path(args.repo_root)
    pool = json.loads((root / POOL).read_text(encoding="utf-8"))
    candidates = list(pool.get("rolling_candidates") or [])

    results: dict[str, dict] = {}
    workers = max(1, min(args.workers, 8))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(
                probe_site,
                str(row.get("website") or ""),
                max_pages=5,
                request_timeout=4.0,
                time_budget_seconds=14.0,
                page_priority="people",
                public_only=True,
            ): row
            for row in candidates
        }
        for future in as_completed(future_map):
            row = future_map[future]
            try:
                evidence = future.result()
            except Exception as exc:
                evidence = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
            results[str(row.get("candidate_id") or row.get("domain"))] = (
                enrich_candidate_location(row, evidence)
            )

    rows = [
        results[str(row.get("candidate_id") or row.get("domain"))]
        for row in candidates
    ]
    payload = {
        "schema_version": "empire.predictive-revenue-enterprise-location.v1",
        "mode": "OBSERVE",
        "candidate_count": len(rows),
        "location_verified_count": sum(r["location_verified"] for r in rows),
        "location_blocked_count": sum(not r["location_verified"] for r in rows),
        "candidates": rows,
        "outreach_authorized": False,
        "payment_action": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
    out = root / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(out)
    print(json.dumps({
        "candidate_count": payload["candidate_count"],
        "location_verified_count": payload["location_verified_count"],
        "location_blocked_count": payload["location_blocked_count"],
        "outreach_authorized": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
