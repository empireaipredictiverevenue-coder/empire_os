"""Materialize real review-ready buyer candidates into the governed gate.

The worker reads canonical prospects, active identity links and accepted
acquisition evidence, runs the existing first-party buyer probe, and proposes a
buyer-candidate review only when evidence already satisfies the bounded GTM
standing-authority thresholds. It never approves, sends, accepts terms, moves
funds or writes revenue.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
import subprocess
import sys
from typing import Any, Callable, Mapping
import urllib.parse

from empire_os.buyer_discovery import (
    accepted_acquisition_website,
    build_candidate,
    build_candidate_review_plan,
)
from empire_os.buyer_probe_worker import rejection_reason
from empire_os.qualification_worker_v2 import request_json


Request = Callable[..., Any]
Probe = Callable[[dict[str, Any]], dict[str, Any]]
Defer = Callable[[Mapping[str, Any]], bool]


REVIEWABLE_OFFER_KEYS = frozenset({
    "solar_opportunity_map",
    "managed_service",
    "software_mrr",
    "white_label",
    "high_ticket",
})


def run_buyer_probe_isolated(
    row: dict[str, Any],
    *,
    hard_timeout_seconds: float = 35.0,
    probe_options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one public-site probe in a bounded child process."""
    timeout = max(8.0, min(float(hard_timeout_seconds), 60.0))
    payload = dict(row)
    defaults = {
        "max_pages": 7,
        "request_timeout": 4.0,
        "time_budget_seconds": min(20.0, max(6.0, timeout - 10.0)),
    }
    if isinstance(probe_options, Mapping):
        defaults.update({
            key: value
            for key, value in probe_options.items()
            if key in {
                "max_pages",
                "request_timeout",
                "time_budget_seconds",
                "allow_company_routed",
            }
        })
    payload["_probe_options"] = defaults
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "empire_os.buyer_probe_worker"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            cwd="/srv/empire_os",
        )
    except subprocess.TimeoutExpired:
        return {
            "prospect_id": row.get("id"),
            "business_name": row.get("business_name"),
            "site_ok": False,
            "review_ready": False,
            "outreach_ready": False,
            "rejection_reason": "site_timeout",
            "mode": "OBSERVE",
            "write_authorized": False,
        }

    if proc.returncode != 0:
        raise RuntimeError(
            "buyer probe child failed: "
            + (proc.stderr or "unknown error")[:240]
        )
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("buyer probe child returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("buyer probe child returned non-object")
    return result


@dataclass(frozen=True)
class BuyerReviewMaterializerResult:
    scanned: int
    eligible: int
    probed: int
    review_ready: int
    proposed: int
    skipped_existing: int
    skipped_ineligible: int
    deferred_enrichment: int
    rejection_counts: tuple[tuple[str, int], ...]
    errors: tuple[str, ...]
    outcomes: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "eligible": self.eligible,
            "probed": self.probed,
            "review_ready": self.review_ready,
            "proposed": self.proposed,
            "skipped_existing": self.skipped_existing,
            "skipped_ineligible": self.skipped_ineligible,
            "deferred_enrichment": self.deferred_enrichment,
            "rejection_counts": dict(self.rejection_counts),
            "errors": list(self.errors),
            "outcomes": [dict(item) for item in self.outcomes],
            "actual_revenue": False,
            "outbound_sent": False,
            "commercial_terms_accepted": False,
            "payment_mutation": False,
        }


def _get(
    request: Request,
    path: str,
    params: Mapping[str, Any],
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


def fetch_candidate_rows(
    request: Request = request_json,
    *,
    scan_limit: int = 25,
    scan_offset: int = 0,
    prospect_ids: list[str] | tuple[str, ...] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    bounded = max(1, min(int(scan_limit), 100))
    offset = max(0, int(scan_offset))

    target_ids: list[str] = []
    if prospect_ids is not None:
        from uuid import UUID

        for value in prospect_ids:
            try:
                normalized = str(UUID(str(value).strip()))
            except (ValueError, TypeError, AttributeError):
                continue
            if normalized not in target_ids:
                target_ids.append(normalized)
        if not target_ids:
            return [], 0
        target_ids = target_ids[:bounded]

    params: dict[str, Any] = {
        "select": (
            "id,business_name,niche,metro,phone,website,buy_signal_score,"
            "status,notes,contact_name,contact_title,contact_source,"
            "contacted_status,created_at"
        ),
        "website": "not.is.null",
        "order": (
            "buy_signal_score.desc.nullslast,created_at.desc"
        ),
        "limit": bounded,
        "offset": offset,
    }
    if target_ids:
        params["id"] = f"in.({','.join(target_ids)})"

    prospects = _get(
        request,
        "/rest/v1/prospects",
        params,
    )

    ready: list[dict[str, Any]] = []
    skipped_existing = 0
    for row in prospects:
        prospect_id = str(row.get("id") or "").strip()
        if not prospect_id:
            continue

        reviews = _get(
            request,
            "/rest/v1/buyer_candidate_reviews",
            {
                "select": "id,status",
                "prospect_id": f"eq.{prospect_id}",
                "order": "proposed_at.desc",
                "limit": 1,
            },
        )
        if any(
            str(item.get("status") or "") in {"pending", "approved"}
            for item in reviews
        ):
            skipped_existing += 1
            continue

        links = _get(
            request,
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
            request,
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

        ready.append(row)

    return ready, skipped_existing


def _eligible_candidate(
    row: Mapping[str, Any],
    *,
    min_company_score: float = 70.0,
):
    candidate = build_candidate(
        row,
        entity_id=row.get("entity_id") or None,
        entity_linked=bool(row.get("entity_id")),
    )
    if not candidate.website:
        return None
    if candidate.offer_key not in REVIEWABLE_OFFER_KEYS:
        return None
    if candidate.company_score < float(min_company_score):
        return None
    return candidate


def run_buyer_review_materializer(
    request: Request = request_json,
    *,
    probe: Probe = run_buyer_probe_isolated,
    defer: Defer | None = None,
    scan_limit: int = 25,
    proposal_limit: int = 5,
    scan_offset: int = 0,
    probe_workers: int = 6,
    prospect_ids: list[str] | tuple[str, ...] | None = None,
    min_company_score: float = 70.0,
) -> BuyerReviewMaterializerResult:
    rows, skipped_existing = fetch_candidate_rows(
        request,
        scan_limit=scan_limit,
        scan_offset=scan_offset,
        prospect_ids=prospect_ids,
    )
    cap = max(1, min(int(proposal_limit), 20))
    workers = max(1, min(int(probe_workers), 24))

    eligible = probed = review_ready = proposed = skipped_ineligible = 0
    deferred_enrichment = 0
    rejection_counts: Counter[str] = Counter()
    errors: list[str] = []
    outcomes: list[dict[str, Any]] = []
    work: list[tuple[Any, dict[str, Any]]] = []

    for row in rows:
        candidate = _eligible_candidate(
            row,
            min_company_score=min_company_score,
        )
        if candidate is None:
            skipped_ineligible += 1
            continue
        eligible += 1
        probe_row = candidate.to_dict()
        probe_row["id"] = probe_row.pop("prospect_id")
        work.append((candidate, probe_row))

    def do_probe(item):
        candidate, probe_row = item
        try:
            return candidate, probe(probe_row), None
        except Exception as exc:
            return candidate, None, exc

    def record_outcome(
        candidate,
        result: Mapping[str, Any] | None,
        *,
        status: str,
        reason: str | None = None,
    ) -> None:
        decision = (
            result.get("decision_maker")
            if isinstance(result, Mapping)
            else None
        )
        recovery = (
            result.get("identity_recovery")
            if isinstance(result, Mapping)
            else None
        )
        outcomes.append({
            "prospect_id": candidate.prospect_id,
            "business_name": candidate.business_name,
            "status": status,
            "reason": reason,
            "review_ready": bool(
                isinstance(result, Mapping)
                and result.get("review_ready") is True
            ),
            "outreach_ready": bool(
                isinstance(result, Mapping)
                and result.get("outreach_ready") is True
            ),
            "decision_name": (
                str(decision.get("name") or "").strip()
                if isinstance(decision, Mapping)
                else None
            ),
            "decision_title": (
                str(decision.get("title") or "").strip()
                if isinstance(decision, Mapping)
                else None
            ),
            "identity_recovery": (
                dict(recovery)
                if isinstance(recovery, Mapping)
                else None
            ),
            "preferred_email": (
                str(result.get("preferred_email") or "").strip()
                if isinstance(result, Mapping)
                else None
            ) or None,
            "contact_route": (
                str(result.get("contact_route") or "").strip()
                if isinstance(result, Mapping)
                else None
            ) or None,
        })

    def queue_deferred(candidate, reason: str) -> None:
        nonlocal deferred_enrichment
        if defer is None:
            return
        payload = {
            "prospect_id": candidate.prospect_id,
            "business_name": candidate.business_name,
            "website": candidate.website,
            "phone": getattr(candidate, "phone", None),
            "entity_id": getattr(candidate, "entity_id", None),
            "reason": reason,
        }
        try:
            if defer(payload):
                deferred_enrichment += 1
        except Exception as exc:
            errors.append(
                f"{candidate.prospect_id}:defer:"
                f"{type(exc).__name__}:{str(exc)[:160]}"
            )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(do_probe, item) for item in work]
        for future in as_completed(futures):
            candidate, result, exc = future.result()
            probed += 1
            if exc is not None:
                rejection_counts["probe_error"] += 1
                errors.append(
                    f"{candidate.prospect_id}:"
                    f"{type(exc).__name__}:{str(exc)[:180]}"
                )
                record_outcome(
                    candidate,
                    None,
                    status="probe_error",
                    reason="probe_error",
                )
                continue
            if not isinstance(result, Mapping):
                rejection_counts["invalid_probe_result"] += 1
                skipped_ineligible += 1
                record_outcome(
                    candidate,
                    None,
                    status="rejected",
                    reason="invalid_probe_result",
                )
                continue
            if (
                result.get("review_ready") is not True
                or result.get("outreach_ready") is not True
            ):
                reason = str(result.get("rejection_reason") or "").strip()
                if not reason:
                    reason = (
                        "outreach_not_ready"
                        if result.get("review_ready") is True
                        else rejection_reason(dict(result))
                    )
                reason = reason or "contact_not_ready"
                rejection_counts[reason] += 1
                queue_deferred(candidate, reason)
                skipped_ineligible += 1
                record_outcome(
                    candidate,
                    result,
                    status="deferred",
                    reason=reason,
                )
                continue

            decision = result.get("decision_maker")
            if not isinstance(decision, Mapping):
                rejection_counts["decision_maker_missing"] += 1
                queue_deferred(candidate, "decision_maker_missing")
                skipped_ineligible += 1
                record_outcome(
                    candidate,
                    result,
                    status="deferred",
                    reason="decision_maker_missing",
                )
                continue
            try:
                decision_score = float(
                    decision.get("decision_score") or 0.0
                )
            except (TypeError, ValueError):
                decision_score = 0.0
            if decision_score < 0.70:
                rejection_counts["decision_score_below_floor"] += 1
                queue_deferred(candidate, "decision_score_below_floor")
                skipped_ineligible += 1
                record_outcome(
                    candidate,
                    result,
                    status="deferred",
                    reason="decision_score_below_floor",
                )
                continue

            review_ready += 1
            if proposed >= cap:
                record_outcome(
                    candidate,
                    result,
                    status="review_ready_not_proposed",
                    reason="proposal_cap_reached",
                )
                continue

            contact_plan = {
                "review_ready": True,
                "outreach_ready": True,
                "preferred_email": result.get("preferred_email"),
                "decision_maker": dict(decision),
                "verified_contacts": result.get("verified_contacts") or [],
                "contact_route": result.get("contact_route"),
                "person_bound": bool(result.get("person_bound")),
                "routing_name": result.get("routing_name"),
                "routing_title": result.get("routing_title"),
            }
            plan = build_candidate_review_plan(
                candidate,
                contact_plan,
                idempotency_key=(
                    f"buyer-review:{candidate.prospect_id}:"
                    f"{str(result.get('preferred_email') or '').lower()}:v1"
                ),
            )
            try:
                response = request(
                    "POST",
                    "/rest/v1/rpc/propose_buyer_candidate_review",
                    payload=plan["params"],
                )
                if isinstance(response, Mapping) and response.get("review_id"):
                    proposed += 1
                    record_outcome(
                        candidate,
                        result,
                        status="proposed",
                    )
                else:
                    errors.append(
                        f"{candidate.prospect_id}:proposal_returned_no_review"
                    )
                    record_outcome(
                        candidate,
                        result,
                        status="proposal_failed",
                        reason="proposal_returned_no_review",
                    )
            except Exception as proposal_exc:
                errors.append(
                    f"{candidate.prospect_id}:"
                    f"{type(proposal_exc).__name__}:"
                    f"{str(proposal_exc)[:180]}"
                )
                record_outcome(
                    candidate,
                    result,
                    status="proposal_failed",
                    reason=type(proposal_exc).__name__,
                )

    return BuyerReviewMaterializerResult(
        scanned=len(rows),
        eligible=eligible,
        probed=probed,
        review_ready=review_ready,
        proposed=proposed,
        skipped_existing=skipped_existing,
        skipped_ineligible=skipped_ineligible,
        deferred_enrichment=deferred_enrichment,
        rejection_counts=tuple(sorted(rejection_counts.items())),
        errors=tuple(errors),
        outcomes=tuple(outcomes),
    )
