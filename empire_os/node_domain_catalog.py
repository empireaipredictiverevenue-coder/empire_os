from __future__ import annotations

import importlib
from types import ModuleType
from typing import Iterable

from empire_os.hybrid_compute import Route
from empire_os.node_registry import (
    NodeAuthority,
    NodeHealth,
    NodeKind,
    NodeRegistry,
    NodeSpec,
)


CATALOG_VERSION = "empire-node-domain-catalog-v1"


def _load(module_name: str) -> tuple[ModuleType | None, dict]:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return None, {
            "module": module_name,
            "contract_verified": False,
            "error": type(exc).__name__,
        }

    return module, {
        "module": module_name,
        "contract_verified": True,
    }


def _require_all(
    module_name: str,
    symbols: Iterable[str],
) -> tuple[NodeHealth, dict]:
    module, meta = _load(module_name)

    if module is None:
        return NodeHealth.OFFLINE, meta

    wanted = tuple(symbols)
    missing = [
        name
        for name in wanted
        if not callable(getattr(module, name, None))
    ]

    if missing:
        return NodeHealth.DEGRADED, {
            **meta,
            "contract_verified": False,
            "required": list(wanted),
            "missing": missing,
        }

    return NodeHealth.HEALTHY, {
        **meta,
        "required": list(wanted),
    }


def _quant_contract() -> tuple[NodeHealth, dict]:
    module, meta = _load("empire_os.quant_brain")

    if module is None:
        return NodeHealth.OFFLINE, meta

    public = sorted(
        name
        for name in dir(module)
        if not name.startswith("_")
        and callable(getattr(module, name, None))
    )

    # Verify deterministic Quant by capability evidence, not a guessed
    # historical function name.
    keywords = {
        "bayesian": ("bayes", "posterior", "beta"),
        "economics": (
            "economic",
            "expected_value",
            "expected_profit",
            "expected_revenue",
            "expected_cost",
        ),
        "calibration": (
            "brier",
            "calibr",
            "log_loss",
            "reliability",
        ),
        "simulation": (
            "monte",
            "simulation",
        ),
        "information": (
            "information",
            "voi",
        ),
    }

    matched: dict[str, list[str]] = {}

    for capability, terms in keywords.items():
        hits = [
            name
            for name in public
            if any(term in name.lower() for term in terms)
        ]
        if hits:
            matched[capability] = hits

    # Require multiple independent deterministic Quant capability families.
    # Import success alone is not enough to declare the node healthy.
    healthy = len(matched) >= 2

    return (
        NodeHealth.HEALTHY
        if healthy
        else NodeHealth.DEGRADED,
        {
            **meta,
            "contract_verified": healthy,
            "public_callable_count": len(public),
            "matched_capability_groups": matched,
            "public_callables": public,
            "llm": False,
        },
    )


def add_domain_nodes(
    registry: NodeRegistry,
) -> NodeRegistry:

    predictive_health, predictive_meta = _require_all(
        "empire_os.predictive_revenue_formula",
        (
            "predictive_revenue_formula",
            "next_best_action_value",
        ),
    )

    registry.register(
        NodeSpec(
            node_id="predictive-revenue-core",
            kind=NodeKind.PREDICTIVE,
            capabilities=frozenset({
                "compute.predictive",
                "predictive.revenue",
                "predictive.next_best_action",
            }),
            routes=frozenset({
                Route.PREDICTIVE,
            }),
            health=predictive_health,
            authority=NodeAuthority.OBSERVE,
            provider="empire-native",
            metadata={
                **predictive_meta,
                "execution_enabled": False,
                "actual_revenue_authority": False,
            },
        )
    )

    quant_health, quant_meta = _quant_contract()

    registry.register(
        NodeSpec(
            node_id="quant-brain",
            kind=NodeKind.DETERMINISTIC,
            capabilities=frozenset({
                "compute.deterministic",
                "quant.bayesian",
                "quant.economics",
                "quant.calibration",
                "quant.simulation",
                "quant.value_of_information",
            }),
            routes=frozenset({
                Route.DETERMINISTIC,
            }),
            health=quant_health,
            authority=NodeAuthority.OBSERVE,
            provider="empire-native",
            metadata={
                **quant_meta,
                "execution_enabled": False,
            },
        )
    )

    # Optimization runtime must import successfully. Solver promotion remains
    # separately benchmark-gated by the existing optimization fabric.
    opt_module, opt_meta = _load(
        "empire_os.optimization_runtime"
    )

    opt_health = (
        NodeHealth.HEALTHY
        if opt_module is not None
        else NodeHealth.OFFLINE
    )

    registry.register(
        NodeSpec(
            node_id="optimization-runtime",
            kind=NodeKind.OPTIMIZATION,
            capabilities=frozenset({
                "compute.optimization",
                "optimization.portfolio",
                "optimization.solver_selection",
            }),
            routes=frozenset({
                Route.OPTIMIZATION,
            }),
            health=opt_health,
            authority=NodeAuthority.OBSERVE,
            provider="empire-native",
            metadata={
                **opt_meta,
                "execution_enabled": False,
                "benchmark_required": True,
                "solver_authority": False,
            },
        )
    )

    return registry
