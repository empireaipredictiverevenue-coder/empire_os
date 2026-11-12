from fastapi.testclient import TestClient
from empire_os.public_gateway import app
from empire_os.website_designos_roofing_guard import FROZEN_ROOFING_DESIGN_STATE

client = TestClient(app)

def test_legacy_page_continues_online_without_design_approval():
    assert FROZEN_ROOFING_DESIGN_STATE == "LEGACY_LIVE_VISUALLY_REJECTED"
    r = client.get("/roofing")
    assert r.status_code == 200
    assert "Roof Replacement" in r.text
    assert "roofing-homeowner-guides" in r.text

def test_designos_overrides_unreviewed_website_change(monkeypatch):
    monkeypatch.setattr(
        "empire_os.website_designos_roofing_guard.frozen_roofing_page_body",
        lambda _root: None,
    )
    r = client.get("/roofing")
    assert r.status_code == 404
    assert r.json()["error"] == "roofing_designos_visual_release_hold"
    assert r.headers.get("cache-control") == "no-store"
    assert client.get("/").status_code == 200
