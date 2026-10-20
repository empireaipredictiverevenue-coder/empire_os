"""Synthetic aggregate funnel metrics never establish payments or verified revenue."""
import pytest
from empire_os.meta_pilot_measurement import SCHEMA, assess_telemetry


def test_no_telemetry_is_not_fabricated():
    result = assess_telemetry(None, {"us_hvac_phoenix"})
    assert result["status"] == "NO_FIRST_PARTY_TELEMETRY"
    assert result["revenue_verified"] is False


def test_impressive_self_report_is_still_unverified():
    result = assess_telemetry({
        "schema_version": SCHEMA,
        "lanes": [{
            "lane_id": "us_hvac_phoenix",
            "eligible_landing_visits": 1000,
            "opted_in_enquiries": 100,
            "qualified_enquiries": 40,
            "payer_accepted_appointments": 12,
            "settled_payouts": 10,
        }],
    }, {"us_hvac_phoenix"})
    assert result["status"] == "UNVERIFIED_AGGREGATE_REPORT_FOR_REVIEW"
    assert result["lanes"][0]["learning_signal"] == "CLAIMED_PAYOUT_REQUIRES_CANONICAL_RECONCILIATION"
    assert result["lanes"][0]["actual_payouts_independently_verified"] is False
    assert result["revenue_verified"] is False


def test_zero_conversion_is_a_stop_review_not_fake_revenue():
    result = assess_telemetry({
        "schema_version": SCHEMA,
        "lanes": [{
            "lane_id": "us_hvac_phoenix",
            "eligible_landing_visits": 100,
            "opted_in_enquiries": 0,
            "qualified_enquiries": 0,
            "payer_accepted_appointments": 0,
            "settled_payouts": 0,
        }],
    }, {"us_hvac_phoenix"})
    assert result["lanes"][0]["learning_signal"] == "REVIEW_STOP_ZERO_CONVERSION"


def test_rejects_private_records_duplicated_unknown_lanes_bad_funnel():
    row = {
        "lane_id": "us_hvac_phoenix",
        "eligible_landing_visits": 10,
        "opted_in_enquiries": 5,
        "qualified_enquiries": 4,
        "payer_accepted_appointments": 2,
        "settled_payouts": 1,
    }
    with pytest.raises(ValueError, match="personal_data"):
        assess_telemetry({"schema_version": SCHEMA, "lanes": [{**row, "phone": "123"}]}, {"us_hvac_phoenix"})
    with pytest.raises(ValueError, match="duplicate"):
        assess_telemetry({"schema_version": SCHEMA, "lanes": [row, row]}, {"us_hvac_phoenix"})
    with pytest.raises(ValueError, match="unknown"):
        assess_telemetry({"schema_version": SCHEMA, "lanes": [row]}, {"us_roofing_tampa"})
    with pytest.raises(ValueError, match="non_monotonic"):
        assess_telemetry({"schema_version": SCHEMA,
                          "lanes": [{**row, "payer_accepted_appointments": 9}]},
                         {"us_hvac_phoenix"})
