"""Synthetic ownership-policy fixtures only; no EmpireOS agent is assigned."""
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os.agent_owner_authority_review import (
    OwnerAuthorityHold, POLICY_SCHEMA, TICKET_SCHEMA, verify_owner_mutation
)

NOW = datetime.now(timezone.utc)


def signed(private, payload):
    data=json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf8")
    return {**payload,"signature":private.sign(data).hex()}


def fixture():
    private=Ed25519PrivateKey.generate()
    policy=signed(private,{
        "schema_version":POLICY_SCHEMA,
        "issuer":"FOUNDER_CONTROLLED_EXECUTION_OWNER",
        "assignments":[{
            "assignment_id":"synthetic_website_lane",
            "principal":"synthetic_website_worker",
            "department":"synthetic_site",
            "allowed_paths":["apps/example-site"],
            "allowed_domains":["synthetic_site"],
            "capabilities":["frontend_code"],
            "founder_decision_ref":"SYNTHETIC_TEST_ONLY",
            "approved":True,
        },{
            "assignment_id":"synthetic_research_lane",
            "principal":"synthetic_research_worker",
            "department":"synthetic_research",
            "allowed_paths":["empire_os/example_research"],
            "allowed_domains":["synthetic_research"],
            "capabilities":["backend_code"],
            "founder_decision_ref":"SYNTHETIC_TEST_ONLY_2",
            "approved":True,
        }]
    })
    ticket=signed(private,{
        "schema_version":TICKET_SCHEMA,
        "job_id":"job_123",
        "ticket_id":"synthetic_ticket_123",
        "principal":"synthetic_website_worker",
        "assignment_id":"synthetic_website_lane",
        "founder_decision_ref":"SYNTHETIC_TEST_ONLY",
        "department":"synthetic_site",
        "capability":"frontend_code",
        "authority":"internal_write",
        "issued_at":(NOW-timedelta(minutes=1)).isoformat(),
        "expires_at":(NOW+timedelta(minutes=20)).isoformat(),
        "changed_paths":["apps/example-site/src/page.tsx"],
        "lease_resources":["path:apps/example-site/src/page.tsx","domain:synthetic_site"],
    })
    def digest(p):
        return hashlib.sha256(json.dumps(p,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    kwargs=dict(
        signed_policy=policy,
        signed_ticket=ticket,
        trusted_founder_public_key=private.public_key(),
        trusted_policy_sha256=digest(policy),
        authenticated_worker_principal="synthetic_website_worker",
        request_job_id="job_123",
        request_department="synthetic_site",
        request_capability="frontend_code",
        changed_paths=("apps/example-site/src/page.tsx",),
        lease_resources=("path:apps/example-site/src/page.tsx","domain:synthetic_site"),
        now=NOW,
    )
    return private,kwargs,digest


def test_valid_signed_owner_still_needs_original_mutation_lease():
    _,params,_=fixture()
    result=verify_owner_mutation(**params)
    assert result["status"]=="FOUNDER_OWNER_SCOPE_VALIDATED_BEFORE_LEASE"
    assert result["existing_execution_lease_still_required"] is True
    assert result["production_release_authorized"] is False
    assert result["external_actions_authorized"] is False


@pytest.mark.parametrize("key,value,reason",[
    ("authenticated_worker_principal","synthetic_research_worker","SPOOFED_WORKER_OWNER"),
    ("request_job_id","job_different","JOB_ID_MISMATCH"),
    ("request_department","synthetic_research","DEPARTMENT_MISMATCH"),
    ("request_capability","backend_code","CAPABILITY_MISMATCH"),
    ("changed_paths",("empire_os/example_research/run.py",),"UNSIGNED_OR_CHANGED_FILE_SET"),
    ("lease_resources",("domain:synthetic_site",),"LEASE_NOT_BOUND_TO_OWNER_TICKET"),
    ("trusted_policy_sha256","0"*64,"STALE_OR_REVOKED_OWNER_POLICY"),
])
def test_request_or_owner_spoof_is_held(key,value,reason):
    _,params,_=fixture()
    params[key]=value
    with pytest.raises(OwnerAuthorityHold,match=reason):
        verify_owner_mutation(**params)


def test_unsigned_self_assignment_cannot_override_policy():
    _,params,_=fixture()
    altered=deepcopy(params["signed_ticket"])
    altered["principal"]="synthetic_research_worker"
    params["signed_ticket"]=altered
    params["authenticated_worker_principal"]="synthetic_research_worker"
    with pytest.raises(OwnerAuthorityHold,match="AUTHORITY_SIGNATURE_INVALID"):
        verify_owner_mutation(**params)


def test_expired_ticket_is_rejected_even_when_signed():
    private,params,_=fixture()
    t=deepcopy(params["signed_ticket"])
    t.pop("signature")
    t["expires_at"]=(NOW-timedelta(seconds=1)).isoformat()
    params["signed_ticket"]=signed(private,t)
    with pytest.raises(OwnerAuthorityHold,match="TICKET_NOT_CURRENT"):
        verify_owner_mutation(**params)


def test_ticket_cannot_cover_more_than_two_hours():
    private,params,_=fixture()
    t=deepcopy(params["signed_ticket"])
    t.pop("signature")
    t["expires_at"]=(NOW+timedelta(hours=3)).isoformat()
    params["signed_ticket"]=signed(private,t)
    with pytest.raises(OwnerAuthorityHold,match="TICKET_LIFETIME_INVALID"):
        verify_owner_mutation(**params)


def test_signed_cross_lane_changed_file_fails_despite_valid_signature():
    private,params,_=fixture()
    t=deepcopy(params["signed_ticket"])
    t.pop("signature")
    t["changed_paths"]=["empire_os/example_research/run.py"]
    t["lease_resources"]=["path:empire_os/example_research/run.py"]
    params["signed_ticket"]=signed(private,t)
    params["changed_paths"]=tuple(t["changed_paths"])
    params["lease_resources"]=tuple(t["lease_resources"])
    with pytest.raises(OwnerAuthorityHold,match="CROSS_AGENT_FILE_CHANGE"):
        verify_owner_mutation(**params)


def test_signed_unapproved_domain_fails_even_when_file_allowed():
    private,params,_=fixture()
    t=deepcopy(params["signed_ticket"])
    t.pop("signature")
    t["lease_resources"]=["path:apps/example-site/src/page.tsx","domain:synthetic_research"]
    params["signed_ticket"]=signed(private,t)
    params["lease_resources"]=tuple(t["lease_resources"])
    with pytest.raises(OwnerAuthorityHold,match="UNAPPROVED_LOGICAL_DOMAIN"):
        verify_owner_mutation(**params)


def test_ambiguous_overlapping_owner_registry_cannot_issue_ticket():
    private,params,digest=fixture()
    p=deepcopy(params["signed_policy"])
    p.pop("signature")
    p["assignments"][1]["allowed_paths"]=["apps/example-site/src"]
    params["signed_policy"]=signed(private,p)
    params["trusted_policy_sha256"]=digest(params["signed_policy"])
    with pytest.raises(OwnerAuthorityHold,match="OVERLAPPING_WORKSTREAM_ASSIGNMENTS"):
        verify_owner_mutation(**params)


def test_missing_registration_blocks_mutation():
    private,params,digest=fixture()
    p=deepcopy(params["signed_policy"])
    p.pop("signature")
    p["assignments"]=p["assignments"][1:]
    params["signed_policy"]=signed(private,p)
    params["trusted_policy_sha256"]=digest(params["signed_policy"])
    with pytest.raises(OwnerAuthorityHold,match="UNKNOWN_WORKSTREAM"):
        verify_owner_mutation(**params)


def test_reassignment_requires_new_founder_policy_and_ticket():
    private,params,digest=fixture()
    p=deepcopy(params["signed_policy"])
    p.pop("signature")
    p["assignments"][0]["principal"]="new_synthetic_worker"
    params["signed_policy"]=signed(private,p)
    params["trusted_policy_sha256"]=digest(params["signed_policy"])
    with pytest.raises(OwnerAuthorityHold,match="WORKSTREAM_NOT_ASSIGNED_TO_REQUESTER"):
        verify_owner_mutation(**params)


def test_runtime_or_repo_metadata_path_is_never_mutation_authority():
    private,params,_=fixture()
    for forbidden in ("runtime/secrets/x",".git/config","apps/example-site/../other.py","apps/example-site/.env.production","apps/example-site/.env.local"):
        t=deepcopy(params["signed_ticket"])
        t.pop("signature")
        t["changed_paths"]=[forbidden]
        t["lease_resources"]=[f"path:{forbidden}"]
        params["signed_ticket"]=signed(private,t)
        params["changed_paths"]=(forbidden,)
        params["lease_resources"]=(f"path:{forbidden}",)
        with pytest.raises(OwnerAuthorityHold,match="UNSAFE_PATH|PROTECTED_PATH"):
            verify_owner_mutation(**params)


def test_unauthorized_worker_cannot_obtain_the_original_execution_lease(tmp_path):
    from empire_os.execution_lease import ExecutionLeaseManager
    from empire_os.agent_owner_authority_review import acquire_owner_authorized_lease
    _,params,_=fixture()
    lease=ExecutionLeaseManager(tmp_path/"leases")
    params["authenticated_worker_principal"]="synthetic_research_worker"
    with pytest.raises(OwnerAuthorityHold, match="SPOOFED_WORKER_OWNER"):
        acquire_owner_authorized_lease(lease_manager=lease, **params)
    assert lease.active()==[]


def test_signed_and_verified_owner_may_use_existing_lease_not_new_lock(tmp_path):
    from empire_os.execution_lease import ExecutionLeaseManager
    from empire_os.agent_owner_authority_review import (
        acquire_owner_authorized_lease, provision_owner_ticket_receipts_for_review,
    )
    _,params,_=fixture()
    lease=ExecutionLeaseManager(tmp_path/"leases")
    provision_owner_ticket_receipts_for_review(lease)
    first=acquire_owner_authorized_lease(lease_manager=lease, ttl_seconds=900, **params)
    assert first.owner=="synthetic_website_worker"
    assert len(lease.active())==1
    with pytest.raises(OwnerAuthorityHold, match="SIGNED_OWNER_TICKET_ALREADY_CONSUMED"):
        acquire_owner_authorized_lease(lease_manager=lease, ttl_seconds=900, **params)
    assert lease.release(first.lease_id)
    assert lease.active()==[]
    # The ticket remains consumed after the original lease was released.
    with pytest.raises(OwnerAuthorityHold, match="SIGNED_OWNER_TICKET_ALREADY_CONSUMED"):
        acquire_owner_authorized_lease(lease_manager=lease, ttl_seconds=900, **params)


def test_unsigned_founder_review_register_has_no_mutation_authority():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    p = root / "docs/handoffs/FOUNDER_WORKSTREAM_OWNER_REGISTER_DRAFT_20261027.json"
    proposal=json.loads(p.read_text())
    assert proposal["status"]=="FOUNDER_ROLLOUT_AUTHORIZED_RUNTIME_LANE_ASSIGNMENTS_UNVERIFIED"
    assert proposal["founder_governance_owner"]["connected_github_login"] == "empireaipredictiverevenue-coder"
    assert proposal["founder_governance_owner"]["github_permission_verified"] == "admin"
    assert proposal["founder_governance_owner"]["approval_is_not_a_cryptographic_signing_key_or_internal_write_ticket"] is True
    assert proposal["production_enforcement_enabled"] is False
    assert proposal["policy_signed"] is False
    assert proposal["job_tickets_issued"] == 0
    assert all(row["approved"] is False and row["authenticated_principal"] is None
               for row in proposal["candidate_assignments"])
    _,params,digest=fixture()
    params["signed_policy"]=proposal
    params["trusted_policy_sha256"]=digest(proposal)
    with pytest.raises(OwnerAuthorityHold,match="MISSING_SIGNED_AUTHORITY"):
        verify_owner_mutation(**params)


def test_lease_cannot_extend_past_the_signed_ticket(tmp_path):
    from empire_os.execution_lease import ExecutionLeaseManager
    from empire_os.agent_owner_authority_review import (
        acquire_owner_authorized_lease, provision_owner_ticket_receipts_for_review,
    )
    private, params, _ = fixture()
    ticket = deepcopy(params["signed_ticket"])
    ticket.pop("signature")
    ticket["expires_at"] = (NOW + timedelta(seconds=90)).isoformat()
    params["signed_ticket"] = signed(private, ticket)
    leases = ExecutionLeaseManager(tmp_path / "leases")
    provision_owner_ticket_receipts_for_review(leases)
    with pytest.raises(OwnerAuthorityHold, match="OWNER_LEASE_OUTLIVES_SIGNED_TICKET"):
        acquire_owner_authorized_lease(lease_manager=leases, ttl_seconds=1200, **params)
    assert leases.active() == []
    allowed = acquire_owner_authorized_lease(lease_manager=leases, ttl_seconds=60, **params)
    assert allowed.owner == "synthetic_website_worker"
    assert leases.release(allowed.lease_id)


@pytest.mark.parametrize("bad_ttl", [0, -1, 1, 59, 7201, True, 61.5, "1800"])
def test_lease_ttl_rejects_invalid_or_implicitly_clamped_durations(tmp_path, bad_ttl):
    from empire_os.execution_lease import ExecutionLeaseManager
    from empire_os.agent_owner_authority_review import acquire_owner_authorized_lease
    _, params, _ = fixture()
    manager = ExecutionLeaseManager(tmp_path / "leases")
    with pytest.raises(OwnerAuthorityHold, match="OWNER_LEASE_TTL_OUT_OF_BOUNDS"):
        acquire_owner_authorized_lease(lease_manager=manager, ttl_seconds=bad_ttl, **params)
    assert manager.active() == []


def test_actual_worktree_changed_path_attestation(tmp_path):
    from empire_os.agent_owner_authority_review import attest_actual_worktree_changes
    root = tmp_path / "safe"
    target = root / "apps/example-site/src/page.tsx"
    target.parent.mkdir(parents=True)
    target.write_text("safe changes")
    changed = ("apps/example-site/src/page.tsx",)
    result = attest_actual_worktree_changes(
        trusted_worktree_root=root,
        signed_changed_paths=changed,
        independently_observed_changed_paths=changed,
    )
    assert result["status"] == "ORIGINAL_OWNER_WORKTREE_PATH_ATTESTED"
    assert result["production_publication_authorized"] is False


def test_symlinked_changed_file_cannot_escape_owner_worktree(tmp_path):
    from empire_os.agent_owner_authority_review import attest_actual_worktree_changes
    root = tmp_path / "safe"
    target = root / "apps/example-site"
    target.mkdir(parents=True)
    outside = tmp_path / "other-agent.py"
    outside.write_text("secret")
    (target / "page.tsx").symlink_to(outside)
    changed = ("apps/example-site/page.tsx",)
    with pytest.raises(OwnerAuthorityHold, match="SYMLINKED_CHANGED_PATH_DENIED"):
        attest_actual_worktree_changes(
            trusted_worktree_root=root,
            signed_changed_paths=changed,
            independently_observed_changed_paths=changed,
        )


def test_symlinked_parent_directory_is_rejected(tmp_path):
    from empire_os.agent_owner_authority_review import attest_actual_worktree_changes
    root = tmp_path / "safe"
    root.mkdir()
    outside = tmp_path / "other-agent"
    outside.mkdir()
    (outside / "page.py").write_text("value")
    (root / "apps").symlink_to(outside, target_is_directory=True)
    changed = ("apps/page.py",)
    with pytest.raises(OwnerAuthorityHold, match="SYMLINKED_CHANGED_PATH_DENIED"):
        attest_actual_worktree_changes(
            trusted_worktree_root=root,
            signed_changed_paths=changed,
            independently_observed_changed_paths=changed,
        )


def test_hardlinked_changed_file_is_rejected(tmp_path):
    import os
    from empire_os.agent_owner_authority_review import attest_actual_worktree_changes
    root = tmp_path / "safe"
    root.mkdir()
    outside = tmp_path / "other-agent.py"
    outside.write_text("value")
    os.link(outside, root / "page.py")
    changed = ("page.py",)
    with pytest.raises(OwnerAuthorityHold, match="HARDLINKED_CHANGED_FILE_DENIED"):
        attest_actual_worktree_changes(
            trusted_worktree_root=root,
            signed_changed_paths=changed,
            independently_observed_changed_paths=changed,
        )


def test_postflight_added_or_deleted_files_need_independent_review(tmp_path):
    from empire_os.agent_owner_authority_review import attest_actual_worktree_changes
    root = tmp_path / "safe"
    root.mkdir()
    (root / "page.py").write_text("approved")
    with pytest.raises(OwnerAuthorityHold, match="ACTUAL_CHANGES_NOT_EQUAL_TO_SIGNED_FILES"):
        attest_actual_worktree_changes(
            trusted_worktree_root=root,
            signed_changed_paths=("page.py",),
            independently_observed_changed_paths=("page.py", "unexpected.py"),
        )
    with pytest.raises(OwnerAuthorityHold, match="MISSING_CHANGED_PATH_REQUIRES_OWNER_REVIEW"):
        attest_actual_worktree_changes(
            trusted_worktree_root=root,
            signed_changed_paths=("deleted.py",),
            independently_observed_changed_paths=("deleted.py",),
        )


@pytest.mark.parametrize("unsafe_path", ["apps/site/page.py\n", "apps/site/page.py\x00"])
def test_control_character_paths_are_not_mutation_targets(tmp_path, unsafe_path):
    from empire_os.agent_owner_authority_review import attest_actual_worktree_changes
    root = tmp_path / "safe"
    root.mkdir()
    with pytest.raises(OwnerAuthorityHold, match="UNSAFE_PATH"):
        attest_actual_worktree_changes(
            trusted_worktree_root=root,
            signed_changed_paths=(unsafe_path,),
            independently_observed_changed_paths=(unsafe_path,),
        )


def test_replay_receipt_survives_new_lease_manager_instance(tmp_path):
    from empire_os.execution_lease import ExecutionLeaseManager
    from empire_os.agent_owner_authority_review import (
        acquire_owner_authorized_lease, provision_owner_ticket_receipts_for_review,
    )
    _, params, _ = fixture()
    root = tmp_path / "original_execution_plane"
    first_manager = ExecutionLeaseManager(root)
    provision_owner_ticket_receipts_for_review(first_manager)
    first = acquire_owner_authorized_lease(
        lease_manager=first_manager, ttl_seconds=900, **params
    )
    assert first_manager.release(first.lease_id)
    new_process_manager = ExecutionLeaseManager(root)
    with pytest.raises(OwnerAuthorityHold, match="SIGNED_OWNER_TICKET_ALREADY_CONSUMED"):
        acquire_owner_authorized_lease(
            lease_manager=new_process_manager, ttl_seconds=900, **params
        )


def test_replay_receipt_missing_or_deleted_never_resets_used_tickets(tmp_path):
    from empire_os.execution_lease import ExecutionLeaseManager
    from empire_os.agent_owner_authority_review import (
        acquire_owner_authorized_lease, provision_owner_ticket_receipts_for_review,
    )
    _, params, _ = fixture()
    manager = ExecutionLeaseManager(tmp_path / "leases")
    with pytest.raises(OwnerAuthorityHold, match="TICKET_RECEIPT_MISSING_OR_UNREADABLE"):
        acquire_owner_authorized_lease(
            lease_manager=manager, ttl_seconds=900, **params
        )
    receipt = provision_owner_ticket_receipts_for_review(manager)
    with pytest.raises(OwnerAuthorityHold, match="EXISTING_TICKET_RECEIPT_CANNOT_BE_RESET"):
        provision_owner_ticket_receipts_for_review(manager)
    ticket = acquire_owner_authorized_lease(
        lease_manager=manager, ttl_seconds=900, **params
    )
    assert manager.release(ticket.lease_id)
    receipt.unlink()
    with pytest.raises(OwnerAuthorityHold, match="TICKET_RECEIPT_MISSING_OR_UNREADABLE"):
        acquire_owner_authorized_lease(
            lease_manager=manager, ttl_seconds=900, **params
        )


def test_corrupt_or_symlinked_private_ticket_receipt_is_a_hold(tmp_path):
    from empire_os.execution_lease import ExecutionLeaseManager
    from empire_os.agent_owner_authority_review import (
        acquire_owner_authorized_lease, provision_owner_ticket_receipts_for_review,
    )
    _, params, _ = fixture()
    manager = ExecutionLeaseManager(tmp_path / "leases")
    receipt = provision_owner_ticket_receipts_for_review(manager)
    receipt.write_text("{" + "broken_json" * 10)
    with pytest.raises(OwnerAuthorityHold, match="TICKET_RECEIPT_MISSING_OR_UNREADABLE"):
        acquire_owner_authorized_lease(
            lease_manager=manager, ttl_seconds=900, **params
        )
    receipt.unlink()
    fake = tmp_path / "fake.json"
    fake.write_text("[]")
    receipt.symlink_to(fake)
    with pytest.raises(OwnerAuthorityHold, match="UNSAFE_TICKET_RECEIPT_CUSTODY"):
        acquire_owner_authorized_lease(
            lease_manager=manager, ttl_seconds=900, **params
        )


def test_second_distinct_ticket_waits_on_original_conflict_without_being_consumed(tmp_path):
    from empire_os.execution_lease import ExecutionLeaseManager
    from empire_os.agent_owner_authority_review import (
        acquire_owner_authorized_lease, provision_owner_ticket_receipts_for_review,
    )
    private, params, _ = fixture()
    manager = ExecutionLeaseManager(tmp_path / "leases")
    provision_owner_ticket_receipts_for_review(manager)
    first = acquire_owner_authorized_lease(
        lease_manager=manager, ttl_seconds=900, **params
    )
    ticket = deepcopy(params["signed_ticket"])
    ticket.pop("signature")
    ticket["ticket_id"] = "synthetic_new_ticket_456"
    params["signed_ticket"] = signed(private, ticket)
    with pytest.raises(OwnerAuthorityHold, match="ORIGINAL_EXECUTION_LEASE_CONFLICT"):
        acquire_owner_authorized_lease(
            lease_manager=manager, ttl_seconds=900, **params
        )
    assert manager.release(first.lease_id)
    second = acquire_owner_authorized_lease(
        lease_manager=manager, ttl_seconds=900, **params
    )
    assert second.lease_id != first.lease_id


def test_failed_original_lease_commit_burns_ticket_instead_of_allowing_replay(tmp_path, monkeypatch):
    from empire_os.execution_lease import ExecutionLeaseManager
    from empire_os.agent_owner_authority_review import (
        acquire_owner_authorized_lease, provision_owner_ticket_receipts_for_review,
    )
    _, params, _ = fixture()
    manager = ExecutionLeaseManager(tmp_path / "leases")
    provision_owner_ticket_receipts_for_review(manager)
    original_write = manager._write
    def simulate_crash(_leases):
        raise OSError("injected_lease_persistence_failure")
    monkeypatch.setattr(manager, "_write", simulate_crash)
    with pytest.raises(OSError, match="injected_lease_persistence_failure"):
        acquire_owner_authorized_lease(
            lease_manager=manager, ttl_seconds=900, **params
        )
    monkeypatch.setattr(manager, "_write", original_write)
    with pytest.raises(OwnerAuthorityHold, match="SIGNED_OWNER_TICKET_ALREADY_CONSUMED"):
        acquire_owner_authorized_lease(
            lease_manager=manager, ttl_seconds=900, **params
        )


def test_parallel_replay_cannot_acquire_two_leases(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from empire_os.execution_lease import ExecutionLeaseManager
    from empire_os.agent_owner_authority_review import (
        acquire_owner_authorized_lease, provision_owner_ticket_receipts_for_review,
    )
    _, params, _ = fixture()
    root = tmp_path / "leases"
    provision_owner_ticket_receipts_for_review(ExecutionLeaseManager(root))
    def try_one(_):
        manager = ExecutionLeaseManager(root)
        try:
            lease = acquire_owner_authorized_lease(
                lease_manager=manager, ttl_seconds=900, **params
            )
            return ("GRANTED", lease.lease_id)
        except OwnerAuthorityHold as exc:
            return ("HELD", str(exc))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(try_one, range(8)))
    assert sum(status == "GRANTED" for status, _ in results) == 1
    assert sum(status == "HELD" for status, _ in results) == 7
    assert all(
        reason == "SIGNED_OWNER_TICKET_ALREADY_CONSUMED"
        for status, reason in results if status == "HELD"
    )


def test_founder_github_custody_is_limited_to_execution_plane_files():
    root = Path(__file__).resolve().parents[1]
    rules = (root / ".github/CODEOWNERS").read_text().splitlines()
    entries = [line.split() for line in rules if line.strip() and not line.lstrip().startswith("#")]
    expected_paths = {
        "/.github/CODEOWNERS",
        "/empire_os/agent_execution_plane.py",
        "/empire_os/execution_lease.py",
        "/empire_os/execution_plane_dispatcher.py",
        "/empire_os/hermes_control.py",
        "/empire_os/pi_sandbox_runner.py",
        "/empire_os/empire_coder_sandbox_runner.py",
        "/empire_os/coder/worker.py",
        "/empire_os/agent_owner_authority_review.py",
        "/empire_os/agent_owner_integration_readiness.py",
        "/docs/AGENT_TOOL_EXECUTION_PLANE_ARCHITECTURE.md",
        "/docs/handoffs/FOUNDER_WORKSTREAM_OWNER_REGISTER_DRAFT_20261027.json",
    }
    assert set(item[0] for item in entries) == expected_paths
    assert all(item[1:] == ["@empireaipredictiverevenue-coder"] for item in entries)
    assert all(not x.startswith(("/apps/", "/empire_os/buyer_",
                                 "/empire_os/search_", "/empire_os/commercial_"))
               for x in expected_paths)


def test_founder_governance_approval_does_not_approve_runtime_workers():
    root = Path(__file__).resolve().parents[1]
    proposal = json.loads((
        root / "docs/handoffs/FOUNDER_WORKSTREAM_OWNER_REGISTER_DRAFT_20261027.json"
    ).read_text())
    assert proposal["founder_governance_owner"]["founder_has_approved_controlled_governance_integration"] is True
    assert proposal["founder_governance_owner"]["worker_service_identity_bound_to_founder"] is False
    assert proposal["job_tickets_issued"] == 0
    assert proposal["policy_signed"] is False
    assert proposal["production_enforcement_enabled"] is False
    assert all(entry["approved"] is False for entry in proposal["candidate_assignments"])
    assert all(entry["authenticated_principal"] is None for entry in proposal["candidate_assignments"])
