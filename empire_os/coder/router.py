"""Provider-agnostic model routing for Empire Coder."""
from __future__ import annotations

from dataclasses import dataclass
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
        if len(text) > 1000 or any(word in text for word in hard):
            return 3
        if len(text) > 250 or any(word in text for word in medium):
            return 2
        return 1

    def route(self, objective: str) -> ModelRoute:
        need = self.complexity(objective)
        candidates = sorted(
            self.profiles,
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
                "no model profile configured; orchestration remains tool-only",
                local=False,
                cost_tier=0,
            )
        chosen = candidates[0]
        return ModelRoute(
            chosen.provider,
            chosen.model,
            f"complexity={need}; capability={chosen.capability}",
            local=chosen.local,
            cost_tier=chosen.cost_tier,
        )
