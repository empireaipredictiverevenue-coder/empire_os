"""Five source-specific Chicago evidence images; original source not rewritten."""
from hashlib import sha256
from pathlib import Path

import pytest

from empire_os import microsite_original_evidence_photos_v17 as v17


def test_five_unique_image_subjects_and_reuse_rights_are_explicit():
    assert len(v17.EVIDENCE) == 5
    assert len(v17.SOURCE_IMAGE_SHA256) == 5
    assert len(set(v17.SOURCE_IMAGE_SHA256)) == 5
    subjects = [r[0] for r in v17.EVIDENCE]
    sources = [r[4] for r in v17.EVIDENCE]
    assert len(set(subjects)) == len(set(sources)) == 5
    assert all(u.startswith("https://commons.wikimedia.org/wiki/File:") for u in sources)
    assert all(r[5].startswith("https://creativecommons.org/") for r in v17.EVIDENCE)
    assert all(r[2] and r[3] for r in v17.EVIDENCE)
    assert any("Chicago City Hall" in x[1] for x in v17.EVIDENCE)
    assert any("Oregon" in x[1] for x in v17.EVIDENCE)
    assert any("Indiana" in x[1] for x in v17.EVIDENCE)
    assert any("Chicago West Lawn" in x[1] for x in v17.EVIDENCE)


def test_exact_first_party_preview_sha_gate(tmp_path):
    with pytest.raises(ValueError, match="exact V16"):
        v17.enrich(b"<html>NOT ORIGINAL</html>", tmp_path)


def test_source_must_contain_exact_original_three_images(monkeypatch,tmp_path):
    original=b"<html><div>research</div></html>"
    monkeypatch.setattr(v17,"V16_SOURCE_SHA",sha256(original).hexdigest())
    with pytest.raises(ValueError,match="Three existing"):
        v17.enrich(original,tmp_path)


def test_real_offline_stage_integrity_when_present():
    base=Path("/home/ubuntu/empire_releases")
    source=(base/"chicago_original_owner_metadata_review_20261027"/
            "chicago_owner_review_export.html")
    images=base/"chicago_evidence_image_licence_research_20261027"
    if not source.exists() or not images.exists():
        pytest.skip("Production-private source/image fixtures not mounted")
    original=source.read_bytes()
    digest=sha256(original).hexdigest()
    assert digest==v17.V16_SOURCE_SHA
    html,receipt=v17.enrich(original,images)
    assert sha256(original).hexdigest()==digest
    assert receipt["output_html_sha256"]==sha256(html).hexdigest()
    assert len(html)<400000
    assert html.count(b'class="evidence-visual"')==5
    assert html.count(b"Read official source")==5
    assert html.count(b"data:image/png;base64,")==1
    assert html.count(b'class="wordmark"')==1
    assert html.count(b"data:image/webp;base64,")==7
    assert b"noindex,nofollow,noarchive" in html
    assert receipt["remote_image_requests"]==0
    assert receipt["live_publication"] is False
    assert receipt["brand_media_owner_signoff"] is False
    assert receipt["seo_owner_signoff"] is False
    assert len(set(x["embedded_webp_sha256"] for x in receipt["five_evidence_photos"]))==5
    for row in receipt["five_evidence_photos"]:
        assert row["source_url"].encode() in html
        assert row["license_url"].encode() in html


def test_source_photo_mutation_never_keeps_old_license_credit(monkeypatch,tmp_path):
    # Test the actual private source document when available; no live change.
    base=Path("/home/ubuntu/empire_releases")
    source=base/"chicago_original_owner_metadata_review_20261027/chicago_owner_review_export.html"
    folder=base/"chicago_evidence_image_licence_research_20261027"
    if not source.exists() or not folder.exists():
        pytest.skip("Owner-private evidence absent")
    monkeypatch.setattr(v17,"SOURCE_IMAGE_SHA256",("0"*64,)+v17.SOURCE_IMAGE_SHA256[1:])
    with pytest.raises(ValueError,match="photograph 1 does not match"):
        v17.enrich(source.read_bytes(),folder)


def test_actual_photo_replaces_the_old_decorative_placeholder():
    assert "micro::before {display:none!important}" in v17.STYLE
