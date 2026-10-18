"""Byte-exact release custody tests; never touch EmpireDB, live services or web."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path

import pytest

from empire_os.organic_live_release_integrity import (
    CODE, PAGES, audit_live_release,
)


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def fixture(tmp_path):
    repo = tmp_path / "repo"
    backup = tmp_path / "backup"
    prepared = tmp_path / "staged"
    source = tmp_path / "candidate"
    current = repo / "apps/empire-public-site/out"
    rollback = tmp_path / "original-site"
    for root in (repo, backup, prepared, source, current, rollback):
        root.mkdir(parents=True, exist_ok=True)
    added = "_next/static/chunks/brand-new.122.js"
    prior = {"index.html": b"original-home",
             "privacy.html": b"legal-notice",
             **{name: ("old:" + name).encode() for name in PAGES}}
    now = {**prior, **{name: ("new:" + name).encode() for name in PAGES},
           added: b"brand-new"}
    for root, values in ((current, now), (rollback, prior)):
        for name, value in values.items():
            file = root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(value)
    old_code = sorted(CODE)[:4]
    fresh_code = sorted(CODE)[4:]
    original_digests = {}
    for name in sorted(CODE):
        target = repo / name
        candidate = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        candidate.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(("deployed:" + name).encode())
        candidate.write_bytes(target.read_bytes())
        if name in old_code:
            old_copy = backup / name
            old_copy.parent.mkdir(parents=True, exist_ok=True)
            old_copy.write_bytes(("old:" + name).encode())
            original_digests[name] = digest(old_copy.read_bytes())
    rollback_record = {
        "site": str(rollback),
        "code": original_digests,
        "new_code": fresh_code,
    }
    receipt = {
        "status": "DEPLOYED_SMOKE_PASS",
        "payment_action": False, "outbound": False,
        "buyer_records_written": False,
        "event_release_registered": False,
        "web_pages_replaced": len(PAGES),
        "site_files_verified": len(now),
        "source_files_replaced": sorted(CODE),
        "rollback_site": str(rollback),
        "rollback_source": str(backup),
    }
    manifest = {
        "status": "PREPARED_NOT_DEPLOYED",
        "production_writes": False,
        "replaced_existing_pages": {name: digest(now[name]) for name in PAGES},
        "source_live_sha256": {name: digest(prior[name]) for name in PAGES},
        "staged_file_count": len(now),
        "additive_immutable_asset_count": 1,
    }
    for name, value in (
        ("rollback_manifest.json", rollback_record),
        ("deployment_receipt.json", receipt),
    ):
        (backup / name).write_text(json.dumps(value))
    manifest_path = prepared / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    arguments = {
        "repository": repo, "backup": backup,
        "staged_manifest": manifest_path, "site": current,
        "rollback_site": rollback, "released_source": source,
    }
    return arguments


def report(paths):
    return audit_live_release(**paths)


def test_verified_release_preserves_rollback_and_reports_unknown_metrics(tmp_path):
    paths = fixture(tmp_path)
    result = report(paths)
    assert result["status"] == "LIVE_BYTES_VERIFIED"
    assert result["issues"] == []
    for name in ("observed_visits", "accepted_campaign_events",
                 "qualified_buyers", "consented_commercial_enquiries",
                 "realised_revenue"):
        assert result[name] is None
    assert result["database_writes_performed_by_review"] is False
    assert result["live_campaign_release_verified"] is None
    assert (paths["site"] / "index.html").read_bytes() == b"original-home"


@pytest.mark.parametrize("which,expected", [
    ("source", "deployed_source_drift"),
    ("protected", "protected_site_asset_changed"),
    ("published", "published_industry_page_mismatch"),
    ("rollback", "rollback_original_page_mismatch"),
    ("receipt", "unsafe_or_unknown_release_authority"),
    ("missing_new", "additive_immutable_asset_count_mismatch"),
])
def test_release_drift_fails_closed(tmp_path, which, expected):
    paths = fixture(tmp_path)
    if which == "source":
        (paths["repository"] / sorted(CODE)[0]).write_text("edited")
    elif which == "protected":
        (paths["site"] / "index.html").write_text("tampered")
    elif which == "published":
        (paths["site"] / "commercial.html").write_text("tampered")
    elif which == "rollback":
        (paths["rollback_site"] / "commercial.html").write_text("tampered")
    elif which == "receipt":
        path = paths["backup"] / "deployment_receipt.json"
        data = json.loads(path.read_text())
        data["payment_action"] = True
        path.write_text(json.dumps(data))
    elif which == "missing_new":
        (paths["site"] / "_next/static/chunks/brand-new.122.js").unlink()
    result = report(paths)
    assert result["status"] == "HOLD_INTEGRITY_DRIFT"
    assert any(expected in msg for msg in result["issues"])


def test_unexpected_page_or_bad_release_inventory_rejected(tmp_path):
    paths = fixture(tmp_path)
    (paths["site"] / "unapproved.html").write_text("x")
    assert "unexpected_added_site_file:unapproved.html" in report(paths)["issues"]
    paths = fixture(tmp_path / "other")
    (paths["backup"] / "rollback_manifest.json").write_text("{}")
    assert "unreadable_or_invalid_release_custody" in report(paths)["issues"]


def test_symlinked_site_fails_closed(tmp_path):
    paths = fixture(tmp_path)
    (paths["site"] / "index.html").unlink()
    (paths["site"] / "index.html").symlink_to(paths["rollback_site"] / "index.html")
    assert "unreadable_or_invalid_release_custody" in report(paths)["issues"]
