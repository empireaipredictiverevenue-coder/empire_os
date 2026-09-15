"""Empire OS dynamic model router.

The router chooses the best currently eligible model for a request.

Important:
- quality values in the registry are PRIOR estimates until calibration exists
- unknown costs are never treated as zero
- hard budget constraints are enforced before selection
- execution remains in llm_gateway.py
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from empire_os.model_registry import ModelRegistry, ModelSpec


@dataclass(frozen=True)
class RouteDecision:
    route: str
    model: ModelSpec
    score: float
    reasoning_gain: float
    estimated_cost: float
    signals: dict[str, float]
    candidates: tuple[str, ...]
    budget_blocked: bool = False
    rationale: str = ""


class ModelRouter:
    """Cost-aware, capability-aware model selection."""

    VERIFICATION_TERMS = {
        "verify", "validate", "prove", "equivalent", "correctness",
        "entailment", "constraint", "test", "audit", "reconcile",
        "factual", "compliance", "regression", "evidence", "consistency",
    }

    AMBIGUOUS_TERMS = {
        "compare", "tradeoff", "uncertain", "ambiguous", "partial",
        "strategy", "multi-criteria", "contested", "forecast",
        "scenario", "counterfactual", "recommendation",
    }

    CODING_TERMS = {
        "code", "python", "javascript", "typescript", "sql", "bug",
        "function", "stack trace", "compile", "test", "patch",
        "refactor", "repository", "git", "implementation",
    }

    RESEARCH_TERMS = {
        "research", "investigate", "analyze", "literature", "sources",
        "evidence", "market", "competitor", "deep research",
    }

    HIGH_STAKES = {"high", "critical"}

    def __init__(self, registry: ModelRegistry | None = None) -> None:
        self.registry = registry or ModelRegistry()
        self.blocked_providers = set()
        self.blocked_models = set()
        try:
            import json
            from pathlib import Path
            policy_path = Path("config/model_registry.json")
            raw = json.loads(policy_path.read_text(encoding="utf-8"))
            policy = raw.get("policy", {})
            self.blocked_providers = {
                str(x).lower()
                for x in policy.get("blocked_providers", [])
            }
            self.blocked_models = {
                str(x).lower()
                for x in policy.get("blocked_models", [])
            }
        except Exception:
            pass

    def _signals(
        self,
        *,
        task: str,
        messages: list[dict[str, Any]],
        system: str | None,
    ) -> dict[str, float]:
        text = " ".join(
            str(m.get("content", ""))
            for m in messages
            if isinstance(m, dict)
        )
        if system:
            text += " " + system

        lower = text.lower()
        words = max(1, len(re.findall(r"\b\w+\b", text)))

        code = 1.0 if (
            "```" in text
            or re.search(r"\b(def|class|SELECT|import|pytest|git diff)\b", text, re.I)
        ) else 0.0

        numeric = min(
            1.0,
            sum(ch.isdigit() for ch in text) / max(50, len(text)),
        )

        def density(terms: set[str]) -> float:
            hits = sum(1 for term in terms if term in lower)
            return min(1.0, hits / 3.0)

        verification = density(self.VERIFICATION_TERMS)
        ambiguous = density(self.AMBIGUOUS_TERMS)
        coding = density(self.CODING_TERMS)
        research = density(self.RESEARCH_TERMS)
        length = min(1.0, words / 1200.0)

        normalized_task = (task or "reasoning").strip().lower()

        if normalized_task in {
            "verification", "judge", "reasoning", "audit",
            "fact_check", "code_review",
        }:
            verification = max(verification, 1.0)

        if normalized_task in {"coding", "code", "code_review"}:
            coding = max(coding, 1.0)

        if normalized_task in {"research", "deep_research"}:
            research = max(research, 1.0)

        return {
            "length": length,
            "code": code,
            "numeric_density": numeric,
            "verification": verification,
            "ambiguous": ambiguous,
            "coding": coding,
            "research": research,
        }

    @staticmethod
    def _estimated_cost(model: ModelSpec) -> float:
        """
        Registry cost is expressed per 1k output tokens.

        Unknown/invalid cost is represented internally as infinity.
        This prevents '0' from accidentally meaning 'free'.
        """
        if model.free:
            return 0.0

        if model.cost_per_1k_output is None:
            return math.inf

        try:
            value = float(model.cost_per_1k_output)
        except (TypeError, ValueError):
            return math.inf

        if not math.isfinite(value) or value <= 0:
            return math.inf

        return value

    @staticmethod
    def _cost_penalty(model: ModelSpec, cost_weight: float) -> float:
        cost = ModelRouter._estimated_cost(model)

        if model.free:
            return 0.0

        if not math.isfinite(cost):
            return 1.0

        return min(0.65, cost * cost_weight)

    def _required_capabilities(
        self,
        task: str,
        signals: dict[str, float],
    ) -> set[str]:
        if signals["coding"] >= 0.5:
            return {"coding"}

        if task in {"classification", "extraction", "summarization", "research"}:
            return {task}

        return {"general"}

    def route(
        self,
        *,
        task: str,
        messages: list[dict[str, Any]],
        system: str | None = None,
        stakes: str = "normal",
        require_reasoning: bool = False,
        require_vision: bool = False,
        budget_remaining: float | None = None,
        remaining_queries: int | None = None,
    ) -> RouteDecision:
        task = (task or "reasoning").strip().lower()
        stakes = (stakes or "normal").strip().lower()

        signals = self._signals(
            task=task,
            messages=messages,
            system=system,
        )

        verification_pressure = min(
            1.0,
            signals["verification"] * 0.50
            + signals["code"] * 0.18
            + signals["numeric_density"] * 0.07
            + signals["ambiguous"] * 0.12
            + signals["research"] * 0.08
            + signals["length"] * 0.05,
        )

        if stakes in self.HIGH_STAKES:
            verification_pressure = min(
                1.0,
                verification_pressure + 0.20,
            )

        required = self._required_capabilities(task, signals)

        candidates = self.registry.candidates(
            task=task,
            required_capabilities=required,
            require_reasoning=require_reasoning,
            require_vision=require_vision,
        )

        # If strict capability filtering yields nothing, relax only the
        # capability filter. Do not invent providers/models.
        if not candidates:
            candidates = self.registry.candidates(
                task=task,
                require_reasoning=require_reasoning,
                require_vision=require_vision,
            )

        if not candidates and require_reasoning:
            # A graceful fallback is preferable to crashing the whole agent,
            # but the decision records that reasoning was unavailable.
            candidates = self.registry.candidates(
                task=task,
                require_vision=require_vision,
            )

        candidates = [
            m for m in candidates
            if m.provider.lower() not in self.blocked_providers
            and m.model.lower() not in self.blocked_models
        ]

        if not candidates:
            raise RuntimeError("no_policy_eligible_llm_models")

        # Hard per-query budget when both remaining budget and query count
        # are known.
        per_query_budget = None
        if (
            budget_remaining is not None
            and remaining_queries is not None
            and remaining_queries > 0
        ):
            per_query_budget = max(
                0.0,
                float(budget_remaining) / remaining_queries,
            )

        scored: list[tuple[float, ModelSpec, float, float, bool, str]] = []

        for model in candidates:
            quality = max(0.0, min(1.0, model.quality_for(task)))

            # This is explicitly a PRIOR until we have matched-pair
            # calibration from real Empire workloads.
            reasoning_gain = (
                0.22 * verification_pressure
                if model.reasoning
                else 0.0
            )

            cost = self._estimated_cost(model)
            budget_blocked = False

            if per_query_budget is not None:
                if math.isinf(cost) and not model.free:
                    budget_blocked = True
                elif cost > per_query_budget:
                    budget_blocked = True

            # Higher quality wins, reasoning gets paid for only where the
            # query presents enough verification pressure, and cost matters.
            score = quality + reasoning_gain
            score -= self._cost_penalty(model, 0.08)

            if signals["coding"] >= 0.5 and "coding" in model.capabilities:
                score += 0.05

            if signals["research"] >= 0.5 and "research" in model.capabilities:
                score += 0.05

            if model.free:
                score += 0.03

            if budget_blocked:
                score = -math.inf

            rationale_parts = []

            if model.reasoning:
                rationale_parts.append(
                    f"reasoning_prior={reasoning_gain:.3f}"
                )

            if model.free:
                rationale_parts.append("free")

            if budget_blocked:
                rationale_parts.append("budget_blocked")

            scored.append(
                (
                    score,
                    model,
                    reasoning_gain,
                    cost,
                    budget_blocked,
                    ",".join(rationale_parts),
                )
            )

        scored.sort(
            key=lambda row: (
                row[0],
                -row[1].priority,
            ),
            reverse=True,
        )

        eligible = [row for row in scored if math.isfinite(row[0])]

        # If all paid models are unaffordable/unknown-cost, choose the best
        # free model rather than violating the hard budget.
        if not eligible:
            free_models = [
                row for row in scored
                if row[1].free
            ]

            if not free_models:
                # Nothing can legally satisfy the budget. Keep the decision
                # explicit instead of silently overspending.
                raise RuntimeError("llm_budget_exhausted")

            eligible = free_models

        best_score, best_model, reasoning_gain, cost, budget_blocked, reason = eligible[0]

        route = "ROUTE_NONREASONING"

        if best_model.reasoning and verification_pressure >= 0.55:
            route = "ROUTE_REASONING"

        if (
            signals["ambiguous"] >= 0.66
            and stakes in self.HIGH_STAKES
        ):
            route = "ROUTE_ENSEMBLE"

        rationale = (
            f"verification_pressure={verification_pressure:.3f}; "
            f"quality_prior={best_model.quality_for(task):.3f}; "
            f"{reason or 'standard_selection'}"
        )

        if per_query_budget is not None:
            rationale += f"; per_query_budget={per_query_budget:.6f}"

        if math.isinf(cost):
            estimated_cost = 0.0 if best_model.free else math.inf
        else:
            estimated_cost = cost

        return RouteDecision(
            route=route,
            model=best_model,
            score=best_score,
            reasoning_gain=reasoning_gain,
            estimated_cost=estimated_cost,
            signals=signals,
            candidates=tuple(row[1].model_id for row in scored),
            budget_blocked=budget_blocked,
            rationale=rationale,
        )
