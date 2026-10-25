"""Fail-closed test suite for read-only paired SaaS route release review."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts import review_saas_evidence_release_candidate_20261025 as qa


def fixture():
    old = {
        "predictive-revenue.html": "a",
        "predictive-revenue.txt": "b",
        "index.html": "c",
    }
    new = {
        **old,
        "predictive-revenue.html": "A",
        "predictive-revenue.txt": "B",
        "_next/static/chunks/app/predictive-revenue/page-119dcf00a0b5a51e.js": "d",
    }
    manifest = {
        "schema_version": "empire.saas.offline_single_route_union.v1",
        "status": "OFFLINE_PAIRED_HTML_RSC_UNION_CANDIDATE_PREPARED_NOT_PUBLISHED",
        "release_owner_approved": False,
        "site_published": False,
        "live_site_mutated": False,
        "money_or_outbound_touched": False,
        "public_catalogue_fixture_in_candidate": False,
        "replacement_routes": sorted(qa.REPLACE),
        "previously_retained_stale_rsc_corrected": True,
        "changed_other_old_files": 0,
        "approved_live_file_count": 3,
        "candidate_file_count": 4,
        "added_static_assets": [
            {
                "path": "_next/static/chunks/app/predictive-revenue/page-119dcf00a0b5a51e.js",
                "sha256": "d",
            }
        ],
        "prior_html_sha256": "a",
        "candidate_html_sha256": "A",
        "original_rsc_sha256": "b",
        "candidate_rsc_sha256": "B",
        "candidate_inventory_sha256": qa.index_digest(new),
    }
    return old, new, manifest


def assert_small_pass(old, new, m):
    return qa.validated_scope(old, new, m, live_count=3,
                              union_count=4, added_count=1)


def test_exact_two_payloads_and_new_only_assets_allowed():
    old, new, manifest = fixture()
    report = assert_small_pass(old, new, manifest)
    assert report["replacement_files"] == sorted(qa.REPLACE)
    assert report["unchanged_original_files"] == 1
    assert report["added_assets"] == [
        "_next/static/chunks/app/predictive-revenue/page-119dcf00a0b5a51e.js"]


@pytest.mark.parametrize("field,value", [
    ("release_owner_approved", True),
    ("site_published", True),
    ("live_site_mutated", True),
    ("money_or_outbound_touched", True),
    ("public_catalogue_fixture_in_candidate", True),
    ("status", "APPROVED_TO_SEND"),
    ("changed_other_old_files", 1),
    ("previously_retained_stale_rsc_corrected", False),
    ("candidate_rsc_sha256", "fake"),
    ("original_rsc_sha256", "fake"),
    ("candidate_inventory_sha256", "fake"),
    ("replacement_routes", ["predictive-revenue.html"]),
])
def test_permission_spoof_stale_route_or_manifest_drift_rejected(field,value):
    old, new, manifest = fixture()
    manifest[field] = value
    with pytest.raises(qa.SitePreflightHold):
        assert_small_pass(old, new, manifest)


def test_old_rsc_pair_still_present_must_fail():
    old, new, m = fixture()
    new["predictive-revenue.txt"] = old["predictive-revenue.txt"]
    with pytest.raises(qa.SitePreflightHold, match="DELTA"):
        assert_small_pass(old, new, m)


def test_unrelated_existing_file_must_not_change():
    old, new, m = fixture()
    new["index.html"] = "UNEXPECTED"
    with pytest.raises(qa.SitePreflightHold, match="DELTA"):
        assert_small_pass(old, new, m)


def test_non_static_new_file_must_not_be_added():
    old, new, m = fixture()
    new.pop("_next/static/chunks/app/predictive-revenue/page-119dcf00a0b5a51e.js")
    new["v1/checkout/predictive-revenue/products"] = "FAKE_CATALOGUE"
    with pytest.raises(qa.SitePreflightHold, match="STATIC_SCOPE"):
        assert_small_pass(old, new, m)


def test_asset_checksum_disagreement_fails():
    old, new, m = fixture()
    m["added_static_assets"][0]["sha256"] = "wrong"
    with pytest.raises(qa.SitePreflightHold, match="ASSET_RECEIPT"):
        assert_small_pass(old, new, m)


def test_resource_integrity_and_old_chunk_rejected(tmp_path):
    page = tmp_path / "predictive-revenue.html"
    rsc = tmp_path / "predictive-revenue.txt"
    rel = "static/chunks/app/predictive-revenue/page-119dcf00a0b5a51e.js"
    asset = tmp_path / "_next" / rel
    asset.parent.mkdir(parents=True)
    asset.write_text("compiled")
    page.write_text(
        '<div id="deployment-request"></div>'
        '<div id="free-evidence-sample"></div>'
        '<a href="/_next/' + rel + '">Explore a free revenue-evidence example</a>'
    )
    rsc.write_text("6:I[1,[" + rel + "]]")
    result = qa.paired_resources_valid(tmp_path)
    assert result["paired_navigation_chunk_verified"] is True
    assert result["local_browser_assets_missing"] == 0
    asset.unlink()
    with pytest.raises(qa.SitePreflightHold, match="RESOURCE_MISSING"):
        qa.paired_resources_valid(tmp_path)
    asset.write_text("compiled")
    rsc.write_text(
        "6:I[1,static/chunks/app/predictive-revenue/page-8a641c1798fea86e.js]"
    )
    with pytest.raises(qa.SitePreflightHold, match="RSC_NOT_MATCHING"):
        qa.paired_resources_valid(tmp_path)


def test_symlink_in_release_index_is_rejected(tmp_path):
    (tmp_path / "index.html").write_text("ok")
    (tmp_path / "alias.html").symlink_to(tmp_path / "index.html")
    with pytest.raises(qa.SitePreflightHold, match="SYMLINK"):
        qa.read_index(tmp_path)


def test_real_existing_release_candidate_readonly_when_present():
    if not (qa.LIVE.is_dir() and qa.CANDIDATE.is_dir() and
            qa.MANIFEST.is_file() and qa.LIVE_APPROVED_PIN.is_file()):
        pytest.skip("Requires attached EmpireOS private on-host release candidate")
    report = qa.review()
    assert report["status"] == "PRIVATE_REVIEW_PASS_PUBLICATION_HELD"
    assert report["existing_live_file_count"] == 662
    assert report["offline_candidate_file_count"] == 672
    assert report["replacement_files"] == sorted(qa.REPLACE)
    assert report["local_browser_assets_missing"] == 0
    assert report["publication_authorized"] is False
    assert report["publication_performed"] is False
