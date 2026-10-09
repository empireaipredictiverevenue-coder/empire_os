from decimal import Decimal

from empire_os.buyer_network_integration import (
    BuyerNetworkIntegration,
    integration_status,
)


def test_existing_stack_imports_without_modification():

    status = integration_status()

    assert status.ready is True
    assert status.authority == "OBSERVE"


def test_candidate_assessment():

    result = BuyerNetworkIntegration.candidate(
        vertical_match=True,
        publisher_program_confidence=.95,
        active_demand_confidence=.90,
        inventory_fit_confidence=.90,
        integration_confidence=.80,
        economics_confidence=.75,
        contactable=True,
        evidence_count=5,
    )

    assert result.readiness == "READY_TO_APPROACH"


def test_supply_fit():

    result = BuyerNetworkIntegration.supply_fit(
        buyer_verticals=("roofing",),
        buyer_inventory_types=("inbound_call",),
        buyer_geographies=("TX",),
        supply_vertical="roofing",
        supply_inventory_type="inbound_call",
        supply_geographies=("TX",),
        tracking_required=True,
        tracking_ready=True,
    )

    assert result.gate == "TEST_COMPATIBLE"


def test_reply_intelligence():

    result = BuyerNetworkIntegration.reply(
        "Tell me where the traffic source originates, "
        "whether it is calls or forms, your website, "
        "then book a meeting."
    )

    assert (
        result.intent
        == "MEETING_AND_INFORMATION_REQUEST"
    )


def test_economics_remain_observed_only():

    result = BuyerNetworkIntegration.economics([
        {
            "event_type": "SUBMITTED",
            "units": 10,
        },
        {
            "event_type": "LEAD_ACCEPTED",
            "units": 5,
        },
        {
            "event_type": "REALISED_REVENUE",
            "value": "500",
        },
    ])

    assert (
        result["revenue_per_accepted"]
        == Decimal("100")
    )

    assert result["observed_cost"] is None


def test_capacity_requires_more_buyers():

    result = BuyerNetworkIntegration.lane_health(
        active_buyers=1,
        observed_supply_volume=30,
        buyer_caps=(20,),
        accepted_today=(10,),
    )

    assert result.discovery_required is True
    assert result.observed_gap == 20


def test_bounded_test_is_proposal_only():

    result = BuyerNetworkIntegration.bounded_test(
        requested_units=20,
        safety_max_units=10,
        buyer_remaining_cap=12,
        verified_supply_available=8,
    )

    assert result.units == 8
    assert result.authority == "PROPOSAL_ONLY"
