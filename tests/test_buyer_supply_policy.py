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


def test_lead_smart_confirmed_roofing_policy_preserves_new_buyer_evidence():
    from empire_os.buyer_supply_policy import (
        lead_smart_confirmed_roofing_policy,
    )

    policy = lead_smart_confirmed_roofing_policy(
        source_ref="gmail:1a10c6b2530f2951"
    )

    assert policy["acquisition"]["offer_name"] == (
        "Main Roofing Contractors - Nationwide - Variable Rate"
    )
    assert (
        policy["acquisition"]["traffic_sources"]
        ["organic_seo_landing_pages"]["buyer_approved"]
        is True
    )
    assert policy["conversion"]["qualification_seconds"] is None
    assert policy["conversion"]["qualification_seconds_min"] == 60
    assert policy["conversion"]["qualification_seconds_max"] == 120
    assert policy["conversion"]["qualification_route_dependent"] is True
    assert policy["conversion"]["appointment_cpl_possible"] is True
    assert policy["conversion"]["caller_requirement"] == "homeowner"
    assert policy["conversion"]["geography_requirement"] == "covered_zip"
    assert policy["conversion"]["duplicate_window_days"] == 30
    assert policy["capacity"]["mode"] == "uncapped"
    assert policy["routing"]["platform"] == "Ringba"
    assert policy["routing"]["subids_required"] is False


def test_lead_smart_confirmed_policy_does_not_invent_live_payout():
    from empire_os.buyer_supply_policy import (
        lead_smart_confirmed_roofing_policy,
    )

    policy = lead_smart_confirmed_roofing_policy(
        source_ref="gmail:1a10c6b2530f2951"
    )

    assert policy["pricing"]["pricing_mode"] == "live_bid_at_call_time"
    assert policy["pricing"]["payout_value"] is None
    assert policy["pricing"]["currency"] is None
    assert policy["pricing"]["verified"] is False


def test_lead_smart_confirmed_policy_preserves_runtime_gates():
    from empire_os.buyer_supply_policy import (
        lead_smart_confirmed_roofing_policy,
        pilot_readiness,
    )

    policy = lead_smart_confirmed_roofing_policy(
        source_ref="gmail:1a10c6b2530f2951"
    )

    assert policy["routing"]["tracking_number_assigned"] is True
    assert policy["routing"]["tracking_number"] == "+18883579305"
    assert policy["routing"]["tracking_verified"] is False
    assert policy["routing"]["routing_verified"] is False
    assert policy["review"]["ads_reviewed"] is True
    assert policy["review"]["sites_reviewed"] is False
    assert policy["review"]["landing_pages_reviewed"] is False

    readiness = pilot_readiness(policy)

    assert readiness["ready"] is False
    assert readiness["live_traffic_authorized"] is False
    assert set(readiness["missing"]) == {
        "sites_reviewed",
        "landing_pages_reviewed",
    }


def test_lead_smart_buyer_attestation_does_not_grant_live_routing():
    from empire_os.buyer_supply_policy import lead_smart_confirmed_roofing_policy

    policy = lead_smart_confirmed_roofing_policy(
        source_ref="gmail:1a10c6b2530f2951"
    )
    routing = policy["routing"]
    report = routing["buyer_route_report"]
    assert report["source_ref"] == "gmail:1a121bc6211d60b7"
    assert report["status"] == "EXPECTED_ACTIVE_BUYER_REPORTED"
    assert report["independently_verified"] is False
    assert routing["routing_verified"] is False
    assert routing["rtb_enabled"] is False
    requirements = routing["rtb_transport_requirements"]
    assert requirements["zipcode_required"] is True
    assert requirements["caller_id_required"] is True
    assert requirements["expose_caller_id"] == "yes"
    assert requirements["caller_id_must_match_live_call"] is True
    assert requirements["transport_implemented"] is False


def test_lead_smart_confirmed_policy_records_no_execution_authority():
    from empire_os.buyer_supply_policy import (
        lead_smart_confirmed_roofing_policy,
    )

    policy = lead_smart_confirmed_roofing_policy(
        source_ref="gmail:1a10c6b2530f2951"
    )

    assert policy["evidence"]["execution_authority"] is False


def test_lead_smart_confirmed_policy_records_ringba_offer_approval():
    from empire_os.buyer_supply_policy import (
        lead_smart_confirmed_roofing_policy,
    )

    policy = lead_smart_confirmed_roofing_policy(
        source_ref="gmail:1a10c6b2530f2951"
    )

    routing = policy["routing"]

    assert routing["offer_application_required"] is True
    assert routing["offer_application_status"] == "approved"
    assert routing["offer_application_approved"] is True
    assert routing["ringba_offer_label"] == "Roofing - Nationwide"
    assert (
        routing["ringba_campaign_id"]
        == "CA8278ed3f26e9495b881fe3833174d007"
    )
    assert (
        routing["offer_approval_source_ref"]
        == "gmail:1a1112c17349445a"
    )

    # Offer approval is not routing authority.
    assert routing["tracking_number_assigned"] is True
    assert routing["tracking_number"] == "+18883579305"
    assert routing["tracking_verified"] is False
    assert routing["routing_verified"] is False
