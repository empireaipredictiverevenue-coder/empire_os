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

CAUSAL_LINEAGE_SCHEMA = "empire.commercial_causal_lineage.v1"
CAUSAL_LINEAGE_REFS = (
    "tenant_id", "opportunity_key", "opportunity_id", "prediction_ref",
    "decision_ref", "execution_ref", "selection_authority_ref", "source_ref", "state_ref", "task_key",
)


def validate_causal_lineage(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate structured provenance, not authenticity or execution authority."""
    fields = {"schema_version", *CAUSAL_LINEAGE_REFS, "execution_performed",
              "causal_eligible", "shadow_only", "execution_authority"}
    if not isinstance(raw, Mapping) or set(raw) != fields:
        raise ValueError("malformed commercial causal lineage")
    if raw["schema_version"] != CAUSAL_LINEAGE_SCHEMA or raw["execution_authority"] != "none":
        raise ValueError("causal lineage cannot grant authority")
    for key in CAUSAL_LINEAGE_REFS:
        value = raw[key]
        if value is not None and (not isinstance(value, str) or not value.strip() or value != value.strip()):
            raise ValueError(f"invalid causal lineage {key}")
    if any(type(raw[key]) is not bool for key in ("shadow_only", "execution_performed", "causal_eligible")):
        raise ValueError("explicit causal lineage truth flags required")
    if raw["shadow_only"] and (raw["selection_authority_ref"] or raw["execution_performed"]):
        raise ValueError("shadow lineage cannot claim authority or execution")
    if raw["decision_ref"] and not raw["shadow_only"] and not raw["selection_authority_ref"]:
        raise ValueError("non-shadow lineage requires selection evidence")
    if bool(raw["execution_ref"]) != raw["execution_performed"]:
        raise ValueError("execution reference requires canonical execution")
    if raw["execution_performed"] and (not raw["task_key"] or raw["execution_ref"] != f"department_work:{raw['task_key']}"):
        raise ValueError("canonical department work execution reference required")
    eligible = bool(raw["execution_performed"] and not raw["shadow_only"]
                    and raw["decision_ref"] and raw["selection_authority_ref"])
    if raw["execution_performed"] and not eligible or raw["causal_eligible"] != eligible:
        raise ValueError("invalid causal execution eligibility")
    return dict(raw)


def causal_lineage_from_work(work: Mapping[str, Any], *, tenant_id: str,
                             opportunity_key: str, opportunity_id: str | None,
                             claimed_lineage: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Read canonical persisted work; never create identities or bind execution."""
    provenance = work.get("commercial_decision_provenance") or {}
    if not tenant_id or work.get("tenant_id") != tenant_id or provenance.get("tenant_id") != tenant_id:
        raise ValueError("work causal tenant mismatch or missing")
    if not opportunity_key or provenance.get("opportunity_key") != opportunity_key:
        raise ValueError("work causal opportunity mismatch or missing")
    if provenance.get("opportunity_id") != opportunity_id:
        raise ValueError("work causal opportunity ID mismatch")
    selected = work.get("decision_identity")
    raw = (work.get("result") or {}).get("decision_identity") or selected
    identity = {}
    if raw is not None:
        review = review_decision_identity(raw)
        if not review["valid"] or raw.get("task_key") != work.get("id"):
            raise ValueError("invalid canonical work decision identity")
        identity = review["identity"]
        if not selected or any(identity[key] != selected.get(key) for key in
                ("decision_ref", "prediction_ref", "candidate_id", "source_ref", "state_ref", "selection_authority_ref", "shadow_only")):
            raise ValueError("completed decision contradicts canonical selection")
        if identity["candidate_id"] != opportunity_key or identity["prediction_ref"] != provenance.get("prediction_ref"):
            raise ValueError("work causal candidate or prediction mismatch")
    if identity.get("execution_performed") is True:
        result = work.get("result") or {}
        if (work.get("status") != "DONE" or not work.get("result_evidence_refs")
                or identity["execution_ref"] != f"department_work:{work.get('id')}"
                or result.get("returncode") != 0 or result.get("adapter") != "safe_internal_command"
                or any(result.get(key) is True for key in ("simulated", "shadow_only", "proposed", "queued", "attempted", "blocked"))):
            raise ValueError("work does not prove completed canonical execution")
    values = {key: identity.get(key) for key in CAUSAL_LINEAGE_REFS}
    values.update(tenant_id=tenant_id, opportunity_key=opportunity_key, opportunity_id=opportunity_id)
    values.update(schema_version=CAUSAL_LINEAGE_SCHEMA, execution_authority="none",
                  execution_performed=identity.get("execution_performed", False),
                  causal_eligible=identity.get("causal_eligible", False), shadow_only=identity.get("shadow_only", True))
    lineage = validate_causal_lineage(values)
    if claimed_lineage is not None:
        if not isinstance(claimed_lineage, Mapping) or any(key not in lineage or value != lineage[key]
                for key, value in claimed_lineage.items()):
            raise ValueError("caller lineage contradicts canonical work")
    return lineage


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
