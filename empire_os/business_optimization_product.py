"""Empire Business Optimization Engine.

One product contract for evidence-backed optimization across the business.
Workloads compile into the canonical Empire Optimization IR and are solved only
through Empire-owned runtime lanes. The product is recommendation-only: no
pricing, spend, staffing, allocation, inventory, fulfilment, scheduling,
capital, or market action is executed here.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from empire_os.intelligence_optimization_fabric import (
    build_optimization_fabric_plan,
)
from empire_os.optimization_problem_factory import build_problem_ir
from empire_os.optimization_runtime import execute_primary_solver


SCHEMA_VERSION = "empire.business_optimization_product.v1"
PRODUCT_CODE = "empire_optimization_engine"


WORKLOAD_SPECS: dict[str, dict[str, Any]] = {
    "lead_allocation": {
        "title": "Lead Allocation",
        "decision_unit": "lead_to_destination_assignment",
        "default_objective_sense": "MAXIMIZE",
        "entity_selection": {"min": 0, "max": 1},
        "primary_resources": ("destination_capacity",),
        "business_value": "route each qualified lead to the highest-value eligible destination",
    },
    "buyer_allocation": {
        "title": "Buyer Allocation",
        "decision_unit": "inventory_to_buyer_assignment",
        "default_objective_sense": "MAXIMIZE",
        "entity_selection": {"min": 0, "max": 1},
        "primary_resources": ("buyer_capacity",),
        "business_value": "maximize evidenced buyer allocation value under verified capacity",
    },
    "pricing": {
        "title": "Pricing Optimization",
        "decision_unit": "product_price_choice",
        "default_objective_sense": "MAXIMIZE",
        "entity_selection": {"min": 1, "max": 1},
        "primary_resources": (),
        "business_value": "select one evidenced price option per product or offer",
    },
    "sales_territories": {
        "title": "Sales Territory Optimization",
        "decision_unit": "territory_to_owner_assignment",
        "default_objective_sense": "MAXIMIZE",
        "entity_selection": {"min": 1, "max": 1},
        "primary_resources": ("seller_capacity",),
        "business_value": "assign territories to the highest-value feasible sales coverage",
    },
    "marketing_budgets": {
        "title": "Marketing Budget Optimization",
        "decision_unit": "channel_budget_choice",
        "default_objective_sense": "MAXIMIZE",
        "entity_selection": {"min": 0, "max": 1},
        "primary_resources": ("marketing_budget",),
        "business_value": "allocate bounded spend to evidence-backed channel choices",
    },
    "staff_capacity": {
        "title": "Staff Capacity Optimization",
        "decision_unit": "work_to_staff_assignment",
        "default_objective_sense": "MAXIMIZE",
        "entity_selection": {"min": 0, "max": 1},
        "primary_resources": ("staff_hours",),
        "business_value": "allocate work against observed staff skill and available capacity",
    },
    "fulfilment": {
        "title": "Fulfilment Optimization",
        "decision_unit": "order_to_fulfilment_path_assignment",
        "default_objective_sense": "MAXIMIZE",
        "entity_selection": {"min": 0, "max": 1},
        "primary_resources": ("fulfilment_capacity",),
        "business_value": "choose feasible fulfilment paths while protecting service and margin",
    },
    "inventory": {
        "title": "Inventory Optimization",
        "decision_unit": "inventory_allocation_choice",
        "default_objective_sense": "MAXIMIZE",
        "entity_selection": {"min": 0, "max": 1},
        "primary_resources": ("inventory_capacity",),
        "business_value": "allocate scarce inventory to the highest-value feasible use",
    },
    "scheduling": {
        "title": "Scheduling Optimization",
        "decision_unit": "job_slot_assignment",
        "default_objective_sense": "MINIMIZE",
        "entity_selection": {"min": 1, "max": 1},
        "primary_resources": ("slot_capacity", "staff_hours"),
        "business_value": "minimize evidenced scheduling cost, delay, or penalty under capacity",
    },
    "capital_allocation": {
        "title": "Capital Allocation",
        "decision_unit": "investment_choice",
        "default_objective_sense": "MAXIMIZE",
        "entity_selection": {"min": 0, "max": 1},
        "primary_resources": ("capital", "risk"),
        "business_value": "select risk-adjusted investments within explicit capital limits",
    },
    "market_expansion": {
        "title": "Market Expansion Optimization",
        "decision_unit": "market_entry_choice",
        "default_objective_sense": "MAXIMIZE",
        "entity_selection": {"min": 0, "max": 1},
        "primary_resources": ("capital", "staff_capacity", "launch_capacity"),
        "business_value": "select evidence-backed markets under capital and operating constraints",
    },
    "portfolio_strategy": {
        "title": "Portfolio Strategy Optimization",
        "decision_unit": "strategic_action_choice",
        "default_objective_sense": "MAXIMIZE",
        "entity_selection": {"min": 0, "max": 1},
        "primary_resources": ("capital", "staff_capacity", "risk"),
        "business_value": "choose the strongest feasible combination of strategic actions",
    },
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if result != result or result in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be finite")
    return result


def _nonnegative(value: Any, name: str) -> float:
    result = _number(value, name)
    if result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def _refs(raw: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(sorted({
        _text(ref)
        for ref in (raw.get("evidence_refs") or ())
        if _text(ref)
    }))


def _constraint_spec(
    raw: Any,
    *,
    name: str,
) -> dict[str, float]:
    if isinstance(raw, Mapping):
        parsed: dict[str, float] = {}
        for key in ("min", "max", "exact"):
            if raw.get(key) is not None:
                parsed[key] = _nonnegative(
                    raw[key],
                    f"{name}:{key}",
                )
        if not parsed:
            raise ValueError(f"{name} requires min, max, or exact")
        if "exact" in parsed and len(parsed) != 1:
            raise ValueError(f"{name}: exact cannot be mixed with min/max")
        if (
            "min" in parsed
            and "max" in parsed
            and parsed["min"] > parsed["max"]
        ):
            raise ValueError(f"{name}: min cannot exceed max")
        return parsed
    return {"max": _nonnegative(raw, name)}


def _selection_bounds(
    spec: Mapping[str, Any],
    override: Mapping[str, Any] | None,
) -> tuple[int, int]:
    source = dict(spec.get("entity_selection") or {})
    if override:
        source.update(dict(override))
    minimum = int(source.get("min", 0))
    maximum = int(source.get("max", 1))
    if minimum < 0 or maximum < 0 or minimum > maximum:
        raise ValueError("invalid entity selection bounds")
    return minimum, maximum


def build_business_optimization_problem(
    *,
    workload_type: str,
    options: Sequence[Mapping[str, Any]],
    resource_limits: Mapping[str, Any] | None = None,
    selection_groups: Sequence[Mapping[str, Any]] = (),
    dependencies: Mapping[str, Sequence[str]] | None = None,
    conflicts: Sequence[Sequence[str]] = (),
    required_options: Sequence[str] = (),
    forbidden_options: Sequence[str] = (),
    objective_sense: str | None = None,
    entity_selection: Mapping[str, Any] | None = None,
    tenant_id: str | None = None,
    time_budget_ms: Any = None,
    cost_budget_minor_units: Any = None,
    workload_key: str | None = None,
) -> dict[str, Any]:
    """Compile one business workload into canonical Empire Optimization IR.

    Each option is a binary choice with:
      option_key, entity_key, objective_value, evidence_refs,
      optional target_key, resource_usage, partition_key, metadata.

    UNKNOWN economics/evidence are blocked, never coerced to zero.
    """
    workload = _text(workload_type)
    if workload not in WORKLOAD_SPECS:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "unsupported_business_optimization_workload",
            "supported_workloads": sorted(WORKLOAD_SPECS),
            "execution_authority": "none",
        }

    spec = WORKLOAD_SPECS[workload]
    declared_resource_keys = tuple(sorted({
        _text(resource)
        for resource in dict(resource_limits or {})
        if _text(resource)
    }))
    sense = _text(
        objective_sense or spec["default_objective_sense"]
    ).upper()
    if sense not in {"MAXIMIZE", "MINIMIZE"}:
        raise ValueError("objective_sense must be MAXIMIZE or MINIMIZE")

    minimum_per_entity, maximum_per_entity = _selection_bounds(
        spec,
        entity_selection,
    )

    variables: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    option_to_variable: dict[str, str] = {}
    entity_members: dict[str, list[str]] = {}
    resource_coefficients: dict[str, dict[str, float]] = {}

    for index, raw in enumerate(options):
        if not isinstance(raw, Mapping):
            blocked.append({
                "option_index": index,
                "reason": "option_not_mapping",
            })
            continue

        option_key = _text(raw.get("option_key"))
        entity_key = _text(raw.get("entity_key"))
        target_key = _text(raw.get("target_key")) or None
        refs = _refs(raw)
        missing: list[str] = []
        if not option_key:
            missing.append("option_key")
        if not entity_key:
            missing.append("entity_key")
        if raw.get("objective_value") is None:
            missing.append("objective_value")
        if not refs:
            missing.append("evidence_refs")
        if missing:
            blocked.append({
                "option_key": option_key or None,
                "entity_key": entity_key or None,
                "missing_fields": missing,
                "reason": "unknown_option_evidence_preserved",
            })
            continue
        if option_key in option_to_variable:
            blocked.append({
                "option_key": option_key,
                "reason": "duplicate_option_key",
            })
            continue

        try:
            objective_value = _number(
                raw["objective_value"],
                f"objective_value:{option_key}",
            )
            resource_usage = {
                _text(resource): _nonnegative(
                    amount,
                    f"resource_usage:{option_key}:{resource}",
                )
                for resource, amount in dict(
                    raw.get("resource_usage") or {}
                ).items()
                if _text(resource)
            }
            missing_resource_usage = [
                resource
                for resource in declared_resource_keys
                if resource not in resource_usage
            ]
            if missing_resource_usage:
                blocked.append({
                    "option_key": option_key,
                    "entity_key": entity_key,
                    "reason": "unknown_bounded_resource_usage_preserved",
                    "missing_resource_usage": missing_resource_usage,
                })
                continue
        except ValueError as exc:
            blocked.append({
                "option_key": option_key,
                "reason": "invalid_option_economics",
                "detail": str(exc),
            })
            continue

        variable = f"x::{option_key}"
        option_to_variable[option_key] = variable
        entity_members.setdefault(entity_key, []).append(variable)
        for resource, amount in resource_usage.items():
            resource_coefficients.setdefault(resource, {})[
                variable
            ] = amount

        variables.append({
            "variable": variable,
            "option_key": option_key,
            "entity_key": entity_key,
            "target_key": target_key,
            "objective_value": objective_value,
            "resource_usage": resource_usage,
            "partition_key": (
                _text(raw.get("partition_key")) or None
            ),
            "evidence_refs": refs,
            "metadata": deepcopy(dict(raw.get("metadata") or {})),
        })

    if not variables:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_evidence_complete_options",
            "workload_type": workload,
            "blocked_options": blocked,
            "unknown_is_zero": False,
            "execution_authority": "none",
        }

    constraints: list[dict[str, Any]] = []

    for entity_key, members in sorted(entity_members.items()):
        coefficients = {variable: 1 for variable in members}
        if minimum_per_entity == maximum_per_entity:
            constraints.append({
                "name": f"entity::{entity_key}",
                "coefficients": coefficients,
                "sense": "==",
                "rhs": maximum_per_entity,
                "constraint_type": "entity_selection",
            })
        else:
            if maximum_per_entity >= 0:
                constraints.append({
                    "name": f"entity_max::{entity_key}",
                    "coefficients": coefficients,
                    "sense": "<=",
                    "rhs": maximum_per_entity,
                    "constraint_type": "entity_selection",
                })
            if minimum_per_entity > 0:
                constraints.append({
                    "name": f"entity_min::{entity_key}",
                    "coefficients": coefficients,
                    "sense": ">=",
                    "rhs": minimum_per_entity,
                    "constraint_type": "entity_selection",
                })

    for resource, raw_limit in sorted(
        dict(resource_limits or {}).items()
    ):
        resource_key = _text(resource)
        if not resource_key:
            continue
        limit = _constraint_spec(
            raw_limit,
            name=f"resource_limit:{resource_key}",
        )
        coefficients = dict(
            resource_coefficients.get(resource_key) or {}
        )
        if not coefficients:
            blocked.append({
                "resource": resource_key,
                "reason": "resource_limit_has_no_observed_usage",
            })
            continue
        if "exact" in limit:
            constraints.append({
                "name": f"resource::{resource_key}",
                "coefficients": coefficients,
                "sense": "==",
                "rhs": limit["exact"],
                "constraint_type": "resource_limit",
            })
        else:
            if "max" in limit:
                constraints.append({
                    "name": f"resource_max::{resource_key}",
                    "coefficients": coefficients,
                    "sense": "<=",
                    "rhs": limit["max"],
                    "constraint_type": "resource_limit",
                })
            if "min" in limit:
                constraints.append({
                    "name": f"resource_min::{resource_key}",
                    "coefficients": coefficients,
                    "sense": ">=",
                    "rhs": limit["min"],
                    "constraint_type": "resource_limit",
                })

    for index, raw in enumerate(selection_groups):
        if not isinstance(raw, Mapping):
            raise ValueError("selection_groups must contain mappings")
        group_key = _text(raw.get("group_key")) or f"group::{index}"
        option_keys = [
            _text(value)
            for value in (raw.get("option_keys") or ())
            if _text(value)
        ]
        unknown = sorted({
            key
            for key in option_keys
            if key not in option_to_variable
        })
        if unknown:
            raise ValueError(
                f"selection_group {group_key} references unknown options: "
                + ",".join(unknown)
            )
        bounds = _constraint_spec(
            {
                key: raw[key]
                for key in ("min", "max", "exact")
                if raw.get(key) is not None
            },
            name=f"selection_group:{group_key}",
        )
        coefficients = {
            option_to_variable[key]: 1
            for key in option_keys
        }
        if "exact" in bounds:
            constraints.append({
                "name": f"group::{group_key}",
                "coefficients": coefficients,
                "sense": "==",
                "rhs": bounds["exact"],
                "constraint_type": "selection_group",
            })
        else:
            if "max" in bounds:
                constraints.append({
                    "name": f"group_max::{group_key}",
                    "coefficients": coefficients,
                    "sense": "<=",
                    "rhs": bounds["max"],
                    "constraint_type": "selection_group",
                })
            if "min" in bounds:
                constraints.append({
                    "name": f"group_min::{group_key}",
                    "coefficients": coefficients,
                    "sense": ">=",
                    "rhs": bounds["min"],
                    "constraint_type": "selection_group",
                })

    for child, parents in sorted(dict(dependencies or {}).items()):
        child_key = _text(child)
        if child_key not in option_to_variable:
            raise ValueError(f"dependency child unknown:{child_key}")
        for parent in parents:
            parent_key = _text(parent)
            if parent_key not in option_to_variable:
                raise ValueError(f"dependency parent unknown:{parent_key}")
            constraints.append({
                "name": f"requires::{child_key}::{parent_key}",
                "coefficients": {
                    option_to_variable[child_key]: 1,
                    option_to_variable[parent_key]: -1,
                },
                "sense": "<=",
                "rhs": 0,
                "constraint_type": "dependency",
            })

    seen_conflicts: set[tuple[str, str]] = set()
    for raw_pair in conflicts:
        values = [_text(value) for value in raw_pair if _text(value)]
        if len(values) != 2:
            raise ValueError("each conflict must contain exactly two options")
        left, right = sorted(values)
        if left not in option_to_variable or right not in option_to_variable:
            raise ValueError(f"conflict references unknown option:{left}:{right}")
        if left == right:
            raise ValueError("an option cannot conflict with itself")
        if (left, right) in seen_conflicts:
            continue
        seen_conflicts.add((left, right))
        constraints.append({
            "name": f"conflict::{left}::{right}",
            "coefficients": {
                option_to_variable[left]: 1,
                option_to_variable[right]: 1,
            },
            "sense": "<=",
            "rhs": 1,
            "constraint_type": "conflict",
        })

    for option_key in sorted({_text(v) for v in required_options if _text(v)}):
        if option_key not in option_to_variable:
            raise ValueError(f"required option unknown:{option_key}")
        constraints.append({
            "name": f"required::{option_key}",
            "coefficients": {option_to_variable[option_key]: 1},
            "sense": "==",
            "rhs": 1,
            "constraint_type": "fixed_choice",
        })

    for option_key in sorted({_text(v) for v in forbidden_options if _text(v)}):
        if option_key not in option_to_variable:
            raise ValueError(f"forbidden option unknown:{option_key}")
        constraints.append({
            "name": f"forbidden::{option_key}",
            "coefficients": {option_to_variable[option_key]: 1},
            "sense": "==",
            "rhs": 0,
            "constraint_type": "fixed_choice",
        })

    problem = build_problem_ir(
        workload_key=(
            _text(workload_key)
            or f"business_optimization::{workload}"
        ),
        workload_type=workload,
        source_schema_version=SCHEMA_VERSION,
        variable_type="BINARY",
        variables=variables,
        objective={
            "sense": sense,
            "linear": {
                row["variable"]: row["objective_value"]
                for row in variables
            },
            "quadratic": {},
            "objective_semantics": (
                "evidence_backed_business_value"
                if sense == "MAXIMIZE"
                else "evidence_backed_business_cost_or_penalty"
            ),
        },
        constraints=constraints,
        tenant_id=tenant_id,
        time_budget_ms=time_budget_ms,
        cost_budget_minor_units=cost_budget_minor_units,
        representations=("CQM",),
        metadata={
            "product_code": PRODUCT_CODE,
            "product_schema_version": SCHEMA_VERSION,
            "workload_title": spec["title"],
            "decision_unit": spec["decision_unit"],
            "business_value": spec["business_value"],
            "primary_resources": list(spec["primary_resources"]),
            "blocked_options": blocked,
            "solver_runtime_policy": "empire_owned_only",
            "third_party_service_execution_allowed": False,
        },
    )
    problem["business_optimization"] = {
        "product_code": PRODUCT_CODE,
        "workload_type": workload,
        "workload_title": spec["title"],
        "option_count": len(variables),
        "blocked_option_count": len(blocked),
        "resource_limit_count": len(resource_limits or {}),
        "recommendation_only": True,
        "actual_revenue": False,
        "execution_authority": "none",
    }
    return problem


def build_business_optimization_preview(
    *,
    workload_type: str,
    options: Sequence[Mapping[str, Any]],
    solve: bool = True,
    exact_variable_limit: int = 24,
    max_variables_per_shard: int = 5000,
    **kwargs: Any,
) -> dict[str, Any]:
    """Compile, plan and optionally solve one recommendation-only workload."""
    problem = build_business_optimization_problem(
        workload_type=workload_type,
        options=options,
        **kwargs,
    )
    if str(problem.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "product_code": PRODUCT_CODE,
            "workload_type": workload_type,
            "problem": problem,
            "execution_authority": "none",
        }

    plan = build_optimization_fabric_plan(
        problem,
        exact_variable_limit=exact_variable_limit,
        max_variables_per_shard=max_variables_per_shard,
    )
    result = (
        execute_primary_solver(
            plan,
            exact_variable_limit=exact_variable_limit,
        )
        if solve and str(plan.get("status") or "").upper() == "AVAILABLE"
        else None
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "product_code": PRODUCT_CODE,
        "workload_type": workload_type,
        "problem": problem,
        "plan": plan,
        "result": result,
        "solver_origin": "empire_owned",
        "third_party_service_execution_allowed": False,
        "recommendation_only": True,
        "automatic_action_allowed": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def build_business_optimization_catalog() -> dict[str, Any]:
    """Expose the product/workload catalog without claiming execution."""
    workloads = {
        key: {
            **deepcopy(value),
            "compiler_ready": True,
            "shared_solver_fabric": True,
            "solver_origin": "empire_owned",
            "recommendation_only": True,
        }
        for key, value in sorted(WORKLOAD_SPECS.items())
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "product_code": PRODUCT_CODE,
        "product_name": "Empire Business Optimization Engine",
        "workload_count": len(workloads),
        "workloads": workloads,
        "shared_engine": (
            "Empire Optimization IR -> Empire Solver Intelligence -> "
            "Empire-owned solvers -> Benchmark Arena -> recommendation"
        ),
        "predictive_cloud_compatible": True,
        "agi_compatible": True,
        "enterprise_cross_workload_portfolio": True,
        "shared_resource_optimization": True,
        "multi_tenant_context_supported": True,
        "third_party_service_execution_allowed": False,
        "automatic_business_action_allowed": False,
        "execution_authority": "none",
    }


def build_enterprise_portfolio_problem(
    *,
    options: Sequence[Mapping[str, Any]],
    objective_unit: str,
    resource_limits: Mapping[str, Any],
    objective_sense: str = "MAXIMIZE",
    tenant_id: str | None = None,
    time_budget_ms: Any = None,
    cost_budget_minor_units: Any = None,
) -> dict[str, Any]:
    """Optimize choices from multiple Empire workloads under shared resources.

    Cross-workload objective values must use one explicitly declared comparable
    unit, for example expected_incremental_contribution_cents. The compiler
    never converts unlike units or invents normalization weights.
    """
    unit = _text(objective_unit)
    if not unit:
        raise ValueError("objective_unit required for cross-workload portfolio")

    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(options):
        if not isinstance(raw, Mapping):
            raise ValueError("enterprise portfolio options must be mappings")
        source_workload = _text(raw.get("source_workload"))
        if source_workload not in WORKLOAD_SPECS:
            raise ValueError(
                f"unsupported source_workload at option {index}:"
                f"{source_workload or 'missing'}"
            )
        declared_unit = _text(raw.get("objective_unit"))
        if declared_unit and declared_unit != unit:
            raise ValueError(
                f"objective unit mismatch:{declared_unit}!={unit}"
            )

        packet = deepcopy(dict(raw))
        packet.pop("source_workload", None)
        packet.pop("objective_unit", None)
        metadata = deepcopy(dict(packet.get("metadata") or {}))
        metadata.update({
            "source_workload": source_workload,
            "source_workload_title": WORKLOAD_SPECS[
                source_workload
            ]["title"],
            "objective_unit": unit,
        })
        packet["metadata"] = metadata
        normalized.append(packet)

    problem = build_business_optimization_problem(
        workload_type="portfolio_strategy",
        options=normalized,
        resource_limits=resource_limits,
        objective_sense=objective_sense,
        entity_selection={"min": 0, "max": 1},
        tenant_id=tenant_id,
        time_budget_ms=time_budget_ms,
        cost_budget_minor_units=cost_budget_minor_units,
        workload_key="business_optimization::enterprise_portfolio",
    )
    if str(problem.get("status") or "").upper() == "AVAILABLE":
        problem["workload_type"] = "enterprise_portfolio_strategy"
        # The semantic workload is deliberately changed after generic compile,
        # so rebuild the canonical IR rather than mutating a fingerprinted
        # packet. Use the already validated fields as the input contract.
        problem = build_problem_ir(
            workload_key="business_optimization::enterprise_portfolio",
            workload_type="enterprise_portfolio_strategy",
            source_schema_version=SCHEMA_VERSION,
            variable_type=problem["variable_type"],
            variables=problem["variables"],
            objective=problem["objective"],
            constraints=problem["constraints"],
            tenant_id=problem.get("tenant_id"),
            time_budget_ms=problem.get("time_budget_ms"),
            cost_budget_minor_units=problem.get(
                "cost_budget_minor_units"
            ),
            representations=tuple(problem.get("representations") or ()),
            metadata={
                **dict(problem.get("metadata") or {}),
                "enterprise_cross_workload": True,
                "objective_unit": unit,
                "source_workloads": sorted({
                    _text(raw.get("source_workload"))
                    for raw in options
                    if isinstance(raw, Mapping)
                }),
            },
        )
        problem["business_optimization"] = {
            "product_code": PRODUCT_CODE,
            "workload_type": "enterprise_portfolio_strategy",
            "workload_title": "Enterprise Portfolio Strategy",
            "option_count": len(problem.get("variables") or ()),
            "objective_unit": unit,
            "cross_workload": True,
            "recommendation_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
        }
    return problem


def build_enterprise_portfolio_preview(
    *,
    options: Sequence[Mapping[str, Any]],
    objective_unit: str,
    resource_limits: Mapping[str, Any],
    objective_sense: str = "MAXIMIZE",
    tenant_id: str | None = None,
    time_budget_ms: Any = None,
    cost_budget_minor_units: Any = None,
    exact_variable_limit: int = 24,
    max_variables_per_shard: int = 5000,
) -> dict[str, Any]:
    problem = build_enterprise_portfolio_problem(
        options=options,
        objective_unit=objective_unit,
        resource_limits=resource_limits,
        objective_sense=objective_sense,
        tenant_id=tenant_id,
        time_budget_ms=time_budget_ms,
        cost_budget_minor_units=cost_budget_minor_units,
    )
    if str(problem.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "product_code": PRODUCT_CODE,
            "workload_type": "enterprise_portfolio_strategy",
            "problem": problem,
            "execution_authority": "none",
        }

    plan = build_optimization_fabric_plan(
        problem,
        exact_variable_limit=exact_variable_limit,
        max_variables_per_shard=max_variables_per_shard,
    )
    result = (
        execute_primary_solver(
            plan,
            exact_variable_limit=exact_variable_limit,
        )
        if str(plan.get("status") or "").upper() == "AVAILABLE"
        else None
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "product_code": PRODUCT_CODE,
        "workload_type": "enterprise_portfolio_strategy",
        "objective_unit": objective_unit,
        "problem": problem,
        "plan": plan,
        "result": result,
        "cross_workload": True,
        "solver_origin": "empire_owned",
        "third_party_service_execution_allowed": False,
        "recommendation_only": True,
        "automatic_action_allowed": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
