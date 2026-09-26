from empire_os.buyer_pilot_assets import (
    build_lead_smart_pilot_assets,
    validate_asset_text,
)
from empire_os.buyer_supply_policy import lead_smart_observed_policy


SOURCE = "gmail:1a0da7880f69e8c6"


def policy():
    return lead_smart_observed_policy(source_ref=SOURCE)


def test_prohibited_guarantee_is_detected():
    result = validate_asset_text(
        "Guaranteed same-day service",
        prohibited_categories=[
            "guarantees",
            "unsubstantiated_claims",
        ],
    )

    assert result["compliant"] is False
    assert any(
        item["category"] == "guarantees"
        for item in result["violations"]
    )


def test_prohibited_discount_is_detected():
    result = validate_asset_text(
        "Save 20% with our discount",
        prohibited_categories=["discounts"],
    )

    assert result["compliant"] is False


def test_lead_smart_assets_are_generic_and_unbranded():
    result = build_lead_smart_pilot_assets(
        policy(),
        service_label="Water Damage Restoration",
    )

    assert result["compliance_passed"] is True

    for asset in result["assets"]:
        assert asset["brand"] is None
        assert asset["compliance"]["compliant"] is True


def test_lead_smart_assets_do_not_invent_commercial_terms():
    result = build_lead_smart_pilot_assets(
        policy(),
        service_label="Water Damage Restoration",
    )

    asset_text = str(result["assets"]).lower()

    assert "$" not in asset_text
    assert "payout" not in asset_text
    assert "daily cap" not in asset_text
    assert "volume" not in asset_text


def test_asset_generation_never_authorizes_execution():
    result = build_lead_smart_pilot_assets(
        policy(),
        service_label="Water Damage Restoration",
    )

    assert result["mode"] == "REVIEW_ONLY"
    assert result["published"] is False
    assert result["campaign_created"] is False
    assert result["budget_authorized"] is False
    assert result["traffic_authorized"] is False
    assert result["commercial_activation_authorized"] is False
    assert result["buyer_approved"] is False


def test_supply_review_remains_blocked_after_asset_generation():
    result = build_lead_smart_pilot_assets(
        policy(),
        service_label="Water Damage Restoration",
    )

    review = result["current_supply_review"]

    assert review["pilot_ready"] is False
    assert "sites_reviewed" in review["blockers"]
    assert "landing_pages_reviewed" in review["blockers"]
    assert "ads_reviewed" in review["blockers"]
    assert "traffic_source_buyer_approval" in review["blockers"]
