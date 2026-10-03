import empire_os.outbound_release_attestation as release_attestation_module
from datetime import datetime, timezone
import json

from empire_os.outbound_release_attestation import (
    load_release_attestation,
    validate_release_attestation,
)


NOW = datetime(2026, 10, 3, 21, 30, tzinfo=timezone.utc)
SHA = "a" * 40


def payload(**overrides):
    row = {
        "schema_version": "1",
        "workflow": "outbound-deliverability",
        "sha": SHA,
        "ref": "refs/heads/agent/outbound-deliverability-v1",
        "event_name": "push",
        "run_id": "123",
        "generated_at": "2026-10-03T21:00:00+00:00",
        "targeted_ci_green": True,
        "compile_green": True,
        "tests_green": True,
        "founder_ui_typecheck_green": True,
        "database_activation_authorized": False,
        "service_activation_authorized": False,
        "dns_mutation_authorized": False,
        "provisioning_authorized": False,
        "send_authorized": False,
    }
    row.update(overrides)
    return row


def test_current_matching_attestation_is_current():
    result = validate_release_attestation(
        payload(),
        expected_sha=SHA,
        now=NOW,
    )
    assert result["status"] == "CURRENT"
    assert result["targeted_ci_green"] is True
    assert result["errors"] == []
    assert result["send_authorized"] is False


def test_sha_mismatch_is_invalid():
    result = validate_release_attestation(
        payload(),
        expected_sha="b" * 40,
        now=NOW,
    )
    assert result["status"] == "INVALID"
    assert "attestation_sha_mismatch" in result["errors"]
    assert result["targeted_ci_green"] is False


def test_any_authority_true_invalidates_attestation():
    result = validate_release_attestation(
        payload(send_authorized=True),
        expected_sha=SHA,
        now=NOW,
    )
    assert result["status"] == "INVALID"
    assert "send_authorized_must_be_false" in result["errors"]


def test_failed_matrix_flag_invalidates_attestation():
    result = validate_release_attestation(
        payload(tests_green=False),
        expected_sha=SHA,
        now=NOW,
    )
    assert result["status"] == "INVALID"
    assert "tests_green_not_true" in result["errors"]


def test_old_attestation_is_stale_not_current():
    result = validate_release_attestation(
        payload(generated_at="2026-09-01T00:00:00+00:00"),
        expected_sha=SHA,
        now=NOW,
        max_age_hours=24,
    )
    assert result["status"] == "STALE"
    assert "attestation_stale" in result["warnings"]
    assert result["targeted_ci_green"] is True


def test_future_attestation_is_invalid():
    result = validate_release_attestation(
        payload(generated_at="2099-01-01T00:00:00+00:00"),
        expected_sha=SHA,
        now=NOW,
    )
    assert result["status"] == "INVALID"
    assert "attestation_generated_in_future" in result["errors"]


def test_missing_attestation_is_absent(tmp_path):
    result = load_release_attestation(
        path=tmp_path / "missing.json",
        expected_sha=SHA,
        now=NOW,
    )
    assert result["status"] == "ABSENT"
    assert result["targeted_ci_green"] is False
    assert result["send_authorized"] is False


def test_loader_validates_on_disk_attestation(tmp_path):
    path = tmp_path / "attestation.json"
    path.write_text(json.dumps(payload()), encoding="utf-8")
    result = load_release_attestation(
        path=path,
        expected_sha=SHA,
        now=NOW,
    )
    assert result["status"] == "CURRENT"
    assert result["path"] == str(path)



def test_release_attestation_cli_returns_zero_only_for_current(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "attestation.json"
    path.write_text(json.dumps(payload()), encoding="utf-8")
    monkeypatch.setenv("EMPIRE_OUTBOUND_EXPECTED_SHA", SHA)
    monkeypatch.setenv(
        "EMPIRE_OUTBOUND_RELEASE_ATTESTATION_PATH",
        str(path),
    )
    monkeypatch.setenv(
        "EMPIRE_OUTBOUND_RELEASE_ATTESTATION_MAX_AGE_HOURS",
        "9999",
    )
    assert release_attestation_module.main() == 0


def test_release_attestation_cli_blocks_sha_mismatch(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "attestation.json"
    path.write_text(json.dumps(payload()), encoding="utf-8")
    monkeypatch.setenv(
        "EMPIRE_OUTBOUND_EXPECTED_SHA",
        "b" * 40,
    )
    monkeypatch.setenv(
        "EMPIRE_OUTBOUND_RELEASE_ATTESTATION_PATH",
        str(path),
    )
    assert release_attestation_module.main() == 2
