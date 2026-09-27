from pathlib import Path

from empire_os.commercial_recovery_audit import (
    build_recovery_implementation_audit,
)


def _touch(root: Path, relative: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# evidence\n", encoding="utf-8")


def _product(result, key):
    return next(row for row in result["products"] if row["key"] == key)


def test_audit_separates_registry_state_from_repo_evidence(tmp_path):
    _touch(tmp_path, "empire_os/permit_intelligence_runtime.py")
    _touch(tmp_path, "tests/test_permit_intelligence_runtime.py")

    result = build_recovery_implementation_audit(tmp_path)
    permit = _product(result, "permit_intelligence")

    assert permit["registered_state"] == "ACTIVE_BUILD"
    assert permit["implementation_state"] == "CODE_AND_TESTS_PRESENT"
    assert permit["live_production_claimed"] is False
    assert permit["actual_revenue_claimed"] is False
    assert result["registry_state_is_production_proof"] is False
    assert result["actual_revenue"] is False
    assert result["execution_authority"] == "none"


def test_runtime_proof_is_unknown_until_expected_artifact_exists(tmp_path):
    _touch(tmp_path, "empire_os/revenue_pulse.py")
    _touch(tmp_path, "tests/test_revenue_pulse.py")

    before = build_recovery_implementation_audit(tmp_path)
    pulse_before = _product(before, "revenue_pulse")
    assert pulse_before["runtime_proof"] == "UNKNOWN"
    assert pulse_before["runtime_artifact_evidence"] == []

    _touch(tmp_path, "runtime/revenue_pulse/latest.json")
    after = build_recovery_implementation_audit(tmp_path)
    pulse_after = _product(after, "revenue_pulse")
    assert pulse_after["runtime_proof"] == "ARTIFACT_OBSERVED"
    assert pulse_after["runtime_artifact_evidence"] == [
        "runtime/revenue_pulse/latest.json"
    ]
    assert after["runtime_artifact_is_revenue_proof"] is False


def test_unconfigured_runtime_surface_is_not_invented(tmp_path):
    result = build_recovery_implementation_audit(tmp_path)
    hourly = _product(result, "intel_hourly")

    assert hourly["registered_state"] == "FOUNDER_GATE"
    assert hourly["implementation_state"] == "NO_REPO_EVIDENCE"
    assert hourly["runtime_proof"] == "NOT_CONFIGURED"
    assert hourly["pricing_approved_by_audit"] is False
    assert result["protected_paths_read"] is False


def test_protected_patterns_are_rejected(tmp_path):
    _touch(tmp_path, "recovery/secret.py")
    _touch(tmp_path, "toop/legacy.py")

    result = build_recovery_implementation_audit(tmp_path)

    observed = {
        ref
        for row in result["products"]
        for field in (
            "code_evidence",
            "test_evidence",
            "service_evidence",
            "runtime_artifact_evidence",
        )
        for ref in row[field]
    }
    assert not any(ref.startswith("recovery/") for ref in observed)
    assert not any(ref.startswith("toop/") for ref in observed)
    assert result["protected_paths_read"] is False
