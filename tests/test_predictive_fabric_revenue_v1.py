from hashlib import sha256
from pathlib import Path

import pytest

from empire_os.marketplace_broker import (
    BuyerLiquidityOffer,
    LeadDemand,
    build_allocation_book,
    expected_buyer_value_cents,
    preferred_verified_destination,
)
from empire_os.predictive_cloud_fabric import (
    EconomicTrace,
    EvidenceRef,
    ExecutionAuthority,
    FabricCapability,
    PredictiveCloudFabricContext,
    TenantContextSource,
)
from empire_os.revenue_compiler import (
    OpportunitySignal,
    ProductCandidate,
    compile_revenue_plan,
)


ROOT = Path(__file__).resolve().parents[1]

LOCKED = {
    "empire_os/predictive_revenue_formula.py":
        "ed258882dd71a4292fea670807f5e5a451cdc4482f2da2204d5f6a2293e5bc2e",
    "empire_os/predictive_cloud_formula.py":
        "ccbb9b49c31bd4aca57e9d5312de034d20624f3db0344ab0cffed8ed1b99c406",
    "migrations/empiredb/018_tenant_context_foundation.sql":
        "e7edcfe1d0f94c3898437e68db0714557370b7b86f9b21ee76cc04be60bc3c21",
}


def ev(ref: str) -> EvidenceRef:
    return EvidenceRef(ref=ref, kind="test")


def test_locked_foundations():
    observed = {
        path: sha256((ROOT / path).read_bytes()).hexdigest()
        for path in LOCKED
    }
    assert observed == LOCKED


def test_unknown_economic_truth_stays_unknown():
    trace = EconomicTrace()
    assert trace.realized_revenue_cents is None
    assert trace.reinvestable_cash_cents is None


def test_tenant_cannot_be_payload_asserted():
    with pytest.raises(ValueError):
        PredictiveCloudFabricContext(
            trace_id="t1",
            tenant_id="tenant-x",
            tenant_source=TenantContextSource.NONE,
        )


def test_observe_cannot_execute():
    cap = FabricCapability(
        name="commercial",
        allowed_actions=frozenset({
            "read:liquidity",
            "execute:live_outbound",
        }),
    )

    ctx = PredictiveCloudFabricContext(trace_id="t1")

    assert cap.allows("read:liquidity", context=ctx)
    assert not cap.allows(
        "execute:live_outbound",
        context=ctx,
    )


def test_founder_gate_still_required():
    cap = FabricCapability(
        name="commercial",
        allowed_actions=frozenset({
            "execute:paid_traffic",
        }),
    )

    ctx = PredictiveCloudFabricContext(
        trace_id="t1",
        authority=ExecutionAuthority.EXECUTE_BOUNDED,
    )

    assert not cap.allows(
        "execute:paid_traffic",
        context=ctx,
    )


def test_product_can_be_compiled_to_offer():
    ctx = PredictiveCloudFabricContext(
        trace_id="t1",
        opportunity_id="opp-1",
    )

    opportunity = OpportunitySignal(
        opportunity_id="opp-1",
        vertical="roofing",
        geography="denver",
        opportunity_type="market_gap",
        evidence=(ev("opp-evidence"),),
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
        evidence=(ev("product-evidence"),),
    )

    plan = compile_revenue_plan(
        context=ctx,
        opportunity=opportunity,
        product=product,
    )

    assert plan.ready_for_offer
    assert plan.price_cents == 24900
    assert plan.exact_match_dimensions == 3


def test_missing_price_fails_closed():
    ctx = PredictiveCloudFabricContext(
        trace_id="t1",
        opportunity_id="opp-1",
    )

    opportunity = OpportunitySignal(
        opportunity_id="opp-1",
        vertical="roofing",
        geography="denver",
        opportunity_type="market_gap",
        evidence=(ev("opp-evidence"),),
    )

    product = ProductCandidate(
        product_id="unknown",
        name="Unknown",
        price_cents=None,
        active=True,
        fulfilment_ready=True,
        checkout_ready=True,
        verticals=frozenset({"*"}),
        geographies=frozenset({"*"}),
        opportunity_types=frozenset({"*"}),
    )

    plan = compile_revenue_plan(
        context=ctx,
        opportunity=opportunity,
        product=product,
    )

    assert not plan.ready_for_offer
    assert "price_unavailable" in plan.blockers


def test_expected_buyer_value():
    assert expected_buyer_value_cents(
        payout_cents=10_000,
        acceptance_probability_ppm=800_000,
        quality_probability_ppm=750_000,
        payment_reliability_ppm=900_000,
    ) == 5_400


def test_unknown_buyer_factor_remains_unknown():
    assert expected_buyer_value_cents(
        payout_cents=10_000,
        acceptance_probability_ppm=None,
        quality_probability_ppm=750_000,
        payment_reliability_ppm=900_000,
    ) is None


def test_verified_buyer_economics_beat_unknown():
    ctx = PredictiveCloudFabricContext(
        trace_id="t1",
        lead_id="lead-1",
    )

    lead = LeadDemand(
        lead_id="lead-1",
        vertical="roofing",
        geography="denver",
        source="organic_search",
        evidence=(ev("lead-evidence"),),
    )

    unknown = BuyerLiquidityOffer(
        buyer_id="unknown",
        provider="network-a",
        verticals=frozenset({"roofing"}),
        geographies=frozenset({"denver"}),
        permitted_sources=frozenset({"organic_search"}),
        payout_cents=None,
        acceptance_probability_ppm=None,
        quality_probability_ppm=None,
        payment_reliability_ppm=None,
        capacity_available=True,
        active=True,
        evidence=(ev("network-a"),),
    )

    verified = BuyerLiquidityOffer(
        buyer_id="verified",
        provider="network-b",
        verticals=frozenset({"roofing"}),
        geographies=frozenset({"denver"}),
        permitted_sources=frozenset({"organic_search"}),
        payout_cents=12_000,
        acceptance_probability_ppm=800_000,
        quality_probability_ppm=800_000,
        payment_reliability_ppm=950_000,
        capacity_available=True,
        active=True,
        evidence=(ev("network-b"),),
    )

    book = build_allocation_book(
        context=ctx,
        lead=lead,
        offers=(unknown, verified),
    )

    winner = preferred_verified_destination(book)

    assert winner is not None
    assert winner.buyer_id == "verified"
