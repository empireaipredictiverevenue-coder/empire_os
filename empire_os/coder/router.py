"""Provider-agnostic, role-aware model routing for Empire Coder."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .models import ModelRoute


@dataclass(frozen=True)
class ModelProfile:
    provider: str
    model: str
    capability: int = 1
    cost_tier: int = 0
    local: bool = False
    available: bool = True
    roles: tuple[str, ...] = ("writer", "verifier")


class ModelRouter:
    def __init__(self, profiles: Iterable[ModelProfile] = ()) -> None:
        self.profiles = tuple(p for p in profiles if p.available)

    @staticmethod
    def complexity(objective: str) -> int:
        text = str(objective or "").lower()
        hard = (
            "architecture", "migration", "security", "refactor",
            "production bug", "database", "concurrency", "payment",
            "multi-agent", "self-improve",
        )
        medium = (
            "implement", "build", "debug", "endpoint", "test",
            "module", "feature",
        )
        complexity_text = text
        for word in hard:
            token = re.escape(word)
            complexity_text = re.sub(
                rf"\b(?:no|without|avoid|do not|don't)\s+{token}s?\b",
                " ",
                complexity_text,
            )

        def contains_term(value: str, term: str) -> bool:
            return bool(re.search(
                rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])",
                value,
            ))

        if len(complexity_text) > 1000 or any(
            contains_term(complexity_text, word)
            for word in hard
        ):
            return 3
        if len(text) > 250 or any(
            contains_term(text, word)
            for word in medium
        ):
            return 2
        return 1

    def degraded_local_route(
        self,
        objective: str,
        *,
        role: str = "planner",
        exclude: Iterable[tuple[str, str]] = (),
    ) -> ModelRoute:
        """Return the best local advisory fallback.

        Prefer a local model that still meets the objective capability. Only
        degrade below the required capability when no adequate local profile
        remains healthy. This keeps provider outages from silently collapsing
        hard architecture/database planning onto the smallest model.
        """
        excluded = set(exclude)
        role_name = str(role or "planner").strip().lower()
        need = self.complexity(objective)
        local = [
            profile
            for profile in self.profiles
            if profile.local
            and role_name in profile.roles
            and (profile.provider, profile.model) not in excluded
        ]
        sufficient = [p for p in local if p.capability >= need]
        if sufficient:
            chosen = sorted(
                sufficient,
                key=lambda p: (p.cost_tier, -p.capability, p.provider, p.model),
            )[0]
            return ModelRoute(
                chosen.provider,
                chosen.model,
                (
                    f"local_provider_fallback; role={role_name}; "
                    f"objective_complexity={need}; "
                    f"capability={chosen.capability}"
                ),
                local=True,
                cost_tier=chosen.cost_tier,
            )
        if not local:
            return ModelRoute(
                "unconfigured",
                "none",
                "no local degraded advisory route configured",
                local=False,
                cost_tier=0,
            )
        chosen = sorted(
            local,
            key=lambda p: (-p.capability, p.cost_tier, p.provider, p.model),
        )[0]
        return ModelRoute(
            chosen.provider,
            chosen.model,
            (
                f"degraded_local_fallback; role={role_name}; "
                f"objective_complexity={need}; "
                f"capability={chosen.capability}"
            ),
            local=True,
            cost_tier=chosen.cost_tier,
        )

    def route(
        self,
        objective: str,
        *,
        role: str = "writer",
        exclude: Iterable[tuple[str, str]] = (),
    ) -> ModelRoute:
        objective_need = self.complexity(objective)
        excluded = set(exclude)
        role_name = str(role or "writer").strip().lower()
        # Advisory PLAN output is non-actionable, but the model still must be
        # capable of understanding the objective. Routing every PLAN as
        # capability-1 caused complex architecture/database plans to burn
        # local-model timeouts instead of failing fast or escalating.
        need = objective_need
        candidates = sorted(
            (
                profile
                for profile in self.profiles
                if role_name in profile.roles
                and profile.capability >= need
                and (profile.provider, profile.model) not in excluded
            ),
            key=lambda p: (
                p.capability < need,
                p.cost_tier,
                not p.local,
                -p.capability,
            ),
        )
        if not candidates:
            return ModelRoute(
                "unconfigured",
                "none",
                (
                    f"no distinct {role_name} model profile configured; "
                    "deterministic verification remains authoritative"
                ),
                local=False,
                cost_tier=0,
            )
        chosen = candidates[0]
        return ModelRoute(
            chosen.provider,
            chosen.model,
            (
                f"role={role_name}; complexity={need}; "
                f"capability={chosen.capability}"
            ),
            local=chosen.local,
            cost_tier=chosen.cost_tier,
        )
