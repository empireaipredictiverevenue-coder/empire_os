"""Source-targeted bridge into the canonical qualification rail.

This module does not introduce a new scoring model. It selects prospects backed
by a named acquisition source and delegates them to the existing canonical
qualification worker.

Prospects may enter when they have not yet been scored by Lead Scoring v2 or
when their current v2 qualification is explicitly insufficient_evidence. Rows
already carrying a substantive v2 qualification are left alone.

The existing qualification worker may enrich and materialize internal canonical
evidence, but this bridge never sends outreach, accepts terms, moves funds, or
recognizes revenue.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
import urllib.parse

from empire_os.qualification_worker_v2 import (
    SCORING_ENGINE,
    SCORING_VERSION,
    qualify_prospect,
    request_json,
)


Request = Callable[..., Any]


def _get(
    request: Request,
    path: str,
    params: dict[str, str | int],
) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({
        key: str(value)
        for key, value in params.items()
        if value is not None
    })
    rows = request("GET", f"{path}?{query}") or []
    if not isinstance(rows, list):
        raise ValueError(f"{path} projection must be a list")
    return [row for row in rows if isinstance(row, dict)]


def fetch_pending_source_prospects(
    *,
    source: str,
    niche: str | None = None,
    limit: int = 10,
    request: Request = request_json,
) -> list[dict[str, Any]]:
    """Return source prospects needing first-pass or insufficient-evidence retry."""
    source = str(source or "").strip()
    if not source:
        raise ValueError("source required")

    bounded = max(1, min(int(limit), 25))
    acquisitions = _get(
        request,
        "/rest/v1/prospect_acquisitions",
        {
            "select": "prospect_id,source,created_at",
            "source": f"eq.{source}",
            "order": "created_at.desc",
            "limit": bounded * 8,
        },
    )

    ordered_ids: list[str] = []
    for row in acquisitions:
        prospect_id = str(row.get("prospect_id") or "").strip()
        if prospect_id and prospect_id not in ordered_ids:
            ordered_ids.append(prospect_id)
        if len(ordered_ids) >= bounded * 4:
            break

    if not ordered_ids:
        return []

    existing = _get(
        request,
        "/rest/v1/prospect_qualifications",
        {
            "select": "prospect_id,status,tier,scored_at",
            "scoring_engine": f"eq.{SCORING_ENGINE}",
            "scoring_version": f"eq.{SCORING_VERSION}",
            "prospect_id": f"in.({','.join(ordered_ids)})",
        },
    )

    qualification_by_id = {
        str(row.get("prospect_id") or "").strip(): row
        for row in existing
        if row.get("prospect_id")
    }

    retry_ids: list[str] = []
    for prospect_id in ordered_ids:
        current = qualification_by_id.get(prospect_id)
        if current is None:
            retry_ids.append(prospect_id)
            continue

        status = str(current.get("status") or "").strip().casefold()
        tier = str(current.get("tier") or "").strip().casefold()
        if (
            status == "insufficient_evidence"
            or tier == "insufficient_evidence"
        ):
            retry_ids.append(prospect_id)

    if not retry_ids:
        return []

    params: dict[str, str | int] = {
        "select": (
            "id,created_at,business_name,niche,metro,phone,website,address,"
            "rating,review_count,buy_signal_score,runs_ads,status,notes,"
            "contact_name,contact_title,contact_source"
        ),
        "id": f"in.({','.join(retry_ids)})",
        "limit": len(retry_ids),
    }
    if niche:
        params["niche"] = f"eq.{str(niche).strip()}"

    prospects = _get(
        request,
        "/rest/v1/prospects",
        params,
    )
    by_id = {
        str(row.get("id") or "").strip(): row
        for row in prospects
        if row.get("id")
    }
    return [
        by_id[pid]
        for pid in retry_ids
        if pid in by_id
    ][:bounded]


def run_source_qualification(
    *,
    source: str,
    niche: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Qualify or re-enrich a bounded real-data batch from one source."""
    prospects = fetch_pending_source_prospects(
        source=source,
        niche=niche,
        limit=limit,
    )

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for prospect in prospects:
        try:
            results.append(qualify_prospect(prospect))
        except Exception as exc:
            errors.append({
                "prospect_id": str(prospect.get("id") or ""),
                "business_name": str(prospect.get("business_name") or ""),
                "error": f"{type(exc).__name__}:{str(exc)[:300]}",
            })

    return {
        "schema_version": "empire.source_qualification_bridge.v2",
        "mode": "INTERNAL_MATERIALIZE",
        "source": source,
        "niche": niche,
        "attempted": len(prospects),
        "qualified_or_rescored": len(results),
        "failed": len(errors),
        "identity_resolved": sum(
            1 for row in results if row.get("identity_resolved")
        ),
        "verified_websites_promoted": sum(
            1 for row in results if row.get("verified_website_promoted")
        ),
        "results": results,
        "errors": errors,
        "real_data_only": True,
        "outreach_actions": False,
        "payment_actions": False,
        "recognized_revenue": False,
        "execution_authority": "internal_evidence_only",
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
