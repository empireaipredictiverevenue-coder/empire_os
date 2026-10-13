"""Predictive Revenue enterprise buyer opt-in: fail closed before canonical writes."""
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from empire_os import predictive_revenue_self_serve as intake
from empire_os import self_serve_checkout_api as api

VALID = dict(
    product_code="predictive_revenue_diagnostic",
    business_name="Company Limited",
    email="buyer@example.com",
    domain="example.com",
    industry="Home services",
    geography="United Kingdom",
    annual_revenue_band="25m_100m",
    desired_outcome="We would like to understand forecast error.",
    systems=["CRM"],
    idempotency_key="enterprise-consent-test-001",
    contact_consent=True,
    website="",
)


@pytest.mark.parametrize("bad", [False, None, 1, "true"])
def test_nonliteral_consent_denied_before_ingest(bad):
    calls = []
    with pytest.raises(intake.PredictiveRevenueInterestError, match="specific_contact_consent_required"):
        intake.record_predictive_revenue_interest(
            **{**VALID, "contact_consent": bad},
            request=lambda *args, **kwargs: calls.append((args, kwargs)),
        )
    assert calls == []


def test_honeypot_denied_before_ingest():
    calls = []
    with pytest.raises(intake.PredictiveRevenueInterestError, match="invalid_submission"):
        intake.record_predictive_revenue_interest(
            **{**VALID, "website": "https://spam.example"},
            request=lambda *args, **kwargs: calls.append((args, kwargs)),
        )
    assert calls == []


def test_consent_timestamp_must_be_aware():
    with pytest.raises(intake.PredictiveRevenueInterestError, match="contact_consent_clock_untrusted"):
        intake.record_predictive_revenue_interest(
            **VALID,
            now=datetime(2026, 10, 13),
            request=lambda *args, **kwargs: pytest.fail("DB request must not run"),
        )


def test_specific_response_consent_recorded_without_automatic_outbound():
    seen = []
    def capture(method, path, payload):
        assert method == "POST"
        seen.append(payload)
        return {"decision": "created", "prospect": {"id": "prospect-01"}}

    result = intake.record_predictive_revenue_interest(
        **VALID, request=capture, now=datetime(2026, 10, 13, 21, 0, tzinfo=timezone.utc)
    )
    assert result["decision"] == "deployment_interest_recorded"
    assert result["payment_action"] is False
    assert result["actual_revenue"] is False
    assert len(seen) == 1
    evidence = seen[0]["p_evidence"]
    assert evidence["contact_consent_evidence"] == {
        "kind": "buyer_initiated_specific_response_consent",
        "observed_at": "2026-10-13T21:00:00+00:00",
        "consent_to_contact": True,
        "newsletter_or_ongoing_marketing_consent": False,
        "source_url": "https://empire-ai.co.uk/predictive-revenue",
    }
    assert evidence["automatic_followup_authorized"] is False
    assert evidence["execution_authority"] == "none"


def test_api_rejects_absent_false_consent_and_honeypot_before_backend(monkeypatch):
    called = []
    monkeypatch.setattr(
        api, "record_predictive_revenue_interest",
        lambda **kwargs: called.append(kwargs) or {"decision": "deployment_interest_recorded"},
    )
    client = TestClient(api.app)
    for data in (
        {k: v for k, v in VALID.items() if k != "contact_consent"},
        {**VALID, "contact_consent": False},
        {**VALID, "website": "fake.example"},
    ):
        response = client.post("/v1/predictive-revenue/interests", json=data)
        assert response.status_code == 422
    assert called == []


def test_api_accepts_specific_consent_without_send(monkeypatch):
    called = []
    monkeypatch.setattr(
        api, "record_predictive_revenue_interest",
        lambda **kwargs: called.append(kwargs) or {
            "decision": "deployment_interest_recorded", "payment_action": False
        },
    )
    response = TestClient(api.app).post("/v1/predictive-revenue/interests", json=VALID)
    assert response.status_code == 200
    assert response.json()["payment_action"] is False
    assert called[0]["contact_consent"] is True
    assert called[0]["website"] == ""


def test_live_site_source_requires_optin_and_protects_with_honeypot():
    source = (Path(__file__).resolve().parents[1] /
              "apps/empire-public-site/src/app/predictive-revenue/page.tsx").read_text()
    for required in (
        "contact_consent: contactConsent",
        "website,",
        "type=\"checkbox\" required",
        "disabled={!product || !contactConsent || submitting}",
        "I am not signing up for unrelated marketing.",
        'className="hidden" aria-hidden="true"',
    ):
        assert required in source
