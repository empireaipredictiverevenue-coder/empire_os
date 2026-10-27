"""V9 checks for LinkedIn-inspired 4K Chicago page and exact media provenance.

The tests never write SEO/site/CRM data and do not mistake image staging
for a release, lead, source-approved forecast or payable transaction.
"""
from pathlib import Path
import json
import pytest

from empire_os.microsite_cinematic_background import (
    chicago_4k_photo_asset_validated, chicago_worker_research_photo_data_uri,
    chicago_native_4k_layout_css,
)
from empire_os.predictive_microsite_factory import build_candidate

PILOT = Path(__file__).with_name("fixtures") / "chicago_city_roofing_official_research_pilot_20261027.json"


def test_4k_master_and_illustrative_photo_fail_closed(tmp_path, monkeypatch):
    target = tmp_path / "master.webp"
    target.write_bytes(b"RIFF" + b"x"*4 + b"WEBP" + b"broken" * 4000)
    monkeypatch.setenv("EMPIRE_MICROSITE_CHICAGO_NATIVE_4K_PHOTO", str(target))
    with pytest.raises(ValueError, match="digest"):
        chicago_4k_photo_asset_validated()
    monkeypatch.setenv("EMPIRE_MICROSITE_CHICAGO_RESEARCH_WORKER_PHOTO", str(target))
    with pytest.raises(ValueError, match="digest"):
        chicago_worker_research_photo_data_uri()
    target.unlink()
    with pytest.raises(ValueError, match="regular file"):
        chicago_4k_photo_asset_validated()


def test_canonical_chicago_photo_features_are_site_review_not_live_claims(monkeypatch):
    import empire_os.predictive_microsite_factory as f
    brand = {"colour_tokens": {
        "deep_navy": "#01091C", "cobalt": "#005AFF",
        "electric_cyan": "#02C7FE", "ice": "#E7F1FD", "slate": "#8EA1BF",
    }}
    monkeypatch.setattr(f, "_canonical_brand_contract", lambda: brand)
    monkeypatch.setattr(f, "_original_brand_image",
                        lambda: ("data:image/png;base64,aGVsbG8=", "0"*64))
    monkeypatch.setattr(f, "chicago_owner_photo_data_uri",
                        lambda: "data:image/webp;base64,Y2l0eQ==")
    monkeypatch.setattr(f, "chicago_worker_research_photo_data_uri",
                        lambda: "data:image/webp;base64,d29ya2Vy")
    monkeypatch.setattr(f, "chicago_4k_photo_asset_validated", lambda: True)
    src = json.loads(PILOT.read_text())["candidates"][0]
    packet, html = build_candidate(src)
    assert packet["four_k_original_asset_available_for_site_owner"] is True
    assert packet["illustrative_roofing_photo_used"] is True
    assert packet["status"] == "HOLD_EVIDENCE"
    assert packet["publishing_enabled"] is False
    assert packet["copy_audit"]["score"] == 5
    assert html.count("research-visual-hero") >= 2
    assert 'class="research-visual-hero photo-field"' in html
    assert 'class="research-visual-hero photo-city"' in html
    assert "Illustrative roofing photo · Houston, TX" in html
    assert "Chicago River · source-backed cityscape" in html
    assert "Zohair Mirza / Unsplash" in html
    assert "original source investigation" in html.lower()
    assert "repeat(3,minmax(0,1fr))" in html
    assert "@media(min-width:2560px)" in html
    assert "max-width:3060px" in html
    assert 'var(--chicago-city-image)' in html
    assert html.count("Y2l0eQ==") == 1  # city embedded once, reused as CSS var
    assert "aGVsbG8=" in html
    assert 'name="robots" content="noindex,nofollow,noarchive"' in html
    assert "<form" not in html.lower()
    assert "<script" not in html.lower()


def test_no_roofer_asset_does_not_autogenerate_photos_or_outreach(monkeypatch):
    import empire_os.predictive_microsite_factory as f
    monkeypatch.setattr(f, "_canonical_brand_contract", lambda: {
        "colour_tokens": {
            "deep_navy": "#01091C", "cobalt": "#005AFF",
            "electric_cyan": "#02C7FE", "ice": "#E7F1FD", "slate": "#8EA1BF"
        }
    })
    monkeypatch.setattr(f, "_original_brand_image",
                        lambda: ("data:image/png;base64,aGVsbG8=", "0"*64))
    monkeypatch.setattr(f, "chicago_owner_photo_data_uri", lambda: None)
    monkeypatch.setattr(f, "chicago_worker_research_photo_data_uri", lambda: None)
    monkeypatch.setattr(f, "chicago_4k_photo_asset_validated", lambda: False)
    src = json.loads(PILOT.read_text())["candidates"][0]
    packet, html = build_candidate(src)
    assert packet["four_k_original_asset_available_for_site_owner"] is False
    assert packet["illustrative_roofing_photo_used"] is False
    assert 'class="research-visual-hero photo-field"' not in html
    assert packet["publishing_enabled"] is False
    assert packet["status"] == "HOLD_EVIDENCE"


def test_4k_layout_uses_wide_adaptive_scales_without_js():
    css = chicago_native_4k_layout_css()
    assert "@media(min-width:2560px)" in css
    assert ".wrap {max-width:3060px" in css
    assert ".research-visual-hero {min-height:620px" in css
    assert "3840" not in css  # not a fixed-width-only screenshot
    assert "<script" not in css
