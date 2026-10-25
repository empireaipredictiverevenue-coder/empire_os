"""Evidence-first commercial conversation copy.

This module keeps outreach specific without inventing pain, demand, urgency,
results or revenue. Fresh trigger evidence is preferred; public business proof
is an acceptable lower-confidence reason to start a useful conversation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.outreach_message_optimizer import optimise_first_touch

POSTAL_ADDRESS = "31 St Thomas St, Bolton, BL1 2QR, UK"
_PLACEHOLDERS = {
    "", "unknown", "your team", "your market", "local market",
    "n/a", "none", "null",
}


@dataclass(frozen=True)
class ConversationCopy:
    subject: str
    body: str
    quality_tier: str
    why_now_summary: str | None
    why_now_evidence_ref: str | None
    specific_proof: str | None
    subject_variants: tuple[str, ...] = ()
    quality_review: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _first_name(value: Any) -> str:
    clean = _text(value)
    if not clean:
        raise ValueError("contact name required")
    first = clean.split()[0]
    return first.title() if first.isupper() else first


def _usable(value: Any) -> str:
    text = _text(value)
    return "" if text.lower() in _PLACEHOLDERS else text


def _parse_time(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fresh_why_now(
    evidence: Mapping[str, Any],
    *,
    now: datetime,
    max_age_hours: int = 24 * 30,
) -> dict[str, str] | None:
    nested = evidence.get("why_now")
    row = dict(nested) if isinstance(nested, Mapping) else {}
    summary = _usable(
        row.get("summary")
        or evidence.get("why_now_summary")
        or evidence.get("trigger_summary")
    )
    evidence_ref = _usable(
        row.get("evidence_ref")
        or evidence.get("why_now_evidence_ref")
        or evidence.get("trigger_evidence_ref")
    )
    observed_at = _parse_time(
        row.get("observed_at")
        or evidence.get("why_now_observed_at")
        or evidence.get("trigger_observed_at")
    )
    signal_type = _usable(
        row.get("signal_type")
        or evidence.get("why_now_signal_type")
        or evidence.get("trigger_type")
    )
    if not summary or not evidence_ref or observed_at is None:
        return None
    age_hours = (now.astimezone(timezone.utc) - observed_at).total_seconds() / 3600
    if age_hours < 0 or age_hours > max_age_hours:
        return None
    return {
        "summary": summary,
        "evidence_ref": evidence_ref,
        "observed_at": observed_at.isoformat(),
        "signal_type": signal_type or "market signal",
    }


def _specific_public_proof(evidence: Mapping[str, Any]) -> str | None:
    explicit = _usable(
        evidence.get("specific_proof")
        or evidence.get("proof_summary")
        or evidence.get("observed_proof")
    )
    if explicit:
        return explicit

    rating_raw = evidence.get("rating")
    reviews_raw = evidence.get("review_count")
    try:
        rating = float(rating_raw) if rating_raw not in (None, "") else None
    except (TypeError, ValueError):
        rating = None
    try:
        reviews = int(reviews_raw) if reviews_raw not in (None, "") else None
    except (TypeError, ValueError):
        reviews = None

    if rating is not None and reviews is not None and reviews > 0:
        rating_text = f"{rating:.1f}".rstrip("0").rstrip(".")
        return f"your public profile shows {rating_text}★ across {reviews:,} reviews"
    if reviews is not None and reviews >= 25:
        return f"your public profile shows {reviews:,} reviews"
    return None


def _context(evidence: Mapping[str, Any]) -> tuple[str, str, str]:
    business = _usable(evidence.get("business_name"))
    niche = _usable(evidence.get("niche"))
    metro = _usable(evidence.get("metro"))
    missing = [
        key for key, value in (
            ("business_name", business),
            ("niche", niche),
            ("metro", metro),
        )
        if not value
    ]
    if missing:
        raise ValueError("conversation context missing: " + ",".join(missing))
    return business, niche, metro


def build_first_touch_copy(
    review: Mapping[str, Any],
    *,
    now: datetime,
) -> ConversationCopy:
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    evidence = review.get("evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}
    business, niche, metro = _context(evidence)
    first = _first_name(review.get("contact_name"))
    trigger = _fresh_why_now(evidence, now=now)
    proof = _specific_public_proof(evidence)

    if trigger is None and proof is None:
        raise ValueError(
            "specific outreach evidence required: fresh why-now or public proof"
        )

    reason_now = trigger["summary"] if trigger is not None else proof
    proof_for_copy = (
        reason_now
        if trigger is not None
        else proof
    )
    optimised = optimise_first_touch(
        business_name=business,
        reason_now=reason_now or "",
        proof=proof_for_copy or "",
        contact_title=_usable(review.get("contact_title")) or None,
        territory=metro,
    )
    quality = (
        "trigger_backed_optimised"
        if trigger is not None
        else "proof_backed_optimised"
    )
    body = (
        f"Hi {first},\n\n"
        f"{optimised['body']}\n\n"
        "Best,\nPhil\nFounder, Empire AI\nempire-ai.co.uk\n\n"
        f"{POSTAL_ADDRESS}\n"
        "If you’d rather not hear from me, reply “opt out”."
    )
    return ConversationCopy(
        subject=str(optimised["subject"]),
        body=body,
        quality_tier=quality,
        why_now_summary=(trigger["summary"] if trigger else None),
        why_now_evidence_ref=(trigger["evidence_ref"] if trigger else None),
        specific_proof=proof,
        subject_variants=tuple(
            str(row["subject"])
            for row in optimised["subject_variants"]
        ),
        quality_review=dict(optimised["quality"]),
    )


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _entry_offer_for_followup(
    row: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Pick a verified low-friction entry offer without claiming company size.

    The router uses observable commercial signals only. It does not assert that
    a business is small, medium or enterprise; it simply lowers friction for
    lighter-signal owner-led accounts and preserves the managed pilot for the
    strongest opportunities.
    """
    company_score = _number(row.get("company_score"))
    review_count = int(_number(evidence.get("review_count")))
    buy_signal_score = _number(evidence.get("buy_signal_score"))

    # High intent alone does not justify a high-friction offer. Preserve
    # the $1,500 pilot for accounts with stronger scale evidence; otherwise
    # start with a verified one-off entry product and earn the upsell.
    if company_score >= 90 or review_count >= 1000:
        return {
            "product_code": "managed_service",
            "name": "Empire Opportunity Intelligence Pilot",
            "price_text": "$1,500 flat pilot",
            "cta": "pilot",
        }
    if company_score >= 80 or review_count >= 300 or buy_signal_score >= 90:
        return {
            "product_code": "search_opportunity_map",
            "name": "Search Opportunity Map",
            "price_text": "$249 one-off",
            "cta": "map",
        }
    return {
        "product_code": "competitor_search_gap",
        "name": "Competitor Search Gap",
        "price_text": "$199 one-off",
        "cta": "gap",
    }


def build_followup_copy(
    row: Mapping[str, Any],
    *,
    step: int,
    now: datetime,
) -> ConversationCopy:
    """No-reply NURTURE. Never promote scores into a price, offer or CTA.

    Only the separate original authenticated-buyer-reply intent gate can
    suggest a human-reviewed CTA. This worker has NO authenticated reply
    context and therefore NO commercial offer authority.
    """
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    if step not in (1, 2):
        raise ValueError("follow-up step must be 1 or 2")
    evidence = row.get("candidate_evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}
    business, niche, metro = _context(evidence)
    trigger = _fresh_why_now(evidence, now=now)
    # A rating, a prospect score, an ad flag or an unevidenced 'opportunity'
    # is not a sufficiently fresh new insight to justify another cold touch.
    if trigger is None:
        raise ValueError("FRESH_SOURCE_BACKED_VALUE_REQUIRED_BEFORE_NURTURE")
    ref = trigger["evidence_ref"]
    if step == 2:
        prior = row.get("prior_evidence_refs")
        if (not isinstance(prior, (list, tuple)) or not prior
                or not all(isinstance(item, str) and item.strip() for item in prior)
                or ref in prior):
            raise ValueError("SECOND_TOUCH_NEW_SOURCE_EVIDENCE_REQUIRED")
    root_subject = _usable(row.get("root_subject"))
    subject = f"Re: {root_subject}" if root_subject else f"{business} — observed update"
    observed = trigger["summary"]
    if step == 1:
        message = (
            "Hi,\n\n"
            f"One source-backed observation relevant to {business}: {observed}.\n"
            f"Source reference: {ref}.\n\n"
            f"For {niche} in {metro}, this is worth checking against the "
            "published coverage and service details before drawing conclusions. "
            "It's not evidence that your business needs a service or has a "
            "particular commercial problem.\n\n"
        )
    else:
        message = (
            "Hi,\n\n"
            f"A separate, newer source-backed observation relevant to "
            f"{business}: {observed}.\nSource reference: {ref}.\n\n"
            "This is an update to the earlier research, not a sales "
            "assessment or an assumption about your buying plans.\n\n"
        )
    body = (
        message
        + "Best,\nPhil\nFounder, Empire AI\nempire-ai.co.uk\n\n"
        + POSTAL_ADDRESS
        + "\nIf you’d rather not hear from me, reply “opt out”."
    )
    return ConversationCopy(
        subject=subject,
        body=body,
        quality_tier="source_backed_nurture_no_commercial_cta",
        why_now_summary=trigger["summary"],
        why_now_evidence_ref=ref,
        specific_proof=_specific_public_proof(evidence),
    )
