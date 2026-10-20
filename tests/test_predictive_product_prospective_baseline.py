"""Synthetic fixtures prove product-cohort forecast proposal never gains authority."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.predictive_product_prospective_baseline import (
    prepare_product_prospective_baseline, ProspectiveProductHold,
)
from tests.test_predictive_product_scientific_holdout import packet, NOW, CATALOG, TENANT, PRODUCT


def history(n):
    return [packet(i)["feedback"] for i in range(n)]


def prepare(rows=None, *, catalog=CATALOG, tenant=TENANT,
            as_of=NOW, days=30):
    return prepare_product_prospective_baseline(
        tenant_id=tenant, product_code=PRODUCT,
        opportunity_key="fixture-new-future-opportunity",
        historical_outcomes=history(44) if rows is None else rows,
        catalog=catalog, as_of=as_of, horizon_days=days
    )


def test_validated_fake_fixture_yields_bounded_noncommercial_candidate():
    r = prepare()
    assert r["status"] == "COHORT_PROSPECTIVE_CANDIDATE_UNREGISTERED"
    assert r["terminal_sample_count"] == 44
    assert 0 < r["product_cohort_probability"] < 1
    assert r["cohort_wilson_interval_95"]["low"] < r["product_cohort_probability"] < r["cohort_wilson_interval_95"]["high"]
    assert r["original_forecast_registered"] is False
    assert r["source_issuer_authenticated"] is False
    assert r["customer_probability_claim"] is False
    assert r["prediction_confidence_interval_for_individual_customer"] is None
    assert r["learning_eligible"] is False
    assert r["commercial_value_claim"] is False
    assert r["database_writes"] is False
    assert r["execution_authority"] == "none"
    assert TENANT not in json.dumps(r)
    assert "fixture-order" not in json.dumps(r)


def test_no_outcomes_unknown_not_zero():
    out = prepare([])
    assert out["status"] == "INSUFFICIENT_ORIGINAL_TERMINAL_OUTCOMES"
    assert out["product_cohort_probability"] is None


def test_small_cohort_remains_held():
    out = prepare(history(19))
    assert out["status"] == "INSUFFICIENT_ORIGINAL_TERMINAL_OUTCOMES"
    assert out["terminal_sample_count"] == 19
    assert out["original_forecast_registered"] is False


def test_deterministic_reordering_same_forecast_candidate():
    a, b = prepare(history(44)), prepare(list(reversed(history(44))))
    assert a["product_cohort_probability"] == b["product_cohort_probability"]
    assert a["original_forecast_candidate_digest_untrusted"] == b["original_forecast_candidate_digest_untrusted"]


@pytest.mark.parametrize("mutator", [
    lambda r: r[0].update(tenant_id="wrong"),
    lambda r: r[0].update(product_id="wrong"),
    lambda r: r[0].update(outcome_ref=r[1]["outcome_ref"]),
    lambda r: r[0].update(fulfilment_order_id=r[1]["fulfilment_order_id"]),
    lambda r: r[0].update(available_at="2026-10-21T00:00:00Z"),
    lambda r: r[0].update(available_at="not a time"),
    lambda r: r[0].update(synthetic=True),
    lambda r: r[0]["cortex_packet"]["label"].update(forecast_derived=True),
    lambda r: r[0].update(actual_revenue_cents=1234567),
])
def test_reject_untrusted_forecast_training_evidence(mutator):
    rows = history(44)
    mutator(rows)
    with pytest.raises(ProspectiveProductHold):
        prepare(rows)


def test_wrong_tenant_version_and_future_horizon_refuse():
    rows = history(44)
    with pytest.raises(ProspectiveProductHold):
        prepare(rows, tenant="other-tenant")
    cat = deepcopy(CATALOG)
    cat["products"][0]["catalog_state"] = "UNKNOWN"
    with pytest.raises(ProspectiveProductHold):
        prepare(rows, catalog=cat)
    with pytest.raises(ProspectiveProductHold):
        prepare(rows, days=0)
    with pytest.raises(ProspectiveProductHold):
        prepare(rows, days=True)
    with pytest.raises(ProspectiveProductHold):
        prepare(rows, days=91)
    with pytest.raises(ProspectiveProductHold):
        prepare(rows, as_of=datetime(2026, 10, 20))
