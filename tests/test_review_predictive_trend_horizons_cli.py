"""Private trend runner: safe cloud status, bounded original market series."""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import pytest

import scripts.review_predictive_trend_horizons_20261022 as cli

NOW=datetime(2026,9,10,tzinfo=timezone.utc)
START=datetime(2026,5,1,tzinfo=timezone.utc)
CONTRACT={
    "series_id":"UK-GEO-TEST", "source_kind":"search_interest_index",
    "unit":"index_0_100", "geography":"UK", "vertical":"dental",
    "source_name":"single_canonical_source",
}


def source():
    rows=[]
    for i in range(13):
        stamp=START+timedelta(days=7*i)
        rows.append({
            **CONTRACT,
            "observed_at":stamp.isoformat(),
            "first_available_at":(stamp+timedelta(hours=1)).isoformat(),
            "ingested_at":(stamp+timedelta(hours=2)).isoformat(),
            "value":10+i*2, "revision":1, "evidence_sha256":"b"*64,
        })
    return {
        "schema_version":"empire.predictive_intelligence.trend_series_intake.v1",
        "as_of":(START+timedelta(days=91)).isoformat(),
        "series_contract":CONTRACT,"observations":rows,
    }


def test_cloud_runtime_reports_original_prediction_hold(tmp_path):
    p=tmp_path/"future_trend_latest.json"
    p.write_text(json.dumps({
        "schema_version":"empire.future_trend_intelligence.runtime.v1",
        "mode":"OBSERVE", "algorithm_available":True,
        "analysis_executed":False,"prediction_ready":False,
        "status":"AVAILABLE","actual_revenue":False,
        "source_admission_state":"UNVERIFIED_LOCAL_SNAPSHOT_ONLY",
        "execution_authority":"none",
        "blockers":["verified_terminal_outcomes_required"],
    }))
    reviewed=cli.review_existing_cloud_runtime(p)
    assert reviewed["status"]=="EXISTING_CLOUD_TREND_OBSERVER_READ_ONLY"
    assert reviewed["algorithm_available"] is True
    assert reviewed["historical_trend_analysis_executed"] is False
    assert reviewed["research_trends_consumer_activation"] is False
    assert reviewed["trend_horizons_days"]==[7,30,90]
    assert reviewed["source_blocker_codes"]==["verified_terminal_outcomes_required"]
    assert reviewed["database_writes"] is False


def test_forged_cloud_status_refuses_forecast_ready(tmp_path):
    p=tmp_path/"trend.json"
    p.write_text(json.dumps({
        "schema_version":"empire.future_trend_intelligence.runtime.v1",
        "mode":"WRITE", "algorithm_available":True,
        "analysis_executed":True,"prediction_ready":True,
        "actual_revenue":True,"execution_authority":"money",
    }))
    reviewed=cli.review_existing_cloud_runtime(p)
    assert reviewed["status"]=="EXISTING_CLOUD_TREND_RUNTIME_SECURITY_HOLD"
    assert reviewed["prediction_ready"] is False


def test_original_source_file_is_never_declared_authority(tmp_path,capsys):
    input_file=tmp_path/"series.json"
    input_file.write_text(json.dumps(source()))
    assert cli.main(["--read-only","--series-file",str(input_file)],now=NOW)==0
    r=json.loads(capsys.readouterr().out)
    assert r["status"]=="OBSERVED_TREND_RESEARCH_ONLY"
    assert r["source_kind"]=="search_interest_index"
    assert r["research_input_file_is_a_proven_data_source"] is False
    assert r["local_source_review_mode"]=="OWNER_SUPPLIED_RESEARCH_ONLY"
    assert r["future_scenarios"][0]["directional_scenario_value"] is not None
    assert r["actual_revenue"] is False
    assert "UK-GEO-TEST" not in json.dumps(r)


@pytest.mark.parametrize("attack",["symlink","oversize","unknown_shape","future"])
def test_bad_input_held_redacted(tmp_path,attack,capsys):
    p=tmp_path/"series.json"
    r=source()
    if attack=="symlink":
        q=tmp_path/"original.json"
        q.write_text(json.dumps(r))
        p.symlink_to(q)
    elif attack=="oversize":
        p.write_text("{"+"x"*161_000+"}")
    elif attack=="unknown_shape":
        r["permission_granted"]=True
        p.write_text(json.dumps(r))
    else:
        r["as_of"]=(START+timedelta(days=400)).isoformat()
        p.write_text(json.dumps(r))
    assert cli.main(["--read-only","--series-file",str(p)],now=NOW)==2
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="TREND_SOURCE_RESEARCH_HELD"
    assert result["database_writes"] is False
    assert result["commercial_forecast_authorized"] is False


def test_template_has_zero_observations(capsys):
    assert cli.main(["--read-only","--template"],now=NOW)==0
    r=json.loads(capsys.readouterr().out)
    assert r["observations"]==[]
    assert r["not_a_customer_forecast"] is True


def test_pinned_release_launcher_only_observe():
    src=(Path(__file__).resolve().parents[1]/
         "scripts/prepare_predictive_readonly_release_20261020.sh").read_text()
    for key in (
        "empire_os/predictive_trend_horizon_review.py",
        "scripts/review_predictive_trend_horizons_20261022.py",
        "trends|trends-template|trends-series",
        '"$command" == "trends-series"',
        '"$command" == "trends-template"',
        '"$command" == "trends"',
    ):
        assert key in src
