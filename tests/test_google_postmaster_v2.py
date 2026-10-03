from empire_os.google_postmaster_v2 import (
    default_metric_definitions,
    normalize_compliance_status,
)


def test_default_postmaster_metrics_cover_auth_spam_tls_and_errors():
    definitions = default_metric_definitions()
    names = {row["name"] for row in definitions}
    assert {
        "spam_rate",
        "spf_success_rate",
        "dkim_success_rate",
        "dmarc_success_rate",
        "tls_outbound_rate",
        "reject_error_rate",
        "temp_fail_error_rate",
    } <= names


def test_postmaster_spam_verdict_is_gmail_specific_hold():
    result = normalize_compliance_status({
        "spfStatus": {"state": "COMPLIANT"},
        "dkimStatus": {"state": "COMPLIANT"},
        "dmarcStatus": {"state": "COMPLIANT"},
        "deliverabilityStatusVerdict": {
            "state": {"state": "NOT_COMPLIANT"},
            "reason": "SPAM_RATE_HIGH",
        },
    })
    assert result["posture"] == "HOLD_GMAIL"
    assert result["scope"] == "gmail_destination_only"


def test_low_volume_is_observation_not_false_failure():
    result = normalize_compliance_status({
        "deliverabilityStatusVerdict": {
            "reason": "MESSAGE_VOLUME_LOW",
        },
    })
    assert result["posture"] == "OBSERVE"
