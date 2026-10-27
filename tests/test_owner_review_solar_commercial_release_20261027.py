"""Non-root, disposable-only owner release contract tests."""
from pathlib import Path
import json
import shutil

import pytest
from scripts import owner_review_solar_commercial_release_20261027 as release


def test_preflight_readonly_and_exact_scope():
    r = release.preflight()
    assert r["status"] == "TWO_PAGE_SCOPE_VERIFIED_ORIGINAL_OWNER_APPROVAL_REQUIRED"
    assert (r["site_files_before"], r["site_files_proposed"]) == (700, 710)
    assert (r["old_pages_replaced"], r["new_assets"]) == (10, 10)
    assert r["publication_performed"] is False
    assert r["owner_approval_verified"] is False


def test_root_only_apply_rejects_regular_account(monkeypatch):
    monkeypatch.setattr(release.os,"geteuid",lambda:1000)
    with pytest.raises(release.OwnerReleaseHold, match="ROOT_OPERATOR_ONLY"):
        release.apply()


def test_old_exact_backup_and_manifest_are_pinned():
    r=release.candidate()
    assert release.sha(release.MANIFEST)==release.EXPECTED_MANIFEST_SHA
    assert release.sha(release.SOURCE_INVENTORY)==release.EXPECTED_INVENTORY_SHA
    assert len(r["baseline"])==700
    assert len(r["after"])==710
    assert not (set(r["additions"]) & set(r["baseline"]))
    assert set(r["replacements"])<=set(r["baseline"])


def test_original_helper_exact_success_and_rollback(tmp_path):
    # Actual 700-file live copy; only the 10 scoped originals are replaceable.
    r=release.candidate()
    stage=release.PACKET/"proposed_site"
    cases=("positive","post_commit_failure")
    for case in cases:
        copy=tmp_path/case
        shutil.copytree(release.LIVE,copy)
        assert release.site_inventory(copy)==r["baseline"]
        def verify():
            assert release.site_inventory(copy)==r["after"]
            if case=="post_commit_failure":
                raise RuntimeError("INJECT_AFTER_COMPLETE_SITE_VERIFY")
        if case=="positive":
            out=release.apply_four_pages_and_eight_assets(
                live=copy,stage=stage,baseline=r["baseline"],
                replacements=r["replacements"],additions=r["additions"],
                final_probe=verify,
            )
            assert out["page_navigation_files_replaced"]==10
            assert out["new_hashed_assets_installed"]==10
            assert release.site_inventory(copy)==r["after"]
        else:
            with pytest.raises(RuntimeError,match="INJECT_AFTER_COMPLETE_SITE_VERIFY"):
                release.apply_four_pages_and_eight_assets(
                    live=copy,stage=stage,baseline=r["baseline"],
                    replacements=r["replacements"],additions=r["additions"],
                    final_probe=verify,
                )
            assert release.site_inventory(copy)==r["baseline"]
    assert release.site_inventory(release.LIVE)==r["baseline"]


def test_protected_backup_audit_requires_real_root(monkeypatch):
    monkeypatch.setattr(release.os,"geteuid",lambda:1000)
    with pytest.raises(release.OwnerReleaseHold,match="ORIGINAL_ROOT_OWNER_SESSION_REQUIRED"):
        release.verify_protected_backup(release.candidate())


def test_bad_owner_manifest_and_backup_fail_closed(tmp_path, monkeypatch):
    r=release.candidate()
    # Cannot get approval by supplying a regular temp directory instead of the
    # original root-owned private backup directory.
    monkeypatch.setattr(release.os,"geteuid",lambda:0)
    with pytest.raises(release.OwnerReleaseHold, match="ROOT_PRIVATE_SITE_RELEASE_DIRECTORY_REQUIRED"):
        release.verify_owner_and_archive(
            r,backup_dir=tmp_path,archive=tmp_path/"back.tar.gz",
            approval=tmp_path/"approval.json",
        )


def test_owner_receipt_absent_and_publication_requires_independent_attestation():
    # Backup evidence is not by itself a signoff.
    r=release.preflight()
    assert not r["owner_approval_verified"]
    assert "owner" in r["status"].lower()
    assert release.PUBLISH_FLAG.startswith("--apply-exact-owner-approved-")
    assert release.OWNER_APPROVAL!=release.ROOT_RECEIPT
    assert release.OWNER_APPROVAL.parent==release.BACKUP_DIR
