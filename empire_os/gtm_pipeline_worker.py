"""Bounded standing-authority bridge from buyer review to outbound intent."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from urllib.parse import urlencode

from empire_os.conversation_value import build_first_touch_copy
from empire_os.buyer_discovery import looks_like_person_name

POSTAL_ADDRESS = "31 St Thomas St, Bolton, BL1 2QR, UK"


@dataclass(frozen=True)
class GTMPipelineResult:
    pending_seen: int
    candidate_auto_approved: int
    candidate_skipped: int
    reviews_ready_for_outbound: int
    intents_proposed: int
    outreach_deferred: int
    deferred_reasons: tuple[str, ...]
    proposal_errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "pending_seen": self.pending_seen,
            "candidate_auto_approved": self.candidate_auto_approved,
            "candidate_skipped": self.candidate_skipped,
            "reviews_ready_for_outbound": self.reviews_ready_for_outbound,
            "intents_proposed": self.intents_proposed,
            "outreach_deferred": self.outreach_deferred,
            "deferred_reasons": list(self.deferred_reasons),
            "proposal_errors": list(self.proposal_errors),
            "actual_revenue": False,
            "payment_mutation": False,
            "commercial_terms_accepted": False,
        }


Request = Callable[..., Any]


def _first_name(value: Any) -> str:
    clean = str(value or "").strip()
    return clean.split()[0] if clean else ""


def _required_context(evidence: Mapping[str, Any]) -> tuple[str, str, str]:
    business = str(evidence.get("business_name") or "").strip()
    niche = str(evidence.get("niche") or "").strip()
    metro = str(evidence.get("metro") or "").strip()
    missing = [
        key
        for key, value in (
            ("business_name", business),
            ("niche", niche),
            ("metro", metro),
        )
        if not value
    ]
    if missing:
        raise ValueError(
            "outbound personalization evidence missing: "
            + ",".join(missing)
        )
    return business, niche, metro


def _hydrate_review_evidence(
    request: Request,
    review: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = review.get("evidence")
    merged = dict(evidence) if isinstance(evidence, Mapping) else {}
    if all(
        str(merged.get(key) or "").strip()
        for key in ("business_name", "niche", "metro")
    ):
        return {**dict(review), "evidence": merged}

    prospect_id = str(review.get("prospect_id") or "").strip()
    if not prospect_id:
        return {**dict(review), "evidence": merged}

    query = urlencode({
        "select": "business_name,niche,metro,rating,review_count,buy_signal_score,runs_ads",
        "id": f"eq.{prospect_id}",
        "limit": "1",
    })
    rows = request(
        "GET",
        f"/rest/v1/prospects?{query}",
    ) or []
    if not isinstance(rows, list) or not rows:
        return {**dict(review), "evidence": merged}
    prospect = rows[0] if isinstance(rows[0], Mapping) else {}
    for key in ("business_name", "niche", "metro"):
        if not str(merged.get(key) or "").strip():
            value = str(prospect.get(key) or "").strip()
            if value:
                merged[key] = value
    # Canonical prospect observation wins for mutable public-proof fields.
    for key in ("rating", "review_count", "buy_signal_score", "runs_ads"):
        value = prospect.get(key)
        if value not in (None, ""):
            merged[key] = value
    return {**dict(review), "evidence": merged}


def build_outbound_payload(
    review: Mapping[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    evidence = review.get("evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}
    raw_contact_name = str(review.get("contact_name") or "").strip()
    if not looks_like_person_name(raw_contact_name):
        raise ValueError("verified person contact required")
    first = _first_name(raw_contact_name)
    if not first:
        raise ValueError("outbound contact name required")
    business, niche, metro = _required_context(evidence)

    copy = build_first_touch_copy(review, now=now)
    subject = copy.subject
    body = copy.body
    review_id = str(review.get("id") or "").strip()
    if not review_id:
        raise ValueError("review id required")
    return {
        "p_review_id": review_id,
        "p_subject": subject,
        "p_body_text": body,
        "p_body_html": None,
        "p_idempotency_key": f"standing:{review_id}:outbound:v1",
        "p_proposed_by": "empire_gtm_agent_v1",
        "p_expires_at": (
            now.astimezone(timezone.utc) + timedelta(hours=72)
        ).isoformat(),
        "p_metadata": {
            "source": "bounded_gtm_standing_authority",
            "review_id": review_id,
            "business_name": business,
            "conversation_quality": "v2",
            "conversation_quality_tier": copy.quality_tier,
            "why_now_summary": copy.why_now_summary,
            "why_now_evidence_ref": copy.why_now_evidence_ref,
            "specific_proof": copy.specific_proof,
        },
    }


def run_gtm_pipeline(
    request: Request,
    *,
    limit: int = 10,
    daily_cap: int = 10,
    now: datetime | None = None,
) -> GTMPipelineResult:
    bounded = max(1, min(int(limit), 50))
    cap = max(1, min(int(daily_cap), 50))
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must include timezone")

    pending_query = urlencode({
        "select": "id",
        "status": "eq.pending",
        "order": "proposed_at.asc",
        "limit": str(bounded),
    })
    pending = request(
        "GET",
        f"/rest/v1/buyer_candidate_reviews?{pending_query}",
    ) or []
    if not isinstance(pending, list):
        raise ValueError("pending review projection must be a list")

    approved_count = 0
    skipped = 0
    for row in pending:
        review_id = str((row or {}).get("id") or "").strip()
        if not review_id:
            continue
        try:
            result = request(
                "POST",
                "/rest/v1/rpc/auto_review_buyer_candidate",
                payload={
                    "p_review_id": review_id,
                    "p_daily_cap": cap,
                },
            )
            if isinstance(result, Mapping) and result.get("status") == "approved":
                approved_count += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1

    ready = request(
        "POST",
        "/rest/v1/rpc/list_buyer_reviews_for_outbound",
        payload={"p_limit": bounded},
    ) or []
    if not isinstance(ready, list):
        raise ValueError("approved review projection must be a list")

    proposed = 0
    deferred = 0
    deferred_reasons: list[str] = []
    errors: list[str] = []
    for review in ready[:bounded]:
        try:
            hydrated = _hydrate_review_evidence(request, review)
            payload = build_outbound_payload(hydrated, now=current)
            result = request(
                "POST",
                "/rest/v1/rpc/propose_reviewed_outbound_intent",
                payload=payload,
            )
            if isinstance(result, Mapping) and result.get("intent_id"):
                proposed += 1
            else:
                errors.append(
                    f"{payload['p_review_id']}:proposal_returned_no_intent"
                )
        except ValueError as exc:
            review_id = str((review or {}).get("id") or "unknown")
            message = str(exc)
            if (
                "specific outreach evidence required" in message
                or "verified person contact required" in message
                or "outbound personalization evidence missing" in message
            ):
                deferred += 1
                deferred_reasons.append(f"{review_id}:{message[:180]}")
            else:
                errors.append(
                    f"{review_id}:{type(exc).__name__}:{message[:180]}"
                )
        except Exception as exc:
            review_id = str((review or {}).get("id") or "unknown")
            errors.append(
                f"{review_id}:{type(exc).__name__}:{str(exc)[:180]}"
            )

    return GTMPipelineResult(
        pending_seen=len(pending),
        candidate_auto_approved=approved_count,
        candidate_skipped=skipped,
        reviews_ready_for_outbound=len(ready),
        intents_proposed=proposed,
        outreach_deferred=deferred,
        deferred_reasons=tuple(deferred_reasons),
        proposal_errors=tuple(errors),
    )
