from empire_os.hybrid_compute import (
    HybridRequest,
    Route,
    TaskKind,
)
from empire_os.hybrid_node_bridge import (
    plan_node_execution,
)
from empire_os.node_registry import NodeHealth
from empire_os.node_runtime_catalog import (
    ProbeResult,
    build_runtime_registry,
    runtime_snapshot,
)


def healthy(endpoint: str) -> ProbeResult:
    return ProbeResult(
        healthy=True,
        status_code=200,
        endpoint=endpoint,
    )


def offline(endpoint: str) -> ProbeResult:
    return ProbeResult(
        healthy=False,
        status_code=None,
        endpoint=endpoint,
        error="ConnectionRefusedError",
    )


def test_registers_three_real_runtime_surfaces():
    registry = build_runtime_registry(
        probe=healthy
    )

    assert {
        node.node_id
        for node in registry.all()
    } == {
        "laya-shadow-system1",
        "ollama-local-pool",
        "qwen25-coder-1_5b",
    }


def test_local_small_has_two_candidates():
    registry = build_runtime_registry(
        probe=healthy
    )

    result = registry.candidates(
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
    )

    assert {
        node.node_id
        for node in result
    } == {
        "laya-shadow-system1",
        "qwen25-coder-1_5b",
    }


def test_ollama_not_promoted_to_strong():
    registry = build_runtime_registry(
        probe=healthy
    )

    assert not registry.candidates(
        capability="compute.local.strong",
        route=Route.LOCAL_STRONG,
    )


def test_offline_runtime_not_routable():
    registry = build_runtime_registry(
        probe=offline
    )

    assert all(
        node.health is NodeHealth.OFFLINE
        for node in registry.all()
    )

    assert not registry.candidates(
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
    )


def test_classifier_can_plan_live_local_small():
    registry = build_runtime_registry(
        probe=healthy
    )

    plan = plan_node_execution(
        HybridRequest(
            task_kind=TaskKind.CLASSIFY,
            complexity=0.2,
        ),
        registry,
    )

    assert plan.route is Route.LOCAL_SMALL
    assert plan.fail_closed is False
    assert plan.can_execute is False
    assert len(plan.candidate_node_ids) == 2


def test_strong_reasoning_fails_closed_without_proof():
    registry = build_runtime_registry(
        probe=healthy
    )

    plan = plan_node_execution(
        HybridRequest(
            task_kind=TaskKind.REASON,
            complexity=0.8,
        ),
        registry,
    )

    assert plan.route is Route.LOCAL_STRONG
    assert plan.fail_closed is True
    assert plan.can_execute is False


def test_snapshot_never_grants_authority():
    snapshot = runtime_snapshot(
        probe=healthy
    )

    assert (
        snapshot["production_authority"]
        is False
    )

    assert (
        snapshot["classification"][
            "local_strong_candidates"
        ]
        == []
    )
