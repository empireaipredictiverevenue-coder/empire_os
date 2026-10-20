"""Actual source snapshots remain non-authoritative without original receipts."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.predictive_catalog_readiness_bridge import ProductContractHold
from empire_os.predictive_product_science_readiness import science_source_status
from tests.test_predictive_catalog_readiness_bridge import catalog
from empire_os.predictive_catalog_readiness_bridge import _review_catalogue
import scripts.review_predictive_product_science_20261020 as cli

NOW = datetime(2026, 10, 20, 18, 15, tzinfo=timezone.utc)


def sources():
    catalog_report = _review_catalogue(catalog(), as_of=NOW)
    catalog_report["source_root_custody_verified"] = True
    science = {
        "schema_version": "empire.predictive_intelligence.v1",
        "mode": "OBSERVE", "generated_at": NOW.isoformat(),
        "probability_source": "verified_terminal_commercial_outcomes_only",
        "prediction_only": True, "model_weight_mutation": False,
        "commercial_authority": "none", "execution_authority": "none",
        "search_scores_used": False, "llm_probability_used": False,
        "unverified_pipeline_state_used_as_outcome": False,
        "source_outcome_count": 0, "matched_outcome_count": 0,
        "unmatched_outcome_count": 0,
        "probability_ready_product_count": 0,
        "timing_ready_product_count": 0,
        "minimum_terminal_samples": 20, "minimum_timing_samples": 8,
        "product_estimates": {}, "tenant_id": None,
    }
    return catalog_report, science


def test_no_terminal_outcome_no_product_probability_and_all_skus():
    cat, source = sources()
    original = deepcopy(source)
    r = science_source_status(cat, source, as_of=NOW)
    assert source == original
    assert r["status"] == "NO_PRODUCT_TERMINAL_OUTCOMES_OBSERVED"
    assert r["catalogue_product_count"] == 6
    assert len(r["product_science_workbench"]) == 6
    assert r["source_reported_product_cohorts"] == 0
    assert all(p["prediction"] is None and p["confidence_interval"] is None
               for p in r["product_science_workbench"])
    assert r["forecast_eligible_for_customer"] is False
    assert r["economic_memory_update_eligible"] is False
    assert r["execution_authority"] == "none"


def test_tenant_claimed_cohort_still_no_automatic_forecast_permission():
    cat, source = sources()
    source.update(
        tenant_id="fixture-tenant", source_outcome_count=21,
        matched_outcome_count=21,
        product_estimates={"predictive_revenue_diagnostic": {
            "probability_available": True, "time_to_revenue_available": False,
            "probability_success": 0.8,
        }},
        probability_ready_product_count=1,
    )
    r = science_source_status(cat, source, as_of=NOW)
    assert r["status"] == "PRODUCT_COHORT_PRESENT_OWNER_AUTHENTICATION_STILL_REQUIRED"
    assert r["source_reported_probability_ready_product_count"] == 1
    assert r["tenant_bound_original_source_claim_present"] is True
    assert r["forecast_eligible_for_customer"] is False
    assert r["original_source_issuer_authenticated"] is False
    assert "fixture-tenant" not in json.dumps(r)


@pytest.mark.parametrize("mutator", [
    lambda a, b: b.update(schema_version="incorrect"),
    lambda a, b: b.update(tenant_id=""),
    lambda a, b: b.update(source_outcome_count=True),
    lambda a, b: b.update(source_outcome_count=4),
    lambda a, b: b.update(probability_ready_product_count=1),
    lambda a, b: b.update(tenant_id=None, product_estimates={
        "predictive_revenue_diagnostic": {"probability_available": False}}),
    lambda a, b: b.update(product_estimates={
        "not_a_real_product": {"probability_available": False}}),
    lambda a, b: b.update(generated_at="2026-10-10T12:00:00Z"),
    lambda a, b: b.update(generated_at="2026-10-21T12:00:00Z"),
    lambda a, b: b.update(model_weight_mutation=True),
    lambda a, b: b.update(llm_probability_used=True),
    lambda a, b: b.update(unverified_pipeline_state_used_as_outcome=True),
    lambda a, b: b.update(minimum_terminal_samples=0),
    lambda a, b: b.update(commercial_authority="customer"),
    lambda a, b: a.update(source_original_db_receipt_authenticated=True),
    lambda a, b: a.update(source_root_custody_verified=False),
])
def test_spoofed_or_stale_sources_fail_closed(mutator):
    cat, source = sources()
    mutator(cat, source)
    with pytest.raises(ProductContractHold):
        science_source_status(cat, source, as_of=NOW)


def test_cli_fail_closed_redacts_exception(monkeypatch, capsys):
    monkeypatch.setattr(cli, "review_existing_product_science",
                        lambda: (_ for _ in ()).throw(ProductContractHold("private id")))
    assert cli.main(["--read-only"]) == 2
    out = capsys.readouterr().out
    assert "private id" not in out
    assert json.loads(out)["forecast_eligible_for_customer"] is False


def test_cli_all_products_explicit_only(monkeypatch, capsys):
    cat, source = sources()
    result = science_source_status(cat, source, as_of=NOW)
    monkeypatch.setattr(cli, "review_existing_product_science", lambda: result)
    assert cli.main(["--read-only"]) == 0
    assert "product_science_workbench" not in json.loads(capsys.readouterr().out)
    assert cli.main(["--read-only", "--all-products"]) == 0
    assert len(json.loads(capsys.readouterr().out)["product_science_workbench"]) == 6
