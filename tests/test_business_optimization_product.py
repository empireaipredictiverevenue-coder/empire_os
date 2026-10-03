import pytest

from empire_os.business_optimization_product import (
    PRODUCT_CODE,
    WORKLOAD_SPECS,
    build_business_optimization_catalog,
    build_business_optimization_preview,
    build_business_optimization_problem,
)


ALL_WORKLOADS = tuple(sorted(WORKLOAD_SPECS))


@pytest.mark.parametrize("workload_type", ALL_WORKLOADS)
def test_every_business_workload_compiles_into_shared_empire_ir(workload_type):
    spec = WORKLOAD_SPECS[workload_type]
    sense = spec["default_objective_sense"]
    options = [
        {
            "option_key": "entity-a::choice-1",
            "entity_key": "entity-a",
            "target_key": "choice-1",
            "objective_value": 10 if sense == "MAXIMIZE" else 10,
            "resource_usage": {"shared_capacity": 1},
            "evidence_refs": ["evidence:a1"],
        },
        {
            "option_key": "entity-a::choice-2",
            "entity_key": "entity-a",
            "target_key": "choice-2",
            "objective_value": 20 if sense == "MAXIMIZE" else 5,
            "resource_usage": {"shared_capacity": 1},
            "evidence_refs": ["evidence:a2"],
        },
    ]

    problem = build_business_optimization_problem(
        workload_type=workload_type,
        options=options,
        resource_limits={"shared_capacity": 1},
        tenant_id="tenant-a",
        time_budget_ms=1000,
    )

    assert problem["status"] == "AVAILABLE"
    assert problem["workload_type"] == workload_type
    assert problem["tenant_id"] == "tenant-a"
    assert problem["metadata"]["product_code"] == PRODUCT_CODE
    assert problem["metadata"]["solver_runtime_policy"] == "empire_owned_only"
    assert (
        problem["metadata"]["third_party_service_execution_allowed"]
        is False
    )
    assert problem["execution_authority"] == "none"
    assert problem["actual_revenue"] is False


@pytest.mark.parametrize("workload_type", ALL_WORKLOADS)
def test_every_business_workload_runs_through_same_solver_fabric(workload_type):
    spec = WORKLOAD_SPECS[workload_type]
    exact_choice_required = (
        spec["entity_selection"]["min"]
        == spec["entity_selection"]["max"]
        == 1
    )
    options = [
        {
            "option_key": "entity-a::low",
            "entity_key": "entity-a",
            "objective_value": (
                100 if spec["default_objective_sense"] == "MAXIMIZE" else 10
            ),
            "evidence_refs": ["evidence:low"],
        },
        {
            "option_key": "entity-a::high",
            "entity_key": "entity-a",
            "objective_value": (
                200 if spec["default_objective_sense"] == "MAXIMIZE" else 5
            ),
            "evidence_refs": ["evidence:high"],
        },
    ]

    preview = build_business_optimization_preview(
        workload_type=workload_type,
        options=options,
        time_budget_ms=1000,
    )

    assert preview["status"] == "AVAILABLE"
    assert preview["plan"]["status"] == "AVAILABLE"
    assert preview["plan"]["production_solver_origin"] == "empire_owned"
    assert preview["result"]["status"] == "AVAILABLE"
    selected = preview["result"]["result"]["selected_variables"]
    if spec["default_objective_sense"] == "MAXIMIZE":
        assert selected == ["x::entity-a::high"]
    elif exact_choice_required:
        assert selected == ["x::entity-a::high"]
    assert preview["third_party_service_execution_allowed"] is False
    assert preview["automatic_action_allowed"] is False
    assert preview["execution_authority"] == "none"


def test_resource_limits_change_the_optimal_portfolio():
    problem = build_business_optimization_problem(
        workload_type="capital_allocation",
        options=[
            {
                "option_key": "project-a",
                "entity_key": "project-a",
                "objective_value": 100,
                "resource_usage": {"capital": 70},
                "evidence_refs": ["ev:a"],
            },
            {
                "option_key": "project-b",
                "entity_key": "project-b",
                "objective_value": 80,
                "resource_usage": {"capital": 40},
                "evidence_refs": ["ev:b"],
            },
            {
                "option_key": "project-c",
                "entity_key": "project-c",
                "objective_value": 70,
                "resource_usage": {"capital": 40},
                "evidence_refs": ["ev:c"],
            },
        ],
        resource_limits={"capital": {"max": 80}},
        time_budget_ms=1000,
    )

    preview = build_business_optimization_preview(
        workload_type="capital_allocation",
        options=[
            {
                "option_key": "project-a",
                "entity_key": "project-a",
                "objective_value": 100,
                "resource_usage": {"capital": 70},
                "evidence_refs": ["ev:a"],
            },
            {
                "option_key": "project-b",
                "entity_key": "project-b",
                "objective_value": 80,
                "resource_usage": {"capital": 40},
                "evidence_refs": ["ev:b"],
            },
            {
                "option_key": "project-c",
                "entity_key": "project-c",
                "objective_value": 70,
                "resource_usage": {"capital": 40},
                "evidence_refs": ["ev:c"],
            },
        ],
        resource_limits={"capital": {"max": 80}},
        time_budget_ms=1000,
    )

    assert problem["status"] == "AVAILABLE"
    assert preview["result"]["result"]["objective_value"] == 150.0
    assert preview["result"]["result"]["selected_variables"] == [
        "x::project-b",
        "x::project-c",
    ]


def test_dependencies_conflicts_required_and_forbidden_compile_safely():
    problem = build_business_optimization_problem(
        workload_type="portfolio_strategy",
        options=[
            {
                "option_key": "platform",
                "entity_key": "platform",
                "objective_value": 50,
                "evidence_refs": ["ev:platform"],
            },
            {
                "option_key": "expansion",
                "entity_key": "expansion",
                "objective_value": 100,
                "evidence_refs": ["ev:expansion"],
            },
            {
                "option_key": "alternative",
                "entity_key": "alternative",
                "objective_value": 70,
                "evidence_refs": ["ev:alternative"],
            },
        ],
        dependencies={"expansion": ["platform"]},
        conflicts=[("expansion", "alternative")],
        required_options=["platform"],
        forbidden_options=["alternative"],
        time_budget_ms=1000,
    )

    names = {row["name"] for row in problem["constraints"]}
    assert "requires::expansion::platform" in names
    assert "conflict::alternative::expansion" in names
    assert "required::platform" in names
    assert "forbidden::alternative" in names


def test_unknown_option_evidence_is_blocked_not_zero_filled():
    problem = build_business_optimization_problem(
        workload_type="marketing_budgets",
        options=[
            {
                "option_key": "paid-search",
                "entity_key": "search",
                "objective_value": None,
                "resource_usage": {"marketing_budget": 100},
                "evidence_refs": ["ev:search"],
            },
            {
                "option_key": "content",
                "entity_key": "content",
                "objective_value": 200,
                "resource_usage": {"marketing_budget": 100},
                "evidence_refs": ["ev:content"],
            },
        ],
        resource_limits={"marketing_budget": 100},
        time_budget_ms=1000,
    )

    assert problem["status"] == "AVAILABLE"
    assert problem["business_optimization"]["blocked_option_count"] == 1
    assert problem["metadata"]["blocked_options"][0]["option_key"] == (
        "paid-search"
    )
    assert problem["unknown_is_zero"] is False


def test_product_catalog_exposes_one_engine_twelve_workloads():
    catalog = build_business_optimization_catalog()

    assert catalog["status"] == "AVAILABLE"
    assert catalog["product_code"] == PRODUCT_CODE
    assert catalog["workload_count"] == 12
    assert set(catalog["workloads"]) == set(ALL_WORKLOADS)
    assert all(
        row["compiler_ready"] is True
        and row["shared_solver_fabric"] is True
        and row["solver_origin"] == "empire_owned"
        for row in catalog["workloads"].values()
    )
    assert catalog["predictive_cloud_compatible"] is True
    assert catalog["agi_compatible"] is True
    assert catalog["third_party_service_execution_allowed"] is False
    assert catalog["execution_authority"] == "none"


def test_enterprise_portfolio_optimizes_across_business_functions():
    from empire_os.business_optimization_product import (
        build_enterprise_portfolio_preview,
    )

    preview = build_enterprise_portfolio_preview(
        options=[
            {
                "option_key": "marketing-search",
                "entity_key": "marketing-search",
                "source_workload": "marketing_budgets",
                "objective_unit": "expected_contribution_cents",
                "objective_value": 9000,
                "resource_usage": {
                    "capital": 4000,
                    "staff_hours": 10,
                },
                "evidence_refs": ["ev:marketing"],
            },
            {
                "option_key": "new-market",
                "entity_key": "new-market",
                "source_workload": "market_expansion",
                "objective_unit": "expected_contribution_cents",
                "objective_value": 15000,
                "resource_usage": {
                    "capital": 8000,
                    "staff_hours": 30,
                },
                "evidence_refs": ["ev:market"],
            },
            {
                "option_key": "fulfilment-automation",
                "entity_key": "fulfilment-automation",
                "source_workload": "fulfilment",
                "objective_unit": "expected_contribution_cents",
                "objective_value": 8000,
                "resource_usage": {
                    "capital": 3000,
                    "staff_hours": 10,
                },
                "evidence_refs": ["ev:fulfilment"],
            },
        ],
        objective_unit="expected_contribution_cents",
        resource_limits={
            "capital": {"max": 11000},
            "staff_hours": {"max": 40},
        },
        time_budget_ms=1000,
    )

    assert preview["status"] == "AVAILABLE"
    assert preview["problem"]["metadata"]["enterprise_cross_workload"] is True
    assert preview["problem"]["metadata"]["source_workloads"] == [
        "fulfilment",
        "market_expansion",
        "marketing_budgets",
    ]
    assert preview["result"]["result"]["objective_value"] == 23000.0
    assert preview["result"]["result"]["selected_variables"] == [
        "x::fulfilment-automation",
        "x::new-market",
    ]
    assert preview["cross_workload"] is True
    assert preview["solver_origin"] == "empire_owned"
    assert preview["automatic_action_allowed"] is False


def test_enterprise_portfolio_rejects_mixed_objective_units():
    from empire_os.business_optimization_product import (
        build_enterprise_portfolio_problem,
    )

    with pytest.raises(ValueError, match="objective unit mismatch"):
        build_enterprise_portfolio_problem(
            options=[
                {
                    "option_key": "a",
                    "entity_key": "a",
                    "source_workload": "capital_allocation",
                    "objective_unit": "score",
                    "objective_value": 1,
                    "evidence_refs": ["ev:a"],
                }
            ],
            objective_unit="expected_contribution_cents",
            resource_limits={},
            time_budget_ms=1000,
        )


def test_catalog_exposes_cross_workload_enterprise_mode():
    catalog = build_business_optimization_catalog()

    assert catalog["enterprise_cross_workload_portfolio"] is True
    assert catalog["shared_resource_optimization"] is True

def test_bounded_resource_usage_must_be_explicit_for_each_candidate():
    problem = build_business_optimization_problem(
        workload_type="marketing_budgets",
        options=[
            {
                "option_key": "search",
                "entity_key": "search",
                "objective_value": 100,
                "resource_usage": {},
                "evidence_refs": ["ev:search"],
            }
        ],
        resource_limits={"marketing_budget": {"max": 1000}},
        time_budget_ms=1000,
    )

    assert problem["status"] == "UNAVAILABLE"
    assert problem["reason"] == "no_evidence_complete_options"
    blocked = problem["blocked_options"][0]
    assert blocked["reason"] == "unknown_bounded_resource_usage_preserved"
    assert blocked["missing_resource_usage"] == ["marketing_budget"]
    assert problem["unknown_is_zero"] is False
