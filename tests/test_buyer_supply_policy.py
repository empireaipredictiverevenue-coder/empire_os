from empire_os.buyer_supply_policy import (
    POLICY_VERSION,
    build_buyer_supply_policy,
    lead_smart_observed_policy,
    pilot_readiness,
)


def test_lead_smart_observed_policy_is_evidence_bound_and_fail_closed():
    policy = lead_smart_observed_policy()
    assert policy["policy_version"] == POLICY_VERSION
    assert policy["proposed_source"] == "empire_first_party_search_led"
    assert policy["buyer_approved"] is False
    assert policy["pricing"]["payout_value"] is None
    assert policy["pricing"]["currency"] is None
    assert policy["pricing"]["verified"] is False
    assert policy["commercial"]["geographies"] is None
    assert policy["commercial"]["trades"] is None
    assert policy["commercial"]["daily_cap"] is None
    assert policy["traffic_authorized"] is False


def test_lead_smart_observed_rules_preserve_buyer_requirements():
    policy = lead_smart_observed_policy()
    assert policy["creative_requirements"]["brand_mode"] == "generic_unbranded"
    assert policy["creative_requirements"]["prohibited"] == [
        "promotions",
        "guarantees",
        "discounts",
        "unsubstantiated_claims",
    ]
    call = policy["call_requirements"]
    assert call["connected_duration_seconds_typical_min"] == 90
    assert call["connected_duration_seconds_typical_max"] == 120
    assert call["campaign_max_observed_seconds"] == 150
    assert call["real_homeowner_required"] is True
    assert call["service_area_match_required"] is True
    assert policy["rtb"]["supported"] is True
    assert policy["rtb"]["terms_verified"] is False


def test_pilot_readiness_blocks_unknown_commercial_terms():
    result = pilot_readiness(lead_smart_observed_policy())
    assert result["decision"] == "blocked_pending_buyer_asset_review"
    assert result["traffic_authorized"] is False
    assert result["commercial_activation_authorized"] is False
    assert "payout_unknown" in result["blockers"]
    assert "currency_unknown" in result["blockers"]
    assert "geographies_unknown" in result["blockers"]
    assert "trades_unknown" in result["blockers"]
    assert "daily_cap_unknown" in result["blockers"]
    assert "rtb_terms_unverified" in result["blockers"]


def test_build_policy_only_promotes_explicit_verified_values():
    policy = build_buyer_supply_policy({
        "buyer_approved": True,
        "traffic_source_approved": True,
        "landing_page_approved": True,
        "ad_creative_approved": True,
        "buyer_asset_review_complete": True,
        "commercial_terms_verified": True,
        "pricing_verified": True,
        "payout_value": 125,
        "currency": "USD",
        "geographies": ["TX"],
        "trades": ["roofing"],
        "daily_cap": 10,
        "capacity_verified": True,
        "delivery_destination_verified": True,
        "rtb_terms_verified": True,
    })
    assert policy["pricing"]["payout_value"] == 125
    assert policy["pricing"]["currency"] == "USD"
    assert policy["readiness"]["decision"] == "ready_for_controlled_pilot"
    assert policy["traffic_authorized"] is True
    assert policy["commercial_activation_authorized"] is True


def test_partial_values_do_not_authorize_traffic():
    policy = build_buyer_supply_policy({
        "buyer_approved": True,
        "payout_value": 125,
        "currency": "USD",
    })
    assert policy["traffic_authorized"] is False
    assert policy["commercial_activation_authorized"] is False
