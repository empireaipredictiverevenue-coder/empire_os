from empire_os.outbound_mx_family import classify_mx_family
from empire_os.microsoft_outlook_evidence import normalize_outlook_delivery_evidence


def test_microsoft_365_mx_is_classified_for_destination_pacing():
    result = classify_mx_family([
        "example-com.mail.protection.outlook.com.",
    ])
    assert result["family"] == "MICROSOFT"


def test_google_workspace_mx_is_classified():
    result = classify_mx_family(["aspmx.l.google.com."])
    assert result["family"] == "GOOGLE"


def test_mixed_mx_is_not_overclaimed():
    result = classify_mx_family([
        "aspmx.l.google.com.",
        "example.mail.protection.outlook.com.",
    ])
    assert result["family"] == "MIXED"


def test_outlook_57515_is_destination_specific_auth_hold():
    result = normalize_outlook_delivery_evidence({
        "smtp_code": 550,
        "response": (
            "550 5.7.515 Access denied, sending domain does not meet "
            "the required authentication level"
        ),
    })
    assert result["posture"] == "HOLD_MICROSOFT"
    assert "microsoft_authentication_requirement_failure" in result["signals"]


def test_outlook_transient_response_causes_backoff_not_global_hold():
    result = normalize_outlook_delivery_evidence({
        "smtp_code": 421,
        "response": "421 temporary deferral",
    })
    assert result["posture"] == "BACKOFF_MICROSOFT"
    assert result["scope"] == "microsoft_destination_only"
