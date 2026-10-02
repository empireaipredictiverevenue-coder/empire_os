#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
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
    classify_decision_role,
    looks_like_person_name,
    merge_public_web_contact_evidence,
    verify_contact_plan,
)
from empire_os.buyer_probe_worker import rejection_reason
from empire_os.mx_validator import MxValidator
from empire_os.public_person_contact_evidence import (
    collect_public_person_contact_evidence,
)
from empire_os.buyer_review_materializer import run_buyer_probe_isolated
from empire_os.sb import request_json
DEFERRED_LOCK = Path("/srv/empire_os/runtime/buyer_deferred_enrichment/run.lock")

# Keep one enrichment cycle safely below the systemd wall. The worker is
# evidence-seeking, not exhaustive: unresolved rows remain durable and retry.
BUYER_PROBE_TIMEOUT_SECONDS = 18.0
IDENTITY_RECOVERY_TIMEOUT_SECONDS = 20.0
TARGETED_PROBE_TIME_BUDGET_SECONDS = 10.0


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


_TRUSTED_CONTACT_RECOVERY_SOURCES = {
    "website_structured_data",
    "official_site_current",
    "hunter_confirmed_first_party",
    "empire_first_party_people_probe",
}


def _direct_public_contact_recovery(
    candidate: Any,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Recover a bound email without re-running the full site probe."""
    if result.get("review_ready") is True:
        return result

    decision = result.get("decision_maker")
    reconciliation = result.get("decision_reconciliation")
    if isinstance(decision, dict):
        if (
            isinstance(reconciliation, dict)
            and reconciliation.get("review_required") is True
        ):
            return result
        name = str(decision.get("name") or "").strip()
        title = str(decision.get("title") or "").strip()
        source = str(decision.get("source") or "").strip()
        role, score = classify_decision_role(title)
        trusted = bool(
            looks_like_person_name(name)
            and score >= 0.70
            and (
                source in _TRUSTED_CONTACT_RECOVERY_SOURCES
                or source.startswith("empire_registry:")
                or source in {"public_web_corroborated", "official_site"}
            )
        )
    else:
        name = str(getattr(candidate, "contact_name", "") or "").strip()
        title = str(getattr(candidate, "contact_title", "") or "").strip()
        source = str(getattr(candidate, "contact_source", "") or "").strip()
        role, score = classify_decision_role(title)
        trusted = bool(
            looks_like_person_name(name)
            and score >= 0.70
            and (
                source in _TRUSTED_CONTACT_RECOVERY_SOURCES
                or source.startswith("empire_registry:")
            )
        )
        decision = {
            "name": name,
            "title": title,
            "source": source,
            "decision_role": role,
            "decision_score": score,
        } if trusted else None

    if not trusted or not isinstance(decision, dict):
        return result

    observed = collect_public_person_contact_evidence(
        business_name=str(candidate.business_name or ""),
        website=str(candidate.website or ""),
        person_name=name,
        person_title=title,
        max_queries=2,
        max_results_per_query=4,
        max_pages_total=3,
    )
    evidence = observed.get("evidence") or []
    if not evidence:
        return {
            **result,
            "public_person_contact_evidence": observed,
        }

    enriched = {
        "decision_maker": dict(decision),
        "decision_reconciliation": (
            dict(reconciliation)
            if isinstance(reconciliation, dict)
            else {
                "status": "trusted_identity_contact_recovery",
                "review_required": False,
                "decision_maker": dict(decision),
            }
        ),
        "contact_candidates": [
            dict(item)
            for item in (result.get("contacts") or [])
            if isinstance(item, dict)
        ],
    }
    merged = merge_public_web_contact_evidence(enriched, evidence)
    contact = verify_contact_plan(
        merged,
        validator=MxValidator(do_smtp_probe=False),
        allow_company_routed=False,
    )
    return {
        **result,
        "decision_maker": contact.get("decision_maker") or decision,
        "contacts": merged.get("contact_candidates") or [],
        "verified_contacts": contact.get("verified_contacts") or [],
        "preferred_email": contact.get("preferred_email"),
        "contact_route": contact.get("contact_route"),
        "person_bound": bool(contact.get("person_bound")),
        "review_ready": bool(contact.get("review_ready")),
        "outreach_ready": bool(contact.get("outreach_ready")),
        "public_person_contact_evidence": observed,
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
                "id,business_name,niche,metro,address,phone,website,buy_signal_score,"
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


def _retry_minutes(item: dict[str, Any], attempts: int) -> int:
    try:
        priority = int(item.get("priority_score") or 0)
    except (TypeError, ValueError):
        priority = 0
    attempts = max(1, int(attempts))
    reason = str(item.get("reason") or "").strip()

    if reason in {
        "site_unavailable",
        "site_timeout",
        "network_probe_budget_exhausted",
    }:
        if attempts >= 16:
            return 24 * 60
        if attempts >= 8:
            return 6 * 60
        if attempts >= 4:
            return 2 * 60

    if attempts >= 16:
        return 12 * 60
    if attempts >= 8:
        return 3 * 60

    if priority >= 90:
        return min(60, 10 * (2 ** min(max(0, attempts - 1), 3)))
    return min(360, 30 * (2 ** min(max(0, attempts - 1), 3)))


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


def _targeted_enterprise_probe(
    candidate,
    item: dict[str, Any],
    *,
    available_budget: int,
    attempts: int,
) -> tuple[dict[str, Any] | None, int]:
    people = [
        dict(person)
        for person in (item.get("target_people") or [])
        if isinstance(person, dict)
        and looks_like_person_name(person.get("name"))
        and str(person.get("title") or "").strip()
    ]
    if not people or available_budget <= 0:
        return None, 0

    count = min(2, len(people), max(0, int(available_budget)))
    start = ((max(1, int(attempts)) - 1) * 2) % len(people)
    selected = [
        people[(start + offset) % len(people)]
        for offset in range(count)
    ]

    best: dict[str, Any] | None = None
    used = 0
    base = candidate.to_dict()
    base["id"] = base.pop("prospect_id")

    for person in selected:
        probe_row = dict(base)
        probe_row["contact_name"] = str(person["name"]).strip()
        probe_row["contact_title"] = str(person["title"]).strip()
        probe_row["contact_source"] = (
            str(person.get("source") or "").strip()
            or "enterprise_target_observed"
        )

        result = run_buyer_probe_isolated(
            probe_row,
            hard_timeout_seconds=BUYER_PROBE_TIMEOUT_SECONDS,
            probe_options={
                "max_pages": 6,
                "request_timeout": 3.0,
                "time_budget_seconds": TARGETED_PROBE_TIME_BUDGET_SECONDS,
                "allow_company_routed": False,
                "allow_public_person_contact_search": True,
            },
        )
        used += 1
        decision = result.get("decision_maker")
        decision_name = (
            str(decision.get("name") or "").strip()
            if isinstance(decision, dict)
            else ""
        )
        matched = (
            decision_name.casefold()
            == str(person["name"]).strip().casefold()
        )
        result = dict(result)
        result["enterprise_target_match"] = matched
        result["enterprise_target_person"] = dict(person)

        if (
            matched
            and result.get("review_ready") is True
            and result.get("outreach_ready") is True
            and result.get("person_bound") is True
            and result.get("preferred_email")
        ):
            return result, used

        if best is None:
            best = result
        elif (
            result.get("review_ready") is True
            and best.get("review_ready") is not True
        ):
            best = result

    if best is not None:
        best = dict(best)
        best["review_ready"] = False
        best["outreach_ready"] = False
        best["rejection_reason"] = (
            "target_contact_not_verified"
            if best.get("enterprise_target_match") is True
            else "target_identity_mismatch"
        )
    return best, used


def _parse_review_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fresh_existing_review(
    *,
    prospect_id: str,
    contact_email: str,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = current - timedelta(days=7)
    params = urllib.parse.urlencode({
        "select": "id,status,proposed_at,reviewed_at",
        "prospect_id": f"eq.{prospect_id}",
        "contact_email": f"eq.{contact_email.lower()}",
        "status": "in.(pending,approved)",
        "order": "proposed_at.desc",
        "limit": "10",
    })
    rows = request_json(
        "GET",
        f"/rest/v1/buyer_candidate_reviews?{params}",
    ) or []
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        timestamps = (
            _parse_review_time(row.get("proposed_at")),
            _parse_review_time(row.get("reviewed_at")),
        )
        if any(ts is not None and ts >= cutoff for ts in timestamps):
            return row
    return None


def _review_idempotency_key(
    prospect_id: str,
    contact_email: str,
    *,
    now: datetime | None = None,
) -> str:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    day = current.date().isoformat()
    return (
        f"buyer-review:{prospect_id}:"
        f"{contact_email.strip().lower()}:reverified:{day}:v2"
    )


def _propose_review(
    candidate,
    result: dict[str, Any],
    *,
    item: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    decision = result.get("decision_maker")
    if not isinstance(decision, dict):
        return None
    try:
        score = float(decision.get("decision_score") or 0.0)
    except (TypeError, ValueError):
        score = 0.0

    enterprise_item = item if isinstance(item, dict) else {}
    if (
        enterprise_item.get("target_people")
        and result.get("enterprise_target_match") is not True
    ):
        return None

    if (
        score < 0.70
        or result.get("review_ready") is not True
        or result.get("outreach_ready") is not True
    ):
        return None

    preferred_email = str(result.get("preferred_email") or "").strip().lower()
    if not preferred_email:
        return None

    existing = _fresh_existing_review(
        prospect_id=str(candidate.prospect_id),
        contact_email=preferred_email,
    )
    if existing is not None:
        return {
            "decision": "existing_fresh",
            "review_id": existing.get("id"),
            "status": existing.get("status"),
        }

    contact_plan = {
        "review_ready": True,
        "outreach_ready": True,
        "preferred_email": preferred_email,
        "decision_maker": decision,
        "verified_contacts": result.get("verified_contacts") or [],
        "contact_route": result.get("contact_route"),
        "person_bound": bool(result.get("person_bound")),
        "routing_name": result.get("routing_name"),
        "routing_title": result.get("routing_title"),
    }
    offer_key = str(enterprise_item.get("offer_key") or "").strip()
    if offer_key:
        contact_plan["offer_key"] = offer_key

    plan = build_candidate_review_plan(
        candidate,
        contact_plan,
        idempotency_key=_review_idempotency_key(
            str(candidate.prospect_id),
            preferred_email,
        ),
    )
    if enterprise_item.get("account_key"):
        plan["params"]["p_evidence"].update({
            "source": "enterprise_targeted_enrichment.v1",
            "account_key": enterprise_item.get("account_key"),
            "wave": enterprise_item.get("wave"),
            "target_product_codes": (
                enterprise_item.get("target_product_codes") or []
            ),
            "enterprise_target_person": (
                result.get("enterprise_target_person") or {}
            ),
            "enterprise_target_match": True,
            "live_outbound_send": False,
            "actual_revenue": False,
        })

    response = request_json(
        "POST",
        "/rest/v1/rpc/propose_buyer_candidate_review",
        payload=plan["params"],
    )
    if not isinstance(response, dict) or not response.get("review_id"):
        return None
    return dict(response)


def run_cycle(
    *,
    limit: int = 5,
    worker_id: str | None = None,
    materialize_calls: bool = True,
) -> dict[str, Any]:
    queue = BuyerDeferredEnrichmentQueue()
    owner = (
        str(worker_id or "").strip()
        or f"buyer-enrichment:{os.getpid()}"
    )
    due = queue.claim_due(
        limit=limit,
        worker_id=owner,
        lease_seconds=420,
    )
    processed = proposed = fresh_reused = call_ready = deferred_again = identities_recovered = 0
    errors: list[str] = []
    results: list[dict[str, Any]] = []
    rows_by_id = _prospect_rows([
        str(item.get("prospect_id") or "")
        for item in due
    ])
    network_probe_budget = min(max(1, int(limit)), 16)
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
                retry_minutes = _retry_minutes(item, attempts)
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
                queue.defer_again(
                    prospect_id,
                    reason="network_probe_budget_exhausted",
                    attempts=attempts,
                    retry_minutes=10,
                )
                deferred_again += 1
                processed += 1
                results.append({
                    "prospect_id": prospect_id,
                    "outcome": "deferred_by_network_budget",
                    "reason": "network_probe_budget_exhausted",
                })
                continue

            target_people = [
                person
                for person in (item.get("target_people") or [])
                if isinstance(person, dict)
            ]
            result = None
            recovery = None

            if target_people:
                result, used = _targeted_enterprise_probe(
                    candidate,
                    item,
                    available_budget=(
                        network_probe_budget - network_probes
                    ),
                    attempts=attempts,
                )
                network_probes += used

            if result is None:
                if network_probes >= network_probe_budget:
                    queue.defer_again(
                        prospect_id,
                        reason="network_probe_budget_exhausted",
                        attempts=attempts,
                        retry_minutes=10,
                    )
                    deferred_again += 1
                    processed += 1
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
                    hard_timeout_seconds=BUYER_PROBE_TIMEOUT_SECONDS,
                    probe_options={
                        "allow_public_person_contact_search": False,
                    },
                )

                if not result.get("decision_maker"):
                    recovery_location = ", ".join(
                        value
                        for value in (
                            str(candidate.metro or "").strip(),
                            str(row.get("address") or "").strip(),
                        )
                        if value
                    )
                    recovery = recover_identity_isolated(
                        business_name=candidate.business_name,
                        website=candidate.website,
                        metro=recovery_location,
                        hard_timeout_seconds=IDENTITY_RECOVERY_TIMEOUT_SECONDS,
                    )
                    recovered = recovery.get("identity")
                    if isinstance(recovered, dict):
                        probe_row["contact_name"] = recovered.get("name")
                        probe_row["contact_title"] = recovered.get("title")
                        probe_row["contact_source"] = recovered.get("source")
                        result = run_buyer_probe_isolated(
                            probe_row,
                            hard_timeout_seconds=BUYER_PROBE_TIMEOUT_SECONDS,
                            probe_options={
                                "allow_public_person_contact_search": False,
                            },
                        )
                        if not result.get("decision_maker"):
                            result = dict(result)
                            recovered_title = str(
                                recovered.get("title") or ""
                            ).strip()
                            recovered_role, recovered_authority = (
                                classify_decision_role(recovered_title)
                            )
                            result["decision_maker"] = {
                                "name": recovered.get("name"),
                                "title": recovered_title,
                                "url": recovered.get("source_url"),
                                "source": recovered.get("source"),
                                "decision_role": recovered_role,
                                "decision_score": recovered_authority,
                                "identity_confidence": recovered.get(
                                    "confidence"
                                ),
                            }

            result = _direct_public_contact_recovery(
                candidate,
                dict(result or {}),
            )

            identity_recovered = False
            if (
                not target_people
                or result.get("enterprise_target_match") is True
            ):
                identity_recovered = _persist_recovered_identity(
                    row,
                    candidate,
                    result,
                )
            if identity_recovered:
                identities_recovered += 1

            review_result = _propose_review(candidate, result, item=item)
            if review_result is not None:
                review_decision = str(
                    review_result.get("decision") or "proposed"
                )
                outcome = (
                    "buyer_review_existing_fresh"
                    if review_decision == "existing_fresh"
                    else "buyer_review_proposed"
                )
                queue.resolve(
                    prospect_id,
                    outcome=outcome,
                )
                if review_decision == "existing_fresh":
                    fresh_reused += 1
                else:
                    proposed += 1
                processed += 1
                results.append({
                    "prospect_id": prospect_id,
                    "outcome": outcome,
                    "review_id": review_result.get("review_id"),
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
            retry_minutes = _retry_minutes(item, attempts)
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
            retry_minutes = _retry_minutes(item, attempts)
            queue.defer_again(
                prospect_id,
                reason=str(item.get("reason") or "contact_not_ready"),
                attempts=attempts,
                retry_minutes=retry_minutes,
            )
            errors.append(
                f"{prospect_id}:{type(exc).__name__}:{str(exc)[:240]}"
            )

    call_plans = (
        materialize_call_plans()
        if materialize_calls
        else {"count": 0}
    )
    return {
        "schema_version": "empire.buyer_deferred_enrichment.v1",
        "mode": "INTERNAL_ENRICHMENT",
        "worker_id": owner,
        "processed": processed,
        "network_probes_used": network_probes,
        "network_probe_budget": network_probe_budget,
        "buyer_reviews_proposed": proposed,
        "fresh_reviews_reused": fresh_reused,
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


def run_parallel_cycle(
    *,
    limit: int = 48,
    workers: int = 8,
) -> dict[str, Any]:
    total_limit = max(1, min(int(limit), 48))
    worker_count = max(1, min(int(workers), 8, total_limit))
    base = total_limit // worker_count
    remainder = total_limit % worker_count
    lane_limits = [
        base + (1 if index < remainder else 0)
        for index in range(worker_count)
    ]
    lane_limits = [value for value in lane_limits if value > 0]

    lanes: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(lane_limits)) as executor:
        futures = {
            executor.submit(
                run_cycle,
                limit=lane_limit,
                worker_id=f"buyer-enrichment:{os.getpid()}:lane-{index+1}",
                materialize_calls=False,
            ): index
            for index, lane_limit in enumerate(lane_limits)
        }
        for future in as_completed(futures):
            lanes.append(future.result())

    call_plans = materialize_call_plans()
    queue = BuyerDeferredEnrichmentQueue()
    numeric = (
        "processed",
        "network_probes_used",
        "network_probe_budget",
        "buyer_reviews_proposed",
        "fresh_reviews_reused",
        "identities_recovered",
        "deferred_again",
        "call_ready_added",
    )
    merged = {
        key: sum(int(row.get(key) or 0) for row in lanes)
        for key in numeric
    }
    merged.update({
        "schema_version": "empire.buyer_deferred_enrichment.v2",
        "mode": "INTERNAL_ENRICHMENT_PARALLEL",
        "worker_count": len(lane_limits),
        "lane_limits": lane_limits,
        "errors": [
            error
            for row in lanes
            for error in (row.get("errors") or [])
        ],
        "queue": queue.snapshot(),
        "call_plans": {
            "count": call_plans.get("count", 0),
            "execution_allowed": False,
        },
        "live_calls_placed": 0,
        "execution_allowed": False,
        "authority_expansion": False,
        "results": [
            result
            for row in lanes
            for result in (row.get("results") or [])
        ],
    })
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=48)
    parser.add_argument("--workers", type=int, default=8)
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

        result = run_parallel_cycle(
            limit=max(1, min(args.limit, 48)),
            workers=max(1, min(args.workers, 8)),
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
