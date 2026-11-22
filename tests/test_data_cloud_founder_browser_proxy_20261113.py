"""Data Cloud original signed CRM -> protected original metered search.

Everything here is offline. No operator API key, runtime secrets, live HTTP,
production metering, migrations or service writes.
"""
from __future__ import annotations

import hashlib
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import Response

from empire_os.predictive_cloud_customer_api import founder_browser_proxy as proxy
from empire_os.predictive_cloud_customer_api import founder_browser_ui as ui


class OriginalSignedAuthority:
    def exchange(self, bearer):
        if bearer == "expired" or bearer == "wrong":
            raise ValueError("invalid_or_expired_crm")
        if bearer == "wrongtenant":
            raise PermissionError("tenant_access_refused")
        if bearer != "genuine-founder-fixture":
            raise ValueError("not_authenticated")
        return {"access_token": "signed-data-cloud-fixture"}


@pytest.fixture
def original_authority(monkeypatch):
    monkeypatch.setattr(proxy, "DataCloudFounderAuthority", OriginalSignedAuthority)
    return OriginalSignedAuthority()


def original_response(*, rows=None, status="results"):
    if rows is None:
        rows = [{
            "title": "Python documentation", "snippet": "Tutorial",
            "url": "https://docs.python.org/3/",
            "source": {
                "url": "https://docs.python.org/3/",
                "source_id": "empire_search_fabric_public",
                "observed_at": "2026-11-13T21:00:00+00:00",
                "upstream_engine": "bing_html",
            },
        }]
    return {
        "status": status, "results": rows,
        "buyer_intent_verified": False,
    }


def app_with_upstream(monkeypatch, original_authority, *, upstream=None, credential=None):
    app = FastAPI()
    calls = []
    if upstream is None:
        upstream = original_response()

    def intercept(request):
        calls.append(request)
        return httpx.Response(200, json=upstream)

    transport = httpx.MockTransport(intercept)
    factory = lambda: httpx.Client(transport=transport, trust_env=False, follow_redirects=False)
    reader = credential or (lambda: "server-sealed-key-fixture-" + "x" * 30)
    proxy.install_founder_crm_search(
        app, original_authority, credential_reader=reader, client_factory=factory,
    )
    return app, calls


def request(client, bearer="genuine-founder-fixture", *, query="python programming language", limit=2, **headers):
    return client.post(
        "/v1/data/founder/search",
        headers={"Authorization": "Bearer " + bearer,
                 "Origin": "http://testserver", **headers},
        json={"query": query, "limit": limit},
    )


def test_real_original_protocol_one_upstream_post_and_no_browser_secret(monkeypatch, original_authority):
    app, calls = app_with_upstream(monkeypatch, original_authority)
    with TestClient(app) as client:
        resp = request(client)
    assert resp.status_code == 200, resp.text
    assert resp.headers["cache-control"] == "no-store"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.json() == {
        "status": "results", "results": [{
            "title": "Python documentation", "url": "https://docs.python.org/3/",
            "snippet": "Tutorial", "engine": "bing_html",
            "observed_at": "2026-11-13T21:00:00+00:00",
            "source_id": "empire_search_fabric_public",
        }], "buyer_intent_verified": False,
    }
    assert len(calls) == 1, "one request => one metered provider call"
    outbound = calls[0]
    assert outbound.url == httpx.URL("http://127.0.0.1:80/v1/data/search")
    assert outbound.headers["x-empire-data-session"] == "signed-data-cloud-fixture"
    assert outbound.headers["authorization"].startswith("Bearer server-sealed-key-fixture-")
    assert outbound.headers["idempotency-key"].startswith("crm-founder-search-")
    assert outbound.headers.get("cookie") is None
    assert outbound.headers.get("x-forwarded-for") is None
    assert b"python programming language" in outbound.content
    assert "sealed-key" not in resp.text
    assert "signed-data-cloud-fixture" not in resp.text
    assert "genuine-founder-fixture" not in resp.text


@pytest.mark.parametrize("bearer,expected", [
    ("", 401), ("expired", 401), ("wrong", 401), ("wrongtenant", 403),
])
def test_real_crm_membership_and_expiry_are_enforced(monkeypatch, original_authority, bearer, expected):
    app, calls = app_with_upstream(monkeypatch, original_authority)
    with TestClient(app) as client:
        resp = request(client, bearer=bearer)
    assert resp.status_code == expected
    assert calls == []


@pytest.mark.parametrize("query,limit", [
    ("xy", 2), (" control\nchar", 2), ("hello", 0),
    ("hello", 4), ("hello", True),
])
def test_invalid_request_fails_before_metering(monkeypatch, original_authority, query, limit):
    app, calls = app_with_upstream(monkeypatch, original_authority)
    with TestClient(app) as client:
        resp = request(client, query=query, limit=limit)
    assert resp.status_code == 422
    assert calls == []


def test_cross_origin_post_cannot_use_browser_signed_session(monkeypatch, original_authority):
    app, calls = app_with_upstream(monkeypatch, original_authority)
    with TestClient(app) as client:
        resp = request(client, Origin="https://attacker.example")
    assert resp.status_code == 403
    assert calls == []


def test_missing_systemd_credentials_fail_closed(monkeypatch, original_authority):
    def absent():
        raise ValueError("protected credential not installed")
    app, calls = app_with_upstream(monkeypatch, original_authority, credential=absent)
    with TestClient(app) as client:
        resp = request(client)
    assert resp.status_code == 503
    assert "credential" not in resp.text.lower()
    assert calls == []


@pytest.mark.parametrize("url", [
    "http://docs.python.org/3/", "https://127.0.0.1/private",
    "https://localhost/private", "https://metadata.internal/",
    "https://person:password@docs.python.org/", "https://docs.python.org:444/",
    "https://docs.python.org/ok\nbad",
])
def test_unsafe_or_unverified_output_never_reaches_browser(monkeypatch, original_authority, url):
    response = original_response()
    response["results"][0]["url"] = url
    response["results"][0]["source"]["url"] = url
    app, calls = app_with_upstream(monkeypatch, original_authority, upstream=response)
    with TestClient(app) as client:
        resp = request(client)
    assert resp.status_code == 503
    assert len(calls) == 1
    assert url not in resp.text


def test_other_source_identity_is_not_relabelled(monkeypatch, original_authority):
    response = original_response()
    response["results"][0]["source"]["source_id"] = "unreviewed_supplier"
    app, calls = app_with_upstream(monkeypatch, original_authority, upstream=response)
    with TestClient(app) as client:
        resp = request(client)
    assert resp.status_code == 503
    assert len(calls) == 1


@pytest.mark.parametrize("source_http,expected", [(429,429),(403,403),(500,503),(401,503)])
def test_upstream_fails_safely_and_never_retries(monkeypatch, original_authority, source_http, expected):
    app = FastAPI()
    calls = []
    def intercept(request):
        calls.append(request)
        return httpx.Response(source_http, text="untrusted upstream secret")
    proxy.install_founder_crm_search(
        app, original_authority,
        credential_reader=lambda: "x" * 40,
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(intercept)),
    )
    with TestClient(app) as client:
        resp = request(client)
    assert resp.status_code == expected
    assert len(calls) == 1
    assert "secret" not in resp.text


def test_duplicate_original_private_route_is_refused(monkeypatch, original_authority):
    app, _ = app_with_upstream(monkeypatch, original_authority)
    with pytest.raises(ValueError, match="route_collision"):
        proxy.install_founder_crm_search(app, original_authority)


HTML = '<main><p id="data-cloud-verify-status">Verified original exchange.</p><p>Existing CRM work is preserved.</p></main>'
JS = ('(function(){\n  let sessionBearer = null, sessionUntil = 0, sessionGeneration = 0;\n'
      'function clearPrivateUi(){\n    byId("verify-data-cloud").disabled = true;\n}\n'
      'function login(){\n      byId("verify-data-cloud").disabled = false;\n}\n'
      '  byId("verify-data-cloud").addEventListener("click", verifyDataCloudExchange);\n'
      '  setLoginState();\n})();')


def test_browser_patch_preserves_existing_login_and_session_closure(monkeypatch):
    app = FastAPI()
    app.router.routes.insert(0, ui.Route(
        ui.JS_PATH,
        endpoint=lambda request: Response(JS, media_type="text/javascript",
                                         headers={"cache-control": "no-store"}),
        methods=["GET"],
    ))
    app.router.routes.insert(0, ui.Route(
        ui.HTML_PATH,
        endpoint=lambda request: Response(HTML, media_type="text/html", headers={
            "cache-control": "no-store",
            "content-security-policy": "default-src 'none'; script-src 'self'",
        }),
        methods=["GET"],
    ))
    monkeypatch.setattr(ui, "ORIGINAL_HTML_SHA", hashlib.sha256(HTML.encode()).hexdigest())
    monkeypatch.setattr(ui, "ORIGINAL_JS_SHA", hashlib.sha256(JS.encode()).hexdigest())
    before = len(app.router.routes)
    ui.install_founder_search_ui(app)
    assert len(app.router.routes) == before + 2
    with TestClient(app) as client:
        html = client.get(ui.HTML_PATH)
        js = client.get(ui.JS_PATH)
    assert html.status_code == js.status_code == 200
    assert "Existing CRM work is preserved." in html.text
    assert "data-cloud-search-button" in html.text
    assert html.headers["content-security-policy"].startswith("default-src")
    assert "sessionBearer" in js.text
    assert 'byId("data-cloud-search-button").disabled = true;' in js.text
    assert 'byId("data-cloud-search-button").disabled = false;' in js.text
    assert 'data-cloud-search-results").replaceChildren()' in js.text
    assert 'fetch("/v1/data/founder/search"' in js.text
    assert 'textContent' in js.text
    assert 'innerHTML' not in js.text
    assert 'localStorage' not in js.text
    assert 'sessionStorage' not in js.text
    assert "Bearer " in js.text  # only the original CRM bearer
    assert "empire-data-cloud-founder-api-key" not in js.text


def test_html_patches_fail_closed_if_original_owner_changed():
    with pytest.raises(RuntimeError):
        ui.patch_html("other original UI")
    with pytest.raises(RuntimeError):
        ui.patch_js("other original JS")
