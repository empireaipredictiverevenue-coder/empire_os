"""Typed records for the Empire Search Intelligence foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping


class SearchExecutionMode(str, Enum):
    OBSERVE = "OBSERVE"
    RECOMMEND = "RECOMMEND"
    APPROVE_AND_EXECUTE = "APPROVE_AND_EXECUTE"


class PageLifecycleState(str, Enum):
    DISCOVERED = "DISCOVERED"
    DRAFT = "DRAFT"
    QUALITY_REVIEW = "QUALITY_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    INDEXABLE = "INDEXABLE"
    SUBMITTED = "SUBMITTED"
    DISCOVERED_BY_GOOGLE = "DISCOVERED_BY_GOOGLE"
    CRAWLED = "CRAWLED"
    INDEXED = "INDEXED"
    DECLINED = "DECLINED"
    NOINDEX = "NOINDEX"
    REFRESH_REQUIRED = "REFRESH_REQUIRED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class SearchPage:
    url: str
    id: str | None = None
    tenant_id: str | None = None
    site_id: str | None = None
    slug: str | None = None
    page_type: str | None = None
    title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    robots_state: str | None = None
    indexable: bool | None = None
    content_quality_score: float | None = None
    opportunity_score: float | None = None
    target_query: str | None = None
    search_intent: str | None = None
    industry: str | None = None
    location: str | None = None
    service: str | None = None
    topic: str | None = None
    entity_references: tuple[str, ...] = ()
    publish_state: str | None = None
    index_state: PageLifecycleState = PageLifecycleState.DISCOVERED
    first_published_at: str | None = None
    last_modified_at: str | None = None
    last_crawled_at: str | None = None
    last_indexed_at: str | None = None
    refresh_required: bool = False
    revenue_attributed_cents: int | None = None
    leads_attributed: int | None = None
    conversions_attributed: int | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["index_state"] = self.index_state.value
        return data


@dataclass(frozen=True)
class SearchOpportunity:
    query: str
    topic: str | None = None
    intent: str | None = None
    commercial_intent: float | None = None
    industry: str | None = None
    geography: str | None = None
    competitor_presence: float | None = None
    current_empire_coverage: float | None = None
    content_gap: float | None = None
    target_page_type: str | None = None
    relevance: float | None = None
    authority_fit: float | None = None
    trend_signal: float | None = None
    conversion_history: float | None = None
    revenue_history_cents: int | None = None
    estimated_business_value_cents: int | None = None
    intent_score: float | None = None
    conversion_probability: float | None = None
    freshness: float | None = None
    competition: float | None = None
    opportunity_score: float | None = None
    score_reason: str | None = None


@dataclass(frozen=True)
class QualityResult:
    overall_score: float | None
    factor_scores: Mapping[str, float | None]
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recommended_actions: tuple[str, ...] = ()
    index_decision: str = "noindex,follow"
    eligible_for_approval: bool = False
    known_factor_count: int = 0


@dataclass(frozen=True)
class MetadataRecommendation:
    title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    robots: str = "noindex,follow"
    open_graph: Mapping[str, Any] = field(default_factory=dict)
    social: Mapping[str, Any] = field(default_factory=dict)
    language: str | None = None
    author: str | None = None
    publish_date: str | None = None
    updated_date: str | None = None
    page_type: str | None = None
    entity_context: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SchemaPreview:
    schema_type: str
    json_ld: Mapping[str, Any]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CanonicalRecommendation:
    input_url: str
    recommended_url: str
    issues: tuple[str, ...] = ()
    recommended_actions: tuple[str, ...] = ()
    requires_review: bool = False


@dataclass(frozen=True)
class IndexabilityRecommendation:
    current_state: PageLifecycleState
    recommended_state: PageLifecycleState
    robots: str
    eligible_for_approval: bool
    blocked_by_observe: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class TransitionRecommendation:
    current_state: PageLifecycleState
    requested_state: PageLifecycleState
    transition_valid: bool
    execution_allowed: bool
    blocked_reason: str | None = None
