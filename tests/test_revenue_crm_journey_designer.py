"""Journey designer is a functional local editor behind existing CRM authentication."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_api import create_revenue_crm_router

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "empire_os/static/revenue_crm_journey_designer.html"
JS = ROOT / "empire_os/static/revenue_crm_journey_designer.js"


class FakeRepo:
    tenant_id = "00000000-0000-0000-0000-000000000101"
    def prospects(self, *, limit): return []
    def prospect(self, prospect_id): return None
    def buyers(self, *, limit): return []


def client(repository=None, *, resolver=None):
    app = FastAPI()
    app.include_router(create_revenue_crm_router(
        repository, resolve_authenticated_read=resolver,
    ))
    return TestClient(app)


def test_designer_is_authenticated_only_and_respects_existing_disabled_pilot():
    unavailable = client()
    for path in ("/v1/revenue-crm/journeys/designer",
                 "/v1/revenue-crm/journeys/designer.js"):
        assert unavailable.get(path).status_code == 503
    denied = client(resolver=lambda request: None)
    for path in ("/v1/revenue-crm/journeys/designer",
                 "/v1/revenue-crm/journeys/designer.js"):
        assert denied.get(path, headers={"X-Tenant-ID": FakeRepo.tenant_id,
                                        "X-Consent": "true"}).status_code == 401


def test_authenticated_designer_is_first_party_and_read_only():
    c = client(FakeRepo())
    page = c.get("/v1/revenue-crm/journeys/designer")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert page.headers["cache-control"] == "no-store"
    assert page.headers["x-content-type-options"] == "nosniff"
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert "connect-src 'self'" in page.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert "/v1/revenue-crm/journeys/designer.js" in page.text
    assert "DESIGN ONLY" in page.text
    assert '<button id="export" disabled>' in page.text
    assert '<button id="add-review" disabled>' in page.text
    assert '<button id="connect" disabled>' in page.text
    assert "cdn." not in page.text
    assert "localStorage" not in page.text
    asset = c.get("/v1/revenue-crm/journeys/designer.js")
    assert asset.status_code == 200
    assert "text/javascript" in asset.headers["content-type"]
    assert "no-store" == asset.headers["cache-control"]
    for text in ("pointerdown", "keydown", "export", "import", "refreshSegments",
                 "Canonical security gate cannot be modified",
                 "Journey cannot contain a cycle",
                 "DESIGN_ONLY", "No server changes", "structuredClone"):
        assert text in asset.text
    for forbidden in ("localStorage.", "sessionStorage.", "fetch(\"/send", "fetch(\"/execute",
                      "fetch(\"/publish", "fetch(\"/subscribe", "eval(", "innerHTML"):
        assert forbidden not in asset.text


def test_designer_graph_api_still_has_zero_authority():
    c = client(FakeRepo())
    graph = c.get("/v1/revenue-crm/journeys/blueprint")
    assert graph.status_code == 200
    g = graph.json()
    assert g["mode"] == "OBSERVE"
    assert g["execution_authority"] == "none"
    assert g["outbound_enabled"] is False
    assert g["payment_enabled"] is False
    assert g["actual_drag_drop_editor_built"] is True  # Local editor exists.
    assert g["visual_editor_route"] == "/v1/revenue-crm/journeys/designer"
    assert g["visual_editor_mode"] == "LOCAL_DESIGN_ONLY"
    assert g["workflow_server_persistence"] is False
    segments = c.get("/v1/revenue-crm/journeys/segments/preview")
    assert segments.status_code == 200
    assert segments.json()["send_authorized"] is False


def test_designer_asset_contains_no_external_scripts_or_post_mutations():
    html, js = HTML.read_text(), JS.read_text()
    assert "http://" not in html and "https://" not in html
    assert "fetch(\"/v1/revenue-crm/journeys/blueprint\"" in js
    assert "fetch(\"/v1/revenue-crm/journeys/segments/preview?limit=100\"" in js
    assert "method: \"POST\"" not in js
    assert "document.cookie" not in js
    assert "localStorage." not in js
    assert "XMLHttpRequest" not in js
