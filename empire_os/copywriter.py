"""Evidence-first Empire Copywriter.

The copywriter turns verified product, buyer and market evidence into
channel-specific commercial copy. It does not invent pricing, urgency,
outcomes, pain, revenue, guarantees, social proof or scarcity.

This is a deterministic foundation for the later LLM-backed copy agent.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from empire_os.outreach_message_optimizer import optimise_first_touch


SUPPORTED_CHANNELS = {
    "cold_email",
    "followup_email",
    "landing_hero",
    "ad_primary",
    "upsell",
    "mrr_expansion",
    "vsl_outline",
}

_PLACEHOLDERS = {
    "",
    "unknown",
    "your team",
    "your business",
    "your market",
    "n/a",
    "none",
    "null",
}


@dataclass(frozen=True)
class CopyBrief:
    channel: str
    objective: str
    product_code: str
    product_name: str
    audience: str
    business_name: str | None = None
    niche: str | None = None
    metro: str | None = None
    verified_price: str | None = None
    evidence: Mapping[str, Any] | None = None
    expansion_offer: str | None = None
    contact_title: str | None = None
    sender_email: str | None = None
    brand_domain: str | None = None
    enterprise_target: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CopyDraft:
    channel: str
    headline: str | None
    subject: str | None
    body: str
    cta: str
    evidence_used: tuple[str, ...]
    claims: tuple[str, ...]
    quality_tier: str
    requires_human_review: bool
    subject_variants: tuple[str, ...] = ()
    quality_review: Mapping[str, Any] | None = None
    sender_identity: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _usable(value: Any) -> str:
    text = _text(value)
    return "" if text.lower() in _PLACEHOLDERS else text


def _proof(evidence: Mapping[str, Any]) -> tuple[str | None, tuple[str, ...]]:
    refs: list[str] = []

    explicit = _usable(
        evidence.get("specific_proof")
        or evidence.get("proof_summary")
        or evidence.get("observed_proof")
    )
    if explicit:
        ref = _usable(
            evidence.get("proof_evidence_ref")
            or evidence.get("evidence_ref")
        )
        if ref:
            refs.append(ref)
        return explicit, tuple(refs)

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
        return (
            f"{rating:g}★ across {reviews:,} public reviews",
            ("public_profile_rating_reviews",),
        )
    if reviews is not None and reviews >= 25:
        return (
            f"{reviews:,} public reviews",
            ("public_profile_reviews",),
        )
    return None, tuple()


def _trigger(evidence: Mapping[str, Any]) -> tuple[str | None, tuple[str, ...]]:
    nested = evidence.get("why_now")
    row = nested if isinstance(nested, Mapping) else {}
    summary = _usable(
        row.get("summary")
        or evidence.get("why_now_summary")
        or evidence.get("trigger_summary")
    )
    ref = _usable(
        row.get("evidence_ref")
        or evidence.get("why_now_evidence_ref")
        or evidence.get("trigger_evidence_ref")
    )
    if summary and ref:
        return summary, (ref,)
    return None, tuple()


def _validate_brief(brief: CopyBrief) -> None:
    if brief.channel not in SUPPORTED_CHANNELS:
        raise ValueError(f"unsupported copy channel: {brief.channel}")
    if not _usable(brief.objective):
        raise ValueError("copy objective required")
    if not _usable(brief.product_code):
        raise ValueError("product code required")
    if not _usable(brief.product_name):
        raise ValueError("product name required")
    if not _usable(brief.audience):
        raise ValueError("audience required")


def _evidence_context(brief: CopyBrief) -> tuple[str | None, tuple[str, ...]]:
    evidence = brief.evidence if isinstance(brief.evidence, Mapping) else {}
    trigger, trigger_refs = _trigger(evidence)
    proof, proof_refs = _proof(evidence)

    if trigger:
        return trigger, trigger_refs
    if proof:
        return proof, proof_refs
    return None, tuple()


def build_copy(brief: CopyBrief) -> CopyDraft:
    _validate_brief(brief)

    business = _usable(brief.business_name)
    niche = _usable(brief.niche)
    metro = _usable(brief.metro)
    product = _usable(brief.product_name)
    audience = _usable(brief.audience)
    expansion = _usable(brief.expansion_offer)
    proof, evidence_refs = _evidence_context(brief)

    claims: list[str] = []
    if proof:
        claims.append(proof)

    if brief.channel in {"cold_email", "followup_email"}:
        if not business or not metro:
            raise ValueError("email copy requires business_name and metro")
        if not proof:
            raise ValueError(
                "email copy requires observed trigger or specific public proof"
            )

    if brief.channel == "cold_email":
        email_evidence = (
            brief.evidence if isinstance(brief.evidence, Mapping) else {}
        )
        trigger, _trigger_refs = _trigger(email_evidence)
        reason_now = trigger or (
            f"{business} has {proof}"
            if proof
            else ""
        )
        optimised = optimise_first_touch(
            business_name=business,
            reason_now=reason_now,
            proof=proof,
            contact_title=_usable(brief.contact_title) or None,
            territory=metro,
            sender_email=_usable(brief.sender_email) or None,
            brand_domain=_usable(brief.brand_domain) or None,
            enterprise_target=brief.enterprise_target,
        )
        subject_variants = tuple(
            str(row["subject"])
            for row in optimised["subject_variants"]
        )
        sender_identity = optimised.get("sender_identity")
        requires_review = bool(
            sender_identity
            and sender_identity.get("blockers")
        )
        return CopyDraft(
            channel=brief.channel,
            headline=None,
            subject=str(optimised["subject"]),
            body=str(optimised["body"]),
            cta=str(optimised["cta"]),
            evidence_used=evidence_refs,
            claims=tuple(claims),
            quality_tier="evidence_backed_optimised",
            requires_human_review=requires_review,
            subject_variants=subject_variants,
            quality_review=dict(optimised["quality"]),
            sender_identity=(
                dict(sender_identity)
                if isinstance(sender_identity, Mapping)
                else None
            ),
        )

    if brief.channel == "followup_email":
        body = (
            f"Quick follow-up on {business}. The useful part is still the "
            f"evidence: {proof}.\n\n"
            f"If {product} is relevant, I can send the short {metro} brief "
            "with the highest-priority signals and no deck."
        )
        return CopyDraft(
            channel=brief.channel,
            headline=None,
            subject=f"Re: {business}",
            body=body,
            cta="Reply “send it”.",
            evidence_used=evidence_refs,
            claims=tuple(claims),
            quality_tier="evidence_backed",
            requires_human_review=False,
        )

    if brief.channel == "landing_hero":
        headline = f"Turn market intelligence into recurring revenue."
        body = (
            f"{product} helps {audience} connect observed market evidence "
            "to prioritisation, commercial action and measurable revenue "
            "operations—without treating forecasts as revenue."
        )
        return CopyDraft(
            channel=brief.channel,
            headline=headline,
            subject=None,
            body=body,
            cta="See how the system works",
            evidence_used=evidence_refs,
            claims=tuple(claims),
            quality_tier="product_positioning",
            requires_human_review=False,
        )

    if brief.channel == "ad_primary":
        body = (
            f"More data is not the advantage. Knowing what changed, what "
            f"matters and what deserves action is. {product} gives "
            f"{audience} an evidence-first path from signal to commercial "
            "decision."
        )
        return CopyDraft(
            channel=brief.channel,
            headline=f"Intelligence before revenue does.",
            subject=None,
            body=body,
            cta="Explore the intelligence layer",
            evidence_used=evidence_refs,
            claims=tuple(claims),
            quality_tier="product_positioning",
            requires_human_review=True,
        )

    if brief.channel in {"upsell", "mrr_expansion"}:
        if not expansion:
            raise ValueError(
                "upsell and mrr_expansion copy require expansion_offer"
            )
        body = (
            f"You are already using {product}. The next logical layer is "
            f"{expansion}: it extends the same evidence trail into a broader "
            "commercial workflow rather than adding another disconnected "
            "tool."
        )
        return CopyDraft(
            channel=brief.channel,
            headline=f"Add {expansion} to your current Empire workflow",
            subject=None,
            body=body,
            cta="Review the expansion",
            evidence_used=evidence_refs,
            claims=tuple(claims),
            quality_tier="expansion_positioning",
            requires_human_review=False,
        )

    # VSL is intentionally an outline, not an autonomous publishable script.
    sections = [
        "1. Problem: commercial teams have data but not decision timing.",
        f"2. Mechanism: {product} converts observed evidence into prioritised action.",
        "3. Proof: show only verified product/customer evidence available at render time.",
        "4. Workflow: signal → decision → governed execution → economic truth.",
        "5. Expansion: monitoring, automation, data/API and managed execution.",
        "6. CTA: invite the viewer to inspect the evidence and next commercial step.",
    ]
    return CopyDraft(
        channel=brief.channel,
        headline=f"{product}: from signal to commercial action",
        subject=None,
        body="\n".join(sections),
        cta="See the evidence-backed workflow",
        evidence_used=evidence_refs,
        claims=tuple(claims),
        quality_tier="vsl_outline",
        requires_human_review=True,
    )
