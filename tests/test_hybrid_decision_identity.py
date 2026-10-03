import pytest

from empire_os.hybrid_compute_policy import (
    RoutingRecommendation,
    build_hybrid_shadow_decision_identity,
)


def recommendation():
    return RoutingRecommendation(
        quality_floor=0.90,
        latency_ceiling_ms=60000,
        selected_candidate_id=(
            "qwen3-coder-30b-ollama"
        ),
        selected_provider="ollama",
        selected_model="qwen3-coder:30b",
        measured_quality=0.95,
        measured_reliability=1.0,
        measured_latency_ms=38382.794,
        candidate_count=4,
        economic_ready=False,
        route_applied=False,
        can_execute=False,
        production_authority=False,
        reason_codes=(
            "shadow_recommendation_only",
        ),
    )


def test_v4_recommendation_gets_stable_noncausal_identity():
    first = build_hybrid_shadow_decision_identity(
        recommendation(),
        state_ref=(
            "runtime:opportunity:123"
        ),
        task_key="predictive_reasoning",
        prediction_ref=(
            "quant_prediction:abc"
        ),
    )

    second = build_hybrid_shadow_decision_identity(
        recommendation(),
        state_ref=(
            "runtime:opportunity:123"
        ),
        task_key="predictive_reasoning",
        prediction_ref=(
            "quant_prediction:abc"
        ),
    )

    assert (
        first["decision_ref"]
        == second["decision_ref"]
    )

    assert first["shadow_only"] is True
    assert first["execution_performed"] is False
    assert first["causal_eligible"] is False
    assert first["selection_authority_ref"] is None
    assert first["execution_authority"] == "none"


def test_missing_selected_model_cannot_create_identity():
    empty = RoutingRecommendation(
        quality_floor=0.9,
        latency_ceiling_ms=60000,
        selected_candidate_id=None,
        selected_provider=None,
        selected_model=None,
        measured_quality=None,
        measured_reliability=None,
        measured_latency_ms=None,
        candidate_count=0,
        economic_ready=False,
        route_applied=False,
        can_execute=False,
        production_authority=False,
        reason_codes=(),
    )

    with pytest.raises(
        ValueError,
        match="no selected candidate",
    ):
        build_hybrid_shadow_decision_identity(
            empty,
            state_ref="state:1",
            task_key="reason",
        )
