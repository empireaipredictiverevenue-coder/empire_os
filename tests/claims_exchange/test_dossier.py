import copy
from datetime import date, timedelta

import pytest

from empire_os.claims_exchange.dossier import SCHEMA, build_dossiers

TODAY = date(2026, 10, 9)


def cohort():
    return {
        "schema_version": "empire.revenue_strike.storm.v1",
        "outbound_sent": False,
        "market": "Dallas-Fort Worth, TX",
        "prospects": [
            {"id": "historical-1", "business_name": "Example Roofing",
             "website": "https://example.com"},
        ],
    }


def observations(**overrides):
    item = {
        "original_domain": "example.com",
        "source_url": "https://example.com/roofing",
        "final_url": "https://example.com/roofing",
        "observed_at": TODAY.isoformat(),
        "reviewer": "public_website_verification",
        "self_described_name": "Example Roofing",
        "roofing_services_observed": True,
        "dfw_service_area_observed": True,
        "public_business_contact": {"type": "email", "value": "hello@example.com"},
        "insurance_claims_wording_observed": False,
    }
    item.update(overrides)
    return {"schema": SCHEMA, "sites": [item]}


def test_happy_path_requires_independent_company_identity():
    r = build_dossiers(cohort(), observations(), as_of=TODAY)
    assert r["summary"]["historic_cohort_size"] == 1
    d = r["dossiers"][0]
    assert d["qualification_stage"] == "CORROBORATION_PENDING"
    assert d["public_contact_source_observed"] is True
    assert "INDEPENDENT_COMPANY_IDENTITY_CORROBORATION_REQUIRED" in d["research_tasks"]
    assert d["founder_review_ready"] is False
    assert r["outbound_authorized"] is False


def test_redirect_to_different_company_blocks():
    r = build_dossiers(cohort(), observations(
        final_url="https://another-company.com",
        self_described_name="Another Company"
    ), as_of=TODAY)
    d = r["dossiers"][0]
    assert d["qualification_stage"] == "IDENTITY_CHANGE_HOLD"
    assert "REDIRECTED_TO_DIFFERENT_COMPANY_DOMAIN" in d["research_tasks"]
    assert d["research_priority"] == 0
    assert not d["public_contact_source_observed"]


def test_missing_observation_stays_on_hold():
    r = build_dossiers(cohort(), {"schema": SCHEMA, "sites": []}, as_of=TODAY)
    assert "SOURCE_OBSERVATION_MISSING" in r["dossiers"][0]["research_tasks"]
    assert not r["dossiers"][0]["public_contact_source_observed"]


def test_duplicate_observation_cannot_auto_resolve():
    payload = observations()
    payload["sites"].append(copy.deepcopy(payload["sites"][0]))
    r = build_dossiers(cohort(), payload, as_of=TODAY)
    assert "CONFLICTING_SITE_OBSERVATIONS" in r["dossiers"][0]["research_tasks"]


def test_expired_observation_not_trusted():
    payload = observations(observed_at=(TODAY - timedelta(days=92)).isoformat())
    r = build_dossiers(cohort(), payload, as_of=TODAY)
    assert r["dossiers"][0]["qualification_stage"] == "SOURCE_REVIEW_HOLD"


def test_future_observation_not_trusted():
    payload = observations(observed_at=(TODAY + timedelta(days=1)).isoformat())
    r = build_dossiers(cohort(), payload, as_of=TODAY)
    assert "STALE_OR_FUTURE_OBSERVATION" in r["dossiers"][0]["research_tasks"]


def test_first_party_source_domain_required():
    payload = observations(source_url="https://other.com/roofing")
    r = build_dossiers(cohort(), payload, as_of=TODAY)
    assert "SOURCE_URL_IDENTITY_MISMATCH" in r["dossiers"][0]["research_tasks"]


def test_contact_email_must_match_public_site():
    payload = observations(public_business_contact={
        "type": "email", "value": "hello@different.org"})
    r = build_dossiers(cohort(), payload, as_of=TODAY)
    assert "FIRST_PARTY_EMAIL_DOMAIN_MISMATCH" in r["dossiers"][0]["research_tasks"]
    assert not r["dossiers"][0]["public_contact_source_observed"]


def test_service_area_missing_blocks():
    payload = observations(dfw_service_area_observed=False)
    r = build_dossiers(cohort(), payload, as_of=TODAY)
    assert "DFW_SERVICE_AREA_NOT_VERIFIED_ON_SITE" in r["dossiers"][0]["research_tasks"]


def test_claims_language_flags_ad_review_not_claim_authority():
    payload = observations(insurance_claims_wording_observed=True)
    r = build_dossiers(cohort(), payload, as_of=TODAY)
    d = r["dossiers"][0]
    assert "INSURANCE_ADVERTISING_LEGAL_COPY_REVIEW" in d["research_tasks"]
    assert not d["claim_services_authorized"]


def test_sensitive_policyholder_data_rejected():
    payload = observations()
    payload["sites"][0]["policy_number"] = "bad-data"
    with pytest.raises(ValueError):
        build_dossiers(cohort(), payload, as_of=TODAY)


@pytest.mark.parametrize("bad", ["http://example.com", "https://127.0.0.1/", "https://user@other.org"])
def test_untrusted_final_url_never_promotes(bad):
    r = build_dossiers(cohort(), observations(final_url=bad), as_of=TODAY)
    assert "FINAL_URL_NOT_VERIFIED" in r["dossiers"][0]["research_tasks"]


def test_order_and_replay_deterministic():
    x = build_dossiers(cohort(), observations(), as_of=TODAY)
    y = build_dossiers(cohort(), observations(), as_of=TODAY)
    assert x == y


def test_stale_public_contact_not_counted_as_verified_observation():
    payload = observations(observed_at="2025-01-01")
    d = build_dossiers(cohort(), payload, as_of=TODAY)["dossiers"][0]
    assert d["qualification_stage"] == "SOURCE_REVIEW_HOLD"
    assert d["public_contact_source_observed"] is False


def test_mismatched_company_name_cannot_bind_first_party_contact():
    payload = observations(self_described_name="Different Contractor")
    d = build_dossiers(cohort(), payload, as_of=TODAY)["dossiers"][0]
    assert "BUSINESS_NAME_NOT_MATCHED_ON_SITE" in d["research_tasks"]
    assert d["public_contact_source_observed"] is False
