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

    def route(
        self,
        objective: str,
        *,
        role: str = "writer",
        exclude: Iterable[tuple[str, str]] = (),
    ) -> ModelRoute:
        need = self.complexity(objective)
        excluded = set(exclude)
        role_name = str(role or "writer").strip().lower()
        candidates = sorted(
            (
                profile
                for profile in self.profiles
                if role_name in profile.roles
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
