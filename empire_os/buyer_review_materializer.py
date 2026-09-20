"""Materialize real review-ready buyer candidates into the governed gate.

The worker reads canonical prospects, active identity links and accepted
acquisition evidence, runs the existing first-party buyer probe, and proposes a
buyer-candidate review only when evidence already satisfies the bounded GTM
standing-authority thresholds. It never approves, sends, accepts terms, moves
funds or writes revenue.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Mapping
import urllib.parse

from empire_os.buyer_discovery import (
    accepted_acquisition_website,
    build_candidate,
    build_candidate_review_plan,
)
from empire_os.buyer_probe_worker import run as run_buyer_probe
from empire_os.qualification_worker_v2 import request_json


Request = Callable[..., Any]
Probe = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class BuyerReviewMaterializerResult:
    scanned: int
    eligible: int
    probed: int
    review_ready: int
    proposed: int
    skipped_existing: int
    skipped_ineligible: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "eligible": self.eligible,
            "probed": self.probed,
            "review_ready": self.review_ready,
            "proposed": self.proposed,
            "skipped_existing": self.skipped_existing,
            "skipped_ineligible": self.skipped_ineligible,
            "errors": list(self.errors),
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
) -> tuple[list[dict[str, Any]], int]:
    bounded = max(1, min(int(scan_limit), 100))
    offset = max(0, int(scan_offset))
    prospects = _get(
        request,
        "/rest/v1/prospects",
        {
            "select": (
                "id,business_name,niche,metro,phone,website,buy_signal_score,"
                "status,notes,contact_name,contact_title,contact_source,"
                "contacted_status,created_at"
            ),
            "order": "buy_signal_score.desc.nullslast,created_at.desc",
            "limit": bounded,
            "offset": offset,
        },
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


def _eligible_candidate(row: Mapping[str, Any]):
    candidate = build_candidate(
        row,
        entity_id=row.get("entity_id") or None,
        entity_linked=bool(row.get("entity_id")),
    )
    if not candidate.website:
        return None
    if candidate.offer_key != "managed_service":
        return None
    if candidate.company_score < 70:
        return None
    return candidate


def run_buyer_review_materializer(
    request: Request = request_json,
    *,
    probe: Probe = run_buyer_probe,
    scan_limit: int = 25,
    proposal_limit: int = 5,
    scan_offset: int = 0,
    probe_workers: int = 6,
) -> BuyerReviewMaterializerResult:
    rows, skipped_existing = fetch_candidate_rows(
        request,
        scan_limit=scan_limit,
        scan_offset=scan_offset,
    )
    cap = max(1, min(int(proposal_limit), 20))
    workers = max(1, min(int(probe_workers), 12))

    eligible = probed = review_ready = proposed = skipped_ineligible = 0
    errors: list[str] = []
    work: list[tuple[Any, dict[str, Any]]] = []

    for row in rows:
        candidate = _eligible_candidate(row)
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

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(do_probe, item) for item in work]
        for future in as_completed(futures):
            candidate, result, exc = future.result()
            probed += 1
            if exc is not None:
                errors.append(
                    f"{candidate.prospect_id}:"
                    f"{type(exc).__name__}:{str(exc)[:180]}"
                )
                continue
            if not isinstance(result, Mapping):
                skipped_ineligible += 1
                continue
            if (
                result.get("review_ready") is not True
                or result.get("outreach_ready") is not True
            ):
                skipped_ineligible += 1
                continue

            decision = result.get("decision_maker")
            if not isinstance(decision, Mapping):
                skipped_ineligible += 1
                continue
            try:
                decision_score = float(
                    decision.get("decision_score") or 0.0
                )
            except (TypeError, ValueError):
                decision_score = 0.0
            if decision_score < 0.70:
                skipped_ineligible += 1
                continue

            review_ready += 1
            if proposed >= cap:
                continue

            contact_plan = {
                "review_ready": True,
                "outreach_ready": True,
                "preferred_email": result.get("preferred_email"),
                "decision_maker": dict(decision),
                "verified_contacts": result.get("verified_contacts") or [],
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
                else:
                    errors.append(
                        f"{candidate.prospect_id}:proposal_returned_no_review"
                    )
            except Exception as proposal_exc:
                errors.append(
                    f"{candidate.prospect_id}:"
                    f"{type(proposal_exc).__name__}:"
                    f"{str(proposal_exc)[:180]}"
                )

    return BuyerReviewMaterializerResult(
        scanned=len(rows),
        eligible=eligible,
        probed=probed,
        review_ready=review_ready,
        proposed=proposed,
        skipped_existing=skipped_existing,
        skipped_ineligible=skipped_ineligible,
        errors=tuple(errors),
    )
