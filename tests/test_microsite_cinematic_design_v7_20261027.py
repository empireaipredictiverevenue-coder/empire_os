"""Regression coverage for the founder's Chicago cinematic design direction."""
from base64 import b64decode
from pathlib import Path
import json

from empire_os.microsite_cinematic_background import (
    chicago_night_skyline_data_uri, chicago_premium_css,
)
from empire_os.predictive_microsite_factory import build_candidate

PILOT = Path(__file__).parent / "fixtures/chicago_city_roofing_official_research_pilot_20261027.json"


def _canonical(monkeypatch):
    import empire_os.predictive_microsite_factory as f
    brand = {
        "colour_tokens": {
            "deep_navy": "#01091C", "cobalt": "#005AFF",
            "electric_cyan": "#02C7FE", "ice": "#E7F1FD", "slate": "#8EA1BF",
        }
    }
    monkeypatch.setattr(f, "_canonical_brand_contract", lambda: brand)
    monkeypatch.setattr(
        f, "_original_brand_image",
        lambda: ("data:image/png;base64,aGVsbG8=", "c" * 64),
    )
    return f


def test_original_city_art_is_static_self_contained_and_illustrative():
    url = chicago_night_skyline_data_uri()
    assert url.startswith("data:image/svg+xml;base64,")
    source = b64decode(url.split(",", 1)[1]).decode("utf-8")
    assert "<svg " in source
    assert 'viewBox="0 0 1440 720"' in source
    assert "url(#windows)" in source
    assert "stop-color" in source
    assert "http://" not in source.replace('xmlns="http://www.w3.org/2000/svg"', "")
    assert not any(x in source.lower() for x in ("<script", "<image", "<foreignobject", "href=", "javascript:"))


def test_chicago_cinematic_design_only_with_canonical_brand(monkeypatch):
    _canonical(monkeypatch)
    spec = json.loads(PILOT.read_text())["candidates"][0]
    packet, html = build_candidate(spec)
    assert packet["cinematic_chicago_art_rendered"] is True
    assert "class=\"site-art\"" in html
    assert 'aria-hidden="true"' in html
    assert "class=\"hero-title-accent\"" in html
    assert "linear-gradient" in html
    assert "backdrop-filter:blur" in html
    assert "repeat(5,minmax(0,1fr))" in html
    assert "data:image/svg+xml;base64," in html
    assert all(x in html for x in ("#01091C", "#005AFF", "#02C7FE", "#E7F1FD", "#8EA1BF"))
    assert html.count("Read official source") == 5
    assert packet["copy_audit"]["score"] == 5
    assert packet["status"] == "HOLD_EVIDENCE"
    assert packet["publishing_enabled"] is False
    assert packet["visual_qa"]["brand_public_distribution_approved_by_owner"] is False
    assert '<meta name="robots" content="noindex,nofollow,noarchive">' in html
    assert "<form" not in html.lower()
    assert "<script" not in html.lower()


def test_no_chicago_skyline_on_unrelated_regions_even_with_canonical_brand(monkeypatch):
    _canonical(monkeypatch)
    spec = json.loads(PILOT.read_text())["candidates"][0]
    # A different site kind in the SAME market must not receive the
    # city-specific local-utility hero by default.
    spec["site_kind"] = "market_report"
    packet, html = build_candidate(spec)
    assert packet["cinematic_chicago_art_rendered"] is False
    assert 'class="site-art"' not in html
    assert "hero-title-accent" not in html
    assert packet["publishing_enabled"] is False


def test_cinematic_css_is_accessible_and_mobile_bounded():
    css = chicago_premium_css()
    assert "@media(max-width:540px)" in css
    assert ".grid,.decision-list {grid-template-columns:1fr" in css
    assert "overflow-x:clip" in css
    assert "var(--brand-cobalt)" not in css or "background" in css
    assert "<script" not in css
