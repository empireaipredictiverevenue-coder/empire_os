"""Real source-quality baseline custody, tamper and chronology regression."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.flagship_source_quality_history import (
    CATEGORIES, SourceQualityCustodyHold, append_quality_observation,
    from_canonical_stream_review, plan_quality_observation,
    read_quality_history, review_quality_history, verify_history,
)
from empire_os.revenue_stream_mining import build_revenue_stream_mining
from test_revenue_stream_mining import fixture_sources

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


def fresh_observation(tmp_path, at=NOW):
    fixture_sources(tmp_path)
    review = build_revenue_stream_mining(tmp_path, as_of=at)
    return from_canonical_stream_review(review, as_of=at)


def test_initial_real_canonical_observation_no_drift_no_buyer_claim(tmp_path):
    observation = fresh_observation(tmp_path)
    assert observation["source_count"] == 4
    assert sum(observation["source_quality_categories"].values()) == 4
    assert set(observation["source_evidence_fingerprints"]) == {
        "acquisition", "opportunity_routes", "quant", "competitor",
    }
    assert observation["independent_outcomes_sampled"] == 0
    assert observation["source_rows_or_contacts_exported"] is False
    assert "@" not in json.dumps(observation)
    path = tmp_path/"journal"/"quality.jsonl"
    preview = append_quality_observation(path, observation)
    assert preview["status"] == "APPEND_READY"
    assert not path.exists()
    result = append_quality_observation(path, observation, apply=True)
    assert result["status"] == "APPENDED_PRIVATE_SOURCE_QUALITY_OBSERVATION"
    assert result["production_database_writes"] is False
    assert result["external_data_exported"] is False
    assert path.stat().st_mode & 0o777 == 0o600
    assert verify_history(read_quality_history(path))["observations"] == 1
    status = review_quality_history(path, as_of=NOW)
    assert status["status"] == "HISTORICAL_BASELINE_OBSERVED_NOT_CALIBRATED"
    assert status["comparison_status"] == "NOT_POSSIBLE_WITH_ONE_SOURCE_SNAPSHOT"
    assert status["latest_quality_category_counts"] == observation["source_quality_categories"]
    assert status["next_internal_quality_action"] in {
        "INVESTIGATE_HELD_SOURCE_EVIDENCE", "CHECK_STALE_SOURCE_REFRESH",
        "RESTORE_MISSING_SOURCE_ADAPTER", "REVIEW_UNAVAILABLE_SOURCE_GATEWAY",
        "COLLECT_INDEPENDENT_SECOND_OBSERVATION",
    }
    assert status["statistical_significance_established"] is False
    assert status["buyer_or_revenue_verified"] is False


def test_repeat_same_timestamp_idempotent_and_conflict_held(tmp_path):
    first = fresh_observation(tmp_path)
    path = tmp_path/"journal"/"quality.jsonl"
    append_quality_observation(path, first, apply=True)
    before = path.read_bytes()
    output = append_quality_observation(path, first, apply=True)
    assert output["status"] == "EXACT_OBSERVATION_REPLAY"
    assert output["written"] is False
    assert path.read_bytes() == before
    changed = deepcopy(first)
    changed["source_evidence_fingerprints"]["acquisition"] = "a"*64
    with pytest.raises(SourceQualityCustodyHold, match="conflicting observation"):
        append_quality_observation(path, changed, apply=True)
    assert path.read_bytes() == before


def test_second_observation_below_24h_not_called_drift(tmp_path):
    path = tmp_path/"journal"/"quality.jsonl"
    first = fresh_observation(tmp_path)
    append_quality_observation(path, first, apply=True)
    second = deepcopy(first)
    second["observed_at"] = (NOW+timedelta(hours=5)).isoformat()
    append_quality_observation(path, second, apply=True)
    status = review_quality_history(path, as_of=NOW+timedelta(hours=5))
    assert status["observation_count"] == 2
    assert status["comparison_status"] == "NEED_AT_LEAST_24H_SEPARATION"
    assert status["absolute_proportion_changes"] is None


def test_second_observation_after_24h_only_descriptive_quality_counts(tmp_path):
    path = tmp_path/"journal"/"quality.jsonl"
    first = fresh_observation(tmp_path)
    append_quality_observation(path, first, apply=True)
    second = deepcopy(first)
    second["observed_at"] = (NOW+timedelta(days=1)).isoformat()
    categories = second["source_quality_categories"]
    if categories["OBSERVED"] > 0:
        categories["OBSERVED"] -= 1
        categories["HELD"] += 1
    else:
        categories["MISSING"] -= 1
        categories["HELD"] += 1
    append_quality_observation(path, second, apply=True)
    result = review_quality_history(path, as_of=NOW+timedelta(days=1))
    assert result["status"] == "DESCRIPTIVE_SOURCE_QUALITY_CHANGE_REVIEW"
    assert result["comparison_status"] == "DESCRIPTIVE_COUNTS_ONLY_FOUR_CORRELATED_ADAPTERS"
    assert result["statistical_significance_established"] is False
    assert result["evidently_drift_test_executed"] is False
    assert result["quality_change_does_not_establish_forecast_accuracy"] is True
    assert max(result["absolute_proportion_changes"].values()) == 0.25


def test_tampered_journal_never_silently_recovers(tmp_path):
    path = tmp_path/"journal"/"quality.jsonl"
    first = fresh_observation(tmp_path)
    append_quality_observation(path, first, apply=True)
    rows = path.read_bytes()
    assert b"OBSERVED" in rows
    path.write_bytes(rows.replace(b"OBSERVED", b"UNTRUSTD", 1))
    held = review_quality_history(path, as_of=NOW)
    assert held["status"] == "LOCAL_SOURCE_QUALITY_CUSTODY_HELD"
    with pytest.raises(SourceQualityCustodyHold):
        append_quality_observation(path, fresh_observation(tmp_path), apply=True)


def test_crash_truncated_line_cannot_claim_intact_history(tmp_path):
    path = tmp_path/"journal"/"quality.jsonl"
    first = fresh_observation(tmp_path)
    append_quality_observation(path, first, apply=True)
    path.write_bytes(path.read_bytes().removesuffix(b"\n"))
    assert review_quality_history(path, as_of=NOW)["status"] == "LOCAL_SOURCE_QUALITY_CUSTODY_HELD"


def test_old_backdated_observation_refused(tmp_path):
    path = tmp_path/"journal"/"quality.jsonl"
    first = fresh_observation(tmp_path)
    append_quality_observation(path, first, apply=True)
    second = deepcopy(first)
    second["observed_at"] = (NOW - timedelta(minutes=1)).isoformat()
    with pytest.raises(SourceQualityCustodyHold, match="backdated"):
        append_quality_observation(path, second, apply=True)


def test_future_source_history_refuses_comparison(tmp_path):
    path = tmp_path/"journal"/"quality.jsonl"
    first = fresh_observation(tmp_path)
    append_quality_observation(path, first, apply=True)
    result = review_quality_history(path, as_of=NOW-timedelta(seconds=1))
    assert result["status"] == "LOCAL_SOURCE_QUALITY_CUSTODY_HELD"
    assert result["comparison_status"] == "FUTURE_SOURCE_QUALITY_OBSERVATION"


def test_untrusted_lane_cannot_forge_quality_baseline(tmp_path):
    fixture_sources(tmp_path)
    report = build_revenue_stream_mining(tmp_path, as_of=NOW)
    forged = deepcopy(report)
    forged["department_lanes"][0]["evidence_fingerprint"] = "FAKE"
    with pytest.raises(SourceQualityCustodyHold):
        from_canonical_stream_review(forged, as_of=NOW)
    forged = deepcopy(report)
    forged["sources"]["competitor"]["status"] = "FRESH"
    with pytest.raises(SourceQualityCustodyHold):
        from_canonical_stream_review(forged, as_of=NOW)


def test_read_source_baseline_without_history_never_invents_a_reference(tmp_path):
    state = review_quality_history(tmp_path/"none.jsonl", as_of=NOW)
    assert state["status"] == "NEED_FIRST_CANONICAL_OBSERVATION"
    assert state["observation_count"] == 0
    assert state["absolute_proportion_changes"] is None
    assert state["buyer_or_revenue_verified"] is False


def test_symlink_journal_is_rejected(tmp_path):
    original = tmp_path/"real"
    original.write_text("private")
    symlink = tmp_path/"quality.jsonl"
    symlink.symlink_to(original)
    with pytest.raises(SourceQualityCustodyHold, match="unsafe"):
        read_quality_history(symlink)
    with pytest.raises(SourceQualityCustodyHold, match="unsafe"):
        append_quality_observation(symlink, fresh_observation(tmp_path), apply=True)
    assert original.read_text() == "private"


def test_world_readable_journal_and_hardlinks_are_held(tmp_path):
    observation = fresh_observation(tmp_path)
    path = tmp_path/"journal"/"quality.jsonl"
    append_quality_observation(path, observation, apply=True)
    path.chmod(0o644)
    assert review_quality_history(path, as_of=NOW)["status"] == "LOCAL_SOURCE_QUALITY_CUSTODY_HELD"
    with pytest.raises(SourceQualityCustodyHold, match="unsafe journal file custody"):
        append_quality_observation(
            path, dict(observation, observed_at=(NOW+timedelta(days=1)).isoformat()),
            apply=True,
        )
    path.chmod(0o600)
    second = tmp_path/"other-link.jsonl"
    second.hardlink_to(path)
    with pytest.raises(SourceQualityCustodyHold, match="unsafe journal link count"):
        read_quality_history(path)
    with pytest.raises(SourceQualityCustodyHold, match="unsafe journal file custody"):
        append_quality_observation(
            path, dict(observation, observed_at=(NOW+timedelta(days=1)).isoformat()),
            apply=True,
        )
