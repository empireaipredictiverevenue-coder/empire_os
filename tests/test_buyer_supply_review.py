from empire_os.buyer_supply_policy import lead_smart_observed_policy
from empire_os.buyer_supply_review import build_supply_review


SOURCE = "gmail:1a0da7880f69e8c6"


def policy():
    return lead_smart_observed_policy(source_ref=SOURCE)


def test_lead_smart_review_fail_closed():
    result = build_supply_review(policy())

    assert result["pilot_ready"] is False
    assert result["live_traffic_authorized"] is False
    assert result["commercial_activation_authorized"] is False


def test_lead_smart_asset_review_blockers():
    result = build_supply_review(policy())

    assert "sites_reviewed" in result["blockers"]
    assert "landing_pages_reviewed" in result["blockers"]
    assert "ads_reviewed" in result["blockers"]


def test_lead_smart_commercial_blockers():
    result = build_supply_review(policy())

    assert "traffic_source_buyer_approval" in result["blockers"]
    assert "dynamic_payout_verification" in result["blockers"]
    assert "rtb_terms_verification" in result["blockers"]


def test_asset_review_alone_does_not_make_pilot_ready():
    p = policy()

    p["review"] = {
        "sites_reviewed": True,
        "landing_pages_reviewed": True,
        "ads_reviewed": True,
    }

    result = build_supply_review(p)

    assert result["asset_review"]["ready"] is True
    assert result["pilot_ready"] is False
    assert result["live_traffic_authorized"] is False


def test_complete_review_evidence_still_does_not_authorize_traffic():
    p = policy()

    p["review"] = {
        "sites_reviewed": True,
        "landing_pages_reviewed": True,
        "ads_reviewed": True,
    }

    p["acquisition"]["buyer_approved"] = True
    p["pricing"]["verified"] = True
    p["routing"]["rtb_terms_verified"] = True

    result = build_supply_review(p)

    assert result["blockers"] == []
    assert result["pilot_ready"] is True

    # Readiness never grants execution authority.
    assert result["live_traffic_authorized"] is False
    assert result["commercial_activation_authorized"] is False



def test_explicit_direct_route_does_not_require_optional_rtb_terms():
    p = policy()
    p["routing"]["selected_mode"] = "direct"
    p["routing"]["rtb_supported"] = True
    p["routing"]["rtb_terms_verified"] = False

    result = build_supply_review(p)

    assert "rtb_terms_verification" not in result["blockers"]
    assert result["requirements"]["selected_routing_mode"] == "direct"


def test_explicit_rtb_route_requires_rtb_terms():
    p = policy()
    p["routing"]["selected_mode"] = "rtb"
    p["routing"]["rtb_supported"] = True
    p["routing"]["rtb_terms_verified"] = False

    result = build_supply_review(p)

    assert "rtb_terms_verification" in result["blockers"]
    assert result["requirements"]["selected_routing_mode"] == "rtb"


def test_explicit_rtb_route_requires_rtb_support():
    p = policy()
    p["routing"]["selected_mode"] = "rtb"
    p["routing"]["rtb_supported"] = False
    p["routing"]["rtb_terms_verified"] = False

    result = build_supply_review(p)

    assert "rtb_not_supported" in result["blockers"]
    assert result["pilot_ready"] is False


def test_unknown_route_fails_closed():
    p = policy()
    p["routing"]["selected_mode"] = "telepathy"

    result = build_supply_review(p)

    assert "routing_mode_invalid" in result["blockers"]
    assert result["pilot_ready"] is False


def test_legacy_policy_without_selected_route_preserves_old_rtb_gate():
    p = policy()
    p["routing"].pop("selected_mode", None)
    p["routing"]["rtb_supported"] = True
    p["routing"]["rtb_terms_verified"] = False

    result = build_supply_review(p)

    assert "rtb_terms_verification" in result["blockers"]
    assert result["requirements"]["selected_routing_mode"] is None



def test_verified_dynamic_pricing_mechanism_does_not_require_fixed_payout():
    p = policy()

    p["pricing"]["dynamic"] = True
    p["pricing"]["mechanism_verified"] = True
    p["pricing"]["actual_payout_observed"] = False
    p["pricing"]["payout_value"] = None
    p["pricing"]["currency"] = None
    p["pricing"]["verified"] = False

    result = build_supply_review(p)

    assert "dynamic_payout_verification" not in result["blockers"]
    assert result["requirements"]["pricing_mechanism_verified"] is True
    assert result["requirements"]["actual_payout_observed"] is False


def test_unverified_dynamic_pricing_mechanism_still_blocks():
    p = policy()

    p["pricing"]["dynamic"] = True
    p["pricing"]["mechanism_verified"] = False
    p["pricing"]["verified"] = False

    result = build_supply_review(p)

    assert "dynamic_payout_verification" in result["blockers"]


def test_legacy_verified_dynamic_pricing_remains_compatible():
    p = policy()

    p["pricing"]["dynamic"] = True
    p["pricing"].pop("mechanism_verified", None)
    p["pricing"]["verified"] = True

    result = build_supply_review(p)

    assert "dynamic_payout_verification" not in result["blockers"]
