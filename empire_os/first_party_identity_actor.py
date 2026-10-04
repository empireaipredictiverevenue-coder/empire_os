"""Governed first-party identity actor for Empire Revenue Actors.

This actor does not discover or guess company identity.

It consumes only:
- a previously qualified RESOLVE_IDENTITY intent decision;
- an observed business name;
- a verified first-party company website.

Only after those gates pass may Empire's existing identity recovery stack
resolve a named commercial decision maker.

No outbound, canonical promotion, payment or revenue authority exists here.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from empire_os.identity_recovery import recover_identity
from empire_os.revenue_actor import (
    ActorDescriptor,
    build_actor_envelope,
    validate_actor_envelope,
)


DESCRIPTOR = ActorDescriptor(
    actor_key="first_party_identity",
    actor_version="1.0.0",
    purpose=(
        "Resolve a named commercial decision maker from a verified "
        "first-party company website using Empire identity recovery."
    ),
    input_schema="empire.identity_resolution_request.v1",
    output_schema="empire.identity_resolution_decision.v1",
    policy_version="first_party_identity_policy.v1",
    model_version=None,
)


RecoveryFn = Callable[..., Mapping[str, Any]]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _identity_evidence_refs(
    recovery: Mapping[str, Any],
    website: str,
) -> list[str]:
    refs = [website] if website else []

    identity = recovery.get("identity")
    if isinstance(identity, Mapping):
        source_url = _clean(identity.get("source_url"))
        if source_url:
            refs.append(source_url)

    evidence = recovery.get("evidence")
    if isinstance(evidence, (list, tuple)):
        for row in evidence:
            if not isinstance(row, Mapping):
                continue
            source_url = _clean(row.get("source_url"))
            if source_url:
                refs.append(source_url)

    return list(dict.fromkeys(refs))


def run_first_party_identity_actor(
    payload: Mapping[str, Any],
    *,
    recovery_fn: RecoveryFn = recover_identity,
) -> dict[str, Any]:
    upstream_decision = _clean(
        payload.get("upstream_decision")
        or payload.get("intent_decision")
    )

    business_name = _clean(payload.get("business_name"))
    website = _clean(payload.get("website"))
    metro = _clean(payload.get("metro"))
    niche = _clean(payload.get("niche"))

    site_verified = (
        payload.get("first_party_site_verified") is True
        or payload.get("canonical_business_site_verified") is True
    )

    blockers: list[str] = []
    supports: list[str] = []

    if upstream_decision != "RESOLVE_IDENTITY":
        decision = "NOT_ELIGIBLE"
        next_action = "none"
        blockers.append(
            "upstream_intent_not_approved_for_identity_resolution"
        )

        output = {
            "business_name": business_name or None,
            "website": website or None,
            "business_site_verified": site_verified,
            "identity_verified": False,
            "decision_maker": None,
            "recovery": None,
        }

    elif not business_name:
        decision = "NEEDS_BUSINESS_IDENTITY"
        next_action = "resolve_business_identity"
        blockers.append("business_name_unresolved")

        output = {
            "business_name": None,
            "website": website or None,
            "business_site_verified": site_verified,
            "identity_verified": False,
            "decision_maker": None,
            "recovery": None,
        }

    elif not website:
        decision = "NEEDS_BUSINESS_IDENTITY"
        next_action = "resolve_business_first_party_site"
        blockers.append("first_party_business_site_missing")

        output = {
            "business_name": business_name,
            "website": None,
            "business_site_verified": False,
            "identity_verified": False,
            "decision_maker": None,
            "recovery": None,
        }

    elif not site_verified:
        decision = "VERIFY_BUSINESS_SITE"
        next_action = "verify_first_party_business_site"
        blockers.append("first_party_business_site_unverified")

        output = {
            "business_name": business_name,
            "website": website,
            "business_site_verified": False,
            "identity_verified": False,
            "decision_maker": None,
            "recovery": None,
        }

    else:
        supports.append("verified_business_identity_anchor")
        supports.append("verified_first_party_business_site")

        recovery = recovery_fn(
            business_name=business_name,
            website=website,
            metro=metro,
            max_search_results=8,
        )

        if not isinstance(recovery, Mapping):
            recovery = {
                "recovered": False,
                "identity": None,
                "sources_tried": [],
                "evidence": [],
            }

        identity = recovery.get("identity")
        identity = (
            dict(identity)
            if isinstance(identity, Mapping)
            else None
        )

        recovered = recovery.get("recovered") is True

        first_party = bool(
            identity
            and identity.get("first_party") is True
        )

        confidence = (
            _float(identity.get("confidence"))
            if identity
            else 0.0
        )

        name = (
            _clean(identity.get("name"))
            if identity
            else ""
        )

        title = (
            _clean(identity.get("title"))
            if identity
            else ""
        )

        source_url = (
            _clean(identity.get("source_url"))
            if identity
            else ""
        )

        identity_verified = bool(
            recovered
            and identity
            and first_party
            and confidence >= 0.70
            and name
            and title
            and source_url
        )

        if identity_verified:
            decision = "IDENTITY_VERIFIED"
            next_action = (
                "merge_verified_identity_and_reassess_intent"
            )
            supports.extend([
                "named_decision_maker_recovered",
                "first_party_person_evidence",
                "decision_maker_confidence_floor_met",
            ])
        elif recovered and identity:
            decision = "NEEDS_REVIEW"
            next_action = "review_identity_evidence"
            blockers.append(
                "recovered_identity_failed_first_party_verification"
            )
        else:
            decision = "IDENTITY_UNRESOLVED"
            next_action = "hold_for_more_identity_evidence"
            blockers.append(
                "named_decision_maker_not_resolved"
            )

        output = {
            "business_name": business_name,
            "website": website,
            "business_site_verified": True,
            "identity_verified": identity_verified,
            "decision_maker": (
                {
                    "name": name,
                    "title": title,
                    "source": _clean(identity.get("source")),
                    "source_url": source_url,
                    "confidence": confidence,
                    "first_party": first_party,
                }
                if identity
                else None
            ),
            "recovery": {
                "recovered": recovered,
                "sources_tried": list(
                    recovery.get("sources_tried") or ()
                ),
                "evidence": list(
                    recovery.get("evidence") or ()
                ),
            },
        }

    envelope = build_actor_envelope(
        descriptor=DESCRIPTOR,
        actor_input=dict(payload),
        decision=decision,
        recommended_next_action=next_action,
        output=output,
        evidence_refs=(
            _identity_evidence_refs(
                output.get("recovery") or {},
                website,
            )
            if output.get("recovery")
            else ([website] if website else [])
        ),
        truth_class="mixed",
        confidence={
            "identity": (
                _float(
                    (
                        output.get("decision_maker")
                        or {}
                    ).get("confidence")
                )
            ),
        },
        blockers=blockers,
        supports=supports,
        execution_authority="none",
    )

    return validate_actor_envelope(envelope)
