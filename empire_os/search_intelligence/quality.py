"""Content quality firewall for programmatic/search pages."""
from __future__ import annotations

from typing import Mapping

from .models import QualityResult

POSITIVE_FACTORS = (
    "originality",
    "useful_content",
    "intent_coverage",
    "factual_support",
    "source_quality",
    "topic_completeness",
    "page_uniqueness",
    "internal_link_support",
    "structured_data_validity",
    "user_value",
)
RISK_FACTORS = (
    "duplication_risk",
    "thin_content_risk",
    "unsupported_claims_risk",
    "keyword_stuffing_risk",
    "template_duplication_risk",
    "hallucination_risk",
)


class ContentQualityEvaluator:
    def __init__(self, *, threshold: float = 0.75, minimum_known_factors: int = 8):
        self.threshold = min(1.0, max(0.0, float(threshold)))
        self.minimum_known_factors = max(1, int(minimum_known_factors))

    @staticmethod
    def _validate(value: float | None) -> float | None:
        if value is None:
            return None
        value = float(value)
        if not 0.0 <= value <= 1.0:
            raise ValueError("quality factors must be within 0..1")
        return value

    def evaluate(self, factors: Mapping[str, float | None]) -> QualityResult:
        scores: dict[str, float | None] = {}
        contributions: list[float] = []
        warnings: list[str] = []
        actions: list[str] = []

        for name in POSITIVE_FACTORS:
            raw = self._validate(factors.get(name))
            scores[name] = raw
            if raw is None:
                warnings.append(f"unknown:{name}")
            else:
                contributions.append(raw)
                if raw < 0.6:
                    actions.append(f"improve:{name}")

        for name in RISK_FACTORS:
            raw = self._validate(factors.get(name))
            scores[name] = raw
            if raw is None:
                warnings.append(f"unknown:{name}")
            else:
                contributions.append(1.0 - raw)
                if raw > 0.4:
                    warnings.append(f"high:{name}")
                    actions.append(f"reduce:{name}")

        known = [value for value in scores.values() if value is not None]
        overall = (
            round(sum(contributions) / len(contributions), 4)
            if contributions
            else None
        )
        enough_evidence = len(known) >= self.minimum_known_factors
        passes = (
            enough_evidence
            and overall is not None
            and overall >= self.threshold
            and not any(item.startswith("high:unsupported_claims_risk") for item in warnings)
            and not any(item.startswith("high:hallucination_risk") for item in warnings)
        )

        reasons = [
            f"known_quality_factors:{len(known)}",
            f"required_quality_factors:{self.minimum_known_factors}",
        ]
        if not enough_evidence:
            reasons.append("insufficient_quality_evidence")
        elif passes:
            reasons.append("quality_threshold_met")
        else:
            reasons.append("quality_threshold_not_met")

        return QualityResult(
            overall_score=overall,
            factor_scores=scores,
            reasons=tuple(reasons),
            warnings=tuple(sorted(set(warnings))),
            recommended_actions=tuple(sorted(set(actions))),
            index_decision="eligible_for_approval" if passes else "noindex,follow",
            eligible_for_approval=passes,
            known_factor_count=len(known),
        )
