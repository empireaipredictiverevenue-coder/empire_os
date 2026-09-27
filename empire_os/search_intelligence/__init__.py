"""Empire Search Intelligence Engine foundation."""
from .canonical import evaluate_canonical
from .cannibalisation import CannibalisationFinding, detect_cannibalisation
from .content_decay import ContentDecayResult, evaluate_content_decay
from .internal_links import InternalLinkFinding, analyze_internal_links
from .robots import RobotsRecommendation, recommend_robots
from .sitemap import build_sitemap_plan
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
    "CannibalisationFinding",
    "ContentDecayResult",
    "InternalLinkFinding",
    "RobotsRecommendation",
    "analyze_internal_links",
    "build_sitemap_plan",
    "detect_cannibalisation",
    "evaluate_content_decay",
    "recommend_robots",
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
