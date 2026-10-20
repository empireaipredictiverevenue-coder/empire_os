"""Offline safety regression for staged flagship and existing public routes."""
from pathlib import Path
import json

import pytest

from scripts import review_flagship_full_export_union_20261020 as release


def _case(tmp_path):
    live = tmp_path / "live"
    stage = tmp_path / "stage"
    live.mkdir()
    stage.mkdir()
    files = {}
    for i in range(132):
        files[f"_next/static/chunks/stage_{i:03}.js"] = f"synthetic_stage_{i}".encode()
    files.update({
        "index.html": b'<html><script src="/_next/static/chunks/stage_001.js"></script></html>',
        "buy.html": b'<html><script src="/_next/static/chunks/stage_002.js"></script></html>',
        "commercial.html": b'<html><script src="/_next/static/chunks/stage_003.js"></script></html>',
    })
    for name, value in files.items():
        p = stage / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(value)
    for name, value in {
        "buy.html": b"<html>old buyer export</html>",
        "about.html": b'<html><script src="/_next/static/chunks/old_about.js"></script></html>',
        "_next/static/chunks/old_about.js": b"synthetic old script",
    }.items():
        p = live / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(value)
    source = tmp_path / "source"
    source.mkdir()
    manifest = tmp_path / "source_manifest.json"
    manifest.write_text('{"source":"synthetic"}')
    return live, stage, source, manifest


def test_private_union_retains_original_routes_and_approved_new_pages(tmp_path, monkeypatch):
    live, stage, source, manifest = _case(tmp_path)
    monkeypatch.setattr(release, "_require_original_stage", lambda *_: None)
    before = release._file_index(live)
    out = tmp_path / "private" / "out"
    proof = release._build_union(
        out, live=live, stage=stage, source=source, stage_manifest=manifest
    )
    assert proof["status"] == "PRIVATE_MIXED_GENERATION_STATIC_CANDIDATE_ASSEMBLED"
    assert proof["summary"]["combined_file_count"] == 137
    assert proof["summary"]["retained_live_only_html"] == ["about.html"]
    assert (out/"about.html").read_bytes() == (live/"about.html").read_bytes()
    assert (out/"buy.html").read_bytes() == (stage/"buy.html").read_bytes()
    assert release._file_index(live) == before
    assert proof["new_public_release_authorized"] is False
    assert proof["mixed_next_build_routing_navigation_review_required"] is True
    assert proof["legacy_unreviewed_routes_included"] is True
    receipt = json.loads((out.parent/"RELEASE_CANDIDATE_RECEIPT.json").read_text())
    assert receipt["static_file_sha256"]


def test_repeat_candidate_prepare_does_not_modify_existing_file(tmp_path, monkeypatch):
    live, stage, source, manifest = _case(tmp_path)
    monkeypatch.setattr(release, "_require_original_stage", lambda *_: None)
    out = tmp_path / "private" / "out"
    release._build_union(out, live=live, stage=stage, source=source, stage_manifest=manifest)
    with pytest.raises(release.ReleaseHold, match="RELEASE_CANDIDATE_ALREADY_EXISTS"):
        release._build_union(out, live=live, stage=stage, source=source, stage_manifest=manifest)
    assert (out/"buy.html").read_bytes() == (stage/"buy.html").read_bytes()


def test_missing_legacy_dependency_causes_explicit_release_hold(tmp_path, monkeypatch):
    live, stage, source, manifest = _case(tmp_path)
    (live/"_next/static/chunks/old_about.js").unlink()
    monkeypatch.setattr(release, "_require_original_stage", lambda *_: None)
    with pytest.raises(release.ReleaseHold, match="HTML_REFERENCES_MISSING_STATIC_ASSETS"):
        release._build_union(
            tmp_path/"private"/"out",
            live=live, stage=stage, source=source, stage_manifest=manifest
        )


def test_symlink_in_public_export_fails_before_any_stage_copy(tmp_path, monkeypatch):
    live, stage, source, manifest = _case(tmp_path)
    (live/"symlink_to_buy").symlink_to(live/"buy.html")
    monkeypatch.setattr(release, "_require_original_stage", lambda *_: None)
    with pytest.raises(release.ReleaseHold, match="UNREVIEWED_STATIC_SYMLINK"):
        release._build_union(
            tmp_path/"private"/"out",
            live=live, stage=stage, source=source, stage_manifest=manifest
        )
    assert not (tmp_path/"private"/"out").exists()


def test_stage_missing_or_unexpected_count_fails_closed():
    with pytest.raises(release.ReleaseHold, match="UNEXPECTED_STAGE_FILE_COUNT"):
        release.summarize_indexes(
            {"buy.html": ("a", 5)},
            {"buy.html": ("b", 4), "index.html": ("c", 4)}
        )


def test_never_accept_live_root_as_candidate_target(tmp_path, monkeypatch):
    live, stage, source, manifest = _case(tmp_path)
    monkeypatch.setattr(release, "_require_original_stage", lambda *_: None)
    with pytest.raises(release.ReleaseHold, match="RELEASE_CANDIDATE_ALREADY_EXISTS"):
        release._build_union(
            live, live=live, stage=stage, source=source, stage_manifest=manifest
        )


def test_private_receipt_detects_tamper_and_does_not_reapprove(tmp_path, monkeypatch):
    live, stage, source, manifest = _case(tmp_path)
    monkeypatch.setattr(release, "_require_original_stage", lambda *_: None)
    out = tmp_path/"candidate"/"out"
    release._build_union(out, live=live, stage=stage, source=source, stage_manifest=manifest)
    # Fixed 632-file production check is deliberately stricter than fixture.
    with pytest.raises(release.ReleaseHold, match="PRIVATE_RECEIPT_FILE_INTEGRITY_HOLD"):
        release._verify_private_candidate(out)
    (out/"buy.html").write_bytes(b"<html>tampered</html>")
    with pytest.raises(release.ReleaseHold, match="PRIVATE_RECEIPT_FILE_INTEGRITY_HOLD"):
        release._verify_private_candidate(out)
    assert (live/"buy.html").read_bytes() == b"<html>old buyer export</html>"


def test_private_receipt_untrusted_authority_is_rejected(tmp_path):
    out = tmp_path/"private"/"out"
    out.mkdir(parents=True)
    (out.parent/"RELEASE_CANDIDATE_RECEIPT.json").write_text(
        json.dumps({"schema_version":release.SCHEMA,
                    "status":"PRIVATE_MIXED_GENERATION_STATIC_CANDIDATE_ASSEMBLED",
                    "candidate_integrity_verified":True,
                    "new_public_release_authorized":True,
                    "public_files_modified":False,
                    "mixed_next_build_routing_navigation_review_required":True,
                    "static_file_sha256":{}})
    )
    with pytest.raises(release.ReleaseHold, match="PRIVATE_RECEIPT_AUTHORITY_HOLD"):
        release._verify_private_candidate(out)
