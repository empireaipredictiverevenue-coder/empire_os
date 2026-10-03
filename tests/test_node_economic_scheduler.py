from empire_os.hybrid_compute import Route
from empire_os.node_economic_scheduler import (
    NodePerformance,
    SchedulerPolicy,
    schedule,
)
from empire_os.node_registry import (
    NodeHealth,
    NodeKind,
    NodeRegistry,
    NodeSpec,
)


def registry():
    r = NodeRegistry()

    for node_id in ("a", "b"):
        r.register(
            NodeSpec(
                node_id=node_id,
                kind=NodeKind.COMPUTE,
                capabilities=frozenset({
                    "compute.local.small",
                }),
                routes=frozenset({
                    Route.LOCAL_SMALL,
                }),
                health=NodeHealth.HEALTHY,
            )
        )

    return r


def perf(
    node_id,
    *,
    quality=0.9,
    reliability=0.99,
    latency=100,
    cost=0.01,
    samples=30,
    outcome=0.8,
    economic=True,
):
    return NodePerformance(
        node_id=node_id,
        quality=quality,
        reliability=reliability,
        latency_ms=latency,
        marginal_cost_gbp=cost,
        matched_sample_count=samples,
        verified_outcome_score=outcome,
        benchmark_verified=True,
        economic_memory_verified=economic,
    )


def test_no_receipt_fails_closed():
    result = schedule(
        registry=registry(),
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
        performance={},
    )

    assert result.selected_node_id is None
    assert (
        result.production_authority
        is False
    )


def test_shadow_selection_uses_evidence():
    result = schedule(
        registry=registry(),
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
        performance={
            "a": perf(
                "a",
                quality=0.90,
            ),
            "b": perf(
                "b",
                quality=0.95,
            ),
        },
    )

    assert result.selected_node_id == "b"
    assert (
        result.shadow_selection_available
        is True
    )


def test_insufficient_samples_not_selected():
    result = schedule(
        registry=registry(),
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
        performance={
            "a": perf(
                "a",
                samples=1,
            ),
        },
    )

    assert result.selected_node_id is None


def test_production_needs_economic_memory():
    result = schedule(
        registry=registry(),
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
        performance={
            "a": perf(
                "a",
                economic=False,
            ),
        },
    )

    assert result.selected_node_id == "a"
    assert (
        result.production_selection_available
        is False
    )


def test_production_thresholds():
    result = schedule(
        registry=registry(),
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
        performance={
            "a": perf("a"),
            "b": perf(
                "b",
                reliability=0.90,
            ),
        },
    )

    assert result.selected_node_id == "a"
    assert (
        result.production_selection_available
        is True
    )


def test_missing_metric_is_not_invented():
    p = NodePerformance(
        node_id="a",
        quality=0.9,
        reliability=None,
        latency_ms=100,
        marginal_cost_gbp=0.0,
        matched_sample_count=50,
        benchmark_verified=True,
        economic_memory_verified=True,
    )

    result = schedule(
        registry=registry(),
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
        performance={"a": p},
    )

    assert result.selected_node_id is None


def test_policy_is_explicit():
    policy = SchedulerPolicy(
        production_min_samples=100,
    )

    result = schedule(
        registry=registry(),
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
        performance={
            "a": perf(
                "a",
                samples=30,
            ),
        },
        policy=policy,
    )

    assert result.selected_node_id == "a"

    assert (
        result.production_selection_available
        is False
    )
