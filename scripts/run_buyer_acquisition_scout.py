#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
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


HOME_SERVICE_NICHES = {
    "plumbing",
    "general_contractor",
    "roofing",
    "residential_roofing",
    "roof_repair",
    "restoration",
    "water_damage_restoration",
    "hvac",
    "solar",
}


def _load_buyer_plan(repo_root: str) -> dict:
    try:
        value = json.loads(
            (
                Path(repo_root)
                / "runtime/buyer_acquisition/latest.json"
            ).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _opportunity_validation_seed_records(
    plan: dict,
    *,
    per_target: int = 6,
    request=request_json,
    diagnostics: list[dict] | None = None,
) -> list[dict]:
    """Recover real canonical prospects for opportunity validation fallback.

    This path is used only when public Search Fabric yields no domains. Rows
    remain research candidates and are re-probed against their first-party
    websites by Buyer Scout before surfacing.
    """
    per_target = max(1, min(int(per_target), 10))
    validation = plan.get("opportunity_validation")
    validation = validation if isinstance(validation, dict) else {}
    targets = validation.get("targets")
    targets = targets if isinstance(targets, list) else []

    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for target in targets[:10]:
        if not isinstance(target, dict):
            continue
        opportunity_key = str(
            target.get("opportunity_key") or ""
        ).strip()
        niche = str(target.get("niche_family") or "").strip()
        territory = str(target.get("territory") or "").strip()
        if not opportunity_key or not niche:
            continue

        params_dict = {
            "select": (
                "id,business_name,niche,website,metro,status,created_at"
            ),
            "niche": "eq." + niche,
            "website": "not.is.null",
            "order": "created_at.desc",
            "limit": str(per_target),
        }
        normalized_territory = territory.casefold().strip()
        if normalized_territory not in {
            "",
            "uk",
            "gb",
            "great britain",
            "united kingdom",
        }:
            metro_term = territory.split(",", 1)[0].strip()
            if metro_term:
                params_dict["metro"] = f"ilike.*{metro_term}*"

        params = urllib.parse.urlencode(params_dict)
        try:
            batch = request(
                "GET",
                f"/rest/v1/prospects?{params}",
            ) or []
            if diagnostics is not None:
                diagnostics.append({
                    "opportunity_key": opportunity_key,
                    "niche": niche,
                    "territory": territory or None,
                    "state": "OK",
                    "row_count": (
                        len(batch) if isinstance(batch, list) else 0
                    ),
                    "error": None,
                })
        except Exception as exc:
            batch = []
            if diagnostics is not None:
                diagnostics.append({
                    "opportunity_key": opportunity_key,
                    "niche": niche,
                    "territory": territory or None,
                    "state": "ERROR",
                    "row_count": 0,
                    "error": (
                        f"{type(exc).__name__}:{str(exc)[:240]}"
                    ),
                })

        for raw in batch:
            if not isinstance(raw, dict):
                continue
            website = str(raw.get("website") or "").strip()
            business_name = str(
                raw.get("business_name") or ""
            ).strip()
            prospect_id = str(raw.get("id") or "").strip()
            if not website or not business_name or not prospect_id:
                continue
            dedup_key = (prospect_id, opportunity_key)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            row = dict(raw)
            row["seed_opportunity_key"] = opportunity_key
            row["seed_corridor_key"] = target.get("corridor_key")
            row["seed_product_code"] = target.get("product_code")
            row["seed_buyer_pools"] = [
                "end_service_buyers",
                "local_and_smb_buyers",
            ]
            if niche.casefold() in HOME_SERVICE_NICHES:
                row["icp_profile_key"] = "high_ticket_home_service"
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

    plan = _load_buyer_plan(args.repo_root)
    opportunity_seed_diagnostics: list[dict] = []
    opportunity_seeds = _opportunity_validation_seed_records(
        plan,
        per_target=6,
        diagnostics=opportunity_seed_diagnostics,
    )
    canonical_seeds = [
        *opportunity_seeds,
        *_canonical_seed_records(per_lane=8),
    ]

    payload = refresh_buyer_scout(
        args.repo_root,
        max_queries=args.max_queries,
        results_per_query=args.results_per_query,
        max_domains=args.max_domains,
        max_probes=args.max_probes,
        canonical_seed_records=canonical_seeds,
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
        "opportunity_seed_count": len(opportunity_seeds),
        "opportunity_seed_query_error_count": sum(
            row.get("state") == "ERROR"
            for row in opportunity_seed_diagnostics
        ),
        "opportunity_seed_query_diagnostics": (
            opportunity_seed_diagnostics
        ),
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
