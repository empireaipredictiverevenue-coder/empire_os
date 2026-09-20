"""Sellable Search Intelligence product contracts.

The Search Intelligence engine is the source of evidence. These product
contracts describe customer-facing outputs without inventing metrics,
commercial pricing, traffic, rankings or revenue.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class SearchProduct:
    key: str
    name: str
    category: str
    outcome: str
    buyer_types: tuple[str, ...]
    deliverables: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...] = ()
    commercial_model: str = "terms_required"
    execution_mode: str = "OBSERVE"
    publishing_authority: bool = False
    indexation_authority: bool = False
    link_building_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


SEARCH_PRODUCTS: tuple[SearchProduct, ...] = (
    SearchProduct(
        key="technical_search_audit",
        name="Technical Search Audit",
        category="technical_seo",
        outcome="Find technical/indexation issues that suppress discoverability.",
        buyer_types=("smb", "agency", "multi_location", "enterprise"),
        deliverables=(
            "indexation_health",
            "metadata_quality",
            "schema_review",
            "internal_link_findings",
            "orphan_page_findings",
            "sitemap_and_robots_review",
            "prioritized_fix_backlog",
        ),
        required_capabilities=("pages", "indexation"),
        optional_capabilities=(
            "native_crawler",
            "lighthouse_parser",
            "lighthouse_runner",
            "internal_links",
            "search_console",
        ),
    ),
    SearchProduct(
        key="search_opportunity_map",
        name="Search Opportunity Map",
        category="seo_growth",
        outcome="Prioritize evidence-backed queries, pages and content opportunities.",
        buyer_types=("smb", "agency", "content_team", "enterprise"),
        deliverables=(
            "keyword_opportunity_portfolio",
            "content_gap_map",
            "page_to_query_map",
            "priority_backlog",
            "opportunity_evidence",
        ),
        required_capabilities=("opportunities",),
        optional_capabilities=(
            "rank_history",
            "serp",
            "search_console",
            "competitor_gap",
        ),
    ),
    SearchProduct(
        key="local_search_grid",
        name="Local Search & Maps Grid Intelligence",
        category="local_seo",
        outcome=(
            "Measure observed local-search visibility across a geographic grid "
            "without inventing missing map ranks."
        ),
        buyer_types=(
            "local_business",
            "multi_location",
            "agency",
            "franchise",
            "enterprise",
        ),
        deliverables=(
            "maps_grid_visibility",
            "top3_coverage",
            "top10_coverage",
            "weak_zone_map",
            "unknown_cell_inventory",
            "local_visibility_brief",
        ),
        required_capabilities=("local_grid",),
        optional_capabilities=(
            "search_console",
            "rank_history",
            "competitor_gap",
        ),
    ),
    SearchProduct(
        key="content_protection",
        name="Content Decay & Cannibalisation Monitor",
        category="content_intelligence",
        outcome="Protect existing organic assets before growth is lost.",
        buyer_types=("publisher", "agency", "content_team", "enterprise"),
        deliverables=(
            "content_decay_findings",
            "cannibalisation_findings",
            "refresh_candidates",
            "consolidation_candidates",
            "internal_link_actions",
        ),
        required_capabilities=("decay", "cannibalisation"),
        optional_capabilities=("search_console", "internal_links"),
    ),
    SearchProduct(
        key="authority_intelligence",
        name="Authority & Backlink Intelligence",
        category="authority",
        outcome="Understand observed link authority and evidence-backed authority gaps.",
        buyer_types=("smb", "agency", "digital_pr", "enterprise"),
        deliverables=(
            "observed_backlink_graph",
            "authority_gap_findings",
            "link_source_inventory",
            "lost_or_changed_link_watch",
            "evidence_backed_outreach_targets",
        ),
        required_capabilities=("backlinks",),
        optional_capabilities=("competitor_gap",),
    ),
    SearchProduct(
        key="geo_ai_visibility",
        name="AEO / GEO AI Visibility",
        category="ai_search",
        outcome="Measure where AI engines mention/cite the brand and where competitors win.",
        buyer_types=("brand", "agency", "enterprise", "publisher"),
        deliverables=(
            "ai_citation_observations",
            "citation_share_evidence",
            "citation_gap_findings",
            "query_visibility_map",
            "source_gap_backlog",
        ),
        required_capabilities=("ai_visibility",),
        optional_capabilities=("citation_gap", "competitor_gap"),
    ),
    SearchProduct(
        key="competitor_search_gap",
        name="Competitor Search Gap",
        category="competitive_intelligence",
        outcome="Identify observed SERP and citation spaces occupied by competitors.",
        buyer_types=("smb", "agency", "strategy_team", "enterprise"),
        deliverables=(
            "competitor_presence_map",
            "query_gap_findings",
            "best_observed_positions",
            "content_gap_backlog",
            "citation_gap_backlog",
        ),
        required_capabilities=("competitor_gap",),
        optional_capabilities=("serp", "ai_visibility"),
    ),
    SearchProduct(
        key="search_growth_command",
        name="Search Growth Command",
        category="managed_intelligence",
        outcome="Unify SEO, AEO, GEO, authority, content health and revenue evidence.",
        buyer_types=("growth_team", "agency", "multi_location", "enterprise"),
        deliverables=(
            "executive_search_scorecard",
            "technical_health",
            "opportunity_portfolio",
            "content_protection",
            "authority_intelligence",
            "ai_visibility",
            "competitor_gaps",
            "search_to_revenue_attribution",
            "weekly_priority_brief",
        ),
        required_capabilities=(
            "pages",
            "indexation",
            "opportunities",
            "decay",
            "cannibalisation",
        ),
        optional_capabilities=(
            "search_console",
            "internal_links",
            "backlinks",
            "ai_visibility",
            "competitor_gap",
            "revenue",
        ),
    ),
)


def product_catalog() -> list[dict[str, Any]]:
    return [product.as_dict() for product in SEARCH_PRODUCTS]


def get_search_product(key: str) -> SearchProduct | None:
    normalized = str(key or "").strip().lower()
    return next(
        (product for product in SEARCH_PRODUCTS if product.key == normalized),
        None,
    )


def evaluate_product_readiness(
    product: SearchProduct,
    capability_state: Mapping[str, bool | None],
) -> dict[str, Any]:
    required = {
        name: capability_state.get(name)
        for name in product.required_capabilities
    }
    optional = {
        name: capability_state.get(name)
        for name in product.optional_capabilities
    }

    missing = tuple(
        name for name, available in required.items()
        if available is not True
    )
    unknown = tuple(
        name for name, available in {**required, **optional}.items()
        if available is None
    )
    optional_available = tuple(
        name for name, available in optional.items()
        if available is True
    )

    if not missing:
        status = "READY"
    elif any(value is True for value in required.values()):
        status = "PARTIAL"
    else:
        status = "GATED"

    return {
        "product_key": product.key,
        "status": status,
        "required": required,
        "optional": optional,
        "missing_required": list(missing),
        "unknown_capabilities": list(unknown),
        "optional_available": list(optional_available),
        "commercial_terms_required": True,
        "pricing_observed": False,
        "execution_mode": product.execution_mode,
        "publishing_authority": product.publishing_authority,
        "indexation_authority": product.indexation_authority,
        "link_building_authority": product.link_building_authority,
    }


def product_portfolio_readiness(
    capability_state: Mapping[str, bool | None],
) -> list[dict[str, Any]]:
    return [
        evaluate_product_readiness(product, capability_state)
        for product in SEARCH_PRODUCTS
    ]
