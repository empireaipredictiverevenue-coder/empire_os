import pytest

from empire_os.decision_identity import (
    bind_execution_evidence,
    build_decision_identity,
    review_decision_identity,
)


def test_shadow_decision_identity_is_stable_and_noncausal():
    a = build_decision_identity(
        decision_kind="hybrid_compute_routing",
        task_key="reason",
        state_ref="state:1",
        source_ref="hybrid_policy:v1",
        provider_key="ollama",
        model_key="qwen3-coder:30b",
        candidate_id="qwen3-30b",
        prediction_ref="quant_prediction:abc",
        shadow_only=True,
    )

    b = build_decision_identity(
        decision_kind="hybrid_compute_routing",
        task_key="reason",
        state_ref="state:1",
        source_ref="hybrid_policy:v1",
        provider_key="ollama",
        model_key="qwen3-coder:30b",
        candidate_id="qwen3-30b",
        prediction_ref="quant_prediction:abc",
        shadow_only=True,
    )

    assert (
        a["decision_ref"]
        == b["decision_ref"]
    )

    assert a["shadow_only"] is True
    assert a["execution_performed"] is False
    assert a["causal_eligible"] is False
    assert a["execution_authority"] == "none"


def test_shadow_identity_cannot_be_relabelled_as_execution():
    identity = build_decision_identity(
        decision_kind="hybrid_compute_routing",
        task_key="reason",
        state_ref="state:1",
        source_ref="hybrid_policy:v1",
        shadow_only=True,
    )

    with pytest.raises(
        ValueError,
        match="shadow",
    ):
        bind_execution_evidence(
            identity,
            execution_ref=(
                "department_work:work-1"
            ),
        )


def test_nonshadow_identity_requires_external_authority_ref():
    with pytest.raises(
        ValueError,
        match="selection_authority_ref",
    ):
        build_decision_identity(
            decision_kind="bounded_internal_decision",
            task_key="internal_classification",
            state_ref="state:2",
            source_ref="runtime:decision:2",
            shadow_only=False,
        )


def test_execution_evidence_enables_causal_eligibility_only_after_binding():
    identity = build_decision_identity(
        decision_kind="bounded_internal_decision",
        task_key="internal_classification",
        state_ref="state:2",
        source_ref="runtime:decision:2",
        provider_key="local",
        model_key="model-1",
        shadow_only=False,
        selection_authority_ref=(
            "authority:test:bounded"
        ),
    )

    assert identity["causal_eligible"] is False

    executed = bind_execution_evidence(
        identity,
        execution_ref=(
            "department_work:work-1"
        ),
    )

    assert (
        executed["decision_ref"]
        == identity["decision_ref"]
    )

    assert (
        executed["execution_performed"]
        is True
    )

    assert executed["causal_eligible"] is True
    assert executed["execution_authority"] == "none"


def test_tampered_identity_fails_review():
    identity = build_decision_identity(
        decision_kind="hybrid_compute_routing",
        task_key="reason",
        state_ref="state:1",
        source_ref="hybrid_policy:v1",
        shadow_only=True,
    )

    tampered = {
        **identity,
        "task_key": "payment",
    }

    result = review_decision_identity(
        tampered
    )

    assert result["valid"] is False
    assert (
        "decision_ref_mismatch"
        in result["blockers"]
    )
