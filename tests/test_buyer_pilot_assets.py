from empire_os.buyer_pilot_assets import (
    PROHIBITED_PATTERNS,
    SCHEMA_VERSION,
    build_lead_smart_pilot_assets,
    validate_asset_text,
)


def test_validator_rejects_guarantees_and_discounts():
    result = validate_asset_text("Guaranteed lowest price. Save 20% off today.")
    assert result["passed"] is False
    categories = {row["category"] for row in result["violations"]}
    assert "guarantees" in categories
    assert "discounts" in categories
    assert "unsubstantiated_claims" in categories


def test_validator_rejects_promotions():
    result = validate_asset_text("Limited time special offer and coupon")
    assert result["passed"] is False
    assert any(row["category"] == "promotions" for row in result["violations"])


def test_recovered_patterns_match_original_categories():
    assert tuple(PROHIBITED_PATTERNS) == (
        "promotions",
        "guarantees",
        "discounts",
        "unsubstantiated_claims",
    )


def test_build_assets_are_generic_unbranded_and_review_only():
    bundle = build_lead_smart_pilot_assets(service_label="roofing")
    assert bundle["schema_version"] == SCHEMA_VERSION
    assert bundle["mode"] == "REVIEW_ONLY"
    assert bundle["buyer_name"] == "Lead Smart"
    assert bundle["buyer_asset_review_required"] is True
    assert bundle["traffic_source_approval_required"] is True
    assert bundle["buyer_approved"] is False
    assert bundle["published"] is False
    assert bundle["campaign_created"] is False
    assert bundle["budget_authorized"] is False
    assert bundle["traffic_authorized"] is False
    assert bundle["commercial_activation_authorized"] is False
    assert bundle["compliance_passed"] is True
    assert all(asset["brand"] == "generic_unbranded" for asset in bundle["assets"])
    assert all(asset["status"] == "REVIEW_ONLY" for asset in bundle["assets"])


def test_assets_do_not_invent_price_payout_cap_or_volume_claims():
    bundle = build_lead_smart_pilot_assets(service_label="HVAC")
    text = str(bundle["assets"])
    assert "$" not in text
    assert "payout" not in text.lower()
    assert "daily cap" not in text.lower()
    assert "guaranteed volume" not in text.lower()


def test_supply_blockers_are_preserved_in_asset_bundle():
    bundle = build_lead_smart_pilot_assets(service_label="plumbing")
    review = bundle["current_supply_review"]
    assert review["decision"] == "blocked_pending_buyer_asset_review"
    assert review["traffic_authorized"] is False
    assert "payout_unknown" in review["blockers"]
