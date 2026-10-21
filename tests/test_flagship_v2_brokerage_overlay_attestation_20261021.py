"""Fail-closed tests for one exact staged commercial first-paint delta."""
from hashlib import sha256
import json

from empire_os import flagship_v2_brokerage_overlay_attestation as owner


def _synthetic(tmp_path, monkeypatch):
    static = tmp_path / "live"
    static.mkdir()
    original = {}
    for i in range(631):
        name = f"_next/static/chunks/base-{i:04}.js"
        p = static / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(f"base-{i}".encode())
        original[name] = sha256(p.read_bytes()).hexdigest()
    commercial = static / "commercial.html"
    commercial.write_bytes(b"<html>previous safe commercial</html>")
    original["commercial.html"] = sha256(commercial.read_bytes()).hexdigest()
    receipt = tmp_path / "original.json"
    receipt.write_text(json.dumps({
        "schema_version": owner.SCHEMA,
        "status": "PRIVATE_MIXED_GENERATION_STATIC_CANDIDATE_ASSEMBLED",
        "candidate_integrity_verified": True,
        "new_public_release_authorized": False,
        "public_files_modified": False,
        "static_file_sha256": original,
    }))
    inventory = sha256(json.dumps(original,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    stage = tmp_path / "stage"
    stage.mkdir()
    commercial.write_bytes(b"<html>reviewed brokerage first paint</html>")
    (stage/"commercial.html").write_bytes(commercial.read_bytes())
    extra = {}
    for i in range(13):
        name = f"_next/static/chunks/owner-new-{i:03}.js"
        p = stage/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(f"checked-{i}".encode())
        q = static/name
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_bytes(p.read_bytes())
        extra[name] = sha256(p.read_bytes()).hexdigest()
    monkeypatch.setattr(owner, "BASE_INVENTORY", inventory)
    monkeypatch.setattr(owner, "NEW_COMMERCIAL_SHA", sha256(commercial.read_bytes()).hexdigest())
    monkeypatch.setattr(owner, "APPROVED_ADDITIONS", extra)
    return static, receipt, stage


def test_current_site_exact_v2_plus_one_approved_overlay(tmp_path, monkeypatch):
    site, receipt, stage = _synthetic(tmp_path, monkeypatch)
    assert owner.exact_v2_plus_reviewed_brokerage(site=site, receipt=receipt, stage=stage)


def test_other_main_page_changed_is_not_approved(tmp_path, monkeypatch):
    site, receipt, stage = _synthetic(tmp_path, monkeypatch)
    (site/"_next/static/chunks/base-0002.js").write_bytes(b"unauthorized")
    assert owner.exact_v2_plus_reviewed_brokerage(site=site, receipt=receipt, stage=stage) is False


def test_undeclared_asset_is_a_hard_hold(tmp_path, monkeypatch):
    site, receipt, stage = _synthetic(tmp_path, monkeypatch)
    (site/"rogue.js").write_bytes(b"unauthorized")
    assert owner.exact_v2_plus_reviewed_brokerage(site=site, receipt=receipt, stage=stage) is False


def test_missing_reviewed_asset_is_not_a_healthy_release(tmp_path, monkeypatch):
    site, receipt, stage = _synthetic(tmp_path, monkeypatch)
    (site/"_next/static/chunks/owner-new-003.js").unlink()
    assert owner.exact_v2_plus_reviewed_brokerage(site=site, receipt=receipt, stage=stage) is False


def test_staged_owner_build_tampered_refuses_attestation(tmp_path, monkeypatch):
    site, receipt, stage = _synthetic(tmp_path, monkeypatch)
    (stage/"_next/static/chunks/owner-new-003.js").write_bytes(b"tampered-stage")
    assert owner.exact_v2_plus_reviewed_brokerage(site=site, receipt=receipt, stage=stage) is False


def test_original_source_manifest_changed_is_refused(tmp_path, monkeypatch):
    site, receipt, stage = _synthetic(tmp_path, monkeypatch)
    data = json.loads(receipt.read_text())
    data["static_file_sha256"]["_next/static/chunks/base-0002.js"] = "0"*64
    receipt.write_text(json.dumps(data))
    assert owner.exact_v2_plus_reviewed_brokerage(site=site, receipt=receipt, stage=stage) is False
