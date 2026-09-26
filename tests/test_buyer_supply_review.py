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
