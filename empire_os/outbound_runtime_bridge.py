"""Fail-closed runtime bridge from ACP review progression to Outbound planning.

This bridge is advisory only. It performs no database access, network access,
queue mutation, send, approval, terms action, payment action, or revenue write.

ACP remains the canonical owner of internal buyer-review progression.
Astra/Outbound receives only the resulting verified account context and decides
the next *proposal* state with execution_authority=none.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from empire_os.astra import decide_outbound_account


_REVIEW_ACTIONS = frozenset({
    "prepare_buyer_review",
    "verify_decision_maker",
    "enrich_identity",
    "refresh_buyer_review",
    "recover_contact_evidence",
    "reconcile_identity",
})

_ACCEPTED_OUTCOMES = frozenset({
    "proposed",
    "review_ready",
    "review_ready_not_proposed",
})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _rows(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return tuple(row for row in value if isinstance(row, Mapping))
    return ()


def _first_review_outcome(result: Mapping[str, Any]) -> Mapping[str, Any] | None:
    materializer = result.get("materializer")
    if not isinstance(materializer, Mapping):
        return None

    for row in _rows(materializer.get("outcomes")):
        status = _text(row.get("status")).lower()
        if status in _ACCEPTED_OUTCOMES:
            return row
    return None


def _extract_explicit_outbound_evidence(
    result: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Return only evidence already explicitly shaped for outbound use.

    The bridge never converts generic internal facts into prospect-facing
    claims. Missing evidence therefore yields RESEARCH in the Outbound planner.
    """
    candidates: list[Mapping[str, Any]] = []

    candidates.extend(_rows(result.get("outbound_evidence")))

    probe = result.get("probe")
    if isinstance(probe, Mapping):
        candidates.extend(_rows(probe.get("outbound_evidence")))

    identity_bridge = result.get("identity_bridge")
    if isinstance(identity_bridge, Mapping):
        review_input = identity_bridge.get("review_input")
        if isinstance(review_input, Mapping):
            candidates.extend(_rows(review_input.get("outbound_evidence")))

    accepted: list[Mapping[str, Any]] = []
    seen: set[str] = set()

    for raw in candidates:
        ref = _text(
            raw.get("evidence_ref")
            or raw.get("ref")
            or raw.get("source_ref")
            or raw.get("id")
        )
        summary = _text(
            raw.get("summary")
            or raw.get("observation")
            or raw.get("claim")
            or raw.get("text")
        )

        if not ref or not summary or ref in seen:
            continue

        if raw.get("contradicted") is True:
            continue

        verification = _text(
            raw.get("verification_state")
            or raw.get("evidence_class")
            or raw.get("status")
        ).lower()

        verified = (
            raw.get("verified") is True
            or verification in {"verified", "observed", "first_party_verified"}
        )

        freshness = _text(
            raw.get("freshness")
            or raw.get("freshness_state")
        ).lower()

        fresh = raw.get("fresh") is True or freshness in {"fresh", "current"}

        account_bound = (
            raw.get("account_bound") is True
            or bool(_text(raw.get("prospect_id")))
            or bool(_text(raw.get("company_name")))
        )

        if not (verified and fresh and account_bound):
            continue

        accepted.append(dict(raw))
        seen.add(ref)

    return tuple(accepted)


def outbound_advisory_from_progression(
    receipt: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Build an Outbound next-step advisory from an ACP execution receipt."""
    action = _text(receipt.get("action"))

    if action not in _REVIEW_ACTIONS:
        return None

    result = receipt.get("result")
    if not isinstance(result, Mapping):
        return None

    outcome = _first_review_outcome(result)
    if outcome is None:
        return None

    prospect_id = _text(
        outcome.get("prospect_id")
        or result.get("prospect_id")
        or receipt.get("prospect_id")
    )
    company_name = _text(
        outcome.get("business_name")
        or outcome.get("company_name")
        or receipt.get("company_name")
    )
    decision_maker = _text(
        outcome.get("decision_name")
        or outcome.get("decision_maker")
    )
    decision_title = _text(outcome.get("decision_title"))
    contact_email = _text(
        outcome.get("preferred_email")
        or outcome.get("contact_email")
    )
    contact_route = _text(outcome.get("contact_route"))
    person_bound = bool(outcome.get("person_bound"))

    account = {
        "prospect_id": prospect_id or None,
        "company_name": company_name or None,
        # A proposed/review-ready materializer outcome is canonical review
        # evidence for the exact candidate name; this does not authorize send.
        "company_name_verified": bool(company_name),
        "decision_maker": decision_maker or None,
        "decision_title": decision_title or None,
        "contact_email": contact_email or None,
        "contact_route": contact_route or None,
        "person_bound": person_bound,
        "buyer_review_status": "review_ready",
        "verified_prospect": True,
    }

    evidence = _extract_explicit_outbound_evidence(result)

    plan = decide_outbound_account(
        account,
        evidence=evidence,
        recommendation=None,
    )

    return {
        "schema_version": "empire.outbound_runtime_bridge.v1",
        "source": "autonomous_commercial_progression",
        "source_action": action,
        "advisory_only": True,
        "outbound_sent": False,
        "send_enabled": False,
        "execution_authority": "none",
        "account": {
            "prospect_id": account["prospect_id"],
            "company_name": account["company_name"],
            "decision_maker": account["decision_maker"],
            "decision_title": account["decision_title"],
            "contact_route": account["contact_route"],
            "person_bound": (
                False if account["contact_route"] == "company_routed"
                else account["person_bound"]
            ),
        },
        "explicit_outbound_evidence_count": len(evidence),
        "plan": plan,
    }
