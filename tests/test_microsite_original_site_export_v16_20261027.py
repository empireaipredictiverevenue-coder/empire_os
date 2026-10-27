"""Original ASTRA one-candidate metadata export never mutates V10 input."""
from hashlib import sha256
import pytest

from empire_os import microsite_original_site_export_v16 as owner


def source_document():
    return (
        '<!doctype html><html><head>'
        '<meta name="robots" content="noindex,nofollow,noarchive">'
        + owner.SOURCE_TITLE + owner.SOURCE_DESCRIPTION
        + '</head><body>'
        + '<div class="research-signal-strip">Research</div>'
        + owner.SOURCE_H1
        + '<img alt="Original Empire AI owner logo" src="data:image/png;base64,YQ==">'
        + '<span>Illustrative roofing photo · Houston, TX</span>'
        + '</body></html>'
    ).encode()


def test_unchanged_real_source_hash_required():
    with pytest.raises(ValueError, match="Exact original"):
        owner.prepare_chicago_original_owner_export(source_document())


def test_only_three_bounded_edits_and_original_source_immutable(monkeypatch):
    raw=source_document()
    before=raw[:]
    monkeypatch.setattr(owner,"ORIGINAL_PREVIEW_SHA",sha256(raw).hexdigest())
    html, report=owner.prepare_chicago_original_owner_export(raw)
    assert raw == before
    assert report["deterministic_edits"] == 3
    assert report["source_preview_sha256"] == sha256(raw).hexdigest()
    assert sha256(html).hexdigest() == report["owner_reviewed_html_sha256"]
    assert report["owner_approvals_granted"] is False
    assert report["public_url"] is None
    assert report["production_writes"] == 0
    assert owner.REVIEWED_TITLE.encode() in html
    assert owner.REVIEWED_DESCRIPTION.encode() in html
    assert owner.REVIEWED_H1.encode() in html
    assert b"<title><span" not in html
    assert b"noindex,nofollow,noarchive" in html
    assert b"Illustrative roofing photo" in html
    assert b"<form" not in html and b"<script" not in html


@pytest.mark.parametrize("corruption",["missing_credit","added_script","changed_headline"])
def test_export_denies_incomplete_or_unexpected_review_input(monkeypatch,corruption):
    raw=source_document()
    if corruption=="missing_credit":
        raw=raw.replace(b"Illustrative roofing photo",b"Roof photo")
    if corruption=="added_script":
        raw+=b"<script>alert('unapproved')</script>"
    if corruption=="changed_headline":
        raw=raw.replace(b"Chicago reroofing:",b"Unknown market:")
    monkeypatch.setattr(owner,"ORIGINAL_PREVIEW_SHA",sha256(raw).hexdigest())
    with pytest.raises(ValueError):
        owner.prepare_chicago_original_owner_export(raw)


def test_byte_determinism_of_owner_review_export(monkeypatch):
    raw=source_document()
    monkeypatch.setattr(owner,"ORIGINAL_PREVIEW_SHA",sha256(raw).hexdigest())
    a,receipt_a=owner.prepare_chicago_original_owner_export(raw)
    b,receipt_b=owner.prepare_chicago_original_owner_export(raw)
    assert a==b and receipt_a==receipt_b
