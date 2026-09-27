"""Bounded bridge from evidence-complete buyer reviews to outbound intents.

This module does not send email. It only:
1. asks the existing standing-authority RPC to review pending managed-service
   candidates that already satisfy the database evidence policy; and
2. proposes a compliant first-touch outbound intent for fresh approved reviews.

The Outbound Governor remains the only component that may approve/send the
intent, under its own caps, suppression checks and personhood revalidation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from empire_os.buyer_discovery import looks_like_person_name
from empire_os.gtm_standing_bridge_repository import (
    CanonicalStandingBridgeRepository,
    RequestStandingBridgeRepository,
    StandingBridgeRepository,
)


Request = Callable[..., Any]

POSTAL_ADDRESS = "31 St Thomas St, Bolton, BL1 2QR, UK"
PROPOSED_BY = "gtm-standing-authority"
COPY_VARIANT = "short_evidence_brief_v2"


@dataclass(frozen=True)
class StandingBridgeResult:
    pending_seen: int
    auto_reviewed: int
    review_errors: tuple[str, ...]
    approved_ready: int
    outbound_proposed: int
    skipped_invalid_person: int
    skipped_company_routed_pending: int
    skipped_company_routed_outbound: int
    outbound_errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "pending_seen": self.pending_seen,
            "auto_reviewed": self.auto_reviewed,
            "review_errors": list(self.review_errors),
            "approved_ready": self.approved_ready,
            "outbound_proposed": self.outbound_proposed,
            "skipped_invalid_person": self.skipped_invalid_person,
            "skipped_company_routed_pending": self.skipped_company_routed_pending,
            "skipped_company_routed_outbound": self.skipped_company_routed_outbound,
            "outbound_errors": list(self.outbound_errors),
            "outbound_sent": False,
            "payment_mutation": False,
            "revenue_recognition": False,
        }


def _resolve_repository(
    request: Request | None,
    repository: StandingBridgeRepository | None,
) -> StandingBridgeRepository:
    if request is not None and repository is not None:
        raise ValueError("provide request or repository, not both")
    if repository is not None:
        return repository
    if request is not None:
        return RequestStandingBridgeRepository(request)
    return CanonicalStandingBridgeRepository.from_environment()

def _is_company_routed(review: Mapping[str, Any]) -> bool:
    evidence = review.get("evidence")
    if not isinstance(evidence, Mapping):
        return False
    return str(evidence.get("contact_route") or "").strip().lower() == "company_routed"


def _first_name(value: Any) -> str:
    text = str(value or "").strip()
    return text.split()[0] if text else ""


def _normalized_words(value: Any) -> list[str]:
    text = str(value or "").strip().casefold()
    cleaned = "".join(
        ch if ch.isalnum() else " "
        for ch in text
    )
    return [word for word in cleaned.split() if word]


def _looks_like_real_person_for_business(
    contact_name: Any,
    business_name: Any,
) -> bool:
    if not looks_like_person_name(contact_name):
        return False

    contact_words = _normalized_words(contact_name)
    business_words = _normalized_words(business_name)
    if not contact_words or not business_words:
        return True

    contact = " ".join(contact_words)
    business = " ".join(business_words)
    if contact == business:
        return False

    prefix = " ".join(business_words[: len(contact_words)])
    if len(contact_words) >= 2 and contact == prefix:
        return False

    generic = {
        "team", "company", "services", "service", "office",
        "sales", "support", "contact", "referral", "program",
    }
    if set(contact_words) & generic:
        return False

    return True


def _message(review: Mapping[str, Any]) -> tuple[str, str]:
    evidence = review.get("evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}
    contact_name = str(review.get("contact_name") or "").strip()
    business_name = str(
        evidence.get("business_name") or "your business"
    ).strip()
    metro = str(evidence.get("metro") or "").strip()
    first = _first_name(contact_name)

    subject = f"{first} — quick idea for {business_name}"
    location = f" in {metro}" if metro else ""
    body = (
        f"Hi {first},\n\n"
        f"I’m Phil, founder of Empire AI. I can put together a one-page "
        f"opportunity brief for {business_name}{location} using public "
        f"market evidence and your public business information — no deck, "
        f"just a few concrete opportunities and the first test I’d run.\n\n"
        f"Worth sending over?\n\n"
        f"Phil\n"
        f"Founder, Empire AI\n"
        f"empire-ai.co.uk\n\n"
        f"{POSTAL_ADDRESS}\n"
        f"If you’d rather not hear from me, reply “opt out”."
    )
    return subject, body


def run_standing_bridge(
    request: Request | None = None,
    *,
    repository: StandingBridgeRepository | None = None,
    review_limit: int = 20,
    outbound_limit: int = 20,
    daily_cap: int = 25,
    now: datetime | None = None,
) -> StandingBridgeResult:
    cap = max(1, min(int(daily_cap), 50))
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expires_at = (current + timedelta(hours=24)).isoformat()
    store = _resolve_repository(request, repository)

    pending = store.pending_reviews(limit=review_limit)
    auto_reviewed = 0
    skipped_company_routed_pending = 0
    review_errors: list[str] = []

    for row in pending:
        if _is_company_routed(row):
            skipped_company_routed_pending += 1
            continue
        review_id = str(row.get("id") or "").strip()
        if not review_id:
            continue
        try:
            result = store.auto_review(
                review_id,
                daily_cap=cap,
            )
            if (
                isinstance(result, Mapping)
                and result.get("status") == "approved"
            ):
                auto_reviewed += 1
        except Exception as exc:
            review_errors.append(
                f"{review_id}:{type(exc).__name__}:{str(exc)[:180]}"
            )

    ready = store.approved_for_outbound(
        limit=outbound_limit,
    )
    outbound_proposed = 0
    skipped_invalid_person = 0
    skipped_company_routed_outbound = 0
    outbound_errors: list[str] = []

    for review in ready:
        if _is_company_routed(review):
            skipped_company_routed_outbound += 1
            continue
        review_id = str(review.get("id") or "").strip()
        contact_name = str(
            review.get("contact_name") or ""
        ).strip()
        if not review_id:
            continue
        evidence = review.get("evidence")
        evidence = evidence if isinstance(evidence, Mapping) else {}
        business_name = str(
            evidence.get("business_name") or ""
        ).strip()
        if not _looks_like_real_person_for_business(
            contact_name,
            business_name,
        ):
            skipped_invalid_person += 1
            continue

        subject, body = _message(review)
        try:
            result = store.propose_outbound_intent({
                    "p_review_id": review_id,
                    "p_subject": subject,
                    "p_body_text": body,
                    "p_body_html": None,
                    "p_idempotency_key": (
                        f"standing-outbound:{review_id}:v2"
                    ),
                    "p_proposed_by": PROPOSED_BY,
                    "p_expires_at": expires_at,
                    "p_metadata": {
                        "source": "gtm_standing_bridge_v1",
                        "copy_variant": COPY_VARIANT,
                        "automatic_send": False,
                    },
                })
            if (
                isinstance(result, Mapping)
                and result.get("intent_id")
            ):
                outbound_proposed += 1
        except Exception as exc:
            outbound_errors.append(
                f"{review_id}:{type(exc).__name__}:{str(exc)[:180]}"
            )

    return StandingBridgeResult(
        pending_seen=len(pending),
        auto_reviewed=auto_reviewed,
        review_errors=tuple(review_errors),
        approved_ready=len(ready),
        outbound_proposed=outbound_proposed,
        skipped_invalid_person=skipped_invalid_person,
        skipped_company_routed_pending=skipped_company_routed_pending,
        skipped_company_routed_outbound=skipped_company_routed_outbound,
        outbound_errors=tuple(outbound_errors),
    )
