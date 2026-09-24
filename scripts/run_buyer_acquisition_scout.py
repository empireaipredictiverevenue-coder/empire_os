#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import urllib.parse

from empire_os.buyer_acquisition_scout import refresh_buyer_scout
from empire_os.qualification_worker_v2 import request_json


SEED_LANES = (
    (
        "high_ticket_home_service",
        (
            "plumbing",
            "general_contractor",
            "roofing",
            "residential_roofing",
            "roof_repair",
            "restoration",
            "water_damage_restoration",
            "hvac",
            "solar",
        ),
    ),
    (
        "legal_mass_tort_plaintiff_firm",
        (
            "mass tort lawyer",
            "mass_tort",
            "class action lawyer",
        ),
    ),
    (
        "legal_plaintiff_growth_firm",
        (
            "personal injury lawyer",
            "medical malpractice lawyer",
            "workers comp lawyer",
        ),
    ),
    (
        "insurance_distribution_growth",
        (
            "auto insurance",
            "life insurance agent",
            "public insurance adjuster",
            "final expense insurance",
            "medicare advantage agent",
        ),
    ),
)


def _canonical_seed_records(
    *,
    per_lane: int = 8,
) -> list[dict]:
    per_lane = max(1, min(int(per_lane), 20))
    half_hour_slot = int(
        datetime.now(timezone.utc).timestamp() // 1800
    )
    rows: list[dict] = []

    for lane_index, (profile_key, niches) in enumerate(SEED_LANES):
        offset = ((half_hour_slot + lane_index * 7) % 20) * per_lane
        niche_filter = ",".join(
            '"' + niche.replace('"', '\\"') + '"'
            for niche in niches
        )
        params = urllib.parse.urlencode({
            "select": (
                "id,business_name,niche,website,metro,status,created_at"
            ),
            "niche": f"in.({niche_filter})",
            "website": "not.is.null",
            "order": "created_at.desc",
            "limit": str(per_lane),
            "offset": str(offset),
        })
        try:
            batch = request_json(
                "GET",
                f"/rest/v1/prospects?{params}",
            ) or []
        except Exception:
            batch = []

        for raw in batch:
            if not isinstance(raw, dict):
                continue
            website = str(raw.get("website") or "").strip()
            business_name = str(
                raw.get("business_name") or ""
            ).strip()
            if not website or not business_name:
                continue
            row = dict(raw)
            row["icp_profile_key"] = profile_key
            rows.append(row)

    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--max-queries", type=int, default=20)
    parser.add_argument("--results-per-query", type=int, default=8)
    parser.add_argument("--max-domains", type=int, default=40)
    parser.add_argument("--max-probes", type=int, default=20)
    args = parser.parse_args()

    payload = refresh_buyer_scout(
        args.repo_root,
        max_queries=args.max_queries,
        results_per_query=args.results_per_query,
        max_domains=args.max_domains,
        max_probes=args.max_probes,
        canonical_seed_records=_canonical_seed_records(
            per_lane=8,
        ),
    )
    print(json.dumps({
        "ok": True,
        "query_count": payload["query_count"],
        "domain_count": payload["domain_count"],
        "search_domain_count": payload["search_domain_count"],
        "canonical_seed_domain_count": payload[
            "canonical_seed_domain_count"
        ],
        "canonical_seed_fallback_used": payload[
            "canonical_seed_fallback_used"
        ],
        "candidate_count": payload["candidate_count"],
        "predictive_revenue_enterprise_candidate_count": payload[
            "predictive_revenue_enterprise_candidate_count"
        ],
        "continuous_lane_candidate_counts": payload[
            "continuous_lane_candidate_counts"
        ],
        "explicit_direct_buyer_candidate_count": payload[
            "explicit_direct_buyer_candidate_count"
        ],
        "database_write_performed": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
