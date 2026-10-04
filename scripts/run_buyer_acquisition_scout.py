#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.parse
from urllib.parse import urlparse

from empire_os.buyer_acquisition_scout import refresh_buyer_scout
from empire_os.sb import request_json
SIGNAL_INBOX = Path("runtime/acquisition/signal_inbox.json")

HOME_SERVICE_INTENT_NICHES = {
    "roofing", "residential_roofing", "roof_repair", "hvac",
    "solar", "plumbing", "restoration", "water_damage_restoration",
    "general_contractor", "siding", "gutter",
}

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



def _community_intent_seed_records(
    repo_root: str | Path,
    *,
    limit: int = 12,
) -> list[dict]:
    """Convert stored public intent with first-party URLs into scout seeds."""
    root = Path(repo_root).resolve()
    try:
        payload = json.loads(
            (root / SIGNAL_INBOX).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []

    rows: list[dict] = []
    seen_domains: set[str] = set()
    for signal_id, raw in sorted(
        payload.items(),
        key=lambda item: str(
            (item[1] or {}).get("last_seen_at")
            if isinstance(item[1], dict)
            else ""
        ),
        reverse=True,
    ):
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source") or "").strip()
        if not source.endswith("_intent"):
            continue
        if raw.get("status") not in {"unresolved", "needs_review"}:
            continue

        candidate_raw = raw.get("raw")
        candidate_raw = (
            candidate_raw if isinstance(candidate_raw, dict) else {}
        )
        observation = candidate_raw.get("community_intent")
        observation = (
            observation if isinstance(observation, dict) else {}
        )
        score = int(
            observation.get("intent_score")
            if observation.get("intent_score") is not None
            else raw.get("lead_score") or 0
        )
        band = str(observation.get("intent_band") or "").strip()
        if score < 35 and band not in {"medium", "high"}:
            continue

        evidence_urls = list(
            candidate_raw.get("evidence_urls")
            or observation.get("evidence_urls")
            or []
        )
        website = ""
        domain = ""
        for value in evidence_urls:
            url = str(value or "").strip()
            try:
                host = urlparse(url).netloc.casefold()
            except ValueError:
                continue
            host = host.split("@")[-1].split(":")[0]
            if host.startswith("www."):
                host = host[4:]
            if not host or host in seen_domains:
                continue
            website = url
            domain = host
            break
        if not website:
            continue

        niche = str(raw.get("niche") or observation.get("niche") or "").strip()
        niche_key = niche.casefold().replace(" ", "_")
        if niche_key in HOME_SERVICE_INTENT_NICHES:
            profile_key = "intent_driven_home_service_growth"
            pools = [
                "local_and_smb_buyers",
                "software_and_advisory_buyers",
            ]
        elif "legal" in niche_key or "law" in niche_key:
            profile_key = "legal_plaintiff_growth_firm"
            pools = [
                "enterprise_and_data_buyers",
                "software_and_advisory_buyers",
            ]
        elif "insurance" in niche_key:
            profile_key = "insurance_distribution_growth"
            pools = [
                "enterprise_and_data_buyers",
                "software_and_advisory_buyers",
            ]
        else:
            profile_key = "enterprise_growth_data_team"
            pools = ["software_and_advisory_buyers"]

        title = str(observation.get("title") or "").strip()
        text_value = str(observation.get("text") or "").strip()
        summary = " ".join(
            value for value in (title, text_value) if value
        )[:1800]

        seen_domains.add(domain)
        rows.append({
            "id": None,
            "business_name": "",
            "niche": niche or "commercial_intent",
            "website": website,
            "icp_profile_key": profile_key,
            "seed_buyer_pools": pools,
            "seed_product_code": "managed_service",
            "seed_intent_signal_id": str(
                raw.get("signal_id") or signal_id
            ),
            "recovery_source": "community_intent_signal_inbox",
            "intent_score": score,
            "intent_band": band or None,
            "intent_observed_at": (
                str(observation.get("observed_at") or "").strip()
                or None
            ),
            "intent_pain_points": list(
                observation.get("pain_points") or []
            ),
            "intent_evidence_url": str(raw.get("url") or "").strip() or None,
            "intent_summary": summary or None,
        })
        if len(rows) >= max(1, min(int(limit), 50)):
            break
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--max-queries", type=int, default=20)
    parser.add_argument("--results-per-query", type=int, default=8)
    parser.add_argument("--max-domains", type=int, default=40)
    parser.add_argument("--max-probes", type=int, default=20)
    parser.add_argument("--intent-seed-limit", type=int, default=12)
    args = parser.parse_args()

    seed_records = _canonical_seed_records(per_lane=8)
    intent_seed_records = _community_intent_seed_records(
        args.repo_root,
        limit=args.intent_seed_limit,
    )
    seed_records.extend(intent_seed_records)

    payload = refresh_buyer_scout(
        args.repo_root,
        max_queries=args.max_queries,
        results_per_query=args.results_per_query,
        max_domains=args.max_domains,
        max_probes=args.max_probes,
        canonical_seed_records=seed_records,
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
        "intent_seed_input_count": len(intent_seed_records),
        "intent_seed_domain_count": payload[
            "intent_seed_domain_count"
        ],
        "intent_seed_supplement_used": payload[
            "intent_seed_supplement_used"
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
