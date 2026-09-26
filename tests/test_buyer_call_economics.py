import pytest

from empire_os.buyer_call_economics import build_call_economics, routing_decision


def _base(**overrides):
    values = {
        "buyer_name": "Lead Smart",
        "program_ref": "lead-smart-roofing-pilot",
        "service": "roofing",
        "geography": None,
        "payout_amount": None,
        "payout_currency": None,
        "qualification_seconds": None,
        "daily_cap": None,
        "traffic_source": None,
        "traffic_source_approved": False,
        "routing_mode": None,
        "routing_verified": False,
        "tracking_verified": False,
        "buyer_asset_approved": False,
        "estimated_cost_per_call": None,
    }
    values.update(overrides)
    return build_call_economics(**values)


def test_unknown_buyer_terms_fail_closed():
    economics = _base()

    assert economics["pilot_ready"] is False
    assert economics["live_traffic_authorized"] is False
    assert economics["revenue_recognized"] is False
    assert economics["economics"]["margin_known"] is False
    assert economics["economics"]["gross_margin_per_accepted_call"] is None

    expected = {
        "geography_unverified",
        "payout_unverified",
        "qualification_rule_unverified",
        "capacity_unverified",
        "traffic_source_unverified",
        "traffic_source_not_approved",
        "routing_mode_unverified",
        "routing_not_verified",
        "tracking_not_verified",
        "buyer_asset_not_approved",
    }
    assert set(economics["blockers"]) == expected

    decision = routing_decision(economics)
    assert decision["decision"] == "hold"
    assert decision["live_traffic_authorized"] is False
    assert decision["revenue_recognized"] is False


def test_verified_inputs_make_pilot_ready_but_do_not_authorize_live_traffic():
    economics = _base(
        geography="verified-buyer-geo",
        payout_amount=125.0,
        payout_currency="usd",
        qualification_seconds=120,
        daily_cap=10,
        traffic_source="search",
        traffic_source_approved=True,
        routing_mode="rtb",
        routing_verified=True,
        tracking_verified=True,
        buyer_asset_approved=True,
        estimated_cost_per_call=55.25,
    )

    assert economics["blockers"] == []
    assert economics["pilot_ready"] is True
    assert economics["payout"]["currency"] == "USD"
    assert economics["economics"]["margin_known"] is True
    assert economics["economics"]["gross_margin_per_accepted_call"] == 69.75
    assert economics["live_traffic_authorized"] is False
    assert economics["revenue_recognized"] is False

    decision = routing_decision(economics)
    assert decision["decision"] == "ready_for_separate_live_traffic_activation"
    assert decision["live_traffic_authorized"] is False
    assert decision["revenue_recognized"] is False


def test_margin_stays_unknown_until_acquisition_cost_is_known():
    economics = _base(
        geography="verified-buyer-geo",
        payout_amount=100.0,
        payout_currency="USD",
        qualification_seconds=90,
        daily_cap=5,
        traffic_source="search",
        traffic_source_approved=True,
        routing_mode="direct",
        routing_verified=True,
        tracking_verified=True,
        buyer_asset_approved=True,
    )

    assert economics["pilot_ready"] is True
    assert economics["economics"]["margin_known"] is False
    assert economics["economics"]["gross_margin_per_accepted_call"] is None


@pytest.mark.parametrize(
    ("field", "value", "blocker"),
    [
        ("payout_amount", 0, "payout_invalid"),
        ("payout_amount", -10, "payout_invalid"),
        ("qualification_seconds", 0, "qualification_rule_invalid"),
        ("qualification_seconds", -1, "qualification_rule_invalid"),
        ("daily_cap", 0, "capacity_invalid"),
        ("daily_cap", -1, "capacity_invalid"),
        ("estimated_cost_per_call", -0.01, "acquisition_cost_invalid"),
    ],
)
def test_invalid_economic_inputs_fail_closed(field, value, blocker):
    verified = {
        "geography": "verified-buyer-geo",
        "payout_amount": 100.0,
        "payout_currency": "USD",
        "qualification_seconds": 90,
        "daily_cap": 5,
        "traffic_source": "search",
        "traffic_source_approved": True,
        "routing_mode": "rtb",
        "routing_verified": True,
        "tracking_verified": True,
        "buyer_asset_approved": True,
        "estimated_cost_per_call": 50.0,
    }
    verified[field] = value
    economics = _base(**verified)

    assert blocker in economics["blockers"]
    assert economics["pilot_ready"] is False
    assert routing_decision(economics)["decision"] == "hold"
    assert economics["live_traffic_authorized"] is False
    assert economics["revenue_recognized"] is False


def test_zero_acquisition_cost_is_valid_when_verified():
    economics = _base(
        geography="verified-buyer-geo",
        payout_amount=100.0,
        payout_currency="USD",
        qualification_seconds=90,
        daily_cap=5,
        traffic_source="search",
        traffic_source_approved=True,
        routing_mode="rtb",
        routing_verified=True,
        tracking_verified=True,
        buyer_asset_approved=True,
        estimated_cost_per_call=0.0,
    )

    assert economics["pilot_ready"] is True
    assert economics["acquisition"]["cost_valid"] is True
    assert economics["economics"]["gross_margin_per_accepted_call"] == 100.0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("buyer_name", "", "buyer_name is required"),
        ("program_ref", "", "program_ref is required"),
        ("service", "", "service is required"),
    ],
)
def test_required_identity_fields_are_enforced(field, value, message):
    kwargs = {
        "buyer_name": "Lead Smart",
        "program_ref": "lead-smart-roofing-pilot",
        "service": "roofing",
        "geography": None,
        "payout_amount": None,
        "payout_currency": None,
        "qualification_seconds": None,
        "daily_cap": None,
        "traffic_source": None,
        "traffic_source_approved": False,
        "routing_mode": None,
        "routing_verified": False,
        "tracking_verified": False,
        "buyer_asset_approved": False,
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match=message):
        build_call_economics(**kwargs)
