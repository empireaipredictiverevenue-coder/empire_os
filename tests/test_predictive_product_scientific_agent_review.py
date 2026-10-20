"""Verify Scientific Research Agent governance over the existing product science."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from empire_os.predictive_product_scientific_agent_review import (
    ScientificProtocolHold,
    review_product_scientific_agent_protocol,
)
from tests.test_predictive_product_science_readiness import sources, NOW
from empire_os.predictive_product_science_readiness import science_source_status
from tests.test_predictive_product_scientific_holdout import packet, evaluate

def source():
    catalog, snapshot = sources()
    return science_source_status(catalog, snapshot, as_of=NOW)


def test_original_zero_snapshot_uses_existing_pinned_agent_and_protocol():
    r = review_product_scientific_agent_protocol(science_source=source())
    assert r["existing_scientific_research_agent_skill_custody_verified"] is True
    assert r["existing_scientific_skill_count"] == 6
    assert r["existing_experiment_registry_contract_reused"] is True
    assert r["status"] == "SCIENTIFIC_AGENT_PROTOCOL_READY_WAITING_FOR_REAL_PRODUCT_COHORT"
    exp = r["experiment"]
    assert exp["assignment_integrity_verified"] is False
    assert exp["exposure_integrity_verified"] is False
    assert exp["outcome_window_closed"] is False
    assert r["original_forecast_experiment_registered"] is False
    assert r["customer_model_validated"] is False
    assert r["existing_scientific_agent_inference_invoked"] is False
    assert r["scientific_model_promotion_approved"] is False
    assert r["execution_authority"] == "none"
    assert "tenant_id" not in json.dumps(r)


def test_scientific_diagnostic_on_synthetic_fixtures_not_a_customer_claim():
    rows = [packet(i) for i in range(44)]
    held = evaluate(rows)
    r = review_product_scientific_agent_protocol(science_source=source(), holdout=held)
    assert r["reported_holdout"]["score_review_status"] == "REPORTED_COHORT_DIAGNOSTIC_ONLY"
    assert r["reported_holdout"]["comparable_scored_cases"] >= 12
    assert r["reported_holdout"]["commercial_claim_supported"] is False
    assert r["customer_model_validated"] is False
    assert r["payment_authorized"] is False
    assert r["production_activated"] is False
    assert r["existing_scientific_agent_world_model_benchmark_not_substituted_for_revenue"] is True


def test_perfect_synthetic_skill_never_activates_learning():
    h = evaluate([packet(i, probability=1.0 if i % 3 == 0 else 0.0)
                  for i in range(44)])
    r = review_product_scientific_agent_protocol(science_source=source(), holdout=h)
    assert r["reported_holdout"]["brier_model"] == 0
    assert r["reported_holdout"]["model_improves_on_baseline_in_submitted_data"] is True
    assert r["economic_memory_update_eligible"] is False


@pytest.mark.parametrize("change", [
    lambda x: x.update(execution_authority="send"),
    lambda x: x.update(forecast_eligible_for_customer=True),
    lambda x: x.update(original_source_issuer_authenticated=True),
    lambda x: x.update(original_forecast_registry_readback_authenticated=True),
    lambda x: x.update(source_reported_probability_ready_product_count=1),
    lambda x: x.update(source_reported_terminal_outcome_count=2),
    lambda x: x.update(catalogue_product_count=True),
    lambda x: x.update(mode="LIVE"),
])
def test_forged_source_never_becomes_scientific_authority(change):
    s = source()
    change(s)
    with pytest.raises(ScientificProtocolHold):
        review_product_scientific_agent_protocol(science_source=s)


@pytest.mark.parametrize("change", [
    lambda x: x.update(execution_authority="funds"),
    lambda x: x.update(original_registry_readback_authenticated=True),
    lambda x: x.update(original_source_issuer_authenticated=True),
    lambda x: x.update(forecast_eligible_for_customer=True),
    lambda x: x.update(model_weight_mutation=True),
    lambda x: x.update(out_of_sample_evaluation_count=2),
    lambda x: x.update(model_brier=2.0),
    lambda x: x.update(calibration_gap=-0.1),
])
def test_forged_holdout_cannot_pass_governance(change):
    h = evaluate([packet(i) for i in range(44)])
    change(h)
    with pytest.raises(ScientificProtocolHold):
        review_product_scientific_agent_protocol(science_source=source(), holdout=h)


def test_bad_scientific_skill_custody_refuses(tmp_path):
    with pytest.raises(ScientificProtocolHold):
        review_product_scientific_agent_protocol(science_source=source(),root=tmp_path)


def test_deterministic_protocol_sha_and_no_private_identifier():
    r = review_product_scientific_agent_protocol(science_source=source())
    r2 = review_product_scientific_agent_protocol(science_source=deepcopy(source()))
    assert r == r2
    assert len(r["experiment_plan_sha256_integrity_only"]) == 64


def test_forged_skill_report_fail_closed_without_private_data(monkeypatch):
    import scripts.review_predictive_scientific_agent_20261020 as cli
    from empire_os.predictive_catalog_readiness_bridge import ProductContractHold
    from io import StringIO
    from contextlib import redirect_stdout
    monkeypatch.setattr(cli, "review_existing_product_science", lambda: (
        _ for _ in ()).throw(ProductContractHold("PRIVATE_CUSTOMER_ID_CANNOT_LEAK")))
    out = StringIO()
    with redirect_stdout(out):
        status = cli.main(["--read-only"])
    report = json.loads(out.getvalue())
    assert status == 2
    assert "PRIVATE_CUSTOMER_ID_CANNOT_LEAK" not in out.getvalue()
    assert report["status"] == "SCIENTIFIC_AGENT_PROTOCOL_SOURCE_OR_SKILL_CUSTODY_HELD"
    assert report["customer_model_validated"] is False


def test_forged_reported_skill_disagrees_with_brier():
    held = evaluate([packet(i) for i in range(44)])
    held["skill_vs_past_only_baseline"] = 99
    with pytest.raises(ScientificProtocolHold, match="reported skill"):
        review_product_scientific_agent_protocol(science_source=source(), holdout=held)
