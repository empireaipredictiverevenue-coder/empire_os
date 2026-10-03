import pytest

from empire_os.hybrid_compute import (
    HybridRequest,
    Route,
    Sensitivity,
    TaskKind,
    evaluate_mapping,
    recommend_route,
)


def test_classifier_prefers_small_local() -> None:
    decision = recommend_route(
        HybridRequest(
            task_kind=TaskKind.CLASSIFY,
            sensitivity=Sensitivity.INTERNAL,
            complexity=0.2,
            quality_floor=0.90,
        )
    )

    assert (
        decision.recommended_route
        is Route.LOCAL_SMALL
    )
    assert decision.can_execute is False
    assert decision.mode == "observe"


def test_predictive_revenue_uses_predictive_route() -> None:
    decision = recommend_route(
        HybridRequest(
            task_kind=TaskKind.PREDICTIVE_REVENUE
        )
    )

    assert (
        decision.recommended_route
        is Route.PREDICTIVE
    )
    assert decision.can_execute is False


@pytest.mark.parametrize(
    "task_kind",
    [
        TaskKind.OUTBOUND_SEND,
        TaskKind.COMMERCIAL_BINDING,
        TaskKind.PAYMENT,
        TaskKind.INFRASTRUCTURE_CHANGE,
    ],
)
def test_governed_actions_never_gain_model_authority(
    task_kind: TaskKind,
) -> None:
    decision = recommend_route(
        HybridRequest(
            task_kind=task_kind,
            sensitivity=Sensitivity.INTERNAL,
            complexity=1.0,
            risk=1.0,
            quality_floor=1.0,
            expected_value_gbp=1_000_000,
            requires_external_knowledge=True,
        )
    )

    assert (
        decision.recommended_route
        is Route.HUMAN_GATE
    )

    assert decision.requires_approval is True
    assert decision.can_execute is False

    assert (
        "authority_separate_from_compute"
        in decision.reason_codes
    )

    assert (
        "human_governance_gate"
        in decision.reason_codes
    )

    assert "fail_closed" in decision.reason_codes


def test_restricted_external_knowledge_fails_closed() -> None:
    decision = recommend_route(
        HybridRequest(
            task_kind=TaskKind.RESEARCH,
            sensitivity=Sensitivity.RESTRICTED,
            requires_external_knowledge=True,
        )
    )

    assert (
        decision.recommended_route
        is Route.HUMAN_GATE
    )
    assert decision.frontier_allowed is False
    assert "fail_closed" in decision.reason_codes


def test_high_value_complex_reasoning_can_use_frontier() -> None:
    decision = recommend_route(
        HybridRequest(
            task_kind=TaskKind.REASON,
            sensitivity=Sensitivity.INTERNAL,
            complexity=0.90,
            quality_floor=0.95,
            expected_value_gbp=25_000,
        )
    )

    assert (
        decision.recommended_route
        is Route.FRONTIER
    )
    assert decision.can_execute is False


def test_confidential_reasoning_stays_local() -> None:
    decision = recommend_route(
        HybridRequest(
            task_kind=TaskKind.REASON,
            sensitivity=Sensitivity.CONFIDENTIAL,
            complexity=0.95,
            quality_floor=0.99,
            expected_value_gbp=100_000,
        )
    )

    assert (
        decision.recommended_route
        is Route.LOCAL_STRONG
    )
    assert decision.frontier_allowed is False


def test_route_change_is_observed_not_applied() -> None:
    decision = recommend_route(
        HybridRequest(
            task_kind=TaskKind.CLASSIFY,
            current_route=Route.FRONTIER,
        )
    )

    assert (
        decision.recommended_route
        is Route.LOCAL_SMALL
    )
    assert decision.route_changed is True
    assert decision.can_execute is False


def test_mapping_output_exposes_zero_production_authority() -> None:
    payload = evaluate_mapping(
        {
            "task_kind": "summarise",
            "sensitivity": "internal",
            "current_route": "frontier",
        }
    )

    assert (
        payload["router"]["mode"]
        == "observe"
    )
    assert (
        payload["router"][
            "production_authority"
        ]
        is False
    )
    assert (
        payload["decision"]["can_execute"]
        is False
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("complexity", -0.1),
        ("complexity", 1.1),
        ("risk", 1.1),
        ("quality_floor", -0.1),
    ],
)
def test_invalid_scores_fail_closed(
    field: str,
    value: float,
) -> None:
    kwargs = {
        "task_kind": TaskKind.REASON,
        field: value,
    }

    with pytest.raises(ValueError):
        HybridRequest(**kwargs)


def test_invalid_latency_fails_closed() -> None:
    with pytest.raises(ValueError):
        HybridRequest(
            task_kind=TaskKind.REASON,
            max_latency_ms=0,
        )
