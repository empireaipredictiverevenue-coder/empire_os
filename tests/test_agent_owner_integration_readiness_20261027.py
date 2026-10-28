"""Offline original-owner adoption checks, no runtime or production writes."""
import json
from pathlib import Path

from empire_os.agent_owner_integration_readiness import (
    ENTRY_POINTS,
    REGISTER,
    inspect_original_owner_integration,
)


def fixtures(root: Path) -> None:
    for name, relative in ENTRY_POINTS.items():
        source = root / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("lease = manager.acquire(owner='test')\n")
    register = root / REGISTER
    register.parent.mkdir(parents=True, exist_ok=True)
    register.write_text(json.dumps({
        "schema_version": "empire.execution.owner_register_review_draft.v1",
        "candidate_assignments": [{
            "workstream": "synthetic_only",
            "authenticated_principal": None, "approved": False
        }],
        "policy_signed": False,
        "production_enforcement_enabled": False
    }))


def test_current_mutator_direct_lease_entry_points_are_visible(tmp_path):
    fixtures(tmp_path)
    result = inspect_original_owner_integration(tmp_path)
    assert result["status"] == "ORIGINAL_OWNER_INTEGRATION_HOLD"
    assert set(result["direct_lease_entry_points"]) == set(ENTRY_POINTS)
    assert result["founder_draft_present_unapproved"] is True
    assert result["draft_approved_owner_count"] == 0
    assert result["draft_authenticated_principal_count"] == 0
    assert result["production_enforcement_verified"] is False


def test_static_adapter_string_cannot_claim_live_enforcement(tmp_path):
    fixtures(tmp_path)
    source = tmp_path / ENTRY_POINTS["hermes"]
    source.write_text("acquire_owner_authorized_lease()\n")
    result = inspect_original_owner_integration(tmp_path)
    assert result["worker_entry_points"][0]["signed_owner_adapter_reference_observed"] is True
    assert "hermes" not in result["direct_lease_entry_points"]
    assert result["production_enforcement_verified"] is False
    assert result["trusted_worker_identity_binding_verified"] is False


def test_missing_worker_file_never_passes(tmp_path):
    fixtures(tmp_path)
    (tmp_path / ENTRY_POINTS["pi"]).unlink()
    result = inspect_original_owner_integration(tmp_path)
    assert result["unreadable_worker_sources"] == ["pi"]
    assert result["production_enforcement_verified"] is False


def test_broken_draft_does_not_create_authority(tmp_path):
    fixtures(tmp_path)
    (tmp_path / REGISTER).write_text("not valid json")
    result = inspect_original_owner_integration(tmp_path)
    assert result["founder_draft_present_unapproved"] is False
    assert result["draft_approved_owner_count"] is None
    assert result["production_enforcement_verified"] is False


def test_symlinked_worker_file_is_rejected(tmp_path):
    fixtures(tmp_path)
    p = tmp_path / ENTRY_POINTS["pi"]
    actual = tmp_path / "external.py"
    actual.write_text("lease=manager.acquire(owner='fake')\n")
    p.unlink()
    p.symlink_to(actual)
    result = inspect_original_owner_integration(tmp_path)
    assert "pi" in result["unreadable_worker_sources"]
    assert result["production_enforcement_verified"] is False


def test_readonly_inventory_detects_direct_repo_git_and_lease_writes(tmp_path):
    fixtures(tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / "runtime/execution_plane").mkdir(parents=True)
    (tmp_path / "runtime/execution_plane/leases.json").write_text("[]")
    report = inspect_original_owner_integration(tmp_path)
    audit = report["direct_write_custody_audit"]
    assert "git_history" in audit["observed_direct_write_exposures"]
    assert "source_repository" in audit["observed_direct_write_exposures"]
    assert "lease_state_file" in audit["observed_direct_write_exposures"]
    assert audit["direct_write_boundary_status"] == "LOCAL_DIRECT_WRITE_BYPASS_OBSERVED"
    assert audit["external_git_and_plugin_authorization_verified"] is False
    assert report["production_enforcement_verified"] is False


def test_readonly_inventory_does_not_create_missing_lease_state(tmp_path):
    fixtures(tmp_path)
    report = inspect_original_owner_integration(tmp_path)
    row = next(x for x in report["direct_write_custody_audit"]["inspected_roles"]
               if x["role"] == "lease_state_directory")
    assert row["exists"] is False
    assert not (tmp_path / "runtime").exists()
    assert report["production_write_performed"] is False
