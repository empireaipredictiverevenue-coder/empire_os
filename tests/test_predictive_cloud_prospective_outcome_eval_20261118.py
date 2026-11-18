"""Next official publisher release prospective evaluator: failclosed acceptance."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from empire_os import predictive_cloud_prospective_outcome_eval as x
from empire_os.predictive_cloud_prospective_freeze import EXPECTED_SOURCE_SHA

CURRENT_URL = "https://assets.publishing.service.gov.uk/media/6af42ff0a4004bdbe54e54a5/REPD_Publication_Q3_2026.csv"
NEW_URL = "https://assets.publishing.service.gov.uk/media/abcdef123456789/REPD_Publication_Q4_2026.csv"
NOW = datetime(2027,2,10,tzinfo=timezone.utc)

def source(**changes):
    record={
        "publisher":"DESNZ",
        "quality_pass":True,
        "customer_delivery_authorized":False,
        "source_status":"VERIFIED_UNCHANGED",
        "source_snapshot_sha256":EXPECTED_SOURCE_SHA,
        "source_url":CURRENT_URL,
        "last_success_at":"2026-11-18T11:01:14+00:00",
        "last_checked_at":"2026-11-18T11:01:14+00:00",
        "row_count":14967,
        "sample_not_full_population":False,
    }
    record.update(changes)
    return record

def frozen():
    return {
        "frozen_at":"2026-11-18T18:59:43+00:00",
        "future_publisher_outcomes_observed":False,
        "original_source_sha256":EXPECTED_SOURCE_SHA,
    }

def verified_new():
    return source(
        source_status="VERIFIED_CHANGED",
        source_snapshot_sha256="a"*64,
        source_url=NEW_URL,
        last_checked_at="2027-02-09T13:00:00+00:00",
        last_success_at="2027-02-09T13:00:00+00:00",
    )

def cohort(n=600):
    rows=[]
    later={}
    for i in range(n):
        key="hashed-public-repd-%04d"%i
        stage="Planning Application Submitted" if i%2 else "Operational"
        score=round(0.9-i/(n*1.5),12)
        rows.append({
            "public_project_key_sha256":key,
            "published_development_stage_at_asof":stage,
            "stage_change_research_score":float(score),
        })
        later[key]="Planning Permission Granted" if i%25==0 else stage
    return rows,later

def test_current_official_editions_remain_wait_without_future_scores():
    assert x._release_gate(source(),frozen(),NOW)=="AWAITING_NEW_OFFICIAL_REPD_RELEASE"
    assert x.check_due(Path("/mnt/not-the-real-empire"))["status"]=="NONCANONICAL_RESEARCH_EVALUATION_HELD"

def test_changed_q3_version_cannot_become_future_outcome():
    revised=source(source_snapshot_sha256="f"*64,
                   source_status="VERIFIED_CHANGED")
    with pytest.raises(ValueError,match="REVISED_Q3_PUBLISHER_SOURCE_NOT_A_FUTURE_EDITION"):
        x._release_gate(revised,frozen(),NOW)


def test_q3_encoding_fix_with_same_raw_bytes_remains_wait_not_future_label():
    corrected=source(
        source_snapshot_sha256="a"*64,
        source_status="VERIFIED_CHANGED",
        publisher_publication_metadata={
            "publisher_original_raw_sha256":
                "48e76c49f33a1090e78108d1ea9bfe689b35963ea3be1bb4f6516d038a5ff862",
            "publisher_original_source_url":CURRENT_URL,
            "raw_publisher_encoding":"cp1252",
        },
    )
    assert x._release_gate(corrected,frozen(),NOW)=="AWAITING_NEW_OFFICIAL_REPD_RELEASE"

def test_false_q4_url_with_original_bytes_is_held():
    wrong=source(source_url=NEW_URL)
    with pytest.raises(ValueError,match="SOURCE_BYTES_MATCH_FROZEN"):
        x._release_gate(wrong,frozen(),NOW)

@pytest.mark.parametrize("url",[
    "https://example.com/media/abc/REPD_Publication_Q4_2026.csv",
    "http://assets.publishing.service.gov.uk/media/abc/REPD_Publication_Q4_2026.csv",
    "https://assets.publishing.service.gov.uk/media/abc/REPD_Publication_Q3_2026.csv",
    "https://assets.publishing.service.gov.uk/media/abc/REPD_Publication_Q4_2026.csv?cache=1",
    "https://assets.publishing.service.gov.uk.evil.com/media/abc/REPD_Publication_Q4_2026.csv",
    "https://assets.publishing.service.gov.uk/media/abc/REPD_Publication_Q4_2026.xlsx",
])
def test_only_authentic_official_expected_csv_name_allowed(url):
    assert not x._publisher_url_verified(url)

def test_future_official_url_but_no_checked_provenance_is_held():
    for bad in [
        {"last_success_at":"2026-11-18T11:01:14+00:00"},
        {"last_success_at":"2026-11-19T11:01:14+00:00"},
        {"last_checked_at":"2027-02-13T11:01:14+00:00"},
        {"last_success_at":"2027-02-09T11:01:14"},
        {"sample_not_full_population":True},
        {"quality_pass":False},
        {"customer_delivery_authorized":True},
        {"row_count":0},
    ]:
        with pytest.raises(ValueError,match="CHRONOLOGY_OR_COVERAGE|PUBLICATION_TIMELINE|QUALITY_OR_AUTHORITY"):
            x._release_gate(source(**(verified_new()|bad)),frozen(),NOW)

def test_genuine_q4_verified_source_passes_final_gate_only():
    s=verified_new()
    assert x._release_gate(s,frozen(),NOW)=="OFFICIAL_NEW_Q4_EDITION_VERIFIED_BY_ORIGINAL_SOURCE"
    assert x._publisher_url_verified(s["source_url"])

def test_strict_fixed_top500_without_backfill_and_missing_unlabelled():
    rows,later=cohort()
    # Top-500 project is unlabelled; rank 501 cannot replace it.
    del later[rows[0]["public_project_key_sha256"]]
    later["new-only-project"]="Planning Permission Granted"
    r=x.compare_fixed_cohort(rows,later,expected_total=600)
    assert r["frozen_cohort_rows"]==600
    assert r["matched_publisher_project_rows"]==599
    assert r["missing_unlabelled_frozen_project_rows"]==1
    assert r["original_top_n_matched"]==499
    assert r["original_top_n_unknown_unlabelled"]==1
    assert r["new_only_publisher_rows_excluded"]==1
    assert r["no_renormalization_of_missing_top_500"]
    assert r["missing_next_edition_projects_not_counted_as_negatives"]
    assert r["production_prediction_validation_authorized"] is False
    assert r["published_stage_changes_are_not_customer_demand_or_sales"]
    assert 0<=r["roc_auc"]<=1 and 0<=r["average_precision_tie_grouped"]<=1
    assert sum(b["count"] for b in r["fixed_score_band_calibration"])==599

def test_too_many_missing_project_labels_holds_metrics():
    rows,later=cohort()
    for i in range(12):
        later.pop(rows[i]["public_project_key_sha256"])
    with pytest.raises(ValueError,match="COVERAGE_INSUFFICIENT"):
        x.compare_fixed_cohort(rows,later)

def test_missing_outcome_is_not_assumed_true_or_false():
    rows,later=cohort()
    later={k:v for k,v in later.items() if k in {
        r["public_project_key_sha256"] for r in rows[:400]
    }}
    with pytest.raises(ValueError,match="COVERAGE_INSUFFICIENT"):
        x.compare_fixed_cohort(rows,later)

def test_no_mixed_or_degenerate_label_metrics():
    rows,later=cohort()
    for r in rows:
        later[r["public_project_key_sha256"]]=r["published_development_stage_at_asof"]
    with pytest.raises(ValueError,match="NO_BALANCED"):
        x.compare_fixed_cohort(rows,later)

def test_future_brier_comparison_uses_preexisting_frozen_training_constant():
    rows,later=cohort()
    r=x.compare_fixed_cohort(rows,later,
        expected_total=600,training_only_constant_rate=0.035)
    assert r["frozen_training_only_constant_rate"]==0.035
    assert 0<r["frozen_training_only_constant_brier"]<1
    assert r["brier_skill_against_frozen_training_only_constant"] is not None
    assert r["retrospective_matched_prevalence_brier_reference"] is not None
    with pytest.raises(ValueError,match="FROZEN_TRAINING_ONLY_BASELINE_RATE_INVALID"):
        x.compare_fixed_cohort(rows,later,training_only_constant_rate=1.1)

def test_average_precision_tie_grouping():
    r=[(.4,True,"a"),(.4,False,"b")]
    assert x._average_precision_with_ties(r)==.5
    assert x._average_precision_with_ties([(.9,True,"a"),(.3,False,"b")])==1
    assert x._average_precision_with_ties([(.9,False,"a"),(.3,True,"b")])==.5
    assert x._average_precision_with_ties([(.4,False,"a")]) is None

def test_genuine_systemd_source_owner_attests_wait_no_fake_future_outcomes():
    import os
    import json
    from unittest.mock import patch
    from pathlib import Path
    from empire_os import data_brokerage_enterprise_feed as feed
    wrote=[]
    waiting={"status":"AWAITING_NEW_OFFICIAL_REPD_RELEASE",
             "evaluation_writes":0,"future_official_outcome_rows":0,
             "production_forecasts_produced":0}
    with patch.dict(os.environ,{"INVOCATION_ID":"c"*32}), patch.object(
            feed,"_atomic",
            side_effect=lambda p,raw:wrote.append(json.loads(raw))):
        x=feed.record_scheduled_owner_observation(
            Path("/srv/empire_os"),{}, {},now=NOW,
            future_outcome=waiting)
    assert x["timer_receipt_written"] and len(wrote)==1
    receipt=wrote[0]
    assert receipt["next_publisher_evaluation_status"]==waiting["status"]
    assert receipt["next_publisher_evaluation_writes"]==0
    assert receipt["next_publisher_future_outcome_rows"]==0
    assert receipt["next_publisher_customer_prediction_authorized"] is False
    assert receipt["customer_delivery_authorized"] is False
    with patch.dict(os.environ,{"INVOCATION_ID":"NOT_SYSTEMD"}), patch.object(
            feed,"_atomic",side_effect=AssertionError("FALSE_LIVE_EVIDENCE")):
        fake=feed.record_scheduled_owner_observation(
            Path("/srv/empire_os"),{}, {},now=NOW,
            future_outcome={"status":"SYNTHETIC_FAKE_SUCCESS"})
    assert fake["timer_receipt_written"] is False

def test_no_prospective_future_evaluation_from_noncanonical_root(tmp_path):
    assert x.check_due(tmp_path)["status"]=="NONCANONICAL_RESEARCH_EVALUATION_HELD"
