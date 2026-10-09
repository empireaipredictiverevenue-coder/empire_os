"""Revenue Strike must link one approved catalog product without a cold sales pitch."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

import pytest

import scripts.refresh_contractor_revenue_review as integration

NOW = datetime(2026, 10, 10, 0, 15, tzinfo=timezone.utc)


def review():
    return {
        "schema": "empire.revenue_strike.contractor_founder_review.v1",
        "mode": "OBSERVE", "as_of": NOW.date().isoformat(),
        "outbound_authorized": False, "contract_sent": False,
        "summary": {"historical_contractor_companies": 1},
        "packets": [{
            "company_domain": "spcroofs.com",
            "outbound_authorized": False,
            "existing_outbound_rapport_policy": {
                "next_action": "RESEARCH",
                "commercial_pricing_allowed": False,
                "first_touch_cta_allowed": False,
                "execution_authority": "none",
            },
        }],
    }


def catalog():
    return {
        "schema_version": "empire.commercial-product-catalog.v1",
        "generated_at": NOW.isoformat(),
        "product_count": 1,
        "products": [{
            "product_code": "managed_service",
            "product_id": "a4b11ace-4199-4419-a43d-2bcbeda33364",
            "product_name": "Empire Opportunity Intelligence Pilot",
            "active": True, "catalog_state": "VERIFIED", "version_state": "VERIFIED",
            "binding_terms_ready": True, "readiness_blockers": [],
            "billing_model": "flat_pilot", "currency": "USD",
            "price_basis": {"state": "VERIFIED", "amount_cents": 150000, "currency": "USD", "unit": "flat", "source_type": "founder_approved", "approval_reference": "founder_approval:first_cash_economics:2026-09-21"},
            "actual_revenue": False,
        }],
    }


@pytest.fixture
def verified_pricing(monkeypatch):
    monkeypatch.setattr(integration, "verify_catalog_snapshot",
                        lambda payload, observed_at: {"pricing_matches_approved_policy": True, "drift_count": 0})


def test_catalog_verified_is_internal_and_does_not_open_outbound(verified_pricing):
    source = review()
    out = integration._catalog_internal_provenance(source, catalog(), now=NOW)
    p = out["existing_commercial_product"]
    assert p["status"] == "CATALOG_VERIFIED_INTERNAL_REFERENCE"
    assert p["product_code"] == "managed_service"
    assert p["founder_catalog_price_cents"] == 150000
    assert p["price_mention_allowed_in_first_touch"] is False
    assert p["offer_approved_for_these_prospects"] is False
    assert p["binding_quote_created"] is False
    assert p["outbound_authorized"] is False
    assert p["contract_authorized"] is False
    assert out["summary"]["existing_catalog_offer_verified_internal"] == 1
    assert source.get("existing_commercial_product") is None


def test_invalid_catalog_data_is_rejected_before_cold_pitch(verified_pricing):
    for key, value in [("schema_version", "untrusted"), ("product_count", 2)]:
        data=catalog();data[key]=value
        with pytest.raises(ValueError):
            integration._catalog_internal_provenance(review(), data, now=NOW)


@pytest.mark.parametrize("change", [
    {"active": False}, {"catalog_state": "UNKNOWN"}, {"version_state": "DRAFT"},
    {"binding_terms_ready": False}, {"readiness_blockers": ["cost_not_approved"]},
    {"billing_model": "monthly"}, {"currency": "EUR"},
    {"price_basis": {"state": "VERIFIED", "amount_cents": 250000, "currency": "USD", "unit": "flat"}},
    {"actual_revenue": True},
    {"price_basis": {"state": "VERIFIED", "amount_cents": 150000, "currency": "USD", "unit": "flat", "source_type": "model_generated", "approval_reference": "unapproved"}},
])
def test_unverified_or_drifted_terms_cannot_be_an_offer(verified_pricing, change):
    data=catalog();data["products"][0].update(change)
    out=integration._catalog_internal_provenance(review(),data,now=NOW)
    assert out["existing_commercial_product"]["status"] == "CATALOG_UNVERIFIED_OR_PRICE_DRIFT_HOLD"
    assert out["summary"]["existing_catalog_offer_verified_internal"] == 0
    assert out["outbound_authorized"] is False


def test_pricing_drift_from_existing_verifier_blocks_catalog_link(monkeypatch):
    monkeypatch.setattr(integration, "verify_catalog_snapshot",
                        lambda payload, observed_at: {"pricing_matches_approved_policy": False, "drift_count": 1})
    out=integration._catalog_internal_provenance(review(),catalog(),now=NOW)
    assert out["existing_commercial_product"]["status"]=="CATALOG_UNVERIFIED_OR_PRICE_DRIFT_HOLD"
    assert not out["existing_commercial_product"]["outbound_authorized"]


def test_stale_catalog_is_unusable_even_with_known_price(verified_pricing):
    data=catalog()
    data["generated_at"]=(NOW-timedelta(days=5)).isoformat()
    out=integration._catalog_internal_provenance(review(),data,now=NOW)
    assert out["existing_commercial_product"]["status"]=="CATALOG_UNVERIFIED_OR_PRICE_DRIFT_HOLD"


def test_missing_catalog_reports_absence_not_success(verified_pricing):
    out=integration._catalog_internal_provenance(review(),None,now=NOW)
    assert out["existing_commercial_product"]["status"]=="CATALOG_EVIDENCE_UNAVAILABLE"
    assert out["summary"]["existing_catalog_offer_verified_internal"]==0


def test_catalog_duplicate_product_is_refused(verified_pricing):
    data=catalog()
    data["products"].append(deepcopy(data["products"][0]))
    data["product_count"]=2
    with pytest.raises(ValueError,match="NOT_UNIQUE"):
        integration._catalog_internal_provenance(review(),data,now=NOW)


def test_existing_rapport_gate_wins_even_if_product_is_verified(verified_pricing):
    for mutation in [
        ("outbound_authorized", True),
        ("existing_outbound_rapport_policy", {"commercial_pricing_allowed": True}),
    ]:
        data=review(); data["packets"][0][mutation[0]]=mutation[1]
        with pytest.raises(ValueError,match="CANNOT_OVERRIDE_RAPPORT"):
            integration._catalog_internal_provenance(data,catalog(),now=NOW)


def test_live_catalog_research_adaptor_remains_research_only():
    root=Path(__file__).resolve().parents[1]
    if not (root/"runtime/commercial_catalog/latest.json").exists():
        pytest.skip("canonical production snapshot not present in isolated unit run")
    out=integration.run(as_of=NOW.date())
    assert out["summary"]["historical_contractor_companies"]==8
    assert out["summary"]["rapport_gate_research_count"]==8
    assert out["outbound_authorized"] is False
    assert not any(p["existing_outbound_rapport_policy"]["commercial_pricing_allowed"] for p in out["packets"])
