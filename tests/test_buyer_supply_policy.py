from empire_os.buyer_supply_policy import (
    build_buyer_supply_policy,
    lead_smart_observed_policy,
    pilot_readiness,
)


def test_policy_requires_buyer_and_evidence():
    try:
        build_buyer_supply_policy(
            buyer_name="",
            source_ref="gmail:test",
        )
    except ValueError as exc:
        assert "buyer_name" in str(exc)
    else:
        raise AssertionError("missing buyer_name must fail")


def test_lead_smart_policy_preserves_unknown_payout():
    policy = lead_smart_observed_policy(
        source_ref="gmail:1a0da7880f69e8c6"
    )

    assert policy["buyer_name"] == "Lead Smart"
    assert policy["pricing"]["dynamic"] is True
    assert policy["pricing"]["payout_value"] is None
    assert policy["pricing"]["verified"] is False


def test_lead_smart_creative_requirements():
    policy = lead_smart_observed_policy(
        source_ref="gmail:1a0da7880f69e8c6"
    )

    assert policy["creative"]["unbranded_required"] is True
    assert policy["creative"]["generic_creative_required"] is True
    assert "guarantees" in policy["creative"]["prohibited"]
    assert "unsubstantiated_claims" in policy["creative"]["prohibited"]


def test_lead_smart_conversion_evidence():
    policy = lead_smart_observed_policy(
        source_ref="gmail:1a0da7880f69e8c6"
    )

    conversion = policy["conversion"]

    assert conversion["typical_min_seconds"] == 90
    assert conversion["typical_max_seconds"] == 120
    assert conversion["campaign_max_seconds_observed"] == 150


def test_lead_smart_rtb_is_capability_not_verified_terms():
    policy = lead_smart_observed_policy(
        source_ref="gmail:1a0da7880f69e8c6"
    )

    assert policy["routing"]["rtb_supported"] is True
    assert policy["routing"]["rtb_terms_verified"] is False


def test_lead_smart_pilot_fail_closed_before_asset_review():
    policy = lead_smart_observed_policy(
        source_ref="gmail:1a0da7880f69e8c6"
    )

    result = pilot_readiness(policy)

    assert result["ready"] is False
    assert result["live_traffic_authorized"] is False
    assert result["decision"] == "blocked_pending_buyer_asset_review"
    assert set(result["missing"]) == {
        "sites_reviewed",
        "landing_pages_reviewed",
        "ads_reviewed",
    }


def test_asset_review_does_not_itself_authorize_live_traffic():
    policy = lead_smart_observed_policy(
        source_ref="gmail:1a0da7880f69e8c6"
    )

    policy["review"] = {
        "sites_reviewed": True,
        "landing_pages_reviewed": True,
        "ads_reviewed": True,
    }

    result = pilot_readiness(policy)

    assert result["ready"] is True
    assert result["decision"] == "ready_for_separate_activation_review"
    assert result["live_traffic_authorized"] is False


def test_lead_smart_traffic_source_is_proposed_not_approved():
    policy = lead_smart_observed_policy(
        source_ref="gmail:1a0da7880f69e8c6"
    )

    acquisition = policy["acquisition"]

    assert acquisition["proposed_source"] == "empire_first_party_search_led"
    assert acquisition["buyer_approved"] is False
    assert acquisition["traffic_source_approval_required"] is True


def test_lead_smart_currency_remains_unknown_until_evidenced():
    policy = lead_smart_observed_policy(
        source_ref="gmail:1a0da7880f69e8c6"
    )

    assert policy["pricing"]["currency"] is None


def test_lead_smart_traffic_source_is_proposed_not_approved():
    policy = lead_smart_observed_policy(
        source_ref="gmail:1a0da7880f69e8c6"
    )

    acquisition = policy["acquisition"]

    assert acquisition["proposed_source"] == "empire_first_party_search_led"
    assert acquisition["buyer_approved"] is False
    assert acquisition["traffic_source_approval_required"] is True


def test_lead_smart_currency_remains_unknown_until_evidenced():
    policy = lead_smart_observed_policy(
        source_ref="gmail:1a0da7880f69e8c6"
    )

    assert policy["pricing"]["currency"] is None
