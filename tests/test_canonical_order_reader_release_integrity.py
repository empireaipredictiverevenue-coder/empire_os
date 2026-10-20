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
