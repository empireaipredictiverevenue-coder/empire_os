"""Configuration for Empire Search Intelligence."""
from __future__ import annotations

import os
from dataclasses import dataclass

from .models import SearchExecutionMode


def _mode() -> SearchExecutionMode:
    # Phase-one authority is intentionally hard-clamped to OBSERVE.
    # Future modes require a separately reviewed implementation and gate.
    return SearchExecutionMode.OBSERVE


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class SearchIntelligenceConfig:
    mode: SearchExecutionMode = SearchExecutionMode.OBSERVE
    quality_threshold: float = 0.75
    minimum_known_quality_factors: int = 8

    @classmethod
    def from_env(cls) -> "SearchIntelligenceConfig":
        return cls(
            mode=_mode(),
            quality_threshold=min(
                1.0,
                max(0.0, _float_env("EMPIRE_SEARCH_QUALITY_THRESHOLD", 0.75)),
            ),
            minimum_known_quality_factors=max(
                1,
                _int_env("EMPIRE_SEARCH_MIN_QUALITY_FACTORS", 8),
            ),
        )

    @property
    def observe(self) -> bool:
        return self.mode is SearchExecutionMode.OBSERVE
