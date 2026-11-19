"""Point-in-time published-stage research pilot negative/failclosed tests."""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import csv
import io
import os
from pathlib import Path

import pytest

from empire_os import predictive_cloud_temporal_research_pilot as pilot

def synthetic_rows(n=4,stage="Planning Application Submitted"):
    return [
        {"Ref ID":str(i+1000),"Development Status":stage,
         "Technology Type":"Solar Photovoltaics",
         "Record Last Updated (dd/mm/yyyy)":"09/01/2026"}
        for i in range(n)
    ]

def test_reject_future_updated_publisher_rows(monkeypatch):
    monkeypatch.setattr(pilot,"MIN_ROWS",1)
    rows=synthetic_rows()
    rows[0]["Record Last Updated (dd/mm/yyyy)"]="04/01/2027"
    with pytest.raises(ValueError,match="FUTURE_UPDATED"):
        pilot._validate_status_rows(rows,published=date(2026,2,9),
               id_key="Ref ID",stage_key="Development Status",
               technology_key="Technology Type",
               update_key="Record Last Updated (dd/mm/yyyy)")

def test_reject_duplicate_ids_and_bad_dates(monkeypatch):
    monkeypatch.setattr(pilot,"MIN_ROWS",1)
    rows=synthetic_rows()
    rows[1]["Ref ID"]=rows[0]["Ref ID"]
    with pytest.raises(ValueError,match="DUPLICATED"):
        pilot._validate_status_rows(rows,published=date(2026,2,9),
                id_key="Ref ID",stage_key="Development Status",
                technology_key="Technology Type",
                update_key="Record Last Updated (dd/mm/yyyy)")

def test_valid_missing_metadata_date_not_falsely_held(monkeypatch):
    monkeypatch.setattr(pilot,"MIN_ROWS",1)
    rows=synthetic_rows()
    rows[1]["Record Last Updated (dd/mm/yyyy)"]="Not set"
    values,quality=pilot._validate_status_rows(
        rows,published=date(2026,2,9),
        id_key="Ref ID",stage_key="Development Status",
        technology_key="Technology Type",
        update_key="Record Last Updated (dd/mm/yyyy)")
    assert len(values)==4
    assert quality["unknown_or_invalid_last_update_dates"]==1
    assert quality["publisher_last_updated_is_not_transition_time"] is True

def test_versioned_windows_real_change_vs_disappeared_project():
    prev={"100":{"status":"Planning Application Submitted","technology":"Solar"},
          "200":{"status":"Planning Permission Granted","technology":"Solar"},
          "300":{"status":"Operational","technology":"Wind"},
          "400":{"status":"Planning Permission Granted","technology":"Wind"}}
    nxt={"100":{"status":"Planning Permission Granted","technology":"Solar"},
         "200":{"status":"Planning Permission Granted","technology":"Solar"},
         "300":{"status":"Operational","technology":"Wind"},
         "500":{"status":"Planning Application Submitted","technology":"Solar"}}
    w=pilot._window(prev,nxt,date(2026,8,3),date(2026,11,13))
    assert w["matched_projects"]==3
    assert w["published_stage_changes"]==1
    assert w["new_project_refs"]==1 and w["no_longer_in_publisher_edition"]==1
    assert w["persistence_rule_accuracy"]==pytest.approx(2/3,abs=1e-6)
    assert w["persistence_rule_changed_stage_recall"]==0
    assert w["persistence_rule_balanced_accuracy"]==0.5
    assert w["missing_next_release_records_are_unlabelled_not_negative_examples"]
    assert w["top_status_changes"][0]["from_published_stage"]=="Planning Application Submitted"
    assert w["top_status_changes"][0]["to_published_stage"]=="Planning Permission Granted"

def test_reject_no_valid_temporal_holdout():
    prev={"1":{"status":"A","technology":"B"}}
    with pytest.raises(ValueError,match="INVALID_RESEARCH_HOLDOUT_WINDOW"):
        pilot._window(prev,prev,date(2026,11,13),date(2026,8,3))
    with pytest.raises(ValueError,match="NO_LINKABLE_RELEASE_PROJECTS"):
        pilot._window(prev,{"2":{"status":"B","technology":"C"}},
                      date(2026,8,3),date(2026,11,13))

def test_original_archival_hash_mismatch_prevents_false_backtest(tmp_path,monkeypatch):
    monkeypatch.setattr(pilot,"MIN_ROWS",1)
    relative=pilot.RELATIVE/"source_archives"/"Q2.csv"
    path=tmp_path/relative
    path.parent.mkdir(parents=True)
    stream=io.StringIO(newline="")
    writer=csv.DictWriter(stream,fieldnames=list(synthetic_rows()[0]))
    writer.writeheader();writer.writerows(synthetic_rows())
    path.write_bytes(stream.getvalue().encode('cp1252'))
    correct=sha256(path.read_bytes()).hexdigest()
    config=("2026-08-03","Q2.csv",correct,4,"2026-10-08","REPD_Publication_Q2_2026.csv")
    rows,meta=pilot._archive(tmp_path,config)
    assert len(rows)==4
    assert meta["published_at"]=="2026-08-03"
    assert meta["historical_official_publisher_asset"]
    with pytest.raises(ValueError,match="SOURCE_OWNER_SHA256_MISMATCH"):
        pilot._archive(tmp_path,("2026-08-03","Q2.csv","f"*64,4,
                                 "2026-10-08","REPD_Publication_Q2_2026.csv"))
    with pytest.raises(ValueError,match="ARCHIVE_CAPTURE_BEFORE_REPORTED_PUBLICATION"):
        pilot._archive(tmp_path,("2026-08-03","Q2.csv",correct,4,
                                 "2026-01-01","REPD_Publication_Q2_2026.csv"))

def test_latest_fema_sample_cannot_be_admitted_as_backtest():
    rows=[]
    for idx in range(500):
        rows.append({"declaration_id":str(idx),
                     "incident_begin_date":"2026-01-01T00:00:00.000Z",
                     "declaration_date":"2026-01-12T00:00:00.000Z"})
    r=pilot._storm_descriptive(rows,date(2026,11,18))
    assert r["sample_rows"]==500
    assert r["unique_declaration_ids_observed"]==500
    assert r["declaration_lag_days_median_observed"]==11
    assert r["predictive_backtest_admitted"] is False
    assert r["future_insurance_claims_inferred"] is False
    assert r["county_event_count_unbiased"] is False

def test_source_snapshot_data_cannot_be_processed_with_fake_root(tmp_path):
    assert pilot.research_pilot(tmp_path)["status"]=="NONCANONICAL_RESEARCH_PILOT_HELD"
    assert pilot.refresh_research_pilot(tmp_path)["status"]=="NONCANONICAL_RESEARCH_PILOT_HELD"



def test_hashed_label_ledger_never_uses_future_feature_or_removed_id():
    prev = {
        "100": {"status":"Planning Application Submitted", "technology":"Solar Photovoltaics"},
        "200": {"status":"Under Construction", "technology":"Wind Onshore"},
        "300": {"status":"Operational", "technology":"Biomass"},
    }
    future = {
        "100": {"status":"Planning Permission Granted", "technology":"Solar Photovoltaics"},
        "200": {"status":"Operational", "technology":"Wind Onshore"},
        "500": {"status":"Planning Application Submitted", "technology":"Solar Photovoltaics"},
    }
    labels=pilot._label_rows(prev,future,date(2026,8,3),date(2026,11,13))
    assert len(labels)==2  # missing 300 is unlabelled, added 500 had no prior feature
    assert all(row["features_available_after_publisher_edition"] == "2026-08-03"
               and row["label_available_after_publisher_edition"] == "2026-11-13"
               and row["label_is_publisher_change_not_business_outcome"]
               and row["training_admission_allowed"] is False
               for row in labels)
    assert all(len(row["source_project_key_sha256"])==64 for row in labels)
    assert all("name" not in key and "address" not in key and "operator" not in key
               for row in labels for key in row)
    assert all(row["published_stage_changed"] for row in labels)
    assert all(row["source_project_key_sha256"] not in {"100","200"} for row in labels)


def test_systemd_ledger_receipt_only_under_verified_invocation():
    import json
    import os
    from pathlib import Path
    from unittest.mock import patch
    from empire_os import data_brokerage_enterprise_feed as feed
    writes=[]
    with patch.dict(os.environ,{"INVOCATION_ID":"b"*32}), patch.object(
            feed,"_atomic",side_effect=lambda p,raw:writes.append(json.loads(raw))):
        receipt=feed.record_scheduled_owner_observation(
            Path("/srv/empire_os"),
            {"status":"PROFESSIONAL_FEED_ALL_SOURCES_WITHIN_CADENCE"},
            {"status":"ALL_VERIFIED_VIEWS_CURRENT_OR_SOURCES_HELD"},
            now=datetime(2026,11,18,17,45,tzinfo=timezone.utc),
            temporal_research={"status":"VERIFIED_UNCHANGED_TEMPORAL_RESEARCH_PILOT",
                               "private_label_rows":28625},
        )
    assert receipt["timer_receipt_written"] is True and len(writes)==1
    assert writes[0]["temporal_publisher_label_rows"]==28625
    assert writes[0]["temporal_publisher_forecast_predictions_produced"]==0
    with patch.dict(os.environ,{"INVOCATION_ID":"MANUAL"}), patch.object(
            feed,"_atomic",side_effect=AssertionError("NEVER_WRITE_FALSE_RECEIPT")):
        result=feed.record_scheduled_owner_observation(
            Path("/srv/empire_os"),{}, {},now=datetime.now(timezone.utc),
            temporal_research={"status":"NOT_GENUINE"})
    assert result["timer_receipt_written"] is False


def test_one_window_different_duration_not_claimed_as_accuracy():
    s1={"1":{"status":"Planning Application Submitted","technology":"Solar"}}
    s2={"1":{"status":"Planning Permission Granted","technology":"Solar"}}
    a=pilot._window(s1,s2,date(2026,2,9),date(2026,8,3))
    b=pilot._window(s1,s2,date(2026,8,3),date(2026,11,13))
    assert a["days_between_publications"] != b["days_between_publications"]
    assert a["single_window_does_not_establish_future_accuracy"]
    assert b["single_window_does_not_establish_future_accuracy"]
