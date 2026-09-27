import pytest

from empire_os.execution_lease import (
    ExecutionLeaseError,
    ExecutionLeaseManager,
    resources_conflict,
)


def test_path_parent_and_child_conflict():
    assert resources_conflict(
        ("path:empire_os/search_intelligence",),
        ("path:empire_os/search_intelligence/scoring.py",),
    )


def test_unrelated_paths_do_not_conflict():
    assert not resources_conflict(
        ("path:empire_os/revenue_pulse.py",),
        ("path:empire_os/search_intelligence/scoring.py",),
    )


def test_logical_domain_conflict_is_exact():
    assert resources_conflict(
        ("domain:conversation_os",),
        ("domain:conversation_os",),
    )
    assert not resources_conflict(
        ("domain:conversation_os",),
        ("domain:search_intelligence",),
    )


@pytest.mark.parametrize(
    "resource",
    [
        "recovery/foo.py",
        "toop/foo.py",
        "runtime/foo.json",
        ".git/config",
        ".env",
        "../outside.py",
        "/etc/passwd",
    ],
)
def test_protected_or_unsafe_resources_cannot_be_leased(tmp_path, resource):
    manager = ExecutionLeaseManager(tmp_path / "leases")
    with pytest.raises(ExecutionLeaseError):
        manager.acquire(
            owner="hermes",
            job_id="job-a",
            resources=(resource,),
        )


def test_conflicting_mutating_workers_are_blocked(tmp_path):
    manager = ExecutionLeaseManager(tmp_path / "leases")
    first = manager.acquire(
        owner="hermes",
        job_id="job-a",
        resources=(
            "domain:conversation_os",
            "empire_os/conversation_api.py",
        ),
    )
    assert first.owner == "hermes"

    with pytest.raises(ExecutionLeaseError, match="lease_conflict"):
        manager.acquire(
            owner="pi",
            job_id="job-b",
            resources=("domain:conversation_os",),
        )


def test_release_allows_next_worker(tmp_path):
    manager = ExecutionLeaseManager(tmp_path / "leases")
    first = manager.acquire(
        owner="hermes",
        job_id="job-a",
        resources=("empire_os/conversation_api.py",),
    )
    assert manager.release(first.lease_id) is True

    second = manager.acquire(
        owner="pi",
        job_id="job-b",
        resources=("empire_os/conversation_api.py",),
    )
    assert second.owner == "pi"


def test_active_lease_file_is_operational_not_authority(tmp_path):
    manager = ExecutionLeaseManager(tmp_path / "leases")
    manager.acquire(
        owner="hermes",
        job_id="job-a",
        resources=("domain:search_intelligence",),
    )
    rows = manager.active()
    assert len(rows) == 1
    assert rows[0]["owner"] == "hermes"
