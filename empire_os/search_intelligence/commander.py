"""OBSERVE-mode Search Commander."""
from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any, Mapping

from .canonical import evaluate_canonical
from .config import SearchIntelligenceConfig
from .metadata import generate_metadata
from .models import SearchOpportunity, SearchPage
from .quality import ContentQualityEvaluator
from .scoring import score_opportunity


class SearchCommanderAgent:
    def __init__(self, config: SearchIntelligenceConfig | None = None):
        self.config = config or SearchIntelligenceConfig.from_env()

    def analyse(
        self,
        *,
        page: SearchPage,
        quality_factors: Mapping[str, float | None],
        opportunity: SearchOpportunity | None = None,
    ) -> dict[str, Any]:
        quality = ContentQualityEvaluator(
            threshold=self.config.quality_threshold,
            minimum_known_factors=self.config.minimum_known_quality_factors,
        ).evaluate(quality_factors)
        canonical = evaluate_canonical(page.url)
        metadata = generate_metadata(
            replace(
                page,
                canonical_url=page.canonical_url or canonical.recommended_url,
            ),
            quality=quality,
        )
        scored = score_opportunity(opportunity) if opportunity else None
        return {
            "mode": self.config.mode.value,
            "execution_allowed": False,
            "page": page.as_dict(),
            "quality": asdict(quality),
            "canonical": asdict(canonical),
            "metadata": asdict(metadata),
            "opportunity": asdict(scored) if scored else None,
            "recommendation_only": True,
        }

    def mutation_allowed(self) -> bool:
        return False
