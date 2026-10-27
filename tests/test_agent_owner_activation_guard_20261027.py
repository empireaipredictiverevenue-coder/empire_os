"""Offline root-marker adoption tests, no live marker or production writes."""
import os
import stat
from pathlib import Path

import pytest

from empire_os import execution_lease as leases


def simulated_root_custody(monkeypatch, root_marker: Path):
    """Only mocks metadata for an offline temporary fixture."""
    original = Path.lstat
    fake_paths = {root_marker, root_marker.parent}

    def lstat(target):
        details = original(target)
        if target not in fake_paths:
            return details
        values = list(details)
        values[4] = 0  # st_uid is root in simulated test only
        return os.stat_result(values)

    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(leases, "OWNER_LOCK_MARKER", root_marker)


def test_default_off_mode_preserves_original_execution_lease(tmp_path, monkeypatch):
    marker = tmp_path / "nonexistent/owner_lock.enforced"
    # Fake an existing root-owned config parent; no activation file.
    marker.parent.mkdir()
    simulated_root_custody(monkeypatch, marker)
    assert leases.owner_mutation_lock_active() is False
    manager = leases.ExecutionLeaseManager(tmp_path / "leases")
    lease = manager.acquire(
        owner="synthetic_worker", job_id="job1", resources=("path:apps/sample/a.py",)
    )
    assert lease.owner == "synthetic_worker"


def test_root_custodied_enforce_marker_blocks_plain_original_lease(tmp_path, monkeypatch):
    marker = tmp_path / "root_cfg/owner_lock.enforced"
    marker.parent.mkdir()
    marker.write_bytes(b"ENFORCE\n")
    marker.chmod(0o644)
    simulated_root_custody(monkeypatch, marker)
    assert leases.owner_mutation_lock_active() is True
    manager = leases.ExecutionLeaseManager(tmp_path / "leases")
    with pytest.raises(leases.ExecutionLeaseError, match="SIGNED_WORKSTREAM_TICKET_REQUIRED"):
        manager.acquire(
            owner="forged_self_assigned_owner", job_id="job2",
            resources=("path:empire_os/another_owner.py",),
        )
    assert manager.active() == []


@pytest.mark.parametrize("content", [b"DISABLE\n", b"ON\n", b"ENFORCE ", b"", b"ENFORCE\n\n"])
def test_bad_enforcement_marker_does_not_silently_disable_lock(tmp_path, monkeypatch, content):
    marker = tmp_path / "root_cfg/owner_lock.enforced"
    marker.parent.mkdir()
    marker.write_bytes(content)
    marker.chmod(0o644)
    simulated_root_custody(monkeypatch, marker)
    manager = leases.ExecutionLeaseManager(tmp_path / "leases")
    with pytest.raises(leases.ExecutionLeaseError, match="owner_lock_config_"):
        manager.acquire(
            owner="worker", job_id="job3", resources=("path:apps/sample/b.py",)
        )


def test_world_writable_config_parent_is_not_trusted(tmp_path, monkeypatch):
    marker = tmp_path / "root_cfg/owner_lock.enforced"
    marker.parent.mkdir()
    marker.write_bytes(b"ENFORCE\n")
    marker.parent.chmod(0o777)
    marker.chmod(0o644)
    simulated_root_custody(monkeypatch, marker)
    with pytest.raises(leases.ExecutionLeaseError, match="owner_lock_config_parent_untrusted"):
        leases.owner_mutation_lock_active()


def test_symlinked_config_is_not_trusted(tmp_path, monkeypatch):
    marker = tmp_path / "root_cfg/owner_lock.enforced"
    marker.parent.mkdir()
    actual = tmp_path / "elsewhere.txt"
    actual.write_bytes(b"ENFORCE\n")
    marker.symlink_to(actual)
    simulated_root_custody(monkeypatch, marker)
    with pytest.raises(leases.ExecutionLeaseError, match="owner_lock_config_custody_invalid"):
        leases.owner_mutation_lock_active()


def test_ordinary_environment_value_is_not_activation_authority(tmp_path, monkeypatch):
    marker = tmp_path / "root_cfg/owner_lock.enforced"
    marker.parent.mkdir()
    simulated_root_custody(monkeypatch, marker)
    monkeypatch.setenv("EMPIRE_OWNER_LOCK_MODE", "ENFORCE")
    assert leases.owner_mutation_lock_active() is False


def test_manager_checks_marker_again_after_acquiring_existing_flock(tmp_path, monkeypatch):
    marker = tmp_path / "root_cfg/owner_lock.enforced"
    marker.parent.mkdir()
    simulated_root_custody(monkeypatch, marker)
    checks = iter((False, True))
    monkeypatch.setattr(leases, "owner_mutation_lock_active", lambda: next(checks))
    manager = leases.ExecutionLeaseManager(tmp_path / "leases")
    with pytest.raises(leases.ExecutionLeaseError, match="SIGNED_WORKSTREAM_TICKET_REQUIRED"):
        manager.acquire(
            owner="worker", job_id="job4", resources=("path:empire_os/sample.py",)
        )
    assert manager.active() == []
