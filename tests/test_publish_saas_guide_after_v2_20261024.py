"""Owner release tests; no live writes or privileged operations."""
import json
from pathlib import Path

import pytest

from scripts import publish_saas_guide_after_v2_20261024 as owner


def test_real_pinned_post_v2_preflight_is_readonly_and_explicitly_approved():
    p = owner.preflight()
    assert p["status"] == "SAAS_659_TO_662_FOUNDER_APPROVED_FRESH_ROOT_BACKUP_REQUIRED"
    assert p["separate_founder_approval_recorded"] is True
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


def test_approval_receipt_is_pinned_to_exact_five_files():
    assert owner.APPROVAL.exists()
    record = owner.require_separate_founder_approval()
    assert owner.APPROVAL_SHA256 == "92f241fa47a6844ad1df718a3ed2ce81c4bb201c8831a213d74031857d3c2083"
    assert record["approval_source"] == "FOUNDER_EXPLICIT_CHAT_APPROVAL_20261024"
    assert record["scope"] == list(owner.PAGE_FILES) + sorted(
        owner._read_pinned(owner.CANDIDATE)["new_hashed_assets"])
    assert record["original_website_owner_root_backup_required"] is True
    assert record["full_site_sync_approved"] is False
    assert record["other_aeo_release_approved"] is False
    assert record["release_completed"] is False


def test_candidate_requires_exact_browser_cta_evidence(monkeypatch):
    original = owner._read_pinned
    def tamper(path):
        value = original(path)
        if path == owner.CTA_QA:
            value["checks"][0]["form"]["requiredConsentIsUnchecked"] = False
        return value
    monkeypatch.setattr(owner, "_read_pinned", tamper)
    with pytest.raises(owner.ReleaseHold, match="PRIVATE_FIRST_PARTY_CTA_BROWSER_QA_FAILED"):
        owner.preflight()


def test_candidate_requires_both_genuine_form_destinations(monkeypatch):
    original = owner._read_pinned
    def tamper(path):
        value = original(path)
        if path == owner.CTA_QA:
            value["checks"][1]["landed_path"] = "/buy"
        return value
    monkeypatch.setattr(owner, "_read_pinned", tamper)
    with pytest.raises(owner.ReleaseHold, match="PRIVATE_FIRST_PARTY_CTA_BROWSER_QA_FAILED"):
        owner.preflight()


def test_approval_digest_tampering_holds_without_root_or_backup(monkeypatch):
    monkeypatch.setattr(owner, "APPROVAL_SHA256", "0" * 64)
    with pytest.raises(owner.ReleaseHold, match="SAAS_APPROVAL_RECEIPT_SHA_DRIFT"):
        owner.require_separate_founder_approval()


@pytest.mark.parametrize("change", [
    {"scope": ["predictive-revenue.html"]},
    {"full_site_sync_approved": True},
    {"other_aeo_release_approved": True},
    {"original_website_owner_root_backup_required": False},
    {"approval_source": "FOUNDER_APPROVED_SOME_OTHER_RELEASE"},
])
def test_wrong_scope_or_extra_permissions_fail_closed(tmp_path, monkeypatch, change):
    from hashlib import sha256
    forged = json.loads(owner.APPROVAL.read_text())
    forged.update(change)
    trial = tmp_path / "wrong_release_approval.json"
    trial.write_text(json.dumps(forged, sort_keys=True) + "\n")
    monkeypatch.setattr(owner, "APPROVAL", trial)
    monkeypatch.setattr(owner, "APPROVAL_SHA256", sha256(trial.read_bytes()).hexdigest())
    with pytest.raises(owner.ReleaseHold, match="SAAS_FOUNDER_APPROVAL_WRONG_SCOPE"):
        owner.require_separate_founder_approval()


def test_publication_flag_not_implied_by_founder_approval(capsys):
    code = owner.main(["--preflight"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["separate_founder_approval_recorded"] is True
    assert out["verified_root_backup_exists"] is False
    assert out["public_site_mutated"] is False
    assert "FRESH_ROOT_BACKUP_REQUIRED" in out["status"]
