from empire_os.hybrid_compute import (
    HybridRequest,
    Route,
    TaskKind,
)
from empire_os.hybrid_node_bridge import (
    plan_node_execution,
)
from empire_os.node_registry import (
    NodeHealth,
)
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


def test_registers_runtime_surfaces_and_model_nodes():
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
        "ollama-qwen25-coder-7b",
        "ollama-qwen25-coder-14b",
        "ollama-qwen3-coder-30b",
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


def test_benchmarked_ollama_models_are_local_strong():
    registry = build_runtime_registry(
        probe=healthy
    )

    result = registry.candidates(
        capability="compute.local.strong",
        route=Route.LOCAL_STRONG,
    )

    assert {
        node.node_id
        for node in result
    } == {
        "ollama-qwen25-coder-7b",
        "ollama-qwen25-coder-14b",
        "ollama-qwen3-coder-30b",
    }

    expected_models = {
        "ollama-qwen25-coder-7b":
            "qwen2.5-coder:7b",
        "ollama-qwen25-coder-14b":
            "qwen2.5-coder:14b",
        "ollama-qwen3-coder-30b":
            "qwen3-coder:30b",
    }

    for node in result:
        assert node.health is NodeHealth.HEALTHY
        assert node.authority.value == "observe"
        assert node.provider == "ollama"

        assert (
            node.metadata["model"]
            == expected_models[node.node_id]
        )

        assert (
            node.metadata["execution_enabled"]
            is False
        )

        assert (
            node.metadata["production_authority"]
            is False
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

    assert not registry.candidates(
        capability="compute.local.strong",
        route=Route.LOCAL_STRONG,
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

    assert set(
        plan.candidate_node_ids
    ) == {
        "laya-shadow-system1",
        "qwen25-coder-1_5b",
    }


def test_strong_reasoning_has_shadow_candidates_only():
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

    assert set(
        plan.candidate_node_ids
    ) == {
        "ollama-qwen25-coder-7b",
        "ollama-qwen25-coder-14b",
        "ollama-qwen3-coder-30b",
    }

    assert plan.fail_closed is False
    assert plan.can_execute is False


def test_snapshot_never_grants_authority():
    snapshot = runtime_snapshot(
        probe=healthy
    )

    assert snapshot["node_count"] == 6

    assert (
        snapshot["production_authority"]
        is False
    )

    assert set(
        snapshot["classification"][
            "local_strong_candidates"
        ]
    ) == {
        "ollama-qwen25-coder-7b",
        "ollama-qwen25-coder-14b",
        "ollama-qwen3-coder-30b",
    }

    assert (
        snapshot["classification"][
            "unclassified_local_pools"
        ]
        == ["ollama-local-pool"]
    )
