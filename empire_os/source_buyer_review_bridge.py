"""Source-qualified handoff into the governed buyer-review materializer.

This bridge is selection/orchestration only. It does not introduce a new buyer
score, approve reviews, send outreach, accept terms, move funds, or recognize
revenue.
"""
from __future__ import annotations

from typing import Any, Callable
import json
import subprocess
import sys
import urllib.parse

from empire_os.buyer_deferred_enrichment import BuyerDeferredEnrichmentQueue
from empire_os.buyer_discovery import classify_decision_role
from empire_os.buyer_probe_worker import rejection_reason
from empire_os.buyer_review_materializer import (
    run_buyer_probe_isolated,
    run_buyer_review_materializer,
)
from empire_os.solar_opportunity_map_automation import (
    materialize_solar_maps_for_review_outcomes,
)
from empire_os.market_pricing import (
    infer_country_code,
    market_price,
    sync_market_price,
)
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


def _recover_identity_isolated(
    row: dict[str, Any],
    *,
    hard_timeout_seconds: float = 55.0,
) -> dict[str, Any]:
    timeout = max(15.0, min(float(hard_timeout_seconds), 60.0))
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "empire_os.identity_recovery_worker"],
            input=json.dumps({
                "business_name": row.get("business_name"),
                "website": row.get("website"),
                "metro": row.get("metro"),
            }),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            cwd="/srv/empire_os",
        )
    except subprocess.TimeoutExpired:
        return {
            "recovered": False,
            "identity": None,
            "reason": "identity_recovery_timeout",
        }
    if completed.returncode != 0:
        return {
            "recovered": False,
            "identity": None,
            "reason": "identity_recovery_worker_failed",
        }
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "recovered": False,
            "identity": None,
            "reason": "identity_recovery_invalid_json",
        }
    return payload if isinstance(payload, dict) else {
        "recovered": False,
        "identity": None,
        "reason": "identity_recovery_invalid_shape",
    }


def _source_probe(row: dict[str, Any]) -> dict[str, Any]:
    """Probe once, then make one bounded identity-recovery attempt if useful."""
    first = run_buyer_probe_isolated(
        row,
        hard_timeout_seconds=55.0,
        probe_options={
            "max_pages": 12,
            "request_timeout": 5.0,
            "time_budget_seconds": 35.0,
            "allow_company_routed": True,
        },
    )
    if (
        first.get("review_ready") is True
        and first.get("outreach_ready") is True
    ):
        return first

    reason = str(
        first.get("rejection_reason")
        or rejection_reason(first)
        or ""
    )
    if reason not in {"no_decision_maker", "no_bound_contact"}:
        return first

    recovery = _recover_identity_isolated(row)
    identity = recovery.get("identity")
    if not isinstance(identity, dict):
        result = dict(first)
        result["identity_recovery"] = {
            "attempted": True,
            "recovered": False,
            "reason": recovery.get("reason") or "no_identity_recovered",
        }
        return result

    title = str(identity.get("title") or "").strip()
    decision_role, decision_score = classify_decision_role(title)
    if decision_score < 0.70:
        result = dict(first)
        result["identity_recovery"] = {
            "attempted": True,
            "recovered": True,
            "promoted": False,
            "name": identity.get("name"),
            "title": title,
            "decision_role": decision_role,
            "decision_score": decision_score,
            "identity_confidence": identity.get("confidence"),
            "reason": "recovered_identity_not_buyer_role",
        }
        return result

    retry_row = dict(row)
    retry_row["contact_name"] = identity.get("name")
    retry_row["contact_title"] = title
    retry_row["contact_source"] = identity.get("source")

    second = run_buyer_probe_isolated(
        retry_row,
        hard_timeout_seconds=55.0,
        probe_options={
            "max_pages": 12,
            "request_timeout": 5.0,
            "time_budget_seconds": 35.0,
            "allow_company_routed": True,
        },
    )
    second = dict(second)
    second["identity_recovery"] = {
        "attempted": True,
        "recovered": True,
        "promoted": True,
        "name": identity.get("name"),
        "title": title,
        "decision_role": decision_role,
        "decision_score": decision_score,
        "identity_confidence": identity.get("confidence"),
        "source": identity.get("source"),
        "source_url": identity.get("source_url"),
    }
    return second


def run_source_buyer_review(
    *,
    source: str,
    niche: str | None = None,
    limit: int = 20,
    proposal_limit: int = 10,
    min_company_score: float = 70.0,
    prospect_ids: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    source_country = infer_country_code(source=source)
    if source_country:
        product_catalog = sync_market_price(
            market_price(source_country),
        )
    else:
        product_catalog = {
            "decision": "skipped",
            "reason": "source_country_price_not_configured",
            "source": source,
            "binding_terms_ready": False,
            "actual_revenue": False,
        }

    eligible_ids = fetch_hot_source_prospect_ids(
        source=source,
        niche=niche,
        limit=limit,
    )
    if prospect_ids:
        requested = [
            str(value or "").strip()
            for value in prospect_ids
            if str(value or "").strip()
        ]
        allowed = set(eligible_ids)
        selected_ids = [
            pid for pid in requested
            if pid in allowed
        ]
        selected_ids = list(dict.fromkeys(selected_ids))
    else:
        selected_ids = eligible_ids
    queue = BuyerDeferredEnrichmentQueue()

    materialized = run_buyer_review_materializer(
        request_json,
        probe=_source_probe,
        defer=queue.enqueue,
        scan_limit=max(1, len(selected_ids)),
        proposal_limit=max(1, min(int(proposal_limit), 20)),
        probe_workers=min(6, max(1, len(selected_ids))),
        prospect_ids=selected_ids,
        min_company_score=float(min_company_score),
    )

    artifact_materialization = materialize_solar_maps_for_review_outcomes(
        materialized.outcomes,
    )

    return {
        "schema_version": "empire.source_buyer_review_bridge.v1",
        "mode": "GOVERNED_REVIEW_PREPARATION",
        "source": source,
        "niche": niche,
        "selected_hot_prospects": len(selected_ids),
        "prospect_ids": selected_ids,
        "product_catalog": product_catalog,
        "materializer": materialized.as_dict(),
        "artifact_materialization": artifact_materialization,
        "deferred_queue": queue.snapshot(),
        "review_approval_granted": False,
        "outbound_sent": False,
        "payment_mutation": False,
        "recognized_revenue": False,
        "execution_authority": "review_proposal_only",
    }
