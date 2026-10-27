"""V10: substantial research-section visual continuity, not fake data."""
import json
from pathlib import Path
import pytest
from empire_os.microsite_cinematic_background import chicago_research_depth_v10_css
from empire_os.predictive_microsite_factory import build_candidate

PILOT = Path(__file__).with_name("fixtures") / "chicago_city_roofing_official_research_pilot_20261027.json"


def test_research_background_uses_existing_canonical_city_asset_only():
    css = chicago_research_depth_v10_css()
    assert "#research-method::before" in css
    assert "#research-method::after" in css
    assert "var(--chicago-city-image)" in css
    assert ".research-signal-strip" in css
    assert "@media(max-width:760px)" in css
    assert "@media(min-width:2560px)" in css
    assert "http://" not in css and "https://" not in css
    assert "<script" not in css


def test_research_depth_keeps_original_claims_held(monkeypatch):
    import empire_os.predictive_microsite_factory as factory
    monkeypatch.setattr(factory,"_canonical_brand_contract",lambda:{"colour_tokens":{
        "deep_navy":"#01091C","cobalt":"#005AFF","electric_cyan":"#02C7FE",
        "ice":"#E7F1FD","slate":"#8EA1BF"}})
    monkeypatch.setattr(factory,"_original_brand_image",
                        lambda:("data:image/png;base64,aGVsbG8=", "f"*64))
    monkeypatch.setattr(factory,"chicago_owner_photo_data_uri",
                        lambda:"data:image/webp;base64,Y2l0eQ==")
    monkeypatch.setattr(factory,"chicago_worker_research_photo_data_uri",
                        lambda:"data:image/webp;base64,d29ya2Vy")
    monkeypatch.setattr(factory,"chicago_4k_photo_asset_validated",lambda:True)
    record, html = build_candidate(json.loads(PILOT.read_text())["candidates"][0])
    assert "Original reference notes" in html
    assert "Official research pathways" in html
    assert "Research only · no sales claims" in html
    assert html.count("Y2l0eQ==") == 1
    assert "#research-method::before" in html
    assert "background-image:linear-gradient(" in html
    assert "var(--chicago-city-image)" in html
    assert record["copy_audit"]["score"] == 5
    assert record["status"] == "HOLD_EVIDENCE"
    assert record["publishing_enabled"] is False
    assert len(record["visual_qa"]["original_brand_logo_sha256"]) == 64
    assert "<form" not in html.lower()
    assert "<script" not in html.lower()


def test_only_chicago_gets_cinematic_research_treatment(monkeypatch):
    import empire_os.predictive_microsite_factory as factory
    monkeypatch.setattr(factory,"_canonical_brand_contract",lambda:{"colour_tokens":{
        "deep_navy":"#01091C","cobalt":"#005AFF","electric_cyan":"#02C7FE",
        "ice":"#E7F1FD","slate":"#8EA1BF"}})
    monkeypatch.setattr(factory,"_original_brand_image",
                        lambda:("data:image/png;base64,aGVsbG8=", "f"*64))
    record=json.loads(PILOT.read_text())["candidates"][0]
    record["site_kind"]="market_report"
    output, html=build_candidate(record)
    assert "#research-method::before" not in html
    assert "Research only · no sales claims" not in html
    assert output["publishing_enabled"] is False
