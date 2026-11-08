"""No production changes: exercises additive one-click founder CRM exchange UI."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/data_cloud_verify_ui_patch_20261108.py"
WRAPPER=ROOT/"scripts/data_cloud_verify_ui_entrypoint_20261108.py"

spec=importlib.util.spec_from_file_location("data_cloud_verify_ui_patch_test", SOURCE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def original_app():
    app=FastAPI()
    html_asset=(m.CRM_ASSETS/m.HTML_NAME).read_text()
    js_asset=(m.CRM_ASSETS/m.JS_NAME).read_bytes()
    @app.get(m.HTML_PATH)
    def html():
        return HTMLResponse(
            html_asset.replace("/v1/revenue-crm/journeys/designer.js",
                               "/v1/revenue-crm/journeys/entry.js"),
            headers={
                "Cache-Control":"no-store",
                "Pragma":"no-cache",
                "X-Content-Type-Options":"nosniff",
                "X-Frame-Options":"DENY",
                "Referrer-Policy":"no-referrer",
                "Content-Security-Policy":
                    "default-src 'none'; script-src 'self'; "
                    "style-src 'unsafe-inline'; connect-src 'self'; "
                    "base-uri 'none'; object-src 'none'; "
                    "form-action 'none'; frame-ancestors 'none'",
            })
    @app.get(m.JS_PATH)
    def js():
        return Response(js_asset,media_type="text/javascript",
            headers={"Cache-Control":"no-store",
                "X-Content-Type-Options":"nosniff",
                "Referrer-Policy":"no-referrer"})
    @app.post("/v1/revenue-crm/auth/login")
    def login():
        return {"baseline":"kept"}
    @app.post("/v1/data/auth/exchange")
    def exchange():
        return {"baseline":"kept"}
    return app


def test_source_verbatim_pins_match_real_crm_frozen_assets():
    assert hashlib.sha256((m.CRM_ASSETS/m.HTML_NAME).read_bytes()).hexdigest()==m.PINNED_HTML_SHA
    assert hashlib.sha256((m.CRM_ASSETS/m.JS_NAME).read_bytes()).hexdigest()==m.PINNED_JS_SHA


def test_exact_original_markers_single_insertion():
    html=(m.CRM_ASSETS/m.HTML_NAME).read_text()
    js=(m.CRM_ASSETS/m.JS_NAME).read_text()
    patched_html=m.patch_html(html)
    patched_js=m.patch_js(js)
    assert patched_html.count('id="verify-data-cloud"')==1
    assert patched_html.count('id="data-cloud-verify-status"')==1
    assert patched_js.count("function verifyDataCloudExchange()")==1
    assert patched_js.count('"/v1/data/auth/exchange"')==1
    assert patched_js.count('byId("verify-data-cloud").disabled = true') == 1
    assert "localStorage.setItem" not in patched_js
    assert "sessionStorage.setItem" not in patched_js
    assert "window.sessionBearer" not in patched_js
    assert "console.log(sessionBearer)" not in patched_js
    assert "credentials: \"omit\"" in patched_js
    assert "No token stored." in patched_js


def test_browser_ui_overlay_preserves_original_routes_and_csp():
    app=original_app()
    old_paths=[(route.path,tuple(sorted(route.methods)))
               for route in app.routes if getattr(route,"methods",None)]
    m.build_verified_routes(app)
    with TestClient(app) as client:
        page=client.get(m.HTML_PATH)
        js=client.get(m.JS_PATH)
        login=client.post("/v1/revenue-crm/auth/login")
        exchange=client.post("/v1/data/auth/exchange")
        assert page.status_code==200
        assert js.status_code==200
        assert login.json()=={"baseline":"kept"}
        assert exchange.json()=={"baseline":"kept"}
        assert page.text.count('id="verify-data-cloud"')==1
        assert "verifyDataCloudExchange" in js.text
        assert page.headers["cache-control"]=="no-store"
        assert js.headers["cache-control"]=="no-store"
        assert "default-src 'none'" in page.headers["content-security-policy"]
        assert "script-src 'self'" in page.headers["content-security-policy"]
        assert page.headers["x-frame-options"]=="DENY"
    final_paths=[(route.path,tuple(sorted(route.methods)))
                 for route in app.routes if getattr(route,"methods",None)]
    assert final_paths.count((m.HTML_PATH,("GET",)))==1
    assert final_paths.count((m.HTML_PATH,("GET","HEAD")))==1
    assert final_paths.count((m.JS_PATH,("GET",)))==1
    assert final_paths.count((m.JS_PATH,("GET","HEAD")))==1
    for path in old_paths:
        assert path in final_paths


def test_missing_browser_asset_or_changed_content_blocks_install():
    with pytest.raises(RuntimeError,match="original_crm_browser_asset_contract_drift"):
        m.patch_html("<main/>")
    with pytest.raises(RuntimeError,match="original_crm_browser_asset_contract_drift"):
        m.patch_js("var broken = true;")
    app=FastAPI()
    with pytest.raises(RuntimeError,match="original_crm_browser_route_missing_or_ambiguous"):
        m.build_verified_routes(app)


def test_patched_js_has_exact_safe_fetch_authorization_and_bound_session():
    js=m.patch_js((m.CRM_ASSETS/m.JS_NAME).read_text())
    snippet=js[js.index("async function verifyDataCloudExchange"):js.index("byId(\"verify-data-cloud\").addEventListener")]
    assert 'headers: { "Authorization": "Bearer " + sessionBearer }' in snippet
    assert 'method: "POST"' in snippet
    assert 'cache: "no-store"' in snippet
    assert "generation !== sessionGeneration" in snippet
    assert 'result.scope !== "data:read"' in snippet
    assert 'result.token_type !== "Bearer"' in snippet
    assert "result.access_token =" not in snippet
    assert "sessionBearer = result.access_token" not in snippet
    assert "fetch(\"http://" not in snippet
    assert "fetch(\"https://" not in snippet


def test_no_active_service_or_original_crm_asset_mutations():
    assert "from data_cloud_private_entrypoint_20261107 import app" in WRAPPER.read_text()
    assert "build_verified_routes(app)" in WRAPPER.read_text()
    assert "os.system(" not in SOURCE.read_text()
    assert "systemctl" not in SOURCE.read_text()
    assert "CREATE TABLE" not in SOURCE.read_text()


def test_live_fastapi_lazy_included_router_original_browser_routes_supported():
    # Matches the real CRM service's include_router route graph, which
    # contains _IncludedRouter nodes rather than flattened API leaves.
    from fastapi import APIRouter
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    router=APIRouter(prefix="/v1/revenue-crm")
    html_asset=(m.CRM_ASSETS/m.HTML_NAME).read_text().replace(
        "/v1/revenue-crm/journeys/designer.js",
        "/v1/revenue-crm/journeys/entry.js",
    )
    js_asset=(m.CRM_ASSETS/m.JS_NAME).read_bytes()

    @router.get("/journeys/entry")
    def browser_crm_entry():
        return HTMLResponse(html_asset,headers={
            "Cache-Control":"no-store",
            "Content-Security-Policy":"default-src 'none'; script-src 'self'",
        })

    @router.get("/journeys/entry.js")
    def browser_crm_entry_script():
        return Response(js_asset,media_type="text/javascript",
                        headers={"Cache-Control":"no-store"})

    app.include_router(router)
    assert not any(getattr(r,"path",None)==m.HTML_PATH for r in app.router.routes)
    assert any(type(r).__name__=="_IncludedRouter" for r in app.router.routes)
    m.build_verified_routes(app)
    with TestClient(app) as client:
        p=client.get(m.HTML_PATH)
        j=client.get(m.JS_PATH)
        assert p.status_code==200
        assert j.status_code==200
        assert p.text.count('id="verify-data-cloud"')==1
        assert "function verifyDataCloudExchange" in j.text
        assert p.headers["cache-control"]=="no-store"
        assert "script-src 'self'" in p.headers["content-security-policy"]
    assert len(router.routes)==2
