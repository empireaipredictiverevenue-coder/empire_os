from __future__ import annotations

from empire_os.predictive_cloud_fabric import (
    EvidenceRef,
    PredictiveCloudFabricContext,
)
from empire_os.predictive_fabric_production_bridge import (
    PredictiveFabricProductionBridge,
)
from empire_os.revenue_compiler import (
    OpportunitySignal,
    ProductCandidate,
)
from empire_os.marketplace_broker import (
    BuyerLiquidityOffer,
    LeadDemand,
)


def evidence(ref: str) -> EvidenceRef:
    return EvidenceRef(ref=ref, kind="test")


def test_bridge_uses_revenue_compiler():
    bridge = PredictiveFabricProductionBridge()

    context = PredictiveCloudFabricContext(
        trace_id="trace-1",
        opportunity_id="opp-1",
    )

    opportunity = OpportunitySignal(
        opportunity_id="opp-1",
        vertical="roofing",
        geography="denver",
        opportunity_type="market_gap",
        evidence=(evidence("opp-e1"),),
    )

    product = ProductCandidate(
        product_id="search-map",
        name="Search Opportunity Map",
        price_cents=24900,
        active=True,
        fulfilment_ready=True,
        checkout_ready=True,
        verticals=frozenset({"roofing"}),
        geographies=frozenset({"denver"}),
        opportunity_types=frozenset({"market_gap"}),
        evidence=(evidence("product-e1"),),
    )

    result = bridge.compile_products(
        context=context,
        opportunity=opportunity,
        products=(product,),
    )

    assert result.opportunity_id == "opp-1"
    assert len(result.plans) == 1
    assert result.plans[0].ready_for_offer is True


def test_bridge_uses_marketplace_broker_without_allocating():
    bridge = PredictiveFabricProductionBridge()

    context = PredictiveCloudFabricContext(
        trace_id="trace-1",
        lead_id="lead-1",
    )

    lead = LeadDemand(
        lead_id="lead-1",
        vertical="roofing",
        geography="denver",
        source="organic_search",
        evidence=(evidence("lead-e1"),),
    )

    offer = BuyerLiquidityOffer(
        buyer_id="buyer-1",
        provider="network",
        verticals=frozenset({"roofing"}),
        geographies=frozenset({"denver"}),
        permitted_sources=frozenset({"organic_search"}),
        payout_cents=12000,
        acceptance_probability_ppm=800000,
        quality_probability_ppm=800000,
        payment_reliability_ppm=950000,
        capacity_available=True,
        active=True,
        evidence=(evidence("offer-e1"),),
    )

    result = bridge.marketplace_liquidity(
        context=context,
        lead=lead,
        offers=(offer,),
    )

    assert result.preferred is not None
    assert result.preferred.buyer_id == "buyer-1"


def test_bridge_exposes_canonical_buyer_allocator():
    bridge = PredictiveFabricProductionBridge()

    assert callable(bridge.rank_existing_buyers)
    assert callable(bridge.plan_existing_buyer_allocation)


def test_bridge_exposes_canonical_product_catalog():
    bridge = PredictiveFabricProductionBridge()

    assert callable(bridge.assess_catalog_item)
    assert callable(bridge.summarize_catalog)
    assert callable(bridge.public_catalog_projection)


def test_bridge_exposes_revenue_exchange():
    bridge = PredictiveFabricProductionBridge()

    assert callable(bridge.build_exchange_observation)
