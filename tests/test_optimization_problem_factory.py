import pytest

from empire_os.action_portfolio_optimization import (
    build_portfolio_optimization_problem,
)
from empire_os.optimization_problem_factory import (
    build_decomposition_plan,
    build_problem_ir,
    compile_action_portfolio_problem,
    compile_allocation_problem,
)
from empire_os.quantum_optimization import build_allocation_optimization_problem


def _basic_ir(variable_order=("x::a", "x::b")):
    rows = {
        "x::a": {
            "variable": "x::a",
            "evidence_refs": ["evidence:a"],
            "partition_key": "north",
        },
        "x::b": {
            "variable": "x::b",
            "evidence_refs": ["evidence:b"],
            "partition_key": "south",
        },
    }
    return build_problem_ir(
        workload_key="fixture",
        workload_type="buyer_allocation",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=[rows[key] for key in variable_order],
        objective={
            "sense": "MAXIMIZE",
            "linear": {"x::a": 10, "x::b": 20},
            "quadratic": {},
        },
        constraints=[
            {
                "name": "a_only",
                "coefficients": {"x::a": 1},
                "sense": "<=",
                "rhs": 1,
            },
            {
                "name": "b_only",
                "coefficients": {"x::b": 1},
                "sense": "<=",
                "rhs": 1,
            },
        ],
        representations=("QUBO", "CQM"),
    )


def test_problem_fingerprint_is_stable_across_variable_order():
    left = _basic_ir(("x::a", "x::b"))
    right = _basic_ir(("x::b", "x::a"))

    assert left["problem_fingerprint"] == right["problem_fingerprint"]
    assert left["execution_authority"] == "none"
    assert left["unknown_is_zero"] is False


def test_problem_factory_requires_evidence_and_does_not_invent_it():
    packet = build_problem_ir(
        workload_key="no_evidence",
        workload_type="fixture",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=[{"variable": "x::1"}],
        objective={"sense": "MAXIMIZE", "linear": {"x::1": 1}},
        constraints=[],
    )

    assert packet["status"] == "UNAVAILABLE"
    assert packet["reason"] == "evidence_refs_required"
    assert packet["unknown_is_zero"] is False


def test_problem_factory_rejects_unknown_constraint_variable():
    with pytest.raises(ValueError, match="unknown variables"):
        build_problem_ir(
            workload_key="bad_constraint",
            workload_type="fixture",
            source_schema_version="fixture.v1",
            variable_type="BINARY",
            variables=[
                {"variable": "x::1", "evidence_refs": ["evidence:1"]}
            ],
            objective={"sense": "MAXIMIZE", "linear": {"x::1": 1}},
            constraints=[
                {
                    "name": "bad",
                    "coefficients": {"x::missing": 1},
                    "sense": "<=",
                    "rhs": 1,
                }
            ],
        )


def test_compile_existing_allocation_problem_and_only_offer_qubo_when_safe():
    unit = build_allocation_optimization_problem(
        options=[
            {
                "prospect_id": "p1",
                "buyer_id": "b1",
                "expected_value_cents": 1000,
                "evidence_refs": ["ev:1"],
            }
        ],
        buyer_capacities={"b1": 1},
    )
    unit_ir = compile_allocation_problem(unit)
    assert unit_ir["representations"] == ["CQM", "QUBO"]

    general = build_allocation_optimization_problem(
        options=[
            {
                "prospect_id": "p1",
                "buyer_id": "b1",
                "expected_value_cents": 1000,
                "evidence_refs": ["ev:1"],
            }
        ],
        buyer_capacities={"b1": 2},
    )
    general_ir = compile_allocation_problem(general)
    assert general_ir["representations"] == ["CQM"]


def test_action_portfolio_v2_holds_qubo_until_revalidated():
    source = build_portfolio_optimization_problem(
        actions=[
            {
                "action_key": "a1",
                "expected_incremental_value_cents": 5000,
                "action_cost_cents": 500,
                "capacity_group": "sales",
                "evidence_refs": ["ev:a1"],
            }
        ],
        budget_cents=1000,
        capacity_constraints={"sales": 1},
    )

    packet = compile_action_portfolio_problem(source)

    assert packet["status"] == "AVAILABLE"
    assert packet["representations"] == ["CQM"]
    assert packet["metadata"]["qubo_revalidation_required"] is True


def test_decomposition_requires_coordinator_for_cross_partition_constraints():
    packet = _basic_ir()
    packet["constraints"] = [
        {
            "name": "global_capacity",
            "coefficients": {"x::a": 1, "x::b": 1},
            "sense": "<=",
            "rhs": 1,
        }
    ]

    plan = build_decomposition_plan(packet, max_variables_per_shard=1)

    assert plan["strategy"] == "coordinator_decomposition_required"
    assert plan["independent_shard_execution_safe"] is False
    assert plan["blockers"]["cross_partition_constraints"] == [
        "global_capacity"
    ]


def test_decomposition_allows_proven_independent_partitions():
    plan = build_decomposition_plan(
        _basic_ir(),
        max_variables_per_shard=1,
    )

    assert plan["strategy"] == "independent_shards"
    assert plan["planned_shard_count"] == 2
    assert plan["independent_shard_execution_safe"] is True


def test_problem_factory_rejects_unknown_quadratic_variable():
    with pytest.raises(
        ValueError,
        match="quadratic objective references unknown variables",
    ):
        build_problem_ir(
            workload_key="bad_quadratic",
            workload_type="fixture",
            source_schema_version="fixture.v1",
            variable_type="BINARY",
            variables=[
                {"variable": "x::1", "evidence_refs": ["evidence:1"]}
            ],
            objective={
                "sense": "MINIMIZE",
                "linear": {"x::1": 0},
                "quadratic": {"x::1|x::missing": 1},
            },
            constraints=[],
        )


def test_decomposition_blocks_cross_partition_quadratic_objective():
    problem = build_problem_ir(
        workload_key="quadratic_shard_guard",
        workload_type="fixture",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=[
            {
                "variable": "x::north",
                "partition_key": "north",
                "evidence_refs": ["ev:north"],
            },
            {
                "variable": "x::south",
                "partition_key": "south",
                "evidence_refs": ["ev:south"],
            },
        ],
        objective={
            "sense": "MAXIMIZE",
            "linear": {"x::north": 1, "x::south": 1},
            "quadratic": {"x::north|x::south": 2},
        },
        constraints=[],
    )

    plan = build_decomposition_plan(
        problem,
        max_variables_per_shard=1,
    )

    assert plan["strategy"] == "coordinator_decomposition_required"
    assert plan["independent_shard_execution_safe"] is False
    assert plan["blockers"]["cross_partition_quadratic_terms"] == [
        "x::north|x::south"
    ]
