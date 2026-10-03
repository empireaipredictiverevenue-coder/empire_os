from empire_os.hybrid_compute import (
    HybridRequest,
    Route,
    TaskKind,
)
from empire_os.hybrid_node_bridge import (
    plan_node_execution,
)
from empire_os.node_domain_catalog import (
    add_domain_nodes,
)
from empire_os.node_registry import (
    NodeAuthority,
    NodeHealth,
    NodeRegistry,
)


def registry():
    return add_domain_nodes(NodeRegistry())


def test_three_domain_nodes_exist():
    assert {
        node.node_id
        for node in registry().all()
    } == {
        "optimization-runtime",
        "predictive-revenue-core",
        "quant-brain",
    }


def test_predictive_route():
    plan = plan_node_execution(
        HybridRequest(
            task_kind=TaskKind.PREDICTIVE_REVENUE
        ),
        registry(),
    )

    assert plan.route is Route.PREDICTIVE
    assert plan.can_execute is False


def test_quant_route_is_deterministic():
    plan = plan_node_execution(
        HybridRequest(
            task_kind=TaskKind.QUANT
        ),
        registry(),
    )

    assert plan.route is Route.DETERMINISTIC
    assert plan.can_execute is False


def test_optimization_route():
    plan = plan_node_execution(
        HybridRequest(
            task_kind=TaskKind.OPTIMIZE
        ),
        registry(),
    )

    assert plan.route is Route.OPTIMIZATION
    assert plan.can_execute is False


def test_quant_is_not_llm():
    node = registry().get("quant-brain")

    assert node is not None
    assert node.metadata["llm"] is False


def test_domain_nodes_never_gain_authority():
    for node in registry().all():
        assert node.authority is NodeAuthority.OBSERVE
        assert (
            node.metadata["execution_enabled"]
            is False
        )


def test_unverified_contract_is_not_routable():
    for node in registry().all():
        if not node.metadata.get(
            "contract_verified",
            False,
        ):
            assert node.health is not NodeHealth.HEALTHY
