"""Stable decision identity and execution-evidence binding.

A decision identity is provenance, not authority.

Important invariants:

- shadow decisions can never claim execution or causal eligibility;
- non-shadow decisions require explicit external authority evidence;
- execution evidence is attached after the decision;
- the identity itself grants no execution/commercial/accounting authority;
- commercial outcomes are never created here.

Economic Memory may only grant decision-level causal attribution when:
1. this identity is valid,
2. execution was evidenced,
3. the decision was non-shadow,
4. execution_ref matches the completed work item, and
5. an independently verified canonical commercial outcome is explicitly linked.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping


SCHEMA_VERSION = "empire.decision_identity.v1"


def _text(value: Any) -> str:
    return " ".join(
        str(value or "").strip().split()
    )


def _optional(value: Any) -> str | None:
    value = _text(value)
    return value or None


def _material(
    *,
    decision_kind: str,
    task_key: str,
    state_ref: str,
    provider_key: str | None,
    model_key: str | None,
    candidate_id: str | None,
    prediction_ref: str | None,
    source_ref: str,
    shadow_only: bool,
    selection_authority_ref: str | None,
) -> bytes:
    payload = {
        "decision_kind": decision_kind,
        "task_key": task_key,
        "state_ref": state_ref,
        "provider_key": provider_key,
        "model_key": model_key,
        "candidate_id": candidate_id,
        "prediction_ref": prediction_ref,
        "source_ref": source_ref,
        "shadow_only": shadow_only,
        "selection_authority_ref":
            selection_authority_ref,
    }

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _decision_ref(
    *,
    decision_kind: str,
    task_key: str,
    state_ref: str,
    provider_key: str | None,
    model_key: str | None,
    candidate_id: str | None,
    prediction_ref: str | None,
    source_ref: str,
    shadow_only: bool,
    selection_authority_ref: str | None,
) -> str:
    digest = sha256(
        _material(
            decision_kind=decision_kind,
            task_key=task_key,
            state_ref=state_ref,
            provider_key=provider_key,
            model_key=model_key,
            candidate_id=candidate_id,
            prediction_ref=prediction_ref,
            source_ref=source_ref,
            shadow_only=shadow_only,
            selection_authority_ref=(
                selection_authority_ref
            ),
        )
    ).hexdigest()[:24]

    return f"decision:{digest}"


def review_decision_identity(
    raw: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = (
        dict(raw)
        if isinstance(raw, Mapping)
        else {}
    )

    decision_kind = _text(
        source.get("decision_kind")
    )
    task_key = _text(
        source.get("task_key")
    )
    state_ref = _text(
        source.get("state_ref")
    )
    provider_key = _optional(
        source.get("provider_key")
    )
    model_key = _optional(
        source.get("model_key")
    )
    candidate_id = _optional(
        source.get("candidate_id")
    )
    prediction_ref = _optional(
        source.get("prediction_ref")
    )
    source_ref = _text(
        source.get("source_ref")
    )

    shadow_only = (
        source.get("shadow_only") is True
    )

    selection_authority_ref = _optional(
        source.get(
            "selection_authority_ref"
        )
    )

    execution_performed = (
        source.get("execution_performed")
        is True
    )

    execution_ref = _optional(
        source.get("execution_ref")
    )

    claimed_causal = (
        source.get("causal_eligible")
        is True
    )

    blockers: list[str] = []

    if (
        _text(source.get("schema_version"))
        != SCHEMA_VERSION
    ):
        blockers.append(
            "decision_identity_schema_invalid"
        )

    for name, value in (
        ("decision_kind", decision_kind),
        ("task_key", task_key),
        ("state_ref", state_ref),
        ("source_ref", source_ref),
    ):
        if not value:
            blockers.append(
                f"{name}_required"
            )

    if (
        not shadow_only
        and not selection_authority_ref
    ):
        blockers.append(
            "non_shadow_selection_authority_ref_required"
        )

    if (
        shadow_only
        and selection_authority_ref
    ):
        blockers.append(
            "shadow_decision_cannot_claim_selection_authority"
        )

    if shadow_only and execution_performed:
        blockers.append(
            "shadow_decision_cannot_claim_execution"
        )

    if (
        execution_performed
        and not execution_ref
    ):
        blockers.append(
            "execution_ref_required"
        )

    if (
        execution_ref
        and not execution_performed
    ):
        blockers.append(
            "execution_ref_without_execution"
        )

    causal_eligible = bool(
        execution_performed
        and not shadow_only
        and execution_ref
        and selection_authority_ref
    )

    if claimed_causal != causal_eligible:
        blockers.append(
            "causal_eligibility_claim_invalid"
        )

    expected_ref = ""

    if (
        decision_kind
        and task_key
        and state_ref
        and source_ref
    ):
        expected_ref = _decision_ref(
            decision_kind=decision_kind,
            task_key=task_key,
            state_ref=state_ref,
            provider_key=provider_key,
            model_key=model_key,
            candidate_id=candidate_id,
            prediction_ref=prediction_ref,
            source_ref=source_ref,
            shadow_only=shadow_only,
            selection_authority_ref=(
                selection_authority_ref
            ),
        )

    decision_ref = _text(
        source.get("decision_ref")
    )

    if (
        expected_ref
        and decision_ref != expected_ref
    ):
        blockers.append(
            "decision_ref_mismatch"
        )

    if (
        _text(
            source.get(
                "execution_authority"
            )
        )
        != "none"
    ):
        blockers.append(
            "decision_identity_cannot_grant_execution_authority"
        )

    normalized = {
        "schema_version":
            SCHEMA_VERSION,
        "decision_ref":
            expected_ref,
        "decision_kind":
            decision_kind,
        "task_key":
            task_key,
        "state_ref":
            state_ref,
        "provider_key":
            provider_key,
        "model_key":
            model_key,
        "candidate_id":
            candidate_id,
        "prediction_ref":
            prediction_ref,
        "source_ref":
            source_ref,
        "shadow_only":
            shadow_only,
        "selection_authority_ref":
            selection_authority_ref,
        "execution_performed":
            execution_performed,
        "execution_ref":
            execution_ref,
        "causal_eligible":
            causal_eligible,
        "execution_authority":
            "none",
    }

    return {
        "valid": not blockers,
        "identity": (
            normalized
            if not blockers
            else None
        ),
        "blockers": blockers,
        "execution_authority": "none",
    }


def build_decision_identity(
    *,
    decision_kind: str,
    task_key: str,
    state_ref: str,
    source_ref: str,
    provider_key: str | None = None,
    model_key: str | None = None,
    candidate_id: str | None = None,
    prediction_ref: str | None = None,
    shadow_only: bool,
    selection_authority_ref: str | None = None,
) -> dict[str, Any]:
    decision_kind = _text(decision_kind)
    task_key = _text(task_key)
    state_ref = _text(state_ref)
    source_ref = _text(source_ref)

    provider_key = _optional(provider_key)
    model_key = _optional(model_key)
    candidate_id = _optional(candidate_id)
    prediction_ref = _optional(
        prediction_ref
    )
    selection_authority_ref = (
        _optional(
            selection_authority_ref
        )
    )

    if not decision_kind:
        raise ValueError(
            "decision_kind required"
        )

    if not task_key:
        raise ValueError(
            "task_key required"
        )

    if not state_ref:
        raise ValueError(
            "state_ref required"
        )

    if not source_ref:
        raise ValueError(
            "source_ref required"
        )

    if (
        not shadow_only
        and not selection_authority_ref
    ):
        raise ValueError(
            "non-shadow decision requires "
            "selection_authority_ref"
        )

    if (
        shadow_only
        and selection_authority_ref
    ):
        raise ValueError(
            "shadow decision cannot carry "
            "selection authority"
        )

    ref = _decision_ref(
        decision_kind=decision_kind,
        task_key=task_key,
        state_ref=state_ref,
        provider_key=provider_key,
        model_key=model_key,
        candidate_id=candidate_id,
        prediction_ref=prediction_ref,
        source_ref=source_ref,
        shadow_only=shadow_only,
        selection_authority_ref=(
            selection_authority_ref
        ),
    )

    result = {
        "schema_version":
            SCHEMA_VERSION,
        "decision_ref":
            ref,
        "decision_kind":
            decision_kind,
        "task_key":
            task_key,
        "state_ref":
            state_ref,
        "provider_key":
            provider_key,
        "model_key":
            model_key,
        "candidate_id":
            candidate_id,
        "prediction_ref":
            prediction_ref,
        "source_ref":
            source_ref,
        "shadow_only":
            bool(shadow_only),
        "selection_authority_ref":
            selection_authority_ref,
        "execution_performed":
            False,
        "execution_ref":
            None,
        "causal_eligible":
            False,
        "execution_authority":
            "none",
    }

    review = review_decision_identity(
        result
    )

    if review["valid"] is not True:
        raise ValueError(
            "invalid decision identity: "
            + ",".join(review["blockers"])
        )

    return result


def bind_execution_evidence(
    identity: Mapping[str, Any],
    *,
    execution_ref: str,
) -> dict[str, Any]:
    review = review_decision_identity(
        identity
    )

    if review["valid"] is not True:
        raise ValueError(
            "invalid base decision identity"
        )

    base = dict(
        review["identity"]
        or {}
    )

    if base["shadow_only"] is True:
        raise ValueError(
            "shadow decision cannot be bound "
            "as executed"
        )

    execution_ref = _text(
        execution_ref
    )

    if not execution_ref:
        raise ValueError(
            "execution_ref required"
        )

    result = {
        **base,
        "execution_performed":
            True,
        "execution_ref":
            execution_ref,
        "causal_eligible":
            True,
    }

    bound_review = review_decision_identity(
        result
    )

    if bound_review["valid"] is not True:
        raise ValueError(
            "execution binding invalid: "
            + ",".join(
                bound_review["blockers"]
            )
        )

    return dict(
        bound_review["identity"]
        or {}
    )
