"""Read-only canonical source release integrity: synthetic Git test repositories."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from empire_os.canonical_order_reader_release_integrity import (
    inspect_canonical_reader_release_integrity, review_reader_release_transition,
)
from empire_os.execution_bus_data_repository import ExecutionBusDataRepository


NO_METHOD = """
class ExecutionBusDataRepository:
    def get_order(self, order_id):
        return order_id
"""
YES_METHOD = """
class ExecutionBusDataRepository:
    def verified_outcome_feedback(self, fulfilment_order_id, *, tenant_id, repo_root, as_of):
        return None
"""


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, check=True, timeout=10,
    )


def repo(tmp_path, body):
    root = tmp_path / "owner_source"
    root.mkdir()
    source = root / "empire_os/execution_bus_data_repository.py"
    source.parent.mkdir()
    source.write_text(body)
    git(root, "init", "-q")
    git(root, "add", "empire_os/execution_bus_data_repository.py")
    git(root, "-c", "user.name=Owner Tests",
        "-c", "user.email=owner-tests@example.invalid",
        "commit", "-qm", "owner original source")
    return root, source


def test_missing_original_owner_reader_is_proven_not_committed(tmp_path):
    root, source = repo(tmp_path, NO_METHOD)
    proof = inspect_canonical_reader_release_integrity(root)
    assert proof["status"] == "VERIFIED_ORDER_READER_NOT_COMMITTED"
    assert proof["owner_source_file_matches_committed_head"] is True
    assert proof["verified_outcome_reader_method_checked_in"] is False
    assert proof["actual_canonical_order_read_performed"] is False
    assert proof["original_owner_release_attested"] is False
    assert "Owner Tests" not in json.dumps(proof)


def test_dirty_uncommitted_source_overrides_runtime_method_presence(tmp_path, monkeypatch):
    root, source = repo(tmp_path, NO_METHOD)
    source.write_text(YES_METHOD)
    monkeypatch.setattr(ExecutionBusDataRepository, "verified_outcome_feedback",
                        lambda *_a, **_kw: None, raising=False)
    proof = inspect_canonical_reader_release_integrity(root)
    assert proof["status"] == "ORIGINAL_OWNER_SOURCE_DIRTY_RELEASE_HOLD"
    assert proof["reader_callable_in_running_process"] is True
    assert proof["verified_outcome_reader_method_checked_in"] is False
    assert proof["owner_source_file_matches_committed_head"] is False
    assert proof["verified_buyer_orders"] is None


def test_committed_method_not_imported_cannot_claim_operational_release(tmp_path):
    root, _ = repo(tmp_path, YES_METHOD)
    proof = inspect_canonical_reader_release_integrity(root)
    assert proof["verified_outcome_reader_method_checked_in"] is True
    assert proof["status"] == "COMMITTED_OWNER_READER_NOT_LOADED"
    assert proof["tenant_privileges_proven"] is False


def test_committed_and_loaded_only_needs_separate_owner_approval(tmp_path, monkeypatch):
    root, _ = repo(tmp_path, YES_METHOD)
    monkeypatch.setattr(ExecutionBusDataRepository, "verified_outcome_feedback",
                        lambda *_a, **_kw: None, raising=False)
    proof = inspect_canonical_reader_release_integrity(root)
    assert proof["status"] == "COMMITTED_READER_PRESENT_OWNER_APPROVAL_REQUIRED"
    assert proof["verified_outcome_reader_method_checked_in"] is True
    assert proof["original_owner_release_attested"] is False
    assert proof["realized_revenue_cents"] is None
    assert proof["outbound_authorized"] is False


def test_missing_or_untrusted_git_root_is_unknown_no_authority(tmp_path):
    proof = inspect_canonical_reader_release_integrity(tmp_path)
    assert proof["status"] == "ORIGINAL_OWNER_SOURCE_INTEGRITY_NOT_PROVEN"
    assert proof["execution_authority"] == "none"


def test_release_transition_suppresses_repetition_and_detects_owner_publication(tmp_path, monkeypatch):
    root, source = repo(tmp_path, NO_METHOD)
    initial = inspect_canonical_reader_release_integrity(root)
    first = review_reader_release_transition(None, initial)
    assert first["status"] == "FIRST_ORIGINAL_OWNER_RELEASE_INTEGRITY_CHECK"
    unchanged = review_reader_release_transition(initial, initial)
    assert unchanged["status"] == "UNCHANGED_ORIGINAL_OWNER_RELEASE_HOLD"
    source.write_text(YES_METHOD)
    published = inspect_canonical_reader_release_integrity(root)
    changed = review_reader_release_transition(initial, published)
    assert changed["status"] == "ORIGINAL_OWNER_RELEASE_INTEGRITY_CHANGED_REVIEW_REQUIRED"
    assert changed["existing_owner_review_eligible"] is True
    assert changed["outbound_authorized"] is False


def test_forged_prior_cannot_preapprove_reader(tmp_path):
    root, _ = repo(tmp_path, NO_METHOD)
    current = inspect_canonical_reader_release_integrity(root)
    bad = dict(current)
    bad["original_owner_release_attested"] = True
    r = review_reader_release_transition(bad, current)
    assert r["status"] == "FIRST_ORIGINAL_OWNER_RELEASE_INTEGRITY_CHECK"
    assert r["new_agent_created"] is False


def test_forged_current_cannot_pass_transition(tmp_path):
    root, _ = repo(tmp_path, NO_METHOD)
    current = inspect_canonical_reader_release_integrity(root)
    current["outbound_authorized"] = True
    with pytest.raises(ValueError):
        review_reader_release_transition(None, current)


def test_transient_git_unavailable_does_not_trigger_false_owner_review(tmp_path):
    root, source = repo(tmp_path, NO_METHOD)
    confirmed = inspect_canonical_reader_release_integrity(root)
    first = review_reader_release_transition(None, confirmed)
    unavailable = dict(confirmed, status="ORIGINAL_OWNER_SOURCE_INTEGRITY_NOT_PROVEN")
    unknown = review_reader_release_transition(
        confirmed, unavailable, previous_transition=first,
    )
    assert unknown["status"] == "ORIGINAL_OWNER_SOURCE_TEMPORARILY_UNAVAILABLE_HOLD_NO_REVIEW"
    assert unknown["last_confirmed_original_owner_state"] == "VERIFIED_ORDER_READER_NOT_COMMITTED"
    assert unknown["existing_owner_review_eligible"] is False
    restored = review_reader_release_transition(
        unavailable, confirmed, previous_transition=unknown,
    )
    assert restored["status"] == "UNCHANGED_ORIGINAL_OWNER_RELEASE_HOLD"
    assert restored["existing_owner_review_eligible"] is False


def test_real_release_progress_after_source_unavailability_is_detected(tmp_path, monkeypatch):
    root, source = repo(tmp_path, NO_METHOD)
    before = inspect_canonical_reader_release_integrity(root)
    first = review_reader_release_transition(None, before)
    unavailable = dict(before, status="ORIGINAL_OWNER_SOURCE_INTEGRITY_NOT_PROVEN")
    missing = review_reader_release_transition(before, unavailable, first)
    source.write_text(YES_METHOD)
    git(root, "add", "empire_os/execution_bus_data_repository.py")
    git(root, "-c", "user.name=Owner Tests",
        "-c", "user.email=owner-tests@example.invalid",
        "commit", "-qm", "committed owner method")
    monkeypatch.setattr(ExecutionBusDataRepository, "verified_outcome_feedback",
                        lambda *_a, **_kw: None, raising=False)
    now = inspect_canonical_reader_release_integrity(root)
    changed = review_reader_release_transition(unavailable, now, missing)
    assert changed["status"] == "ORIGINAL_OWNER_RELEASE_INTEGRITY_CHANGED_REVIEW_REQUIRED"
    assert changed["existing_owner_review_eligible"] is True
    assert changed["outbound_authorized"] is False
    assert changed["last_confirmed_original_owner_state"] == now["status"]
    assert now["original_owner_release_attested"] is False


def test_untrusted_previous_transition_does_not_restore_forged_authority(tmp_path):
    root, _ = repo(tmp_path, NO_METHOD)
    source = inspect_canonical_reader_release_integrity(root)
    first = review_reader_release_transition(None, source)
    modified = dict(first)
    modified["last_confirmed_original_owner_state"] = "COMMITTED_READER_PRESENT_OWNER_APPROVAL_REQUIRED"
    modified["new_agent_created"] = True
    unavailable = dict(source, status="ORIGINAL_OWNER_SOURCE_INTEGRITY_NOT_PROVEN")
    out = review_reader_release_transition(source, unavailable, modified)
    assert out["existing_owner_review_eligible"] is False
    assert out["last_confirmed_original_owner_state"] == "VERIFIED_ORDER_READER_NOT_COMMITTED"


def test_existing_production_checkpoint_pre_upgrade_has_no_last_confirmed_field(tmp_path):
    root, source = repo(tmp_path, NO_METHOD)
    current = inspect_canonical_reader_release_integrity(root)
    old_packet = {
        "schema_version": "empire.commercial.canonical_reader_release_transition.v1",
        "mode": "OBSERVE",
        "status": "FIRST_ORIGINAL_OWNER_RELEASE_INTEGRITY_CHECK",
        "previous_allowlisted_owner_state": None,
        "current_allowlisted_owner_state": current["status"],
        "existing_owner_review_eligible": False,
        "new_agent_created": False,
        "outbound_authorized": False,
        "database_writes": False,
        "execution_authority": "none",
    }
    unknown = dict(current, status="ORIGINAL_OWNER_SOURCE_INTEGRITY_NOT_PROVEN")
    after = review_reader_release_transition(
        current, unknown, previous_transition=old_packet,
    )
    assert after["status"] == "ORIGINAL_OWNER_SOURCE_TEMPORARILY_UNAVAILABLE_HOLD_NO_REVIEW"
    assert after["last_confirmed_original_owner_state"] == current["status"]
    assert after["outbound_authorized"] is False
