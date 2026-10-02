"""Bounded standing-authority bridge from buyer review to outbound intent."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from urllib.parse import urlencode

from empire_os.adaptive_outreach_optimizer import (
    build_body_arm_candidates,
    build_subject_arm_candidates,
    select_message_arms,
)
from empire_os.conversation_value import build_first_touch_copy
from empire_os.buyer_discovery import looks_like_person_name
from empire_os.locale_intelligence import contact_window_status, resolve_locale
from empire_os.outreach_message_optimizer import review_message

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
    founder_review_required: tuple[dict[str, Any], ...]
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
            "founder_review_required": [
                dict(item) for item in self.founder_review_required
            ],
            "proposal_errors": list(self.proposal_errors),
            "actual_revenue": False,
            "payment_mutation": False,
            "commercial_terms_accepted": False,
        }


Request = Callable[..., Any]


def _first_name(value: Any) -> str:
    clean = str(value or "").strip()
    return clean.split()[0] if clean else ""


def _locale_for_evidence(evidence: Mapping[str, Any]):
    raw = evidence.get("locale")
    locale_input = dict(raw) if isinstance(raw, Mapping) else {}
    locale_input.setdefault("metro", str(evidence.get("metro") or "").strip())
    locale_input.setdefault("state", str(evidence.get("state") or "").strip())
    return resolve_locale(locale_input)


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
    # Always hydrate the canonical prospect when available. Core context may
    # already be present while mutable observed proof (rating/review_count,
    # buy signal, ads) is missing from the older buyer-review evidence packet.
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
    optimizer_snapshot: Mapping[str, Any] | None = None,
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
    locale = _locale_for_evidence(evidence)
    if not locale.outreach_language:
        raise ValueError("recipient outreach language unresolved")
    timing = contact_window_status(locale, now=now)
    if timing["eligible"] is not True:
        raise ValueError(
            f"{timing['reason']}; next_eligible_utc="
            f"{timing.get('next_eligible_utc')}"
        )

    copy = build_first_touch_copy(review, now=now)
    subject = copy.subject
    body = copy.body
    adaptive_selection = None
    selected_quality = (
        dict(copy.quality_review)
        if isinstance(copy.quality_review, Mapping)
        else None
    )

    review_id = str(review.get("id") or "").strip()
    if not review_id:
        raise ValueError("review id required")

    if optimizer_snapshot is not None:
        body_rows = build_body_arm_candidates(
            business_name=business,
            observed_evidence=(
                copy.why_now_summary
                or copy.specific_proof
                or ""
            ),
        )
        subject_rows = build_subject_arm_candidates(
            copy.subject_variants,
            business_name=business,
            territory=metro,
        )

        # Every candidate must pass the canonical message quality gate before
        # it can enter the adaptive experiment.
        safe_subjects = []
        for row in subject_rows:
            quality = review_message(
                subject=str(row["subject"]),
                body=str(body_rows[0]["core_body"]),
                cta=str(body_rows[0]["cta"]),
                contact_title=str(review.get("contact_title") or ""),
            )
            eligible = quality.get(
                "experiment_eligible",
                int(quality.get("score") or 0) >= 80,
            )
            if bool(eligible) and int(quality.get("score") or 0) >= 80:
                safe_subjects.append(row)

        safe_bodies = []
        safe_subject = (
            str(safe_subjects[0]["subject"])
            if safe_subjects
            else copy.subject
        )
        for row in body_rows:
            quality = review_message(
                subject=safe_subject,
                body=str(row["core_body"]),
                cta=str(row["cta"]),
                contact_title=str(review.get("contact_title") or ""),
            )
            eligible = quality.get(
                "experiment_eligible",
                int(quality.get("score") or 0) >= 80,
            )
            if bool(eligible) and int(quality.get("score") or 0) >= 80:
                safe_bodies.append(row)

        if len(safe_subjects) < 2 or len(safe_bodies) < 2:
            raise ValueError(
                "insufficient quality-gated adaptive outreach variants"
            )

        adaptive_selection = select_message_arms(
            assignment_key=review_id,
            subject_arm_ids=[
                str(row["variant_id"])
                for row in safe_subjects
            ],
            body_arm_ids=[
                str(row["variant_id"])
                for row in safe_bodies
            ],
            offer_key=str(review.get("offer_key") or "managed_service"),
            niche=niche,
            decision_role=evidence.get("decision_role"),
            snapshot=optimizer_snapshot,
        )
        subject_row = next(
            row for row in safe_subjects
            if row["variant_id"] == adaptive_selection["subject_arm"]
        )
        body_row = next(
            row for row in safe_bodies
            if row["variant_id"] == adaptive_selection["body_arm"]
        )
        subject = str(subject_row["subject"])
        core_body = str(body_row["core_body"])
        body = (
            f"Hi {first},\n\n"
            f"{core_body}\n\n"
            "Best,\nPhil\nFounder, Empire AI\nempire-ai.co.uk\n\n"
            f"{POSTAL_ADDRESS}\n"
            "If you’d rather not hear from me, reply “opt out”."
        )
        selected_quality = review_message(
            subject=subject,
            body=core_body,
            cta=str(body_row["cta"]),
            contact_title=str(review.get("contact_title") or ""),
        )
        eligible = selected_quality.get(
            "experiment_eligible",
            int(selected_quality.get("score") or 0) >= 80,
        )
        if not bool(eligible) or int(
            selected_quality.get("score") or 0
        ) < 80:
            raise ValueError(
                "adaptive outreach variant failed message quality gate"
            )

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
            "message_optimizer_version": (
                "adaptive_v1"
                if adaptive_selection is not None
                else "v1"
            ),
            "subject_variants": list(copy.subject_variants),
            "message_quality_review": selected_quality,
            "adaptive_outreach": (
                {
                    **adaptive_selection,
                    "subject_text": subject,
                    "body_variant_id": (
                        str(body_row["variant_id"])
                        if adaptive_selection is not None
                        else None
                    ),
                    "copy_policy": "human_plain_specific_v1",
                    "ai_slop_allowed": False,
                }
                if adaptive_selection is not None
                else None
            ),
            "why_now_summary": copy.why_now_summary,
            "why_now_evidence_ref": copy.why_now_evidence_ref,
            "specific_proof": copy.specific_proof,
            "recipient_locale": locale.as_dict(),
            "recipient_local_timing": timing,
            "outreach_language": locale.outreach_language,
        },
    }


def run_gtm_pipeline(
    request: Request,
    *,
    limit: int = 25,
    daily_cap: int = 25,
    now: datetime | None = None,
    optimizer_snapshot: Mapping[str, Any] | None = None,
) -> GTMPipelineResult:
    bounded = max(1, min(int(limit), 50))
    cap = max(1, min(int(daily_cap), 50))
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must include timezone")

    pending_cutoff = current - timedelta(days=7)
    pending_query = urlencode({
        "select": (
            "id,prospect_id,contact_name,contact_title,contact_email,"
            "offer_key,company_score,decision_score,proposed_at"
        ),
        "status": "eq.pending",
        "proposed_at": f"gte.{pending_cutoff.isoformat()}",
        "order": "proposed_at.desc",
        "limit": str(bounded),
    })
    pending = request(
        "GET",
        f"/rest/v1/buyer_candidate_reviews?{pending_query}",
    ) or []
    if not isinstance(pending, list):
        raise ValueError("pending review projection must be a list")

    approved_cutoff = current - timedelta(days=7)
    approved_query = urlencode({
        "select": "contact_email,reviewed_at",
        "status": "eq.approved",
        "reviewed_at": f"gte.{approved_cutoff.isoformat()}",
        "order": "reviewed_at.desc",
        "limit": "100",
    })
    approved_rows = request(
        "GET",
        f"/rest/v1/buyer_candidate_reviews?{approved_query}",
    ) or []
    if not isinstance(approved_rows, list):
        raise ValueError("approved review projection must be a list")

    seen_contacts = {
        str((row or {}).get("contact_email") or "").strip().lower()
        for row in approved_rows
        if str((row or {}).get("contact_email") or "").strip()
    }

    approved_count = 0
    skipped = 0
    pending_skip_reasons: list[str] = []
    founder_review_required: list[dict[str, Any]] = []
    for row in pending:
        review_id = str((row or {}).get("id") or "").strip()
        if not review_id:
            continue
        contact = str(
            (row or {}).get("contact_email") or ""
        ).strip().lower()
        if contact and contact in seen_contacts:
            skipped += 1
            pending_skip_reasons.append(
                f"{review_id}:duplicate_normalized_contact"
            )
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
                if contact:
                    seen_contacts.add(contact)
            else:
                skipped += 1
                pending_skip_reasons.append(
                    f"{review_id}:auto_review_returned_{str((result or {}).get('status') or 'unknown')}"
                )
        except Exception as exc:
            skipped += 1
            message = str(exc)
            if "offer outside standing authority" in message:
                source_offer_key = str(
                    (row or {}).get("offer_key") or ""
                ).strip() or None
                canonical_offer_key = (
                    "search_growth_command"
                    if source_offer_key == "software_mrr"
                    else source_offer_key
                )
                founder_review_required.append({
                    "review_id": review_id,
                    "prospect_id": str(
                        (row or {}).get("prospect_id") or ""
                    ).strip() or None,
                    "contact_name": str(
                        (row or {}).get("contact_name") or ""
                    ).strip() or None,
                    "contact_title": str(
                        (row or {}).get("contact_title") or ""
                    ).strip() or None,
                    "contact_email": contact or None,
                    "offer_key": canonical_offer_key,
                    "source_offer_key": source_offer_key,
                    "company_score": (row or {}).get("company_score"),
                    "decision_score": (row or {}).get("decision_score"),
                    "proposed_at": (row or {}).get("proposed_at"),
                    "reason": "offer_outside_standing_authority",
                    "founder_gate_required": True,
                    "outbound_authorized": False,
                })
            else:
                pending_skip_reasons.append(
                    f"{review_id}:{type(exc).__name__}:{message[:180]}"
                )

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
            payload = build_outbound_payload(
                hydrated,
                now=current,
                optimizer_snapshot=optimizer_snapshot,
            )
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
                or "recipient outreach language unresolved" in message
                or "recipient_timezone_unresolved" in message
                or "recipient_timezone_invalid" in message
                or "outside_recipient_local_contact_window" in message
                or "recipient_local_weekend" in message
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
        deferred_reasons=tuple(deferred_reasons + pending_skip_reasons),
        founder_review_required=tuple(founder_review_required),
        proposal_errors=tuple(errors),
    )
