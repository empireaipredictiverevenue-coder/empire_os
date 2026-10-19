"""Consent-bound organic campaign touch: no inference of sessions or revenue."""
import pytest
from fastapi.testclient import TestClient

from empire_os.organic_campaign_touch import normalize_organic_touch
from empire_os.first_party_sales_interest import (
    CommercialInterestError, record_founder_led_interest,
)
from empire_os.self_serve_checkout_api import app

CID = "campaign_" + "a" * 24
TOUCH = {
    "campaign_id": CID, "asset_id": CID + ":linkedin",
    "source": "linkedin", "medium": "organic_social",
    "landing_path": "/industries/solar",
}
NOW = "2026-10-18T13:50:00+00:00"


def _inputs():
    from datetime import datetime
    return {
        "product_code": "consultancy_opportunity_assessment",
        "business_name": "Example Corporation",
        "email": "director@example.test",
        "domain": "example.test",
        "industry": "Solar services",
        "geography": "England",
        "desired_outcome": "Review evidence and coverage for installations.",
        "contact_consent": True,
        "idempotency_key": "deterministic-abc12345",
        "now": datetime.fromisoformat(NOW),
    }


def test_known_utm_token_has_no_measured_session_or_conversion():
    row = normalize_organic_touch(TOUCH)
    assert row["campaign_id"] == CID
    assert row["evidence_class"] == "BUYER_SUBMITTED_URL_CAMPAIGN_TOKEN_ONLY"
    assert row["session_verified"] is False
    assert row["channel_click_verified"] is False
    assert row["attributable_enquiry_confirmed"] is False
    assert row["revenue_attribution_confirmed"] is False
    assert "email" not in row


@pytest.mark.parametrize("changes", [
    {"source": "evil"},
    {"medium": "paid_search"},
    {"landing_path": "https://evil.example/path"},
    {"landing_path": "/account/private"},
    {"asset_id": CID + ":facebook"},
    {"campaign_id": "campaign_unauthorized"},
    {"source": "youtube"},
    {"asset_id": CID + ":newsletter"},
    {"landing_path": "/industries/solar?token=private"},
    {"session_id": "example-fake-session"},
])
def test_reject_malformed_or_forged_campaign_touch(changes):
    with pytest.raises(ValueError):
        normalize_organic_touch({**TOUCH, **changes})


def test_optional_touch_is_stored_only_with_consented_real_enquiry(tmp_path):
    evidence = []
    def accepted(method, path, *, payload):
        evidence.append(payload)
        return {"decision": "created", "prospect": {"id": "test-id"}}
    data = record_founder_led_interest(
        **_inputs(), organic_touch=TOUCH, root=tmp_path, request=accepted
    )
    assert data["decision"] == "commercial_enquiry_recorded"
    assert data["actual_revenue"] is False
    assert len(evidence) == 1
    touch = evidence[0]["p_evidence"]["organic_campaign_touch"]
    assert touch["campaign_id"] == CID
    assert touch["attributable_enquiry_confirmed"] is False
    assert evidence[0]["p_prospect"]["contact_source"] == "first_party_commercial_sales_enquiry"


def test_no_touch_preserves_existing_intake_contract(tmp_path):
    calls = []
    def accepted(method, path, *, payload):
        calls.append(payload)
        return {"decision": "created", "prospect": {"id": "test-id"}}
    record_founder_led_interest(**_inputs(), root=tmp_path, request=accepted)
    assert "organic_campaign_touch" not in calls[0]["p_evidence"]


def test_unconsented_or_untrusted_token_cannot_write_to_db(tmp_path):
    def deny(*args, **kwargs):
        pytest.fail("unconsented_or_invalid_touch_wrote_to_canonical_db")
    data = _inputs()
    data["contact_consent"] = False
    with pytest.raises(CommercialInterestError):
        record_founder_led_interest(
            **data, organic_touch=TOUCH, root=tmp_path, request=deny
        )
    with pytest.raises(CommercialInterestError):
        record_founder_led_interest(
            **_inputs(), organic_touch={**TOUCH, "source": "bad"},
            root=tmp_path, request=deny
        )


def test_api_schema_accepts_optional_touch_pass_through(monkeypatch):
    import empire_os.self_serve_checkout_api as api
    seen = []
    def no_real_write(**kwargs):
        seen.append(kwargs)
        return {
            "decision": "commercial_enquiry_recorded",
            "reference": "mock-receipt",
            "actual_revenue": False,
            "execution_authority": "none",
        }
    monkeypatch.setattr(api, "record_founder_led_interest", no_real_write)
    body = {k: v for k, v in _inputs().items() if k != "now"}
    body["organic_touch"] = TOUCH
    response = TestClient(app).post("/v1/commercial/interests", json=body)
    assert response.status_code == 200
    assert seen[0]["organic_touch"] == TOUCH
    assert response.json()["actual_revenue"] is False
