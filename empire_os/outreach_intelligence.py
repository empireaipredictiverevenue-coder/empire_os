"""Evidence-backed Outreach Intelligence for Empire AI.

Pure planning only. This module does not send email/SMS/voice, mutate CRM,
approve intents, book meetings, or activate buyers. It turns real buyer,
market, corridor and conversation evidence into an operator-review packet.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from empire_os.outbound_strategy import build_contact_channel_plan
from empire_os.outreach_account_strategy import (
    build_buying_committee,
    choose_introduction_path,
    evaluate_contact_fatigue,
)
from empire_os.outreach_quality import (
    build_message_brief,
    review_deliverability,
)


ALLOWED_PLAY_TYPES = {
    "new_buyer",
    "seat_expansion",
    "territory_expansion",
    "capacity_fill",
    "renewal",
    "reactivation",
    "managed_service_cross_sell",
    "intelligence_cross_sell",
}

TRIGGER_PRIORITY = {
    "permit": 100,
    "storm": 100,
    "buyer_capacity": 95,
    "territory_open": 95,
    "market_demand": 90,
    "renewal_window": 90,
    "search_gap": 80,
    "ai_visibility_gap": 80,
    "competitor_move": 75,
    "reactivation_window": 75,
    "website_change": 70,
    "hiring": 65,
    "content_engagement": 60,
    "reply_engagement": 60,
}

STOP_REPLY_CLASSES = {"unsubscribe", "negative"}
REVIEW_REPLY_CLASSES = {"positive", "question", "objection", "later", "other"}


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class OutreachTrigger:
    signal_type: str
    summary: str
    source: str
    observed_at: str
    confidence: float
    evidence_ref: str
    age_hours: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OutreachStep:
    step: int
    earliest_day: int
    channel: str
    purpose: str
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def choose_play_type(context: Mapping[str, Any]) -> str:
    explicit = _text(context.get("play_type")).lower()
    if explicit:
        if explicit not in ALLOWED_PLAY_TYPES:
            raise ValueError(f"unsupported play_type: {explicit}")
        return explicit

    if context.get("renewal_due") is True:
        return "renewal"
    if context.get("reactivation_candidate") is True:
        return "reactivation"
    if context.get("existing_buyer") is True and context.get("territory_expansion_ready") is True:
        return "territory_expansion"
    if context.get("existing_buyer") is True and context.get("seat_expansion_ready") is True:
        return "seat_expansion"
    if context.get("existing_buyer") is True and context.get("capacity_headroom") is True:
        return "capacity_fill"
    if context.get("existing_buyer") is True and context.get("managed_service_fit") is True:
        return "managed_service_cross_sell"
    if context.get("existing_buyer") is True and context.get("intelligence_fit") is True:
        return "intelligence_cross_sell"
    return "new_buyer"


def choose_trigger(
    signals: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    max_age_hours: int = 24 * 30,
) -> OutreachTrigger | None:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    candidates: list[tuple[float, OutreachTrigger]] = []

    for raw in signals or ():
        signal_type = _text(raw.get("signal_type")).lower()
        summary = _text(raw.get("summary"))
        source = _text(raw.get("source"))
        evidence_ref = _text(raw.get("evidence_ref"))
        observed_at = _parse_time(raw.get("observed_at"))
        confidence = _number(raw.get("confidence"))
        if (
            signal_type not in TRIGGER_PRIORITY
            or not summary
            or not source
            or not evidence_ref
            or observed_at is None
            or confidence is None
            or not 0 <= confidence <= 1
        ):
            continue
        age_hours = (now - observed_at).total_seconds() / 3600
        if age_hours < 0 or age_hours > max_age_hours:
            continue
        recency = max(0.0, 1.0 - (age_hours / max_age_hours))
        rank = TRIGGER_PRIORITY[signal_type] + (confidence * 20) + (recency * 10)
        candidates.append(
            (
                rank,
                OutreachTrigger(
                    signal_type=signal_type,
                    summary=summary,
                    source=source,
                    observed_at=observed_at.isoformat(),
                    confidence=round(confidence, 4),
                    evidence_ref=evidence_ref,
                    age_hours=round(age_hours, 2),
                ),
            )
        )

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def build_sequence(
    channel_plan: Mapping[str, Any],
    *,
    introduction_path: Mapping[str, Any] | None = None,
) -> list[OutreachStep]:
    """Create a recommendation-only cadence from evidence-backed paths."""
    steps: list[OutreachStep] = []

    if introduction_path is not None:
        intro_kind = _text(introduction_path.get("kind"))
        if intro_kind:
            steps.append(
                OutreachStep(
                    1,
                    0,
                    intro_kind,
                    "operator review for verified warm introduction",
                )
            )

    primary = channel_plan.get("primary")
    direct_day = 3 if introduction_path is not None else 0
    if isinstance(primary, Mapping) and _text(primary.get("channel")):
        primary_channel = _text(primary.get("channel"))
        steps.append(
            OutreachStep(
                len(steps) + 1,
                direct_day,
                primary_channel,
                "evidence-led initial contact",
            )
        )
        steps.append(
            OutreachStep(
                len(steps) + 1,
                direct_day + 3,
                primary_channel,
                "short proof-led follow-up",
            )
        )
        steps.append(
            OutreachStep(
                len(steps) + 1,
                direct_day + 7,
                primary_channel,
                "final value-led follow-up",
            )
        )

    # Company phone never becomes an automatic direct-person call. It can only
    # appear as an operator-review fallback when verified.
    company_fallbacks = channel_plan.get("company_fallbacks") or []
    if company_fallbacks:
        first = company_fallbacks[0]
        if isinstance(first, Mapping) and _text(first.get("channel")) == "voice":
            steps.append(
                OutreachStep(
                    len(steps) + 1,
                    direct_day + 10,
                    "voice",
                    "manual company-switchboard review; do not infer person binding",
                )
            )
    return steps


def reply_next_action(classification: Any) -> dict[str, Any]:
    label = _text(classification).lower() or "other"
    if label == "unsubscribe":
        action = "suppress_and_close"
    elif label == "negative":
        action = "close_without_followup"
    elif label == "later":
        action = "operator_review_for_snooze"
    elif label == "positive":
        action = "closer_review"
    elif label == "question":
        action = "answer_review"
    elif label == "objection":
        action = "objection_brief_review"
    else:
        action = "human_review"
    return {
        "classification": label,
        "recommended_action": action,
        "automatic_send": False,
        "crm_mutation": False,
        "execution_authority": "none",
    }


def _content_assets(play_type: str, trigger: OutreachTrigger | None) -> list[str]:
    assets = ["one-page proof brief", "buyer/corridor economics snapshot"]
    if play_type in {"territory_expansion", "seat_expansion", "capacity_fill"}:
        assets.append("territory/capacity opportunity brief")
    if play_type == "renewal":
        assets.append("realized outcome and renewal review")
    if play_type == "reactivation":
        assets.append("what-changed-since-last-contact brief")
    if trigger is not None:
        if trigger.signal_type == "permit":
            assets.append("permit opportunity brief")
        elif trigger.signal_type == "storm":
            assets.append("storm/territory evidence brief")
        elif trigger.signal_type in {"search_gap", "ai_visibility_gap"}:
            assets.append("search/AI visibility gap report")
        elif trigger.signal_type in {"market_demand", "territory_open"}:
            assets.append("market/territory intelligence report")
    return list(dict.fromkeys(assets))


def build_outreach_packet(
    *,
    account: Mapping[str, Any],
    contact_plan: Mapping[str, Any],
    context: Mapping[str, Any],
    signals: Iterable[Mapping[str, Any]] = (),
    channel_evidence: Iterable[Mapping[str, Any]] = (),
    proof_refs: Iterable[str] = (),
    predicted_economics: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a fail-closed outreach packet from explicit evidence."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    account_id = _text(account.get("account_id"))
    business_name = _text(account.get("business_name"))
    if not account_id or not business_name:
        raise ValueError("account_id and business_name are required")

    play_type = choose_play_type(context)
    trigger = choose_trigger(signals, now=now)
    channel_plan = build_contact_channel_plan(
        contact_plan,
        channel_evidence=channel_evidence,
    )
    committee = build_buying_committee(context.get("buying_committee") or ())
    introduction_path = choose_introduction_path(
        context.get("introduction_paths") or ()
    )
    fatigue = evaluate_contact_fatigue(
        context.get("prior_touches") or (),
        now=now,
    )
    deliverability = review_deliverability(
        context.get("deliverability_evidence")
    )
    sequence = build_sequence(
        channel_plan,
        introduction_path=introduction_path,
    )

    evidence_refs = [
        _text(ref) for ref in proof_refs if _text(ref)
    ]
    if trigger is not None and trigger.evidence_ref not in evidence_refs:
        evidence_refs.append(trigger.evidence_ref)
    if introduction_path is not None:
        intro_ref = _text(introduction_path.get("evidence_ref"))
        if intro_ref and intro_ref not in evidence_refs:
            evidence_refs.append(intro_ref)

    prediction = dict(predicted_economics or {})
    expected_revenue = _number(prediction.get("expected_revenue_cents"))
    expected_cost = _number(prediction.get("expected_cost_cents"))
    expected_gross_profit = _number(prediction.get("expected_gross_profit_cents"))
    if (
        expected_gross_profit is None
        and expected_revenue is not None
        and expected_cost is not None
    ):
        expected_gross_profit = expected_revenue - expected_cost

    blockers: list[str] = []
    if channel_plan.get("primary") is None and introduction_path is None:
        blockers.append("no_verified_contact_or_intro_path")
    if trigger is None:
        blockers.append("no_fresh_evidence_backed_trigger")
    if not evidence_refs:
        blockers.append("no_proof_evidence")
    if context.get("suppressed") is True:
        blockers.append("recipient_suppressed")
    if context.get("outreach_ready") is not True:
        blockers.append("outreach_readiness_unverified")
    if context.get("bound_to_decision_maker") is not True:
        blockers.append("decision_maker_binding_unverified")
    blockers.extend(fatigue["blockers"])

    contact_name = _text(account.get("contact_name"))
    contact_title = _text(account.get("contact_title"))
    offer_key = _text(context.get("offer_key"))
    corridor_key = _text(context.get("corridor_key"))
    territory = _text(context.get("territory"))

    reason_now = (
        trigger.summary
        if trigger is not None
        else "No fresh evidence-backed trigger is available."
    )

    entry_strategy = (
        "verified_warm_intro_review"
        if introduction_path is not None
        else (
            "verified_direct_channel_review"
            if channel_plan.get("primary") is not None
            else "blocked"
        )
    )

    predicted_summary = {
        "expected_revenue_cents": expected_revenue,
        "expected_cost_cents": expected_cost,
        "expected_gross_profit_cents": expected_gross_profit,
        "prediction_ref": _text(prediction.get("prediction_ref")) or None,
        "confidence": _number(prediction.get("confidence")),
        "actual_revenue": False,
    }
    message_brief = build_message_brief(
        business_name=business_name,
        contact_name=contact_name or None,
        contact_title=contact_title or None,
        play_type=play_type,
        offer_key=offer_key or None,
        corridor_key=corridor_key or None,
        territory=territory or None,
        reason_now=reason_now,
        evidence_refs=evidence_refs,
        predicted_economics=predicted_summary,
    )

    return {
        "schema_version": "outreach_intelligence.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "send_enabled": False,
        "sms_enabled": False,
        "voice_dial_enabled": False,
        "booking_execution": False,
        "crm_mutation": False,
        "buyer_activation": False,
        "account": {
            "account_id": account_id,
            "business_name": business_name,
            "contact_name": contact_name or None,
            "contact_title": contact_title or None,
        },
        "commercial_context": {
            "play_type": play_type,
            "offer_key": offer_key or None,
            "corridor_key": corridor_key or None,
            "territory": territory or None,
        },
        "trigger": trigger.as_dict() if trigger is not None else None,
        "reason_now": reason_now,
        "entry_strategy": entry_strategy,
        "introduction_path": introduction_path,
        "buying_committee": committee,
        "contact_fatigue": fatigue,
        "deliverability": deliverability,
        "channel_plan": channel_plan,
        "sequence": [step.as_dict() for step in sequence],
        "message_brief": message_brief,
        "proof_pack": {
            "evidence_refs": evidence_refs,
            "content_assets": _content_assets(play_type, trigger),
        },
        "predicted_economics": predicted_summary,
        "stop_conditions": [
            "unsubscribe",
            "negative reply",
            "complaint",
            "hard bounce",
            "do-not-contact/suppression",
            "contact evidence invalidated",
            "decision-maker binding invalidated",
            "contact fatigue/cooldown reached",
        ],
        "reply_routing": {
            label: reply_next_action(label)
            for label in sorted(STOP_REPLY_CLASSES | REVIEW_REPLY_CLASSES)
        },
        "attribution": {
            "account_id": account_id,
            "campaign_key": _text(context.get("campaign_key")) or None,
            "offer_key": offer_key or None,
            "corridor_key": corridor_key or None,
            "territory": territory or None,
            "prediction_ref": _text(prediction.get("prediction_ref")) or None,
        },
        "review_ready": not blockers,
        "send_gate_ready": not blockers and deliverability["ready_for_send_review"],
        "blockers": list(dict.fromkeys(blockers)),
    }
