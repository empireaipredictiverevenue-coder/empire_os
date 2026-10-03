from empire_os.outbound_destination_reputation import evaluate_destination_reputation


def test_google_spam_hold_is_destination_scoped():
    result = evaluate_destination_reputation({
        "mx_family": "GOOGLE",
        "google_compliance": {
            "spfStatus": {"state": "COMPLIANT"},
            "dkimStatus": {"state": "COMPLIANT"},
            "dmarcStatus": {"state": "COMPLIANT"},
            "deliverabilityStatusVerdict": {
                "state": {"state": "NOT_COMPLIANT"},
                "reason": "SPAM_RATE_HIGH",
            },
        },
        "seed_placement": {"inbox_placement_rate": 0.98},
    })
    assert result["posture"] == "HOLD_DESTINATION"
    assert result["capacity_multiplier"] == 0.0
    assert result["scope"] == "recipient_mx_family"


def test_microsoft_transient_deferral_halves_destination_capacity():
    result = evaluate_destination_reputation({
        "mx_family": "MICROSOFT",
        "microsoft_delivery": {
            "smtp_code": 421,
            "response": "421 temporary deferral",
        },
        "seed_placement": {"inbox_placement_rate": 0.97},
    })
    assert result["posture"] == "LIMIT_DESTINATION"
    assert result["capacity_multiplier"] == 0.5


def test_good_destination_evidence_is_green():
    result = evaluate_destination_reputation({
        "mx_family": "MICROSOFT",
        "microsoft_delivery": {
            "smtp_code": 250,
            "response": "250 accepted",
        },
        "seed_placement": {"inbox_placement_rate": 0.98},
    })
    assert result["posture"] == "GREEN"
