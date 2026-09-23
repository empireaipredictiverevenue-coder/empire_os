"""Source-qualified handoff into the governed buyer-review materializer.

This bridge is selection/orchestration only. It does not introduce a new buyer
score, approve reviews, send outreach, accept terms, move funds, or recognize
revenue.
"""
from __future__ import annotations

from typing import Any, Callable
import urllib.parse

from empire_os.buyer_deferred_enrichment import BuyerDeferredEnrichmentQueue
from empire_os.buyer_review_materializer import run_buyer_review_materializer
from empire_os.qualification_worker_v2 import (
    SCORING_ENGINE,
    SCORING_VERSION,
    request_json,
)


Request = Callable[..., Any]


def _get(
    request: Request,
    path: str,
    params: dict[str, Any],
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


def fetch_hot_source_prospect_ids(
    *,
    source: str,
    niche: str | None = None,
    limit: int = 20,
    request: Request = request_json,
) -> list[str]:
    source = str(source or "").strip()
    if not source:
        raise ValueError("source required")

    bounded = max(1, min(int(limit), 100))
    acquisitions = _get(
        request,
        "/rest/v1/prospect_acquisitions",
        {
            "select": "prospect_id,created_at",
            "source": f"eq.{source}",
            "order": "created_at.desc",
            "limit": bounded * 8,
        },
    )

    source_ids: list[str] = []
    for row in acquisitions:
        pid = str(row.get("prospect_id") or "").strip()
        if pid and pid not in source_ids:
            source_ids.append(pid)
        if len(source_ids) >= bounded * 4:
            break

    if not source_ids:
        return []

    qualifications = _get(
        request,
        "/rest/v1/prospect_qualifications",
        {
            "select": "prospect_id,score,tier,status,evidence_confidence",
            "scoring_engine": f"eq.{SCORING_ENGINE}",
            "scoring_version": f"eq.{SCORING_VERSION}",
            "tier": "eq.hot",
            "status": "eq.scored",
            "prospect_id": f"in.({','.join(source_ids)})",
            "order": "score.desc",
            "limit": bounded * 4,
        },
    )

    ranked_ids = [
        str(row.get("prospect_id") or "").strip()
        for row in qualifications
        if row.get("prospect_id")
    ]
    ranked_ids = list(dict.fromkeys(ranked_ids))
    if not ranked_ids:
        return []

    params: dict[str, Any] = {
        "select": "id,niche,website",
        "id": f"in.({','.join(ranked_ids)})",
        "website": "not.is.null",
        "limit": len(ranked_ids),
    }
    if niche:
        params["niche"] = f"eq.{str(niche).strip()}"

    prospects = _get(
        request,
        "/rest/v1/prospects",
        params,
    )
    eligible = {
        str(row.get("id") or "").strip()
        for row in prospects
        if row.get("id") and str(row.get("website") or "").strip()
    }

    return [
        pid
        for pid in ranked_ids
        if pid in eligible
    ][:bounded]


def run_source_buyer_review(
    *,
    source: str,
    niche: str | None = None,
    limit: int = 20,
    proposal_limit: int = 10,
    min_company_score: float = 70.0,
) -> dict[str, Any]:
    prospect_ids = fetch_hot_source_prospect_ids(
        source=source,
        niche=niche,
        limit=limit,
    )
    queue = BuyerDeferredEnrichmentQueue()

    materialized = run_buyer_review_materializer(
        request_json,
        defer=queue.enqueue,
        scan_limit=max(1, len(prospect_ids)),
        proposal_limit=max(1, min(int(proposal_limit), 20)),
        probe_workers=min(6, max(1, len(prospect_ids))),
        prospect_ids=prospect_ids,
        min_company_score=float(min_company_score),
    )

    return {
        "schema_version": "empire.source_buyer_review_bridge.v1",
        "mode": "GOVERNED_REVIEW_PREPARATION",
        "source": source,
        "niche": niche,
        "selected_hot_prospects": len(prospect_ids),
        "prospect_ids": prospect_ids,
        "materializer": materialized.as_dict(),
        "deferred_queue": queue.snapshot(),
        "review_approval_granted": False,
        "outbound_sent": False,
        "payment_mutation": False,
        "recognized_revenue": False,
        "execution_authority": "review_proposal_only",
    }
