from empire_os.gtm_offer_strategy import (
    NicheOfferContext,
    build_demo_asset_plan,
    build_high_ticket_offer_frame,
    classify_niche_tier,
)


def ctx(**overrides):
    data = {
        "niche": "roofing",
        "metro": "Austin",
        "pe_backed": None,
        "high_cash_flow_evidence": None,
        "founder_network_fit": None,
        "opportunity_evidence_refs": ("opportunity:roofing:austin",),
    }
    data.update(overrides)
    return NicheOfferContext(**data)


def test_roofing_is_tier_one_without_inventing_economics():
    result = classify_niche_tier(ctx())
    assert result["tier"] == 1
    assert result["reason"] == "canonical_high_ticket_vertical"
    assert result["automatic_pricing"] is False


def test_tier_two_requires_high_cash_flow_or_pe_evidence():
    blocked = classify_niche_tier(
        ctx(niche="hvac", opportunity_evidence_refs=("hvac:1",))
    )
    ready = classify_niche_tier(
        ctx(
            niche="hvac",
            pe_backed=True,
            opportunity_evidence_refs=("hvac:1", "pe:1"),
        )
    )
    assert blocked["tier"] is None
    assert ready["tier"] == 2


def test_demo_plan_is_evidence_first_and_not_auto_published():
    result = build_demo_asset_plan(
        context=ctx(),
        capability_evidence_refs=("capability:signal", "capability:crm"),
    )
    assert result["lead_magnet"] == "live_event_radar"
    assert result["target_duration_seconds"] == 180
    assert result["evergreen_pre_nurture"] is True
    assert result["publishing_enabled"] is False
    assert result["automatic_distribution"] is False
    assert result["pricing_claims_allowed_without_evidence"] is False


def test_offer_frame_never_invents_price():
    result = build_high_ticket_offer_frame(
        context=ctx(),
        verified_price_evidence_ref=None,
        verified_outcome_evidence_refs=(),
    )
    assert result["verified_price_available"] is False
    assert result["commercial_terms_ready"] is False
    assert result["automatic_price_selection"] is False
    assert result["actual_revenue"] is False
