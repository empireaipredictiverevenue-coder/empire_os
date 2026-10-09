#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
import json
import urllib.parse

from empire_os.buyer_acquisition_scout import refresh_buyer_scout
from empire_os.buyer_public_research_seed import (
    refresh_public_research_seeds,
)
from empire_os.official_license_market_seed import (
    refresh_official_license_market_seeds,
)
from empire_os.intent_seed_bridge import load_intent_seed_records
from empire_os.verified_identity_seed_bridge import load_verified_identity_seed_records
from empire_os.sb import request_json
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
        demand_critical_permit_lane = (
            profile_key == "high_ticket_home_service"
        )
        offset = (
            0
            if demand_critical_permit_lane
            else ((half_hour_slot + lane_index * 7) % 20) * per_lane
        )
        niche_filter = ",".join(
            '"' + niche.replace('"', '\\"') + '"'
            for niche in niches
        )
        query_params = {
            "select": (
                "id,business_name,niche,website,metro,status,created_at"
            ),
            "niche": f"in.({niche_filter})",
            "website": "not.is.null",
            "order": "created_at.desc",
            "limit": str(per_lane),
            "offset": str(offset),
        }
        if demand_critical_permit_lane:
            query_params["metro"] = "ilike.NYC"

        params = urllib.parse.urlencode(query_params)
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
            if demand_critical_permit_lane:
                row["seed_buyer_pools"] = [
                    "end_service_buyers",
                    "local_and_smb_buyers",
                ]
                row["seed_product_code"] = "permit_intelligence"
                row["seed_corridor_key"] = (
                    "permit-recovery:v1:"
                    + str(row.get("niche") or "home_services")
                    .strip()
                    .lower()
                    .replace(" ", "_")
                    + ":nyc"
                )
            rows.append(row)

    return rows


def research_network_after_scout(
    repo_root: str,
    *,
    runner=None,
) -> dict:
    """Piggyback on the EXISTING 30-min buyer scout, without new timers.

    A failure of an optional read-only research refresh never blocks buyer
    acquisition. It is still independently visible in the evidence JSON.
    """
    root = Path(repo_root).resolve()
    lock_path = root / "runtime/buyer_network_intelligence/research_cycle.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    runner = runner or subprocess.run
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "ALREADY_RUNNING", "mode": "OBSERVE"}
        env = os.environ.copy()
        env.update({
            "EMPIRE_MODE": "OBSERVE",
            "EMPIRE_EXECUTION_AUTHORITY": "OBSERVE",
            "OUTBOUND_ENABLED": "0",
            "EMPIRE_OUTBOUND_ENABLED": "0",
            "LIVE_OUTBOUND": "0",
        })
        # These are independent read-only stages. If the existing buyer
        # due-diligence pipeline hits a concurrent snapshot change, preserve
        # that failure but still reconcile the last consistent Gmail/CRM view.
        try:
            proc = runner(
                [
                    sys.executable,
                    str(root / "scripts/run_buyer_network_evidence_cycle.py"),
                ],
                cwd=root, env=env, capture_output=True,
                text=True, timeout=300, check=False,
            )
            research_code = proc.returncode
        except subprocess.TimeoutExpired:
            research_code = 124
        try:
            linked = runner(
                [
                    sys.executable,
                    str(root / "scripts/reconcile_buyer_email_relationships.py"),
                    "--write",
                ],
                cwd=root, env=env, capture_output=True,
                text=True, timeout=35, check=False,
            )
            registry_code = linked.returncode
        except subprocess.TimeoutExpired:
            registry_code = 124
        successes = int(research_code == 0) + int(registry_code == 0)
        return {
            "status": ("PASS" if successes == 2 else
                       "PARTIAL" if successes == 1 else "FAILED"),
            "mode": "OBSERVE",
            "exit_code": research_code,
            "buyer_network_research": (
                "PASS" if research_code == 0 else
                "TIMEOUT" if research_code == 124 else "FAILED"
            ),
            "relationship_registry": (
                "PASS" if registry_code == 0 else
                "TIMEOUT" if registry_code == 124 else "BLOCKED"
            ),
            "mailbox_ingest_in_this_cycle": False,
            "outbound_sent": False,
            "execution_authority": "NONE",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--max-queries", type=int, default=20)
    parser.add_argument("--results-per-query", type=int, default=8)
    parser.add_argument("--max-domains", type=int, default=40)
    parser.add_argument("--max-probes", type=int, default=20)
    parser.add_argument("--low-yield-canonical-limit", type=int, default=3,
                        help="Allow up to 3 canonical research seeds when public search yields 1-2 domains")
    parser.add_argument("--intent-seed-limit", type=int, default=12)
    parser.add_argument("--skip-buyer-network-research", action="store_true")
    args = parser.parse_args()

    public_research = refresh_public_research_seeds(
        args.repo_root,
        max_queries=min(args.max_queries, 48),
        results_per_query=min(args.results_per_query, 10),
    )

    official_license_research = refresh_official_license_market_seeds(
        args.repo_root,
        max_queries=max(8, min(args.max_queries // 5, 20)),
        results_per_query=min(args.results_per_query, 4),
    )
    research_seeds = [
        *(public_research.get("seeds") or []),
        *(official_license_research.get("seeds") or []),
    ]

    seed_records = _canonical_seed_records(per_lane=8)
    intent_seeds = load_intent_seed_records(
        args.repo_root,
        limit=args.intent_seed_limit,
    )
    seed_records.extend(intent_seeds)

    verified_identity_seeds = (
        load_verified_identity_seed_records(
            args.repo_root,
            limit=12,
        )
    )
    seed_records.extend(
        verified_identity_seeds
    )

    payload = refresh_buyer_scout(
        args.repo_root,
        max_queries=args.max_queries,
        results_per_query=args.results_per_query,
        max_domains=args.max_domains,
        max_probes=args.max_probes,
        canonical_seed_records=seed_records,
        research_seed_records=research_seeds,
        low_yield_canonical_limit=args.low_yield_canonical_limit,
    )
    research_status = (
        {"status": "SKIPPED", "mode": "OBSERVE"}
        if args.skip_buyer_network_research
        else research_network_after_scout(args.repo_root)
    )
    print(json.dumps({
        "ok": True,
        "buyer_network_research": research_status,
        "query_count": payload["query_count"],
        "domain_count": payload["domain_count"],
        "search_domain_count": payload["search_domain_count"],
        "canonical_seed_domain_count": payload[
            "canonical_seed_domain_count"
        ],
        "canonical_seed_fallback_used": payload[
            "canonical_seed_fallback_used"
        ],
        "low_yield_canonical_supplement_count": payload[
            "low_yield_canonical_supplement_count"
        ],
        "intent_seed_input_count": len(intent_seeds),
        "verified_identity_seed_input_count": len(
            verified_identity_seeds
        ),
        "intent_seed_domain_count": payload[
            "intent_seed_domain_count"
        ],
        "intent_seed_supplement_used": payload[
            "intent_seed_supplement_used"
        ],
        "candidate_count": payload["candidate_count"],
        "official_license_query_count": official_license_research[
            "query_count"
        ],
        "official_license_seed_count": official_license_research[
            "seed_count"
        ],
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
