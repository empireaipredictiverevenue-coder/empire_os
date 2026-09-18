"""Empire Search Intelligence Engine foundation."""
from .canonical import evaluate_canonical
from .config import SearchIntelligenceConfig
from .indexation import recommend_indexability, recommend_transition
from .metadata import generate_metadata
from .models import (
    CanonicalRecommendation,
    IndexabilityRecommendation,
    MetadataRecommendation,
    PageLifecycleState,
    QualityResult,
    SchemaPreview,
    SearchExecutionMode,
    SearchOpportunity,
    SearchPage,
    TransitionRecommendation,
)
from .quality import ContentQualityEvaluator
from .schema import generate_schema_preview
from .scoring import score_opportunity

__all__ = [
    "CanonicalRecommendation",
    "ContentQualityEvaluator",
    "IndexabilityRecommendation",
    "MetadataRecommendation",
    "PageLifecycleState",
    "QualityResult",
    "SchemaPreview",
    "SearchExecutionMode",
    "SearchIntelligenceConfig",
    "SearchOpportunity",
    "SearchPage",
    "TransitionRecommendation",
    "evaluate_canonical",
    "generate_metadata",
    "generate_schema_preview",
    "recommend_indexability",
    "recommend_transition",
    "score_opportunity",
]
