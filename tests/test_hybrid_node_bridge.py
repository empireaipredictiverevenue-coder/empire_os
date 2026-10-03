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
    NodeKind,
    NodeRegistry,
    NodeSpec,
)


def registry_with_local_small():
    registry = NodeRegistry()

    registry.register(
        NodeSpec(
            node_id="qwen-local-small",
            kind=NodeKind.COMPUTE,
            capabilities=frozenset(
                {"compute.local.small"}
            ),
            routes=frozenset(
                {Route.LOCAL_SMALL}
            ),
            health=NodeHealth.HEALTHY,
        )
    )

    return registry


def test_classifier_routes_to_registered_node():
    plan = plan_node_execution(
        HybridRequest(
            task_kind=TaskKind.CLASSIFY,
            complexity=0.2,
        ),
        registry_with_local_small(),
    )

    assert plan.route is Route.LOCAL_SMALL
    assert plan.candidate_node_ids == (
        "qwen-local-small",
    )
    assert plan.fail_closed is False
    assert plan.can_execute is False


def test_missing_node_fails_closed():
    plan = plan_node_execution(
        HybridRequest(
            task_kind=TaskKind.CLASSIFY,
            complexity=0.2,
        ),
        NodeRegistry(),
    )

    assert plan.fail_closed is True
    assert plan.can_execute is False
    assert (
        "no_healthy_capability_node"
        in plan.reason_codes
    )


def test_governed_send_keeps_approval_boundary():
    plan = plan_node_execution(
        HybridRequest(
            task_kind=TaskKind.OUTBOUND_SEND
        ),
        NodeRegistry(),
    )

    assert plan.route is Route.HUMAN_GATE
    assert plan.requires_approval is True
    assert plan.candidate_node_ids == ()
    assert plan.fail_closed is True
    assert plan.can_execute is False

    assert (
        "approval_boundary_preserved"
        in plan.reason_codes
    )


def test_tenant_requirement_propagates():
    registry = NodeRegistry()

    registry.register(
        NodeSpec(
            node_id="tenant-local",
            kind=NodeKind.COMPUTE,
            capabilities=frozenset(
                {"compute.local.small"}
            ),
            routes=frozenset(
                {Route.LOCAL_SMALL}
            ),
            health=NodeHealth.HEALTHY,
            tenant_namespace_required=True,
        )
    )

    missing = plan_node_execution(
        HybridRequest(
            task_kind=TaskKind.CLASSIFY,
        ),
        registry,
    )

    present = plan_node_execution(
        HybridRequest(
            task_kind=TaskKind.CLASSIFY,
            tenant_id="tenant-a",
        ),
        registry,
    )

    assert missing.fail_closed is True
    assert present.fail_closed is False
