import pytest

from empire_os.predictive_revenue_products import (
    PREDICTIVE_REVENUE_PRODUCTS,
    predictive_revenue_product,
    predictive_revenue_product_catalog,
)
import empire_os.predictive_revenue_self_serve as intake


def test_predictive_revenue_ladder_is_founder_approved():
    result = predictive_revenue_product_catalog()
    prices = {
        row["product_code"]: row["deployment_price_cents"]
        for row in result["products"]
    }

    assert result["product_count"] == 5
    assert result["pricing_authority"] == "founder_approved_2026_09_24"
    assert prices["predictive_revenue_diagnostic"] == 2_500_000
    assert prices["predictive_revenue_command_center"] == 5_000_000
    assert prices["predictive_revenue_intelligence_os"] == 10_000_000
    assert prices["predictive_revenue_autonomous_os"] == 20_000_000
    assert prices["predictive_revenue_private_strategic"] == 25_000_000
    assert result["binding_terms_ready"] is False
    assert result["actual_revenue"] is False


def test_private_strategic_is_250k_floor():
    row = predictive_revenue_product("predictive_revenue_private_strategic")

    assert row.deployment_price_cents == 25_000_000
    assert row.price_type == "starting_floor"
    assert "private_deployment" in row.included_capabilities


def test_predictive_revenue_interest_records_buyer_stated_evidence():
    calls = []

    def request(method, path, payload=None, **kwargs):
        calls.append((method, path, payload))
        assert path.endswith("/ingest_prospect_atomic")
        assert payload["p_evidence"]["buyer_stated"] is True
        assert payload["p_evidence"]["actual_revenue"] is False
        assert payload["p_evidence"]["payment_action"] is False
        return {
            "decision": "created",
            "prospect": {"id": "prospect-1"},
        }

    result = intake.record_predictive_revenue_interest(
        product_code="predictive_revenue_command_center",
        business_name="Example Group",
        email="buyer@example.com",
        domain="example.com",
        industry="Roofing",
        geography="United Kingdom",
        annual_revenue_band="25m_100m",
        desired_outcome="Improve forecast accuracy and expansion decisions.",
        systems=["CRM", "Finance / Revenue Data"],
        idempotency_key="predictive-test-001",
        request=request,
    )

    assert result["decision"] == "deployment_interest_recorded"
    assert result["prospect_id"] == "prospect-1"
    assert result["binding_commercial_terms"] is False
    assert result["actual_revenue"] is False
    assert len(calls) == 1


def test_predictive_revenue_rejects_unknown_product():
    with pytest.raises(ValueError, match="unknown predictive revenue product"):
        predictive_revenue_product("not-real")
