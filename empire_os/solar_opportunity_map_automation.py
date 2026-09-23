"""Automatic internal Solar Opportunity Map materialization.

Triggered from buyer-review proposal outcomes. This module performs internal
evidence materialization only. It never approves reviews, sends outreach,
creates payment requests, moves funds, or recognizes revenue.
"""
from __future__ import annotations

from pathlib import Path
import urllib.parse
from typing import Any, Mapping, Sequence

from empire_os.qualification_worker_v2 import request_json
from empire_os.solar_opportunity_map import (
    ARTIFACT_ROOT,
    build_solar_opportunity_map,
    write_solar_opportunity_map,
)


def materialize_solar_maps_for_review_outcomes(
    outcomes: Sequence[Mapping[str, Any]],
    *,
    request=request_json,
    root: str | Path | None = None,
) -> dict[str, Any]:
    proposed_ids = list(dict.fromkeys(
        str(row.get("prospect_id") or "").strip()
        for row in outcomes
        if isinstance(row, Mapping)
        and row.get("status") == "proposed"
        and str(row.get("prospect_id") or "").strip()
    ))

    materialized = []
    skipped = []
    errors = []
    for prospect_id in proposed_ids:
        try:
            prospects = request(
                "GET",
                "/rest/v1/prospects?"
                f"select=id,business_name,niche,website&id=eq.{prospect_id}&limit=1",
            ) or []
            prospect = (
                prospects[0]
                if isinstance(prospects, list) and prospects
                and isinstance(prospects[0], Mapping)
                else None
            )
            if not isinstance(prospect, Mapping):
                skipped.append({
                    "prospect_id": prospect_id,
                    "reason": "canonical_prospect_not_found",
                })
                continue
            if str(prospect.get("niche") or "").strip().casefold() != "solar":
                skipped.append({
                    "prospect_id": prospect_id,
                    "reason": "not_solar",
                })
                continue

            payload = build_solar_opportunity_map(
                prospect_id,
                request=request,
            )
            paths = write_solar_opportunity_map(
                payload,
                root=root or ARTIFACT_ROOT,
            )
            materialized.append({
                "prospect_id": prospect_id,
                "business_name": prospect.get("business_name"),
                "buyer_review_id": payload["buyer_review"]["id"],
                "buyer_review_status": payload["buyer_review"]["status"],
                "paths": paths,
                "priority_actions": len(payload.get("priority_backlog") or []),
            })
        except Exception as exc:
            errors.append({
                "prospect_id": prospect_id,
                "error": f"{type(exc).__name__}:{str(exc)[:260]}",
            })

    return {
        "schema_version": "empire.solar-opportunity-map-automation.v1",
        "trigger": "buyer_review_proposed",
        "candidate_count": len(proposed_ids),
        "materialized_count": len(materialized),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "materialized": materialized,
        "skipped": skipped,
        "errors": errors,
        "review_approval_granted": False,
        "outbound_sent": False,
        "payment_mutation": False,
        "recognized_revenue": False,
        "execution_authority": "internal_artifact_only",
    }


def materialize_missing_solar_map_backlog(
    *,
    request=request_json,
    root: str | Path | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Retry only missing artifacts for pending/approved solar reviews."""
    target_root = Path(root or ARTIFACT_ROOT)
    bounded = max(1, min(int(limit), 50))
    query = urllib.parse.urlencode({
        "select": "id,prospect_id,status,evidence,proposed_at",
        "status": "in.(pending,approved)",
        "evidence->>niche": "eq.solar",
        "order": "proposed_at.desc",
        "limit": bounded,
    })
    reviews = request(
        "GET",
        f"/rest/v1/buyer_candidate_reviews?{query}",
    ) or []
    reviews = [
        row for row in reviews
        if isinstance(row, Mapping)
        and str(row.get("prospect_id") or "").strip()
    ]

    candidates = []
    skipped_existing = 0
    for row in reviews:
        pid = str(row.get("prospect_id") or "").strip()
        json_path = target_root / f"{pid}.json"
        md_path = target_root / f"{pid}.md"
        if json_path.exists() and md_path.exists():
            skipped_existing += 1
            continue
        candidates.append({
            "prospect_id": pid,
            "status": "proposed",
        })

    result = materialize_solar_maps_for_review_outcomes(
        candidates,
        request=request,
        root=target_root,
    )
    result = dict(result)
    result["trigger"] = "missing_artifact_repair"
    result["reviews_scanned"] = len(reviews)
    result["skipped_existing"] = skipped_existing
    return result
