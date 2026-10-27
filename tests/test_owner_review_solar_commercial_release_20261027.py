"""Non-root, disposable-only owner release contract tests."""
from pathlib import Path
import json
import shutil

import pytest
from scripts import owner_review_solar_commercial_release_20261027 as release


def test_preflight_readonly_and_exact_scope():
    r = release.candidate()  # historical bytes still inspectable, never releasable
    assert len(r["baseline"]) == 700
    assert len(r["after"]) == 710
    assert (len(r["replacements"]), len(r["additions"])) == (10,10)
    with pytest.raises(release.OwnerReleaseHold, match="FOUNDER_REJECTED_PREVIOUS_V2_BRANDING"):
        release.preflight()


def test_root_only_apply_rejects_regular_account(monkeypatch):
    monkeypatch.setattr(release.os,"geteuid",lambda:1000)
    with pytest.raises(release.OwnerReleaseHold, match="FOUNDER_REJECTED_PREVIOUS_V2_BRANDING"):
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
    # Backup and old founder approval cannot override later explicit rejection.
    with pytest.raises(release.OwnerReleaseHold,match="FOUNDER_REJECTED_PREVIOUS_V2_BRANDING"):
        release.preflight()
    assert release.PUBLISH_FLAG.startswith("--apply-exact-owner-approved-")
    assert release.OWNER_APPROVAL!=release.ROOT_RECEIPT
    assert release.OWNER_APPROVAL.parent==release.BACKUP_DIR



def test_exact_founder_approval_is_cryptographically_pinned():
    assert release.sha(release.FOUNDER_RECEIPT) == release.EXPECTED_FOUNDER_RECEIPT_SHA
    a = release.read_json(release.FOUNDER_RECEIPT)
    m = release.read_json(release.MANIFEST)
    assert a["candidate_manifest_sha256"] == release.EXPECTED_MANIFEST_SHA
    assert a["source_commit"] == release.SOURCE_COMMIT
    assert a["screenshot_sha256"] == m["browser_review_screenshots_sha256"]
    assert a["founder_approval_for_exact_visual_copy_pricing"] is True
    assert a["publication_authorized_now"] is False
    # Historical approval is real but no longer effective for publication.
    with pytest.raises(release.OwnerReleaseHold,match="FOUNDER_REJECTED_PREVIOUS_V2_BRANDING"):
        release.preflight()


def test_mismatched_founder_approval_sha_fails_closed(monkeypatch):
    monkeypatch.setattr(release, "EXPECTED_FOUNDER_RECEIPT_SHA", "0" * 64)
    with pytest.raises(release.OwnerReleaseHold, match="EXACT_FOUNDER_VISUAL_APPROVAL_RECEIPT_CHANGED"):
        release.candidate()



def test_public_readback_succeeds_only_with_all_18_exact_get_hashes(monkeypatch):
    m=release.read_json(release.MANIFEST)
    baseline=release.read_json(release.SOURCE_INVENTORY)["baseline_sha256"]
    final=baseline | {x:y["proposed_sha256"] for x,y in (m["targets"] | m["route_data_sidecars"]).items()} | m["added_assets_sha256"]
    data={}
    for route, file in [
        ("/commercial","commercial.html"),("/industries/solar","industries/solar.html"),
        ("/","index.html"),("/buy","buy.html"),("/industries","industries.html"),
        ("/industries/hvac","industries/hvac.html"),
        ("/predictive-revenue","predictive-revenue.html"),("/trust","trust.html"),
    ]:
        # sha() is real bytes; return immutable exact proposed/original local bytes.
        path=(release.PACKET/"proposed_site"/file) if file in m["targets"] else release.LIVE/file
        data[route]=path.read_bytes()
    for file in m["added_assets_sha256"]:
        data["/"+file]=(release.PACKET/"proposed_site"/file).read_bytes()
    assert len(data)==18
    monkeypatch.setattr(release,"site_inventory",lambda root:final)
    # Offline-only synthetic legacy readback helper can still be evaluated.
    monkeypatch.setattr(release,"_require_original_v2_brand_still_approved",lambda:None)
    result=release.public_readback(fetch=lambda route:data[route])
    assert result["status"]=="PUBLIC_HTTPS_EXACT_SOLAR_COMMERCIAL_V2_18_GET_READBACK_PASS"
    assert result["public_gets_only"] is True and result["http_gets"]==18


def test_public_readback_rejects_old_version_and_asset_mismatch(monkeypatch):
    # Test the exact underlying probe with a bypass ONLY in isolated test scope.
    monkeypatch.setattr(release,"_require_original_v2_brand_still_approved",lambda:None)
    # Old live site must NOT be reported as released.
    with pytest.raises(release.OwnerReleaseHold,match="ORIGINAL_SITE_NOT_PUBLISHED_EXACT_710"):
        release.public_readback(fetch=lambda route:b"NO_EXTERNAL_HTTP_PERFORMED")
    m=release.read_json(release.MANIFEST)
    base=release.read_json(release.SOURCE_INVENTORY)["baseline_sha256"]
    final=base | {x:y["proposed_sha256"] for x,y in (m["targets"] | m["route_data_sidecars"]).items()} | m["added_assets_sha256"]
    monkeypatch.setattr(release,"site_inventory",lambda root:final)
    with pytest.raises(release.OwnerReleaseHold,match="PUBLIC_HTTPS_NEW_HTML_MISMATCH"):
        release.public_readback(fetch=lambda route:b"WRONG_BYTES")



def test_original_v2_release_remains_terminally_blocked_by_founder_rebranding():
    assert release.sha(release.BRAND_SUPERSESSION)==release.EXPECTED_BRAND_SUPERSESSION_SHA
    h=release.read_json(release.BRAND_SUPERSESSION)
    assert h["previous_candidate_manifest_sha256"]==release.EXPECTED_MANIFEST_SHA
    assert h["previous_candidate_publisher_must_fail_closed"] is True
    for action in (release.preflight,release.apply,release.public_readback):
        with pytest.raises(release.OwnerReleaseHold,match="FOUNDER_REJECTED_PREVIOUS_V2_BRANDING"):
            action()
