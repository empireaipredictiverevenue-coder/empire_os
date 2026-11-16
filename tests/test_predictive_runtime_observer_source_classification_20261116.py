"""Classification correction: research is not a registered revenue forecast."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.run_predictive_revenue_runtime_observer import (
    CONTROL_NAMES, PREFLIGHT_REL, PREFLIGHT_SCHEMA, OUT_REL,
    evaluate_original_source, run,
)

NOW = datetime(2026, 11, 16, 10, 20, tzinfo=timezone.utc)


def source(**overrides):
    row = {
        "schema_version": PREFLIGHT_SCHEMA,
        "generated_at": (NOW - timedelta(minutes=2)).isoformat(),
        "mode": "OBSERVE",
        "registry_reader_authenticated_session": True,
        "original_restricted_registry_reader_reused": True,
        "registry_scoped_rows_observed": 0,
    }
    row.update(overrides)
    return row


def test_unauthenticated_and_stale_source_do_not_admit_forecasts():
    cases = [
        (None, "ORIGINAL_REGISTRY_PREFLIGHT_MISSING"),
        ({}, "ORIGINAL_REGISTRY_PREFLIGHT_MISSING"),
        (source(schema_version="not-original"), "ORIGINAL_REGISTRY_PREFLIGHT_CONTRACT_INVALID"),
        (source(generated_at=(NOW - timedelta(days=1)).isoformat()), "ORIGINAL_REGISTRY_PREFLIGHT_STALE"),
        (source(registry_reader_authenticated_session=False), "ORIGINAL_REGISTRY_READER_UNAUTHENTICATED"),
        (source(original_restricted_registry_reader_reused=False), "ORIGINAL_REGISTRY_READER_UNAUTHENTICATED"),
        (source(registry_scoped_rows_observed="7"), "ORIGINAL_REGISTRY_READER_UNAUTHENTICATED"),
        (source(registry_scoped_rows_observed=None), "ORIGINAL_REGISTRY_READER_UNAUTHENTICATED"),
        (source(generated_at=(NOW + timedelta(seconds=1)).isoformat()), "ORIGINAL_REGISTRY_PREFLIGHT_STALE"),
    ]
    for data, expected in cases:
        row = evaluate_original_source(data, now=NOW)
        assert row["status"] == expected
        assert row["candidate_count"] == 0
        assert row["passed_count"] == 0
        assert row["quarantined_count"] == 0
        assert not row["runtime_verified_controls"]
        assert row["runtime_unverified_controls"] == list(CONTROL_NAMES)
        assert row["original_registry_scoped_rows_reported"] is None
        assert row["governance"]["db_write"] is False
        assert row["research_runtime_json_scanned_as_forecast_candidates"] is False


def test_even_authenticated_aggregate_does_not_create_verified_forecast_records():
    result = evaluate_original_source(source(registry_scoped_rows_observed=14), now=NOW)
    assert result["status"] == "REGISTERED_ROWS_REQUIRE_CASE_LEVEL_FORECAST_VALIDATION"
    assert result["original_registry_scoped_rows_reported"] == 14
    assert result["registered_forecast_rows_independently_inspected"] is False
    assert result["candidate_count"] == result["quarantined_count"] == 0
    assert result["genuine_forecast_outcome_pairs_verified"] is False
    assert result["model_calibration_authorized"] is False


def test_valid_empty_registry_does_not_claim_real_forecasts():
    result = evaluate_original_source(source(), now=NOW)
    assert result["status"] == "AUTHENTICATED_REGISTRY_EMPTY_NO_FORECASTS"
    assert result["original_registry_scoped_rows_reported"] == 0
    assert result["candidate_count"] == 0
    assert result["runtime_verified_controls"] == []


def test_buyer_research_nesting_never_enters_prospective_forecasts(tmp_path):
    research = tmp_path / "runtime/buyer_network_intelligence/founder_shortlist_latest.json"
    research.parent.mkdir(parents=True)
    research.write_text(json.dumps({
        "offers": [
            {"buyer_id": f"buyer-{n}", "prediction_status": "research_only",
             "expected_revenue": 10_000, "evidence": ["claimed"]}
            for n in range(1247)
        ]
    }))
    source_path = tmp_path / PREFLIGHT_REL
    source_path.parent.mkdir(parents=True)
    source_path.write_text(json.dumps(source(registry_reader_authenticated_session=False)))
    report = run(root=tmp_path, now=NOW)
    assert report["candidate_count"] == 0
    assert report["quarantined_count"] == 0
    assert report["research_records_released_or_deleted"] is False
    assert research.exists()
    assert len(json.loads(research.read_text())["offers"]) == 1247
    assert json.loads((tmp_path / OUT_REL).read_text())["status"] == (
        "ORIGINAL_REGISTRY_READER_UNAUTHENTICATED"
    )


@pytest.mark.parametrize("untrusted", ["{bad", "[]" , '"hi"', "null"])
def test_malformed_source_fails_closed(tmp_path, untrusted):
    p = tmp_path / PREFLIGHT_REL
    p.parent.mkdir(parents=True)
    p.write_text(untrusted)
    assert run(root=tmp_path, now=NOW, write=False)["candidate_count"] == 0


def test_preflight_symlink_is_rejected(tmp_path):
    source_file = tmp_path / "other.json"
    source_file.write_text(json.dumps(source()))
    p = tmp_path / PREFLIGHT_REL
    p.parent.mkdir(parents=True)
    p.symlink_to(source_file)
    report = run(root=tmp_path, now=NOW, write=False)
    assert report["status"] == "ORIGINAL_REGISTRY_PREFLIGHT_MISSING"


def test_existing_promotion_refuses_unverified_observer(tmp_path):
    from scripts.run_predictive_revenue_runtime_observer import evaluate_original_source
    result = evaluate_original_source(source(), now=NOW)
    assert result["status"] != "VERIFIED_RUNTIME"
    # Existing promotion process intentionally requires VERIFIED_RUNTIME.
    promotion = (Path(__file__).resolve().parents[1] /
                 "scripts/promote_predictive_revenue_runtime_bindings.py").read_text()
    assert '!= "VERIFIED_RUNTIME"' in promotion
