"""Research-only walk-forward science evaluation: source label gate and leakage tests."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from hashlib import sha256

import pytest

from empire_os import predictive_cloud_temporal_research_pilot as pilot
from empire_os import predictive_cloud_temporal_science_eval as science


def frame(start: str, finish: str, n: int = 300, shock: int = 25):
    """Fixed public as-of stage & technology, independently labelled next stage."""
    out=[]
    for i in range(n):
        changed=i%12==0 if shock==25 else i%10==0
        out.append({
            "source_project_key_sha256":sha256(f"{start}/{i}".encode()).hexdigest(),
            "features_available_after_publisher_edition":start,
            "label_available_after_publisher_edition":finish,
            "development_stage_at_asof":
                "Planning Application Submitted" if i%3==0 else "Operational",
            "technology_at_asof":"Solar Photovoltaics" if i%2==0 else "Wind Onshore",
            "later_published_development_stage":
                "Planning Permission Granted" if changed else
                ("Planning Application Submitted" if i%3==0 else "Operational"),
            "published_stage_changed":bool(changed),
            "label_is_publisher_change_not_business_outcome":True,
            "training_admission_allowed":False,
        })
    return out


def three_frames():
    return [
        frame("2026-02-09","2026-05-06"),
        frame("2026-05-06","2026-08-03"),
        frame("2026-08-03","2026-11-13"),
    ]


def test_research_walkforward_valid_three_publisher_windows():
    e=science.research_walkforward(three_frames())
    assert e["status"]=="RETROSPECTIVE_RESEARCH_ONLY_CHRONOLOGICAL_HOLDOUT"
    assert e["first_exploratory_validation"]["training_rows"]==300
    assert e["latest_out_of_time_holdout"]["training_rows"]==600
    assert e["latest_out_of_time_holdout"]["test_rows"]==300
    assert e["first_exploratory_validation"]["test_asof_date"]=="2026-05-06"
    assert e["latest_out_of_time_holdout"]["test_asof_date"]=="2026-08-03"
    assert e["latest_out_of_time_holdout"]["test_outcome_release_date"]=="2026-11-13"
    assert e["production_model_weights_created"] is False
    assert e["production_training_samples_admitted"]==0
    assert e["model_deployment_authorized"] is False
    assert e["customer_revenue_outcomes_included"]==0


def test_future_outcome_excluded_in_training():
    train,test=three_frames()[:2]
    poisoned=deepcopy(train)
    poisoned[0]["label_available_after_publisher_edition"]="2026-11-13"
    with pytest.raises(ValueError,match="FUTURE_OUTCOME_LEAKAGE"):
        science._metrics(poisoned,test)
    assert science._metrics(train,test)["test_rows"]==300


def test_tenant_or_training_authority_label_rejected():
    train,test=three_frames()[:2]
    tampered=deepcopy(train)
    tampered[5]["training_admission_allowed"]=True
    with pytest.raises(ValueError,match="UNTRUSTED_RESEARCH_OUTCOME_LABEL_AUTHORITY"):
        science._metrics(tampered,test)
    tampered=deepcopy(test)
    tampered[10]["label_is_publisher_change_not_business_outcome"]=False
    with pytest.raises(ValueError,match="UNTRUSTED_RESEARCH_OUTCOME_LABEL_AUTHORITY"):
        science._metrics(train,tampered)


def test_holdout_postasof_labels_cannot_be_prematurely_observed():
    train,test=three_frames()[:2]
    poisoned=deepcopy(test)
    poisoned[2]["label_available_after_publisher_edition"]="2026-04-01"
    with pytest.raises(ValueError,match="HOLDOUT_TEMPORAL_ORDER_INVALID"):
        science._metrics(train,poisoned)


def test_do_not_combine_asof_dates_in_one_test():
    train,test=three_frames()[:2]
    mixed=deepcopy(test)
    mixed[6]["features_available_after_publisher_edition"]="2026-04-30"
    with pytest.raises(ValueError,match="MIXED_RESEARCH_TEST_ASOF"):
        science._metrics(train,mixed)


def test_auc_tied_scores_correct():
    # 1 pos, 1 neg same score must be 0.5, not 0 or 1.
    assert science._auc_tie_aware([
        (0.4,True,"a"),(0.4,False,"b")])==0.5
    assert science._auc_tie_aware([
        (0.3,False,"a"),(0.8,True,"b")])==1.0
    assert science._auc_tie_aware([
        (0.8,False,"a"),(0.3,True,"b")])==0.0
    assert science._auc_tie_aware([
        (0.3,False,"a"),(0.3,False,"b")]) is None


def test_brier_calibration_and_top_n_are_heldout_only():
    e=science.research_walkforward(three_frames())
    t=e["latest_out_of_time_holdout"]
    assert t["top_n_predefined"]==300
    assert 0<=t["experiment_precision_at_n"]<=1
    assert 0<=t["experimental_research_roc_auc"]<=1
    assert 0<=t["training_only_global_rate"]<=1
    assert len(t["calibration_deciles"])==10
    assert sum(b["count"] for b in t["calibration_deciles"])==300
    assert all(b["observed_stage_change_share"]<=1 for b in t["calibration_deciles"])
    assert t["no_frozen_prospective_predictions"]
    assert t["research_only_no_production_weight_registration"]


def test_predefined_historical_window_requirement_failclosed():
    f=three_frames()
    with pytest.raises(ValueError,match="THREE_REAL_QUARTERLY_WINDOWS_REQUIRED"):
        science.research_walkforward(f[:2])
    wrong=deepcopy(f)
    wrong[1][0]["features_available_after_publisher_edition"]="2026-05-05"
    with pytest.raises(ValueError,match="NONCONTIGUOUS_PUBLISHER_RELEASE_WINDOWS"):
        science.research_walkforward(wrong)


def test_canonical_owner_research_unavailable_in_test_container(tmp_path):
    assert pilot.research_pilot(tmp_path)["status"]=="NONCANONICAL_RESEARCH_PILOT_HELD"
    assert pilot.refresh_research_pilot(tmp_path)["status"]=="NONCANONICAL_RESEARCH_PILOT_HELD"
