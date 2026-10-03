from empire_os.outbound_yahoo_evidence import normalize_yahoo_delivery_evidence
from empire_os.outbound_apple_evidence import normalize_apple_delivery_evidence
from empire_os.outbound_recipient_domain_policy import evaluate_recipient_domain_policy


def test_yahoo_cfl_complaint_is_destination_hold():
    result = normalize_yahoo_delivery_evidence({
        "smtp_code": 250,
        "response": "accepted",
        "arf_complaints": 1,
    })
    assert result["posture"] == "HOLD_YAHOO"


def test_yahoo_published_spam_ceiling_is_hold():
    result = normalize_yahoo_delivery_evidence({
        "sender_hub_spam_rate": 0.003,
    })
    assert result["posture"] == "HOLD_YAHOO"


def test_apple_transient_deferral_is_destination_backoff():
    result = normalize_apple_delivery_evidence({
        "smtp_code": 421,
        "response": "421 temporary rate limit",
    })
    assert result["posture"] == "BACKOFF_APPLE"


def test_unconsented_consumer_mailbox_prospecting_is_held():
    result = evaluate_recipient_domain_policy({
        "recipient_domain": "gmail.com",
        "traffic_class": "prospecting",
        "consented": False,
        "existing_relationship": False,
        "person_company_bound": True,
    })
    assert result["decision"] == "HOLD"


def test_consented_consumer_mailbox_is_not_automatically_held():
    result = evaluate_recipient_domain_policy({
        "recipient_domain": "outlook.com",
        "traffic_class": "relationship",
        "consented": True,
        "existing_relationship": True,
        "person_company_bound": True,
    })
    assert result["decision"] == "READY"
