from empire_os.intelligence.compat import (
    analyze_lead,
    analyze_with_legacy_fields,
    legacy_fields,
)


def test_legacy_fields_are_derived_from_omega_2():
    lead = {
        "business_name": "Example Roofing",
        "phone": "+1 555 0100",
        "email": "owner@example.com",
        "website": "https://example.com",
        "city": "Dallas",
        "state": "TX",
        "niche": "roofing",
        "status": "qualified",
        "details": "Commercial roofing replacement opportunity.",
    }

    fields = legacy_fields(lead)

    prediction = analyze_lead(lead)

    assert fields["omega_score"] == prediction.legacy_omega_score
    assert fields["omega_tier"] == prediction.legacy_omega_tier


def test_legacy_input_score_is_not_used_by_adapter():
    lead = {
        "business_name": "Example Roofing",
        "phone": "+1 555 0100",
        "email": "owner@example.com",
        "website": "https://example.com",
        "city": "Dallas",
        "state": "TX",
        "niche": "roofing",
        "status": "qualified",
        "details": "Commercial roofing replacement opportunity.",
    }

    low_prediction, low_fields = analyze_with_legacy_fields(
        {**lead, "omega_score": 0}
    )
    high_prediction, high_fields = analyze_with_legacy_fields(
        {**lead, "omega_score": 100}
    )

    assert low_prediction == high_prediction
    assert low_fields == high_fields
