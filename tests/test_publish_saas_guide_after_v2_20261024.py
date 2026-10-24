"""Owner release tests; no live writes or privileged operations."""
import json
from pathlib import Path

import pytest

from scripts import publish_saas_guide_after_v2_20261024 as owner


def test_real_pinned_post_v2_preflight_is_readonly_and_unapproved():
    p = owner.preflight()
    assert p["status"] == "SAAS_659_TO_662_PREFLIGHT_PASS_PUBLICATION_NOT_APPROVED"
    assert p["original_file_count"] == 659
    assert p["candidate_file_count"] == 662
    assert p["existing_page_replacements"] == 2
    assert p["new_asset_count"] == 3
    assert p["verified_root_backup_exists"] is False
    assert p["website_publication_authorized"] is False
    assert p["writes_performed"] is False
    assert not owner.ARCHIVE.exists()
    assert not owner.RELEASE_RECEIPT.exists()


def test_unprivileged_apply_does_not_acquire_lock_or_make_backup(monkeypatch, capsys):
    monkeypatch.setattr(owner.os, "geteuid", lambda: 1000)
    def forbidden_lock():
        raise AssertionError("UNPRIVILEGED_CALL_MUST_NOT_LOCK")
    monkeypatch.setattr(owner, "_locked_release", forbidden_lock)
    assert owner.main([owner.EXACT_APPLY]) == 2
    held = json.loads(capsys.readouterr().out)
    assert held["status"] == "SAAS_GUIDE_POST_V2_PUBLICATION_HELD"
    assert held["reason"] == "ORIGINAL_WEBSITE_ROOT_OWNER_AUTHORITY_REQUIRED"
    assert held["outbound_sent"] is False


def test_root_simulation_still_rejects_without_specific_founder_approval(monkeypatch, capsys):
    monkeypatch.setattr(owner.os, "geteuid", lambda: 0)
    monkeypatch.setattr(owner, "APPROVAL_SHA256", None)
    def forbidden_lock():
        raise AssertionError("NO_APPROVAL_MUST_NOT_LOCK")
    monkeypatch.setattr(owner, "_locked_release", forbidden_lock)
    assert owner.main([owner.EXACT_APPLY]) == 2
    held = json.loads(capsys.readouterr().out)
    assert held["reason"] == "SEPARATE_SAAS_FOUNDER_APPROVAL_NOT_YET_RECORDED"
    assert not owner.ARCHIVE.exists()


def test_candidate_fails_on_untrusted_qa_receipt(monkeypatch):
    original = owner._read_pinned
    def tamper(path):
        value = original(path)
        if path == owner.BROWSER:
            value["blocked_external"] = 1
        return value
    monkeypatch.setattr(owner, "_read_pinned", tamper)
    with pytest.raises(owner.ReleaseHold, match="PRIVATE_POST_V2_BROWSER_QA_FAILED"):
        owner.preflight()


def test_candidate_fails_on_untrusted_rollback_receipt(monkeypatch):
    original = owner._read_pinned
    def tamper(path):
        value = original(path)
        if path == owner.ROLLBACK_QA:
            value["scenarios"][0]["all_hashes_verified"] = False
        return value
    monkeypatch.setattr(owner, "_read_pinned", tamper)
    with pytest.raises(owner.ReleaseHold, match="PRIVATE_POST_V2_ROLLBACK_QA_FAILED"):
        owner.preflight()


def test_candidate_fails_if_other_owner_updates_live_page(monkeypatch):
    original = owner._index
    def changed(root):
        result = original(root)
        if root == owner.LIVE:
            result["commercial.html"] = "9" * 64
        return result
    monkeypatch.setattr(owner, "_index", changed)
    with pytest.raises(owner.ReleaseHold, match="659_LIVE_OR_662_STAGED_FULL_HASH_DRIFT"):
        owner.preflight()


def test_candidate_fails_if_staged_five_file_payload_drifts(monkeypatch):
    original = owner._index
    def changed(root):
        result = original(root)
        if root == owner.PRIVATE / "out":
            result["predictive-revenue.html"] = "0" * 64
        return result
    monkeypatch.setattr(owner, "_index", changed)
    with pytest.raises(owner.ReleaseHold, match="659_LIVE_OR_662_STAGED_FULL_HASH_DRIFT"):
        owner.preflight()


def test_candidate_fails_if_consent_is_omitted(monkeypatch):
    orig = owner._Markup
    class MissingConsent(orig):
        def feed(self, text):
            super().feed(text)
            self.consent = 0
    monkeypatch.setattr(owner, "_Markup", MissingConsent)
    with pytest.raises(owner.ReleaseHold, match="ORIGINAL_INTAKE_CONSENT_OR_ASSETS_NOT_PRESERVED"):
        owner.preflight()


def test_approval_receipt_must_be_separately_pinned():
    assert owner.APPROVAL_SHA256 is None
    assert not owner.APPROVAL.exists()
    with pytest.raises(owner.ReleaseHold, match="SEPARATE_SAAS_FOUNDER_APPROVAL_NOT_YET_RECORDED"):
        owner.require_separate_founder_approval()
