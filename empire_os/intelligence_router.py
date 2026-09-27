"""Capability-level intelligence routing for EmpireOS.

Departments and Astra request an intelligence capability, not a hard-coded
provider/model. The existing ModelRouter still owns LLM model selection.

Important:
- intelligence selection does not grant execution authority;
- Quantitative tasks route to deterministic Quant Brain by default;
- future general/superintelligence classes are compatibility slots, not claims
  that such systems are currently available.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.model_router import ModelRouter


QUANT_TASKS = {
    "quant",
    "quantitative",
    "economics",
    "calibration",
    "monte_carlo",
    "risk",
    "portfolio",
    "value_of_information",
    "causal_statistics",
}

INTELLIGENCE_CLASSES = (
    "deterministic_quant",
    "local_fast",
    "local_reasoning",
    "frontier_fast",
    "frontier_reasoning",
    "ensemble",
    "future_general_intelligence",
    "future_superintelligence",
)


@dataclass(frozen=True)
class IntelligenceRoute:
    task: str
    engine: str
    intelligence_class: str
    provider: str | None
    model: str | None
    model_id: str | None
    route: str
    reasoning: bool
    vision: bool
    candidates: tuple[str, ...]
    rationale: str
    recommendation_only: bool = True
    authority_inherited_from_intelligence: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _classify_model(decision: Any) -> str:
    provider = str(decision.model.provider or "").lower()
    local = provider in {
        "ollama",
        "llama_cpp",
        "local",
        "local_llm",
    }
    if decision.route == "ROUTE_ENSEMBLE":
        return "ensemble"
    if decision.model.reasoning:
        return "local_reasoning" if local else "frontier_reasoning"
    return "local_fast" if local else "frontier_fast"


def preview_intelligence_route(
    *,
    task: str,
    messages: list[dict[str, Any]] | None = None,
    system: str | None = None,
    stakes: str = "normal",
    require_reasoning: bool = False,
    require_vision: bool = False,
    budget_remaining: float | None = None,
    remaining_queries: int | None = None,
    router: ModelRouter | None = None,
) -> dict[str, Any]:
    normalized = str(task or "reasoning").strip().lower()

    if normalized in QUANT_TASKS:
        return IntelligenceRoute(
            task=normalized,
            engine="quant_brain",
            intelligence_class="deterministic_quant",
            provider=None,
            model=None,
            model_id=None,
            route="ROUTE_DETERMINISTIC",
            reasoning=False,
            vision=False,
            candidates=("quant_brain",),
            rationale=(
                "quantitative task routed to deterministic mathematical "
                "verification rather than LLM arithmetic"
            ),
        ).as_dict()

    model_router = router or ModelRouter()
    decision = model_router.route(
        task=normalized,
        messages=list(messages or []),
        system=system,
        stakes=stakes,
        require_reasoning=require_reasoning,
        require_vision=require_vision,
        budget_remaining=budget_remaining,
        remaining_queries=remaining_queries,
    )
    return IntelligenceRoute(
        task=normalized,
        engine="llm_gateway",
        intelligence_class=_classify_model(decision),
        provider=decision.model.provider,
        model=decision.model.model,
        model_id=decision.model.model_id,
        route=decision.route,
        reasoning=bool(decision.model.reasoning),
        vision=bool(decision.model.vision),
        candidates=tuple(decision.candidates),
        rationale=decision.rationale,
    ).as_dict()


def intelligence_architecture() -> dict[str, Any]:
    return {
        "schema_version": "empire.intelligence_router.v1",
        "classes": INTELLIGENCE_CLASSES,
        "current_execution_engines": (
            "quant_brain",
            "llm_gateway",
        ),
        "future_compatibility_slots": (
            "future_general_intelligence",
            "future_superintelligence",
        ),
        "future_intelligence_currently_claimed_available": False,
        "authority_rule": (
            "greater intelligence never grants greater execution authority"
        ),
        "model_provider_agnostic": True,
        "execution_authority": "none",
    }
