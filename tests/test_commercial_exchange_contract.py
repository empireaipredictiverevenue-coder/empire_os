from empire_os.commercial_exchange_contract import (
    build_commercial_exchange_contract,
)


def test_phase4_contract_is_current_and_supabase_native():
    result = build_commercial_exchange_contract()

    assert result["phase"] == "4"
    assert result["status"] == "CURRENT"
    assert "buyers" in result["canonical_source_tables"]
    assert "fulfilment_orders" in result["canonical_source_tables"]
    assert "empire_os/seat_corridors.py" in result["legacy_reference_only"]
    assert "buyer_seats" in result["required_exchange_objects"]


def test_capacity_never_stops_acquisition_and_overflow_is_owned():
    result = build_commercial_exchange_contract()
    rules = result["invariants"]

    assert rules["buyer_capacity_gates_delivery_only"] is True
    assert rules["buyer_capacity_never_gates_acquisition"] is True
    assert rules["full_seats_do_not_stop_acquisition"] is True
    assert rules["overflow_remains_empire_owned"] is True
    assert "future_capacity" in result["overflow_routes"]


def test_phase4_automation_does_not_expand_external_authority():
    result = build_commercial_exchange_contract()
    automation = result["automation"]

    assert automation[
        "automatic_acquisition_continues_when_capacity_full"
    ] is True
    assert automation["automatic_external_delivery"] is False
    assert automation["automatic_commercial_terms_acceptance"] is False
    assert automation["automatic_fund_movement"] is False
    assert automation["automatic_revenue_recognition"] is False
    assert result["production_schema_applied"] is False
    assert result["execution_authority"] == "none"


def test_phase4_pricing_and_exclusivity_fail_closed():
    rules = build_commercial_exchange_contract()["invariants"]

    assert rules["pricing_requires_verified_evidence"] is True
    assert rules["historical_pricing_is_not_current_pricing"] is True
    assert rules["seat_activation_requires_verified_terms"] is True
    assert rules["seat_activation_requires_verified_capacity"] is True
    assert rules["territory_requires_evidence"] is True
    assert rules["exclusivity_requires_evidence"] is True
