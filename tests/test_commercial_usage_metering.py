import pytest

from empire_os.commercial_usage_metering import (
    CommercialTermsEvidence,
    UsageMode,
    build_billable_observation,
)


def verified_terms(**overrides):
    data = {
        "verified": True,
        "source": "manual_contract",
        "reference": "contract:buyer-1",
        "verified_at": "2026-09-20T12:00:00Z",
        "unit_price_cents": 15000,
        "currency": "USD",
        "settlement_asset": "USDT",
        "settlement_chain": "BSC",
    }
    data.update(overrides)
    return CommercialTermsEvidence(**data)


@pytest.mark.parametrize(
    ("mode", "unit"),
    [
        (UsageMode.EVALUATION_SCORE, "evaluation"),
        (UsageMode.EVALUATION_OUTCOME, "verified_outcome"),
        (UsageMode.HOURLY_INTELLIGENCE, "hour"),
        (UsageMode.PAY_PER_LEAD, "verified_lead"),
        (UsageMode.PAY_PER_APPOINTMENT, "verified_appointment"),
        (UsageMode.PAY_PER_CALL, "verified_call"),
        (UsageMode.HYBRID_UPFRONT, "upfront_entitlement"),
        (UsageMode.HYBRID_BACKEND, "verified_backend_outcome"),
    ],
)
def test_recovered_usage_modes_are_evidence_observations(mode, unit):
    result = build_billable_observation(
        mode=mode,
        quantity=1,
        observed_at="2026-09-20T12:30:00Z",
        evidence_refs=["evidence:real:1"],
        terms=verified_terms(),
    )

    assert result.unit == unit
    assert result.billing_ready is True
    assert result.calculated_amount_cents == 15000
    assert result.actual_revenue is False
    assert result.charge_executed is False
    assert result.payment_execution is False
    assert result.revenue_recognition is False
    assert result.execution_authority == "none"


def test_unknown_price_stays_unknown_and_not_billing_ready():
    result = build_billable_observation(
        mode=UsageMode.EVALUATION_SCORE,
        quantity=1,
        observed_at="2026-09-20T12:30:00Z",
        evidence_refs=["omega:score:1"],
        terms=verified_terms(unit_price_cents=None),
    )

    assert result.billing_ready is False
    assert result.calculated_amount_cents is None
    assert "unit_price_unknown" in result.blockers


def test_unverified_terms_cannot_become_billable():
    result = build_billable_observation(
        mode=UsageMode.PAY_PER_LEAD,
        quantity=1,
        observed_at="2026-09-20T12:30:00Z",
        evidence_refs=["lead:verified:1"],
        terms=verified_terms(
            verified=False,
            verified_at=None,
        ),
    )

    assert result.billing_ready is False
    assert result.calculated_amount_cents is None
    assert "commercial_terms_unverified" in result.blockers
    assert "commercial_terms_verified_at_missing" in result.blockers


def test_hourly_usage_calculates_from_explicit_terms_only():
    result = build_billable_observation(
        mode=UsageMode.HOURLY_INTELLIGENCE,
        quantity="1.5",
        observed_at="2026-09-20T12:30:00Z",
        evidence_refs=["worklog:verified:1"],
        terms=verified_terms(unit_price_cents=15000),
    )

    assert result.quantity == "1.5"
    assert result.calculated_amount_cents == 22500
    assert result.actual_revenue is False


def test_billable_observation_requires_provenance():
    with pytest.raises(ValueError, match="evidence refs"):
        build_billable_observation(
            mode=UsageMode.PAY_PER_CALL,
            quantity=1,
            observed_at="2026-09-20T12:30:00Z",
            evidence_refs=[],
            terms=verified_terms(),
        )


@pytest.mark.parametrize("quantity", [0, -1, "NaN", "Infinity"])
def test_quantity_must_be_positive_and_finite(quantity):
    with pytest.raises(ValueError, match="quantity"):
        build_billable_observation(
            mode=UsageMode.PAY_PER_APPOINTMENT,
            quantity=quantity,
            observed_at="2026-09-20T12:30:00Z",
            evidence_refs=["appointment:1"],
            terms=verified_terms(),
        )


def test_commercial_event_projection_is_append_only_observation_shape():
    result = build_billable_observation(
        mode=UsageMode.EVALUATION_OUTCOME,
        quantity=1,
        observed_at="2026-09-20T12:30:00Z",
        evidence_refs=["outcome:verified:1"],
        terms=verified_terms(unit_price_cents=550),
    )

    event = result.to_commercial_event(
        buyer_id="buyer-1",
        product_id="product-evaluation",
    )

    assert event["event_type"] == "billable_usage_observed"
    assert event["amount_cents"] == 550
    assert event["cost_cents"] is None
    assert event["margin_cents"] is None
    assert event["payload"]["actual_revenue"] is False
    assert event["payload"]["payment_execution"] is False
