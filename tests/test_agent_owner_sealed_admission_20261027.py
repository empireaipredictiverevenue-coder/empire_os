"""Synthetic sealed admission and original manager compatibility; never uses production keys."""
import hashlib
import json
import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization

from empire_os import execution_lease
from empire_os import agent_owner_authority_review as owner
from empire_os.execution_lease import ExecutionLeaseManager
from test_agent_owner_authority_review_20261027 import fixture


def _sealed_fixture(tmp_path, monkeypatch):
    private, params, digest = fixture()
    root = tmp_path / "isolated_test_root"
    ticket_dir = root / "tickets" / "hermes"
    ticket_dir.mkdir(parents=True)
    policy = params["signed_policy"]
    ticket = params["signed_ticket"]
    (root / "policy.json").write_text(json.dumps(policy))
    (ticket_dir / "job_123.json").write_text(json.dumps(ticket))
    (root / "founder_public_key.hex").write_text(
        private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()
    )
    (root / "pinned_policy_sha256.txt").write_text(digest(policy))
    uid = os.geteuid()
    worker_registry = {
        "schema_version": "empire.execution.owner_principals.v1",
        "workers": [
            {"uid": uid, "principal": "synthetic_website_worker", "lease_owner": "hermes"},
            {"uid": uid + 1, "principal": "synthetic_pi_worker", "lease_owner": "pi"},
            {"uid": uid + 2, "principal": "synthetic_coder_worker", "lease_owner": "empire_coder"},
        ],
    }
    (root / "principals.json").write_text(json.dumps(worker_registry))
    monkeypatch.setattr(owner, "SEALED_AUTHORITY_ROOT", root)
    # Synthetic distinct service identity: the real Ubuntu production repo UID
    # must NEVER be accepted as a protected worker principal.
    monkeypatch.setattr(owner, "_production_repository_owner_uid", lambda: uid + 1000)
    # These two mocks are TEST ONLY: production requires immutable root ownership.
    monkeypatch.setattr(owner, "_sealed_root_directory", lambda path: None)
    # Synthetic signed-operation tests simulate an independently controlled
    # broker. Separate tests below exercise the real non-bypass condition.
    monkeypatch.setattr(owner, "_attest_protected_original_lease_custody", lambda manager: None)
    def synthetic_root_file_reader(path):
        try:
            return Path(path).read_bytes()
        except OSError as exc:
            raise owner.OwnerAuthorityHold("SEALED_OWNER_FILE_UNAVAILABLE") from exc
    monkeypatch.setattr(owner, "_sealed_file", synthetic_root_file_reader)
    monkeypatch.setattr(execution_lease, "owner_mutation_lock_active", lambda: True)
    manager = ExecutionLeaseManager(tmp_path / "isolated_original_leases")
    owner.provision_owner_ticket_receipts_for_review(manager)
    return manager, params, root, worker_registry


def test_original_manager_uses_sealed_ticket_under_same_original_lock(tmp_path, monkeypatch):
    manager, params, root, _ = _sealed_fixture(tmp_path, monkeypatch)
    resources = params["lease_resources"]
    result = manager.acquire(
        owner="hermes", job_id="job_123", resources=resources, ttl_seconds=600
    )
    assert result.owner == "synthetic_website_worker"
    assert manager.release(result.lease_id)
    with pytest.raises(execution_lease.ExecutionLeaseError, match="SIGNED_OWNER_TICKET_ALREADY_CONSUMED"):
        manager.acquire(owner="hermes", job_id="job_123", resources=resources, ttl_seconds=600)
    assert manager.active() == []


def test_no_unsealed_or_unknown_service_owner_gets_mutation(tmp_path, monkeypatch):
    manager, params, root, _ = _sealed_fixture(tmp_path, monkeypatch)
    for unassigned in ("research", "website", "finance"):
        with pytest.raises(execution_lease.ExecutionLeaseError, match="UNKNOWN_MUTATION_WORKER_CLASS"):
            manager.acquire(
                owner=unassigned, job_id="job_123",
                resources=params["lease_resources"], ttl_seconds=600,
            )
    assert manager.active() == []


def test_wrong_kernel_worker_identity_is_held(tmp_path, monkeypatch):
    manager, params, root, registry = _sealed_fixture(tmp_path, monkeypatch)
    registry["workers"][0]["uid"] += 99
    (root / "principals.json").write_text(json.dumps(registry))
    with pytest.raises(execution_lease.ExecutionLeaseError, match="NO_AUTHENTICATED_WORKER_UID_MAPPING"):
        manager.acquire(
            owner="hermes", job_id="job_123",
            resources=params["lease_resources"], ttl_seconds=600,
        )
    assert manager.active() == []


def test_shared_worker_uid_cannot_impersonate_another_lane(tmp_path, monkeypatch):
    manager, params, root, registry = _sealed_fixture(tmp_path, monkeypatch)
    registry["workers"][1]["uid"] = registry["workers"][0]["uid"]
    (root / "principals.json").write_text(json.dumps(registry))
    with pytest.raises(execution_lease.ExecutionLeaseError, match="SHARED_OR_INVALID_WORKER_UNIX_IDENTITY"):
        manager.acquire(
            owner="hermes", job_id="job_123",
            resources=params["lease_resources"], ttl_seconds=600,
        )


def test_signed_ticket_forged_service_role_or_resources_are_rejected(tmp_path, monkeypatch):
    manager, params, root, _ = _sealed_fixture(tmp_path, monkeypatch)
    with pytest.raises(execution_lease.ExecutionLeaseError, match="WORKER_UID_CROSS_LANE_IMPERSONATION"):
        manager.acquire(
            owner="pi", job_id="job_123",
            resources=params["lease_resources"], ttl_seconds=600,
        )
    with pytest.raises(execution_lease.ExecutionLeaseError, match="UNSIGNED_OR_CHANGED_FILE_SET"):
        manager.acquire(
            owner="hermes", job_id="job_123",
            resources=("path:apps/example-site/src/other.tsx", "domain:synthetic_site"),
            ttl_seconds=600,
        )
    assert manager.active() == []


def test_missing_signed_ticket_is_a_hold(tmp_path, monkeypatch):
    manager, params, root, _ = _sealed_fixture(tmp_path, monkeypatch)
    (root / "tickets/hermes/job_123.json").unlink()
    with pytest.raises(execution_lease.ExecutionLeaseError, match="SEALED_OWNER_FILE_UNAVAILABLE"):
        manager.acquire(
            owner="hermes", job_id="job_123",
            resources=params["lease_resources"], ttl_seconds=600,
        )


def test_real_custody_validation_rejects_non_root_test_directory(tmp_path):
    root = tmp_path / "not_root_owned"
    root.mkdir()
    if root.stat().st_uid == 0:
        pytest.skip("host tests running as root")
    with pytest.raises(owner.OwnerAuthorityHold, match="SEALED_OWNER_CUSTODY_UNSAFE"):
        owner._sealed_root_directory(root)


def test_activation_then_rollback_preserves_original_worker_lease_contract(tmp_path, monkeypatch):
    """Synthetic cutover: unsigned before, signed only during, unsigned after."""
    manager, params, root, _ = _sealed_fixture(tmp_path, monkeypatch)
    state = {"active": False}
    monkeypatch.setattr(
        execution_lease, "owner_mutation_lock_active", lambda: state["active"]
    )
    resources = params["lease_resources"]
    normal = manager.acquire(
        owner="hermes", job_id="before_canonical_cutover",
        resources=resources, ttl_seconds=600,
    )
    assert manager.release(normal.lease_id)
    state["active"] = True
    with pytest.raises(
        execution_lease.ExecutionLeaseError,
        match="SIGNED_WORKSTREAM_TICKET_REQUIRED",
    ):
        manager.acquire(
            owner="hermes", job_id="unsigned_job",
            resources=resources, ttl_seconds=600,
        )
    signed = manager.acquire(
        owner="hermes", job_id="job_123",
        resources=resources, ttl_seconds=600,
    )
    assert signed.owner == "synthetic_website_worker"
    assert manager.release(signed.lease_id)
    state["active"] = False
    restored = manager.acquire(
        owner="hermes", job_id="after_original_rollback",
        resources=resources, ttl_seconds=600,
    )
    assert restored.owner == "hermes"
    assert manager.release(restored.lease_id)


def test_untrusted_or_shared_service_identity_blocks_before_consuming_ticket(
    tmp_path, monkeypatch
):
    manager, params, root, registry = _sealed_fixture(tmp_path, monkeypatch)
    registry["workers"][1]["uid"] = registry["workers"][0]["uid"]
    (root / "principals.json").write_text(json.dumps(registry))
    with pytest.raises(
        execution_lease.ExecutionLeaseError,
        match="SHARED_OR_INVALID_WORKER_UNIX_IDENTITY",
    ):
        manager.acquire(
            owner="hermes", job_id="job_123",
            resources=params["lease_resources"], ttl_seconds=600,
        )
    assert manager.active() == []
    registry["workers"][1]["uid"] += 1
    (root / "principals.json").write_text(json.dumps(registry))
    # No ticket was consumed on the failed mapping check.
    signed = manager.acquire(
        owner="hermes", job_id="job_123",
        resources=params["lease_resources"], ttl_seconds=600,
    )
    assert signed.owner == "synthetic_website_worker"


def test_shared_production_repo_uid_cannot_be_owner_even_with_valid_ticket(tmp_path, monkeypatch):
    manager, params, root, registry = _sealed_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(owner, "_production_repository_owner_uid", os.geteuid)
    with pytest.raises(execution_lease.ExecutionLeaseError,
                       match="SHARED_OR_PRIVILEGED_UNIX_IDENTITY_DENIED"):
        manager.acquire(owner="hermes", job_id="job_123",
                        resources=params["lease_resources"], ttl_seconds=600)
    assert manager.active() == []


def test_real_worker_with_shared_lease_root_is_denied_before_signed_admission(tmp_path):
    manager = ExecutionLeaseManager(tmp_path / "own_original_lease_files")
    assert manager.root.stat().st_uid == os.geteuid()
    with pytest.raises(owner.OwnerAuthorityHold,
                       match="UNTRUSTED_DIRECT_LEASE_OR_REPO_WRITE_ACCESS"):
        owner._attest_protected_original_lease_custody(manager)


def test_missing_root_custody_rejects_original_worker(tmp_path, monkeypatch):
    manager = ExecutionLeaseManager(tmp_path / "owned_leases")
    monkeypatch.setattr(execution_lease, "owner_mutation_lock_active", lambda: True)
    monkeypatch.setattr(owner, "_attest_protected_original_lease_custody",
                        lambda manager: (_ for _ in ()).throw(
                            owner.OwnerAuthorityHold("UNTRUSTED_DIRECT_LEASE_OR_REPO_WRITE_ACCESS")))
    with pytest.raises(execution_lease.ExecutionLeaseError,
                       match="UNTRUSTED_DIRECT_LEASE_OR_REPO_WRITE_ACCESS"):
        manager.acquire(owner="hermes", job_id="job_123",
                        resources=("path:apps/example-site/src/page.tsx",), ttl_seconds=600)



def test_sealed_worker_postflight_accepts_exact_changed_file(tmp_path, monkeypatch):
    manager, params, root, _ = _sealed_fixture(tmp_path, monkeypatch)
    worktree = tmp_path / "isolated_worktree"
    target = worktree / "apps/example-site/src/page.tsx"
    target.parent.mkdir(parents=True)
    target.write_text("owner-approved edit")
    execution_lease.attest_original_worker_proposal(
        lease_owner="hermes", job_id="job_123",
        trusted_worktree_root=worktree,
        independently_observed_changed_paths=("apps/example-site/src/page.tsx",),
    )


def test_sealed_worker_postflight_denies_extra_file(tmp_path, monkeypatch):
    manager, params, root, _ = _sealed_fixture(tmp_path, monkeypatch)
    worktree = tmp_path / "isolated_worktree"
    (worktree / "apps/example-site/src").mkdir(parents=True)
    (worktree / "apps/example-site/src/page.tsx").write_text("allowed")
    (worktree / "apps/example-site/src/unexpected.tsx").write_text("other lane")
    with pytest.raises(execution_lease.ExecutionLeaseError,
                       match="OWNER_PROPOSAL_SCOPE_BLOCKED:ACTUAL_CHANGES_NOT_EQUAL_TO_SIGNED_FILES"):
        execution_lease.attest_original_worker_proposal(
            lease_owner="hermes", job_id="job_123",
            trusted_worktree_root=worktree,
            independently_observed_changed_paths=(
                "apps/example-site/src/page.tsx",
                "apps/example-site/src/unexpected.tsx",
            ),
        )


def test_sealed_worker_postflight_denies_symlinked_path(tmp_path, monkeypatch):
    manager, params, root, _ = _sealed_fixture(tmp_path, monkeypatch)
    worktree = tmp_path / "isolated_worktree"
    target = worktree / "apps/example-site/src/page.tsx"
    target.parent.mkdir(parents=True)
    outside = tmp_path / "outside_agent_file"
    outside.write_text("not allowed")
    target.symlink_to(outside)
    with pytest.raises(execution_lease.ExecutionLeaseError,
                       match="OWNER_PROPOSAL_SCOPE_BLOCKED:SYMLINKED_CHANGED_PATH_DENIED"):
        execution_lease.attest_original_worker_proposal(
            lease_owner="hermes", job_id="job_123",
            trusted_worktree_root=worktree,
            independently_observed_changed_paths=("apps/example-site/src/page.tsx",),
        )


def test_original_worker_postflight_is_noop_when_marker_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(execution_lease, "owner_mutation_lock_active", lambda: False)
    execution_lease.attest_original_worker_proposal(
        lease_owner="hermes", job_id="old_unscheduled_job",
        trusted_worktree_root=tmp_path / "never_exists",
        independently_observed_changed_paths=(),
    )
