"""Photo-backed V8 Chicago design: source rights, SHA and non-publication."""
import json
from pathlib import Path
import pytest

from empire_os.microsite_cinematic_background import chicago_owner_photo_data_uri
from empire_os.predictive_microsite_factory import build_candidate


def test_missing_photo_is_optional_in_default_nonpublishing_review(monkeypatch):
    monkeypatch.delenv("EMPIRE_MICROSITE_CHICAGO_HERO_PHOTO", raising=False)
    assert chicago_owner_photo_data_uri() is None


def test_photo_fails_closed_when_missing_or_tampered(tmp_path, monkeypatch):
    target = tmp_path / "city.webp"
    monkeypatch.setenv("EMPIRE_MICROSITE_CHICAGO_HERO_PHOTO", str(target))
    with pytest.raises(ValueError, match="regular file"):
        chicago_owner_photo_data_uri()
    target.write_bytes(b"RIFF" + b"\x00" * 4 + b"WEBP" + b"x" * 30000)
    with pytest.raises(ValueError, match="rights/hash"):
        chicago_owner_photo_data_uri()
    symlink = tmp_path / "photo-link.webp"
    symlink.symlink_to(target)
    monkeypatch.setenv("EMPIRE_MICROSITE_CHICAGO_HERO_PHOTO", str(symlink))
    with pytest.raises(ValueError, match="regular file"):
        chicago_owner_photo_data_uri()


def test_staged_photo_requires_credit_and_keeps_launch_held(monkeypatch):
    import empire_os.predictive_microsite_factory as factory
    brand = {
        "colour_tokens": {"deep_navy": "#01091C", "cobalt": "#005AFF",
                          "electric_cyan": "#02C7FE", "ice": "#E7F1FD",
                          "slate": "#8EA1BF"}
    }
    monkeypatch.setattr(factory, "_canonical_brand_contract", lambda: brand)
    monkeypatch.setattr(factory, "_original_brand_image", lambda: (
        "data:image/png;base64,aGVsbG8=", "b" * 64
    ))
    monkeypatch.setattr(factory, "chicago_owner_photo_data_uri", lambda: (
        "data:image/webp;base64,aGVsbG8="
    ))
    spec = json.loads((Path(__file__).with_name(
        "fixtures") / "chicago_city_roofing_official_research_pilot_20261027.json").read_text())["candidates"][0]
    review, html = build_candidate(spec)
    assert review["chicago_photographic_background_used"] is True
    assert len(review["chicago_photographic_background_sha256"]) == 64
    assert 'data:image/webp;base64,' in html
    assert 'Gael D / Unsplash' in html
    assert 'https://unsplash.com/license' in html
    assert review["status"] == "HOLD_EVIDENCE"
    assert review["copy_audit"]["score"] == 5
    assert review["publishing_enabled"] is False
    assert "<form" not in html.lower()
    assert "noindex,nofollow,noarchive" in html
    spec["site_kind"] = "market_report"
    other, other_html = build_candidate(spec)
    assert other["chicago_photographic_background_used"] is False
    assert "data:image/webp;base64," not in other_html
