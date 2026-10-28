"""Adversarial checks for the original Chicago source-to-export receipt."""
from pathlib import Path

import pytest
from empire_os import microsite_owner_evidence_chain as chain

ROOT = Path("/home/ubuntu/empire_releases")


def test_actual_original_chicago_source_to_export_chain():
    if not (ROOT / "chicago_original_owner_evidence_final_review_20261027").is_dir():
        pytest.skip("Owner's private machine source stage not mounted")
    result = chain.verify_chain(ROOT)
    assert result["status"] == "SOURCE_TO_EXPORT_AND_MEDIA_QA_PASS"
    assert result["independent_browser_stages_verified"] == 3
    assert result["five_source_image_sha256_verified"] is True
    assert result["native_4k_verified"] is True
    assert result["real_live_url"] is None
    assert result["production_writes"] == 0
    assert len(result["unverified_original_approvals"]) == 3


def test_refuses_wrong_original_source_sha(monkeypatch):
    original = chain._bytes
    def corrupt(path, max_bytes):
        data = original(path,max_bytes)
        if path.name == chain.PREVIEW and path.parent.name == "predictive_microsite_research_depth_v10_FINAL_20261027":
            return data + b"changed-after-QA"
        return data
    monkeypatch.setattr(chain,"_bytes",corrupt)
    with pytest.raises(ValueError,match="original source sha mismatch"):
        chain.verify_chain(ROOT)


def test_refuses_modified_image_with_unchanged_credit(monkeypatch):
    original=chain._bytes
    def changed(path,max_bytes):
        data=original(path,max_bytes)
        if path.name=="candidate_4.jpg":
            return data+b"altered"
        return data
    monkeypatch.setattr(chain,"_bytes",changed)
    with pytest.raises(ValueError,match="Evidence photo 4"):
        chain.verify_chain(ROOT)


def test_refuses_fake_browser_qa_pass(monkeypatch):
    original=chain._json
    def corrupt(path):
        result=original(path)
        if (path.name=="puppeteer_browser_review.json"
            and path.parent.parent.name=="chicago_original_owner_evidence_final_review_20261027"):
            result["blocked_external_requests"]=1
        return result
    monkeypatch.setattr(chain,"_json",corrupt)
    with pytest.raises(ValueError,match="Browser proof"):
        chain.verify_chain(ROOT)


def test_refuses_modified_original_browser_screenshot(monkeypatch):
    original=chain._bytes
    def changed(path,max_bytes):
        data=original(path,max_bytes)
        if path.name==f"{chain.PREVIEW[:-5]}.mobile.png" and path.parent.parent.name=="chicago_original_owner_evidence_final_review_20261027":
            return data+b"altered"
        return data
    monkeypatch.setattr(chain,"_bytes",changed)
    with pytest.raises(ValueError,match="screenshot was modified"):
        chain.verify_chain(ROOT)


def test_refuses_forged_photo_media_rights_approval(monkeypatch):
    original=chain._json
    def changed(path):
        result=original(path)
        if path.name=="five_image_provenance_receipt.json":
            result["brand_media_owner_signoff"]=True
        return result
    monkeypatch.setattr(chain,"_json",changed)
    with pytest.raises(ValueError,match="Photographic page receipt"):
        chain.verify_chain(ROOT)


def test_missing_or_symlinked_evidence_refused(tmp_path):
    with pytest.raises(ValueError,match="Evidence absent"):
        chain._bytes(tmp_path/"missing.html",400000)
    target=tmp_path/"document.html"
    target.write_bytes(b"<html>Hello</html>")
    alias=tmp_path/"alias.html"
    alias.symlink_to(target)
    with pytest.raises(ValueError,match="symlinked"):
        chain._bytes(alias,400000)
