#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.parse
from typing import Any

from empire_os.buyer_deferred_enrichment import BuyerDeferredEnrichmentQueue
from empire_os.buyer_discovery import (
    accepted_acquisition_website,
    build_candidate,
    build_candidate_review_plan,
)
from empire_os.buyer_probe_worker import rejection_reason, run as run_buyer_probe
from empire_os.qualification_worker_v2 import request_json


def _get(path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({
        key: str(value)
        for key, value in params.items()
        if value is not None
    })
    rows = request_json("GET", f"{path}?{query}") or []
    return [row for row in rows if isinstance(row, dict)]


def _prospect_row(prospect_id: str) -> dict[str, Any] | None:
    rows = _get(
        "/rest/v1/prospects",
        {
            "select": (
                "id,business_name,niche,metro,phone,website,buy_signal_score,"
                "status,notes,contact_name,contact_title,contact_source,"
                "contacted_status,created_at"
            ),
            "id": f"eq.{prospect_id}",
            "limit": 1,
        },
    )
    if not rows:
        return None
    row = rows[0]

    links = _get(
        "/rest/v1/prospect_entity_links",
        {
            "select": "entity_id,active,match_score",
            "prospect_id": f"eq.{prospect_id}",
            "active": "eq.true",
            "limit": 1,
        },
    )
    if links:
        row["entity_id"] = links[0].get("entity_id")

    acquisitions = _get(
        "/rest/v1/prospect_acquisitions",
        {
            "select": "evidence,created_at",
            "prospect_id": f"eq.{prospect_id}",
            "order": "created_at.desc",
            "limit": 1,
        },
    )
    if acquisitions:
        evidence = acquisitions[0].get("evidence")
        if accepted_acquisition_website(evidence):
            row["_acquisition_evidence"] = evidence
    return row


def _propose_review(candidate, result: dict[str, Any]) -> bool:
    decision = result.get("decision_maker")
    if not isinstance(decision, dict):
        return False
    try:
        score = float(decision.get("decision_score") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    if (
        score < 0.70
        or result.get("review_ready") is not True
        or result.get("outreach_ready") is not True
    ):
        return False

    plan = build_candidate_review_plan(
        candidate,
        {
            "review_ready": True,
            "outreach_ready": True,
            "preferred_email": result.get("preferred_email"),
            "decision_maker": decision,
            "verified_contacts": result.get("verified_contacts") or [],
        },
        idempotency_key=(
            f"buyer-review:{candidate.prospect_id}:"
            f"{str(result.get('preferred_email') or '').lower()}:v1"
        ),
    )
    response = request_json(
        "POST",
        "/rest/v1/rpc/propose_buyer_candidate_review",
        payload=plan["params"],
    )
    return bool(
        isinstance(response, dict)
        and response.get("review_id")
    )


def run_cycle(*, limit: int = 5) -> dict[str, Any]:
    queue = BuyerDeferredEnrichmentQueue()
    due = queue.due(limit=limit)
    processed = proposed = call_ready = deferred_again = 0
    errors: list[str] = []
    results: list[dict[str, Any]] = []

    for item in due:
        prospect_id = str(item.get("prospect_id") or "").strip()
        attempts = int(item.get("attempts") or 0) + 1
        try:
            row = _prospect_row(prospect_id)
            if not row:
                queue.resolve(prospect_id, outcome="prospect_missing")
                results.append({
                    "prospect_id": prospect_id,
                    "outcome": "prospect_missing",
                })
                processed += 1
                continue

            candidate = build_candidate(
                row,
                entity_id=row.get("entity_id") or None,
                entity_linked=bool(row.get("entity_id")),
            )
            item = {
                **item,
                "business_name": candidate.business_name,
                "website": candidate.website,
                "phone": candidate.phone,
                "entity_id": candidate.entity_id,
            }

            if not candidate.website:
                reason = "site_unavailable"
                marked_call = queue.mark_call_ready(
                    item,
                    reason=reason,
                    enrichment_attempts=attempts,
                )
                if marked_call:
                    call_ready += 1
                retry_minutes = min(360, 30 * (2 ** min(attempts - 1, 3)))
                queue.defer_again(
                    prospect_id,
                    reason=reason,
                    attempts=attempts,
                    retry_minutes=retry_minutes,
                )
                deferred_again += 1
                processed += 1
                results.append({
                    "prospect_id": prospect_id,
                    "outcome": "deferred",
                    "reason": reason,
                    "call_ready": marked_call,
                })
                continue

            probe_row = candidate.to_dict()
            probe_row["id"] = probe_row.pop("prospect_id")
            result = run_buyer_probe(
                probe_row,
                max_pages=15,
                request_timeout=5.0,
                time_budget_seconds=45.0,
            )

            if _propose_review(candidate, result):
                queue.resolve(
                    prospect_id,
                    outcome="buyer_review_proposed",
                )
                proposed += 1
                processed += 1
                results.append({
                    "prospect_id": prospect_id,
                    "outcome": "buyer_review_proposed",
                    "preferred_email": result.get("preferred_email"),
                })
                continue

            reason = rejection_reason(result) or "contact_not_ready"
            marked_call = queue.mark_call_ready(
                item,
                reason=reason,
                enrichment_attempts=attempts,
            )
            if marked_call:
                call_ready += 1
            retry_minutes = min(360, 30 * (2 ** min(attempts - 1, 3)))
            queue.defer_again(
                prospect_id,
                reason=reason,
                attempts=attempts,
                retry_minutes=retry_minutes,
            )
            deferred_again += 1
            processed += 1
            results.append({
                "prospect_id": prospect_id,
                "outcome": "deferred",
                "reason": reason,
                "call_ready": marked_call,
            })
        except Exception as exc:
            retry_minutes = min(360, 30 * (2 ** min(attempts - 1, 3)))
            queue.defer_again(
                prospect_id,
                reason=str(item.get("reason") or "contact_not_ready"),
                attempts=attempts,
                retry_minutes=retry_minutes,
            )
            errors.append(
                f"{prospect_id}:{type(exc).__name__}:{str(exc)[:240]}"
            )

    return {
        "schema_version": "empire.buyer_deferred_enrichment.v1",
        "mode": "INTERNAL_ENRICHMENT",
        "processed": processed,
        "buyer_reviews_proposed": proposed,
        "deferred_again": deferred_again,
        "call_ready_added": call_ready,
        "errors": errors,
        "queue": queue.snapshot(),
        "live_calls_placed": 0,
        "execution_allowed": False,
        "authority_expansion": False,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    result = run_cycle(limit=max(1, min(args.limit, 10)))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
