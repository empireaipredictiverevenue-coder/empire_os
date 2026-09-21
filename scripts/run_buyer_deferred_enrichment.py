#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from empire_os.buyer_call_plan import materialize_call_plans
from empire_os.buyer_deferred_enrichment import BuyerDeferredEnrichmentQueue
from empire_os.buyer_discovery import (
    accepted_acquisition_website,
    build_candidate,
    build_candidate_review_plan,
)
from empire_os.buyer_probe_worker import rejection_reason
from empire_os.buyer_review_materializer import run_buyer_probe_isolated
from empire_os.qualification_worker_v2 import request_json


DEFERRED_LOCK = Path("/srv/empire_os/runtime/buyer_deferred_enrichment/run.lock")


def recover_identity_isolated(
    *,
    business_name: str,
    website: str,
    metro: str,
    hard_timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    timeout = max(10.0, min(float(hard_timeout_seconds), 60.0))
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "empire_os.identity_recovery_worker"],
            input=json.dumps({
                "business_name": business_name,
                "website": website,
                "metro": metro,
            }),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            cwd="/srv/empire_os",
        )
    except subprocess.TimeoutExpired:
        return {
            "decision": "deferred",
            "identity": None,
            "reason": "identity_recovery_timeout",
        }
    if completed.returncode != 0:
        return {
            "decision": "deferred",
            "identity": None,
            "reason": "identity_recovery_worker_failed",
        }
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "decision": "deferred",
            "identity": None,
            "reason": "identity_recovery_invalid_json",
        }
    return result if isinstance(result, dict) else {
        "decision": "deferred",
        "identity": None,
        "reason": "identity_recovery_invalid_shape",
    }


def _get(path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({
        key: str(value)
        for key, value in params.items()
        if value is not None
    })
    rows = request_json("GET", f"{path}?{query}") or []
    return [row for row in rows if isinstance(row, dict)]


def _prospect_rows(prospect_ids: list[str]) -> dict[str, dict[str, Any]]:
    ids = [str(value).strip() for value in prospect_ids if str(value).strip()]
    if not ids:
        return {}
    encoded = f"in.({','.join(ids)})"

    rows = _get(
        "/rest/v1/prospects",
        {
            "select": (
                "id,business_name,niche,metro,phone,website,buy_signal_score,"
                "status,notes,contact_name,contact_title,contact_source,"
                "contacted_status,created_at"
            ),
            "id": encoded,
            "limit": max(1, len(ids)),
        },
    )
    by_id = {
        str(row.get("id")): dict(row)
        for row in rows
        if row.get("id")
    }

    links = _get(
        "/rest/v1/prospect_entity_links",
        {
            "select": "prospect_id,entity_id,active,match_score",
            "prospect_id": encoded,
            "active": "eq.true",
            "order": "match_score.desc",
            "limit": max(1, len(ids) * 2),
        },
    )
    linked: set[str] = set()
    for link in links:
        pid = str(link.get("prospect_id") or "")
        if pid in by_id and pid not in linked:
            by_id[pid]["entity_id"] = link.get("entity_id")
            linked.add(pid)

    acquisitions = _get(
        "/rest/v1/prospect_acquisitions",
        {
            "select": "prospect_id,evidence,created_at",
            "prospect_id": encoded,
            "order": "created_at.desc",
            "limit": max(10, len(ids) * 10),
        },
    )
    acquisition_seen: set[str] = set()
    for acquisition in acquisitions:
        pid = str(acquisition.get("prospect_id") or "")
        if pid not in by_id or pid in acquisition_seen:
            continue
        evidence = acquisition.get("evidence")
        if accepted_acquisition_website(evidence):
            by_id[pid]["_acquisition_evidence"] = evidence
            acquisition_seen.add(pid)

    return by_id


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


def _same_host(left: str, right: str) -> bool:
    def host(value: str) -> str:
        raw = urlparse(str(value or "").strip()).netloc.lower()
        return raw[4:] if raw.startswith("www.") else raw
    return bool(host(left)) and host(left) == host(right)


def _persist_recovered_identity(
    row: dict[str, Any],
    candidate,
    result: dict[str, Any],
) -> bool:
    """Persist only first-party, high-confidence identity evidence.

    Identity recovery is not contact verification and does not make a buyer
    outreach-ready. Existing canonical identities are never overwritten.
    """
    if str(row.get("contact_name") or "").strip():
        return False
    decision = result.get("decision_maker")
    if not isinstance(decision, dict):
        return False

    name = str(decision.get("name") or "").strip()
    title = str(decision.get("title") or "").strip()
    evidence_url = str(
        decision.get("url")
        or decision.get("source_url")
        or ""
    ).strip()
    try:
        score = float(decision.get("decision_score") or 0.0)
    except (TypeError, ValueError):
        score = 0.0

    if not name or not title or score < 0.70:
        return False
    source = str(decision.get("source") or "").strip()
    first_party_evidence = (
        bool(evidence_url)
        and _same_host(evidence_url, candidate.website)
    )
    authoritative_registry = (
        source.startswith("empire_registry:")
        and score >= 0.90
        and bool(evidence_url)
    )
    if not (first_party_evidence or authoritative_registry):
        return False

    params = urllib.parse.urlencode({"id": f"eq.{candidate.prospect_id}"})
    request_json(
        "PATCH",
        f"/rest/v1/prospects?{params}",
        payload={
            "contact_name": name,
            "contact_title": title,
            "contact_source": source or "first_party_identity_recovery",
        },
        prefer="return=minimal",
    )
    return True


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
    processed = proposed = call_ready = deferred_again = identities_recovered = 0
    errors: list[str] = []
    results: list[dict[str, Any]] = []
    rows_by_id = _prospect_rows([
        str(item.get("prospect_id") or "")
        for item in due
    ])
    network_probe_budget = 2
    network_probes = 0

    for item in due:
        prospect_id = str(item.get("prospect_id") or "").strip()
        attempts = int(item.get("attempts") or 0) + 1
        try:
            row = rows_by_id.get(prospect_id)
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

            if network_probes >= network_probe_budget:
                results.append({
                    "prospect_id": prospect_id,
                    "outcome": "deferred_by_network_budget",
                    "reason": "network_probe_budget_exhausted",
                })
                continue
            network_probes += 1

            probe_row = candidate.to_dict()
            probe_row["id"] = probe_row.pop("prospect_id")
            result = run_buyer_probe_isolated(
                probe_row,
                hard_timeout_seconds=28.0,
            )

            recovery = None
            if not result.get("decision_maker"):
                recovery = recover_identity_isolated(
                    business_name=candidate.business_name,
                    website=candidate.website,
                    metro=candidate.metro,
                    hard_timeout_seconds=45.0,
                )
                recovered = recovery.get("identity")
                if isinstance(recovered, dict):
                    probe_row["contact_name"] = recovered.get("name")
                    probe_row["contact_title"] = recovered.get("title")
                    probe_row["contact_source"] = recovered.get("source")
                    result = run_buyer_probe_isolated(
                        probe_row,
                        hard_timeout_seconds=28.0,
                    )
                    if not result.get("decision_maker"):
                        result = dict(result)
                        result["decision_maker"] = {
                            "name": recovered.get("name"),
                            "title": recovered.get("title"),
                            "url": recovered.get("source_url"),
                            "source": recovered.get("source"),
                            "decision_score": recovered.get("confidence"),
                        }

            identity_recovered = _persist_recovered_identity(
                row,
                candidate,
                result,
            )
            if identity_recovered:
                identities_recovered += 1

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
                    "identity_recovered": identity_recovered,
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
                "identity_recovered": identity_recovered,
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

    call_plans = materialize_call_plans()
    return {
        "schema_version": "empire.buyer_deferred_enrichment.v1",
        "mode": "INTERNAL_ENRICHMENT",
        "processed": processed,
        "network_probes_used": network_probes,
        "network_probe_budget": network_probe_budget,
        "buyer_reviews_proposed": proposed,
        "identities_recovered": identities_recovered,
        "deferred_again": deferred_again,
        "call_ready_added": call_ready,
        "errors": errors,
        "queue": queue.snapshot(),
        "call_plans": {
            "count": call_plans.get("count", 0),
            "execution_allowed": False,
        },
        "live_calls_placed": 0,
        "execution_allowed": False,
        "authority_expansion": False,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    DEFERRED_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with DEFERRED_LOCK.open("a+") as handle:
        try:
            fcntl.flock(
                handle.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError:
            print(json.dumps({
                "schema_version": "empire.buyer_deferred_enrichment.v1",
                "decision": "ALREADY_RUNNING_SKIP",
                "processed": 0,
                "execution_allowed": False,
            }, indent=2, sort_keys=True))
            return 0

        result = run_cycle(limit=max(1, min(args.limit, 10)))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
