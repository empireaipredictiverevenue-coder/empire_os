from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from empire_os.buyer_allocation import (
    plan_allocation as canonical_plan_allocation,
    rank_buyers as canonical_rank_buyers,
)
from empire_os.buyer_capacity_readiness import (
    summarize_buyer_capacity as canonical_buyer_capacity,
)
from empire_os.commercial_product_catalog import (
    assess_catalog_item as canonical_assess_catalog_item,
    public_catalog_projection as canonical_public_catalog_projection,
    summarize_catalog as canonical_summarize_catalog,
)
from empire_os.opportunity_radar import (
    build_opportunity_radar as canonical_build_opportunity_radar,
    refresh_opportunity_radar as canonical_refresh_opportunity_radar,
)
from empire_os.revenue_exchange_ingest import (
    build_exchange_observation as canonical_exchange_observation,
)

from empire_os.marketplace_broker import (
    BuyerAllocationProposal,
    BuyerLiquidityOffer,
    LeadDemand,
    build_allocation_book,
    preferred_verified_destination,
)
from empire_os.predictive_cloud_fabric import (
    PredictiveCloudFabricContext,
)
from empire_os.revenue_compiler import (
    OpportunitySignal,
    ProductCandidate,
    RevenuePlan,
    compile_revenue_plans,
)


@dataclass(frozen=True)
class ProductCompilationResult:
    opportunity_id: str
    plans: tuple[RevenuePlan, ...]
    canonical_catalog_summary: Mapping[str, Any] | None


@dataclass(frozen=True)
class BuyerLiquidityResult:
    lead_id: str
    proposals: tuple[BuyerAllocationProposal, ...]
    preferred: BuyerAllocationProposal | None


class PredictiveFabricProductionBridge:
    """
    Single integration boundary between the Predictive Fabric and
    existing EmpireOS production commercial authority.

    This class MUST NOT become a second canonical data store or a
    competing buyer allocator.

    Existing EmpireOS modules remain authoritative for:
    - product catalogue truth
    - opportunity radar
    - buyer qualification/ranking/allocation
    - buyer capacity readiness
    - revenue exchange observations

    Predictive Fabric adds:
    - product/opportunity compilation
    - marketplace liquidity economics
    - cross-system context/evidence
    """

    def assess_catalog_item(
        self,
        row: Mapping[str, Any],
    ) -> Any:
        return canonical_assess_catalog_item(dict(row))

    def summarize_catalog(
        self,
        rows: Iterable[Mapping[str, Any]],
    ) -> Any:
        return canonical_summarize_catalog(
            [dict(row) for row in rows]
        )

    def public_catalog_projection(
        self,
        snapshot: Mapping[str, Any],
    ) -> Any:
        return canonical_public_catalog_projection(
            dict(snapshot)
        )

    def build_opportunity_radar(
        self,
        *,
        market_gps: Mapping[str, Any] | None,
        community_intent: Mapping[str, Any] | None,
        competitor_market: Mapping[str, Any] | None,
        generated_at: str,
    ) -> Any:
        return canonical_build_opportunity_radar(
            market_gps,
            community_intent,
            competitor_market,
            generated_at,
        )

    def refresh_opportunity_radar(
        self,
        repo_root: str | Path,
    ) -> Any:
        return canonical_refresh_opportunity_radar(
            Path(repo_root)
        )

    def compile_products(
        self,
        *,
        context: PredictiveCloudFabricContext,
        opportunity: OpportunitySignal,
        products: Iterable[ProductCandidate],
        canonical_rows: Iterable[Mapping[str, Any]] = (),
    ) -> ProductCompilationResult:
        rows = tuple(dict(row) for row in canonical_rows)

        summary = (
            canonical_summarize_catalog(list(rows))
            if rows
            else None
        )

        plans = compile_revenue_plans(
            context=context,
            opportunity=opportunity,
            products=products,
        )

        return ProductCompilationResult(
            opportunity_id=opportunity.opportunity_id,
            plans=plans,
            canonical_catalog_summary=summary,
        )

    def rank_existing_buyers(
        self,
        *,
        prospect: Mapping[str, Any],
        qualification: Mapping[str, Any],
        buyers: Iterable[Mapping[str, Any]],
        limit: int,
    ) -> Any:
        return canonical_rank_buyers(
            dict(prospect),
            dict(qualification),
            [dict(row) for row in buyers],
            limit,
        )

    def plan_existing_buyer_allocation(
        self,
        *,
        prospect: Mapping[str, Any],
        qualification: Mapping[str, Any],
        identity_link: Mapping[str, Any] | None,
        buyers: Iterable[Mapping[str, Any]],
    ) -> Any:
        return canonical_plan_allocation(
            dict(prospect),
            dict(qualification),
            None if identity_link is None else dict(identity_link),
            [dict(row) for row in buyers],
        )

    def buyer_capacity(
        self,
        *,
        buyers: Iterable[Mapping[str, Any]],
        observed_at: str | datetime,
    ) -> Any:
        return canonical_buyer_capacity(
            [dict(row) for row in buyers],
            observed_at,
        )

    def marketplace_liquidity(
        self,
        *,
        context: PredictiveCloudFabricContext,
        lead: LeadDemand,
        offers: Iterable[BuyerLiquidityOffer],
    ) -> BuyerLiquidityResult:
        proposals = build_allocation_book(
            context=context,
            lead=lead,
            offers=offers,
        )

        return BuyerLiquidityResult(
            lead_id=lead.lead_id,
            proposals=proposals,
            preferred=preferred_verified_destination(
                proposals
            ),
        )

    def build_exchange_observation(
        self,
        *,
        observation_key: str,
        row: Mapping[str, Any],
        evidence: Any,
    ) -> Any:
        return canonical_exchange_observation(
            observation_key,
            dict(row),
            evidence,
        )
