"""Scoped, fully revalidated Economic Memory learning-readiness tests."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.predictive_learning_readiness import (
    read_founder_learning_readiness, review_verified_learning_readiness,
)
from test_verified_outcome_learning_continuity import memory as full_memory, TENANT

NOW = datetime(2026, 10, 18, 19, tzinfo=timezone.utc)


def empty_memory(**changes):
    row = {
        "schema_version": "empire.economic_memory.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "promoted_learning": False,
        "tenant_id": None,
        "generated_at": NOW.isoformat(),
        "calibration_evidence": [],
        "verified_learning_feedback": [],
    }
    row.update(changes)
    return row


def _write(root, row):
    path = root / "runtime/economic_memory/latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row))
    return path


def test_missing_canonical_source_holds_without_faking_zero(tmp_path):
    result = read_founder_learning_readiness(tmp_path, as_of=NOW)
    assert result["status"] == "EVIDENCE_HOLD"
    assert result["verified_review_count"] is None
    assert result["candidate_brier"] is None
    assert result["model_weight_mutation"] is False


def test_empty_current_unscoped_memory_identifies_real_learning_gap(tmp_path):
    source = empty_memory()
    _write(tmp_path, source)
    report = read_founder_learning_readiness(tmp_path, as_of=NOW)
    assert report["status"] == "INSUFFICIENT_VERIFIED_EVIDENCE"
    assert report["source_status"] == "CANONICAL_COHORT_REVALIDATED"
    assert report["verified_review_count"] == 0
    assert report["verified_outcome_feedback_count"] == 0
    assert report["temporal_holdout_count"] == 0
    assert report["candidate_brier"] is None
    assert report["improvement_brier_relative"] is None
    assert report["next_evidence_action"] == "OBTAIN_VERIFIED_TERMINAL_COMMERCIAL_OUTCOMES"
    assert report["learning_promoted"] is False
    assert source == empty_memory()


def test_tenant_records_not_exposed_to_global_console(tmp_path):
    row = empty_memory(tenant_id="customer-secret",
                       verified_learning_feedback=[{"company": "private"}])
    _write(tmp_path, row)
    report = read_founder_learning_readiness(tmp_path, as_of=NOW)
    assert report["status"] == "EVIDENCE_HOLD"
    assert report["reason"] == "TENANT_SCOPE_REQUIRED"
    assert "customer-secret" not in json.dumps(report)
    assert "private" not in json.dumps(report)
    assert report["verified_review_count"] is None


@pytest.mark.parametrize("generated,expected", [
    ((NOW + timedelta(seconds=1)), "economic_memory_timestamp_future"),
    ((NOW - timedelta(hours=7)), "economic_memory_stale"),
])
def test_memory_freshness_must_be_verified(tmp_path, generated, expected):
    _write(tmp_path, empty_memory(generated_at=generated.isoformat()))
    result = read_founder_learning_readiness(tmp_path, as_of=NOW)
    assert result["status"] == "EVIDENCE_HOLD"
    assert result["reason"] == expected


def test_canonical_verified_scoped_memory_remains_shadow_only():
    # Canonical fixtures exercise the existing validator; never claim these
    # fixture outcomes are live EmpireOS sales.
    m = full_memory()
    result = review_verified_learning_readiness(
        m, tenant_id=TENANT, as_of=NOW,
    )
    assert result["status"] == "INSUFFICIENT_VERIFIED_EVIDENCE"
    assert result["verified_review_count"] == 1
    assert result["verified_outcome_feedback_count"] == 1
    assert result["temporal_holdout_count"] == 0
    assert result["next_evidence_action"] == "GROW_TIME_SAFE_VERIFIED_OUTCOME_COHORT"
    assert result["candidate_brier"] is None
    assert result["learning_promoted"] is False


def test_scoped_validation_rejects_tampered_original_calibration():
    m = full_memory()
    m["calibration_evidence"][0]["predicted_value"] = 0.99
    out = review_verified_learning_readiness(
        m, tenant_id=TENANT, as_of=NOW,
    )
    assert out["status"] == "EVIDENCE_HOLD"
    assert out["reason"] == "canonical_calibration_validation_failed"
    assert out["candidate_brier"] is None


def test_scoped_validation_rejects_cross_tenant_and_unsafe_source():
    m = full_memory()
    out = review_verified_learning_readiness(
        m, tenant_id="another-tenant", as_of=NOW,
    )
    assert out["status"] == "EVIDENCE_HOLD"
    assert out["reason"] == "TENANT_SCOPE_MISMATCH"
    m["mode"] = "EXECUTE"
    assert review_verified_learning_readiness(m, tenant_id=TENANT, as_of=NOW)[
        "reason"
    ] == "economic_memory_contract_untrusted"


def test_duplicate_verified_outcomes_never_count_as_new_learning():
    m = full_memory()
    m["calibration_evidence"].append(deepcopy(m["calibration_evidence"][0]))
    out = review_verified_learning_readiness(
        m, tenant_id=TENANT, as_of=NOW,
    )
    assert out["status"] == "EVIDENCE_HOLD"
    assert out["candidate_brier"] is None


def test_symlink_canonical_memory_never_loaded(tmp_path):
    actual = tmp_path / "elsewhere.json"
    actual.write_text(json.dumps(empty_memory()))
    path = tmp_path / "runtime/economic_memory/latest.json"
    path.parent.mkdir(parents=True)
    path.symlink_to(actual)
    report = read_founder_learning_readiness(tmp_path, as_of=NOW)
    assert report["status"] == "EVIDENCE_HOLD"
    assert report["verified_review_count"] is None


def test_naive_as_of_rejected():
    with pytest.raises(ValueError, match="timezone"):
        review_verified_learning_readiness(
            empty_memory(), tenant_id=None, as_of=datetime(2026, 10, 18)
        )


def test_founder_precision_does_not_turn_sparse_outcomes_into_performance_claims():
    result = review_verified_learning_readiness(
        full_memory(), tenant_id=TENANT, as_of=NOW,
    )
    assert result["precision_verified_subset"] is None
    assert result["precision_wilson_95"] is None
    assert result["precision_selection_count"] is None
    assert result["precision_status"] == "INSUFFICIENT_VERIFIED_SELECTED_OUTCOMES"
    assert result["precision_not_full_population"] is True
    assert result["precision_customer_claim_authorized"] is False
    assert result["learning_promoted"] is False
