"""Composable Empire Revenue Actor for Intent Brain + Intent JEV."""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.intent_brain import assess_intent
from empire_os.intent_jev import adjudicate_intent
from empire_os.revenue_actor import (
    ActorDescriptor,
    build_actor_envelope,
    validate_actor_envelope,
)


DESCRIPTOR = ActorDescriptor(
    actor_key="intent_brain",
    actor_version="1.0.0",
    purpose=(
        "Classify commercial intent, actor, niche, pain, urgency, "
        "buying stage, identity state and economic fit, then apply "
        "independent JEV adjudication."
    ),
    input_schema="empire.intent_observation.v1",
    output_schema="empire.intent_actor_decision.v1",
    policy_version="intent_brain_policy.v1",
    model_version=None,
)


NEXT_ACTION = {
    "REJECT": "none",
    "WATCH": "observe_for_additional_evidence",
    "RESOLVE_IDENTITY": "resolve_first_party_identity",
    "NEEDS_REVIEW": "human_or_governed_review",
    "BUYER_SCOUT_SEED": "submit_bounded_buyer_scout_seed",
}


def _evidence_refs(payload: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []

    url = str(payload.get("url") or "").strip()
    if url:
        refs.append(url)

    values = payload.get("evidence_urls")
    if isinstance(values, (list, tuple)):
        refs.extend(
            str(value).strip()
            for value in values
            if str(value).strip()
        )

    return list(dict.fromkeys(refs))


def run_intent_brain_actor(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    brain = assess_intent(payload)
    jev = adjudicate_intent(brain)

    decision = str(
        jev.get("recommendation")
        or brain.get("decision")
        or "WATCH"
    )

    blockers = list(jev.get("blockers") or ())
    supports = list(jev.get("supports") or ())

    output = {
        "intent_brain": brain,
        "jev": jev,
        "commercial_state": {
            "actor_state": brain.get("actor_type"),
            "signal_orientation": brain.get("signal_orientation"),
            "intent_state": brain.get("intent_state"),
            "identity_state": brain.get("identity_state"),
            "buying_stage": brain.get("buying_stage"),
            "economic_state": (
                dict(brain.get("economic_fit") or {}).get("band")
            ),
            "niche": brain.get("niche"),
            "niche_path": brain.get("niche_path"),
            "pain_points": brain.get("pain_points"),
            "urgency": brain.get("urgency"),
        },
    }

    envelope = build_actor_envelope(
        descriptor=DESCRIPTOR,
        actor_input=dict(payload),
        decision=decision,
        recommended_next_action=NEXT_ACTION.get(
            decision,
            "human_or_governed_review",
        ),
        output=output,
        evidence_refs=_evidence_refs(payload),
        truth_class="mixed",
        confidence=dict(brain.get("confidence") or {}),
        blockers=blockers,
        supports=supports,
        execution_authority="none",
    )

    return validate_actor_envelope(envelope)
