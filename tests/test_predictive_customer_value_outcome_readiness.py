"""Live-catalog source readiness diagnostics: synthetic fixtures only."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json
import pytest

from empire_os.predictive_customer_value_outcome_readiness import (
    review_customer_value_outcome_readiness,
    review_customer_value_outcome_readiness_runtime,
)

NOW=datetime(2026,10,19,22,40,tzinfo=timezone.utc)


def sources():
    at=(NOW-timedelta(minutes=2)).isoformat()
    return {
        "intelligence":{
            "schema_version":"empire.predictive_intelligence.v1",
            "mode":"OBSERVE", "execution_authority":"none",
            "generated_at":at,
            "model_weight_mutation":False,
            "unverified_pipeline_state_used_as_outcome":False,
            "source_outcome_count":0,
            "probability_ready_product_count":0,
            "verified_catalog_product_count":26,
            "tenant_id":"hidden-tenant-identifier",
        },
        "capacity":{
            "schema_version":"empire.buyer_capacity_readiness.v1",
            "mode":"OBSERVE","execution_authority":"none",
            "observed_at":at,
            "buyers_seen":1057, "terms_verified":0,
            "capacity_verified":0, "fully_activated":0,
            "payment_action":False,"revenue_recognition":False,
            "private_name":"untrusted@example.org",
        },
    }


def review(s=None):
    return review_customer_value_outcome_readiness(s if s is not None else sources(),as_of=NOW)


def test_live_like_readiness_reports_missing_real_evidence_not_fake_sales():
    r=review()
    assert r["status"]=="CUSTOMER_VALUE_OUTCOME_SOURCE_READINESS_REVIEWED"
    assert r["predictive_source_outcome_count"]==0
    assert r["probability_ready_product_count"]==0
    assert r["canonical_catalog_products_not_proven_sales"]==26
    assert r["buyer_inventory_records_not_authenticated_purchasers"]==1057
    assert r["canonical_capacity_terms_verified_count"]==0
    assert r["canonical_capacity_verified_count"]==0
    assert r["original_prediction_registry_enabled_verified"] is False
    assert r["registered_prospective_value_pilot_count"] is None
    assert r["authenticated_product_app_service_purchases"] is None
    assert r["model_outcome_calibration_authorized"] is False
    assert r["customer_revenue_or_savings_verified_by_this_check"] is False
    assert r["source_outcome_count_is_exhaustive_sales_count"] is False
    assert len(r["owner_receipt_sources_to_integrate"])==4
    assert r["execution_authority"]=="none"
    assert "hidden-tenant" not in json.dumps(r)
    assert "untrusted@example.org" not in json.dumps(r)


def test_positive_counts_do_not_promote_untrusted_actuals_or_accuracy():
    s=sources()
    s["intelligence"]["source_outcome_count"]=7
    s["intelligence"]["probability_ready_product_count"]=2
    s["capacity"]["terms_verified"]=3
    s["capacity"]["capacity_verified"]=2
    r=review(s)
    assert r["status"]=="CUSTOMER_VALUE_OUTCOME_SOURCE_READINESS_REVIEWED"
    assert r["authenticated_product_app_service_purchases"] is None
    assert r["original_prediction_registry_enabled_verified"] is False
    assert r["model_outcome_calibration_authorized"] is False


@pytest.mark.parametrize("update", [
    lambda s:s["intelligence"].update(execution_authority="execute"),
    lambda s:s["intelligence"].update(source_outcome_count=True),
    lambda s:s["intelligence"].update(probability_ready_product_count=300),
    lambda s:s["intelligence"].update(verified_catalog_product_count=2,probability_ready_product_count=3),
    lambda s:s["intelligence"].update(model_weight_mutation=True),
    lambda s:s["intelligence"].update(unverified_pipeline_state_used_as_outcome=True),
    lambda s:s["capacity"].update(terms_verified=9999),
    lambda s:s["capacity"].update(payment_action=True),
    lambda s:s["capacity"].update(observed_at=(NOW+timedelta(minutes=10)).isoformat()),
])
def test_source_authority_or_counter_tamper_is_held(update):
    s=sources()
    update(s)
    r=review(s)
    assert r["status"]=="CANONICAL_AGGREGATE_SOURCE_HOLD"
    assert r["database_writes"] is False
    assert r["authenticated_product_app_service_purchases"] is None


def test_file_runtime_only_reads_allowlisted_aggregate_sources(tmp_path):
    s=sources()
    for name,path in [
        ("intelligence","runtime/predictive_intelligence/latest.json"),
        ("capacity","runtime/buyer_capacity_readiness/latest.json"),
    ]:
        p=tmp_path/path
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(s[name]))
    private=tmp_path/"runtime/predictive_intelligence/private_events.json"
    private.write_text('{"secret":"DONT_READ"}')
    r=review_customer_value_outcome_readiness_runtime(tmp_path,as_of=NOW)
    assert r["status"]=="CUSTOMER_VALUE_OUTCOME_SOURCE_READINESS_REVIEWED"
    assert "DONT_READ" not in json.dumps(r)
    assert not (tmp_path/"runtime/predictive_intelligence/output.json").exists()
    p=tmp_path/"runtime/buyer_capacity_readiness/latest.json"
    p.unlink()
    assert review_customer_value_outcome_readiness_runtime(tmp_path,as_of=NOW)["hold_code"]=="UNAVAILABLE_CAPACITY_SOURCE"
