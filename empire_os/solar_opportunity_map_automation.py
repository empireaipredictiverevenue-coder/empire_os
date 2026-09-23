"""Automatic internal Solar Opportunity Map materialization.

Triggered from buyer-review proposal outcomes. This module performs internal
evidence materialization only. It never approves reviews, sends outreach,
creates payment requests, moves funds, or recognizes revenue.
"""
from __future__ import annotations

from pathlib import Path
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
