"""Global legacy feedback rows are not authenticated tenant outcomes."""
from datetime import datetime, timezone
import json
import pytest
from empire_os.predictive_intelligence import refresh_predictive_intelligence, CATALOG, OUTPUT
from empire_os.predictive_catalog_readiness_bridge import ProductContractHold
from empire_os.predictive_product_science_readiness import science_source_status
from empire_os.predictive_product_scientific_agent_review import _science_summary
from tests.test_predictive_intelligence import catalog
from tests.test_predictive_product_science_readiness import sources, NOW


def run(tmp_path, size, old=None):
    c = tmp_path / CATALOG
    c.parent.mkdir(parents=True, exist_ok=True)
    c.write_text(json.dumps(catalog()))
    if old is not None:
        f = tmp_path / OUTPUT
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(old))
    calls=[]
    def read(method, path, *, payload):
        calls.append(path)
        if path.endswith("get_commercial_outcome_feedback"):
            return [dict(product_id="prod-1", tenant_id="forged-tenant",
                         conversion_outcome="won", actual_revenue=True,
                         private_marker="private-marker-xyz") for _ in range(size)]
        raise AssertionError("unexpected read")
    result = refresh_predictive_intelligence(tmp_path,request=read,max_age_seconds=300)
    return result, calls, json.loads((tmp_path/OUTPUT).read_text())


def test_empty_global_reader_is_still_unverified(tmp_path):
    output,calls,persisted=run(tmp_path,0)
    assert output["source_scope_admission_status"]=="GLOBAL_SOURCE_EMPTY_BUT_ISSUER_UNVERIFIED"
    assert output["product_estimates"]=={}
    assert output["original_tenant_source_authenticated"] is False
    assert persisted==output and len(calls)==1


def test_fifty_plausible_global_wins_cannot_be_learned(tmp_path):
    output,calls,persisted=run(tmp_path,50)
    assert output["source_scope_admission_status"]=="GLOBAL_UNSCOPED_OUTCOMES_QUARANTINED"
    assert output["unscoped_source_rows_quarantined_count"]==50
    assert output["source_outcome_count"]==0
    assert output["product_estimates"]=={}
    assert output["tenant_id"] is None
    assert output["probability_ready_product_count"]==0
    assert "private-marker-xyz" not in json.dumps(persisted)
    assert len(calls)==1


def test_cached_global_wins_are_refetched_and_held(tmp_path):
    old=dict(schema_version="empire.predictive_intelligence.v1",mode="OBSERVE",
             generated_at=datetime.now(timezone.utc).isoformat(),tenant_id=None,
             source_outcome_count=50,matched_outcome_count=50,
             probability_ready_product_count=1,timing_ready_product_count=1,
             product_estimates={"managed_service":{"probability_available":True}},
             commercial_authority="none",execution_authority="none")
    output,calls,_=run(tmp_path,50,old)
    assert output["reused_existing_snapshot"] is False
    assert output["product_estimates"]=={} and len(calls)==1



def test_recent_legacy_empty_snapshot_must_be_replaced_with_issuer_hold(tmp_path):
    legacy = dict(
        schema_version="empire.predictive_intelligence.v1",
        mode="OBSERVE",
        generated_at=datetime.now(timezone.utc).isoformat(),
        tenant_id=None,
        source_outcome_count=0,
        matched_outcome_count=0,
        probability_ready_product_count=0,
        timing_ready_product_count=0,
        product_estimates={},
        commercial_authority="none",
        execution_authority="none",
    )
    output, calls, persisted = run(tmp_path, 0, old=legacy)
    assert output["reused_existing_snapshot"] is False
    assert output["source_scope_admission_status"] == (
        "GLOBAL_SOURCE_EMPTY_BUT_ISSUER_UNVERIFIED"
    )
    assert len(calls) == 1
    assert persisted["original_tenant_source_authenticated"] is False


def test_authenticated_proof_flag_or_quarantine_cache_never_bypasses_refresh(tmp_path):
    output, _, _ = run(tmp_path, 0)
    forged = {**output, "generated_at": datetime.now(timezone.utc).isoformat(),
              "original_tenant_source_authenticated": True}
    result, calls, _ = run(tmp_path, 0, old=forged)
    assert not result["reused_existing_snapshot"] and len(calls) == 1
    quarantined = {**output, "generated_at": datetime.now(timezone.utc).isoformat(),
                   "source_scope_admission_status": "GLOBAL_UNSCOPED_OUTCOMES_QUARANTINED",
                   "unscoped_source_rows_quarantined_count": 10}
    result, calls, _ = run(tmp_path, 0, old=quarantined)
    assert not result["reused_existing_snapshot"] and len(calls) == 1


def test_explicit_zero_issuer_hold_is_only_reusable_cache(tmp_path):
    output, _, _ = run(tmp_path, 0)
    cached, calls, stored = run(tmp_path, 50, old=output)
    assert cached["reused_existing_snapshot"] is True
    assert calls == []
    assert stored == output
    assert cached["source_scope_admission_status"] == (
        "GLOBAL_SOURCE_EMPTY_BUT_ISSUER_UNVERIFIED"
    )


def test_unconfigured_gateway_is_not_misreported_as_empty(tmp_path):
    from empire_os.predictive_intelligence import fetch_outcomes
    with pytest.raises(ValueError, match="source unavailable"):
        fetch_outcomes(lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="source unavailable"):
        fetch_outcomes(lambda *args, **kwargs: [None])


def test_science_reports_quarantine_not_evidence():
    cat,source=sources()
    source.update(source_scope_admission_status="GLOBAL_UNSCOPED_OUTCOMES_QUARANTINED",
                  unscoped_source_rows_quarantined_count=50,
                  original_tenant_source_authenticated=False,
                  original_outcome_issuer_authenticated=False,
                  original_forecast_registered_before_outcome=False)
    r=science_source_status(cat,source,as_of=NOW)
    assert r["status"]=="UNSCOPED_ORIGINAL_OUTCOMES_QUARANTINED"
    assert r["unscoped_source_rows_quarantined_count"]==50
    assert r["forecast_eligible_for_customer"] is False
    assert _science_summary(r)[1]==0
    from empire_os.predictive_product_scientific_agent_review import review_product_scientific_agent_protocol
    protocol = review_product_scientific_agent_protocol(science_source=r)
    assert protocol["status"]=="SCIENTIFIC_AGENT_UNSCOPED_SOURCE_QUARANTINED"
    assert protocol["source_rows_quarantined_from_legacy_reader"]==50
    assert protocol["automated_agent_execution_authorized"] is False
    assert protocol["original_forecast_experiment_registered"] is False


@pytest.mark.parametrize("patch",[
    {"source_scope_admission_status":"GLOBAL_UNSCOPED_OUTCOMES_QUARANTINED",
     "unscoped_source_rows_quarantined_count":0},
    {"source_scope_admission_status":"GLOBAL_SOURCE_EMPTY_BUT_ISSUER_UNVERIFIED",
     "unscoped_source_rows_quarantined_count":5},
    {"original_tenant_source_authenticated":True},
    {"original_forecast_registered_before_outcome":True},
])
def test_false_source_claims_hold(patch):
    cat,source=sources()
    source.update(patch)
    with pytest.raises(ProductContractHold):
        science_source_status(cat,source,as_of=NOW)
