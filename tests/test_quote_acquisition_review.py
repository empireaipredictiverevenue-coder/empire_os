import pytest
from empire_os.quote_acquisition_review import review_quote_request, GATES


def test_unknown_is_held():
    r = review_quote_request(vertical="roofing", request={}, buyer={})
    assert r["match_review"] == "HOLD"
    assert r["quote_qualification"] == "HOLD"
    assert not r["customer_data_disclosed"]


def test_requires_consent_and_verified_capacity():
    request = dict.fromkeys(GATES, True)
    buyer = dict.fromkeys(("contracted", "service_match", "territory_match",
                          "capacity_verified", "terms_accepted", "delivery_permission"), True)
    request["contact_permission"] = False
    assert review_quote_request(vertical="hvac", request=request, buyer=buyer)["match_review"] == "HOLD"
    request["contact_permission"] = True
    buyer["capacity_verified"] = False
    assert review_quote_request(vertical="hvac", request=request, buyer=buyer)["match_review"] == "HOLD"


def test_all_gates_only_allow_review():
    request = dict.fromkeys(GATES, True)
    buyer = dict.fromkeys(("contracted", "service_match", "territory_match",
                          "capacity_verified", "terms_accepted", "delivery_permission"), True)
    result = review_quote_request(vertical="roofing", request=request, buyer=buyer)
    assert result["match_review"] == "READY_FOR_HUMAN_REVIEW"
    assert not any(result[key] for key in ("outbound_authorized", "customer_data_disclosed",
                                         "lead_delivered", "crm_writes", "payment_execution",
                                         "revenue_verified"))


def test_no_leak_of_contact_details():
    result = review_quote_request(vertical="plumbing",
        request={"email": "someone@example.com", "phone": "5551234567"}, buyer={})
    assert "someone@example.com" not in str(result)
    assert "5551234567" not in str(result)


def test_rejects_bad_types_and_verticals():
    with pytest.raises(ValueError):
        review_quote_request(vertical="unknown", request={}, buyer={})
    with pytest.raises(ValueError):
        review_quote_request(vertical="roofing", request=None, buyer={})
