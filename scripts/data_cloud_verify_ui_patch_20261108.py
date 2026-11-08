"""Additive browser-only Data Cloud exchange check in the EXISTING private CRM.

Does not modify any frozen CRM HTML or JavaScript asset. Its two protected
root-frozen response overrides wrap only the original, current CRM login page
and its existing same-origin JS route. The CRM bearer remains inside its
existing browser-tab closure and is never exported, logged or persisted.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from starlette.routing import Route

CRM_ASSETS = Path(
    "/opt/empire-ai/crm-pilot-releases/"
    "smart-crm-work-queue-20261104v1/empire_os/static"
)
HTML_NAME = "revenue_crm_journey_designer.html"
JS_NAME = "revenue_crm_journey_designer.js"
PINNED_HTML_SHA = "0ffcba48366a7dd0f12fffe731b56d79c7f9bdad5464ac17122796d6a27f0a55"
PINNED_JS_SHA = "c4cd2b2f30ac3e8aba55ea1f15142d7af6955bcbd932a05f45b42b3e3fa7be69"
HTML_PATH = "/v1/revenue-crm/journeys/entry"
JS_PATH = "/v1/revenue-crm/journeys/entry.js"
EXCHANGE_PATH = "/v1/data/auth/exchange"

HTML_ANCHOR = (
    '<p id="crm-auth-status" role="status" aria-live="polite">'
    'Not signed in. No CRM records are loaded.</p>'
)
HTML_INSERT = (
    '<div class="inline-buttons">'
    '<button id="verify-data-cloud" type="button" disabled>'
    'Verify Data Cloud</button></div>'
    '<p id="data-cloud-verify-status" role="status" aria-live="polite">'
    'Sign in to check your founder-only Data Cloud exchange.</p>'
)
JS_CLEAR_ANCHOR = '    sessionBearer = null; sessionUntil = 0; sessionGeneration++;'
JS_CLEAR_INSERT = (
    '    byId("verify-data-cloud").disabled = true;\n'
    '    byId("data-cloud-verify-status").textContent = '
    '"Sign in to check your founder-only Data Cloud exchange.";'
)
JS_LOGIN_ANCHOR = ('      sessionUntil = Date.now() + result.expires_in * 1000;\n'
                   '      sessionGeneration++;')
JS_LOGIN_INSERT = (
    '      byId("verify-data-cloud").disabled = false;\n'
    '      byId("data-cloud-verify-status").textContent = '
    '"Ready: verify the signed CRM-to-Data-Cloud exchange.";'
)
JS_BIND_ANCHOR = '  setLoginState();\n})();'
JS_VERIFY_FUNCTION = r'''
  async function verifyDataCloudExchange() {
    const button = byId("verify-data-cloud");
    const output = byId("data-cloud-verify-status");
    if (!sessionBearer || Date.now() >= sessionUntil) {
      output.textContent = "Please sign in again before verifying Data Cloud.";
      return;
    }
    // The bearer remains in the original CRM tab's private closure.
    // Never copy it into DOM, URL, window, storage, logs or clipboard.
    const generation = sessionGeneration;
    button.disabled = true;
    output.textContent = "Verifying your founder CRM session…";
    try {
      const response = await fetch("/v1/data/auth/exchange", {
        method: "POST", cache: "no-store", credentials: "omit",
        redirect: "error",
        headers: { "Authorization": "Bearer " + sessionBearer }
      });
      if (generation !== sessionGeneration ||
          !sessionBearer || Date.now() >= sessionUntil)
        throw new Error("CRM session expired during verification");
      if (!response.ok) throw new Error("Data Cloud exchange denied");
      const result = await response.json();
      if (result.token_type !== "Bearer" ||
          result.scope !== "data:read" ||
          !Number.isInteger(result.expires_in) ||
          result.expires_in < 1 || result.expires_in > 900 ||
          typeof result.access_token !== "string" ||
          result.access_token.length < 100 ||
          result.access_token.length > 4096)
        throw new Error("Data Cloud exchange response invalid");
      // The signed Data Cloud token is purposefully discarded here. This
      // test verifies the REAL founder CRM bearer -> private exchange.
      // It does not claim the separate paid API key or usage GET was tested.
      output.textContent =
        "Verified: your real founder CRM session exchanged for a " +
        "read-only Data Cloud session (HTTP 200). No token stored.";
    } catch (_) {
      if (generation === sessionGeneration)
        output.textContent =
          "Data Cloud exchange was not verified. CRM and existing " +
          "gateway access remain unchanged.";
    } finally {
      if (generation === sessionGeneration && sessionBearer &&
          Date.now() < sessionUntil) button.disabled = false;
    }
  }
  byId("verify-data-cloud").addEventListener("click", verifyDataCloudExchange);
'''


def _one(text: str, anchor: str, replacement: str) -> str:
    if text.count(anchor) != 1:
        raise RuntimeError("original_crm_browser_asset_contract_drift")
    return text.replace(anchor, replacement, 1)


def patch_html(source: str) -> str:
    return _one(source, HTML_ANCHOR, HTML_ANCHOR + "\n" + HTML_INSERT)


def patch_js(source: str) -> str:
    source = _one(source, JS_CLEAR_ANCHOR, JS_CLEAR_ANCHOR + "\n" + JS_CLEAR_INSERT)
    source = _one(source, JS_LOGIN_ANCHOR, JS_LOGIN_ANCHOR + "\n" + JS_LOGIN_INSERT)
    return _one(source, JS_BIND_ANCHOR, JS_VERIFY_FUNCTION + "\n" + JS_BIND_ANCHOR)


def _pinned(path: Path, expected: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("original_frozen_crm_asset_missing")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("original_frozen_crm_asset_changed")
    return data


def build_verified_routes(app: FastAPI) -> None:
    """Shadow exactly two original CRM browser code routes; no API changes."""
    original_html = _pinned(CRM_ASSETS / HTML_NAME, PINNED_HTML_SHA)
    original_js = _pinned(CRM_ASSETS / JS_NAME, PINNED_JS_SHA)
    # Preserve the already verified original handler HTTP/CSP/cache headers.
    originals = {}
    # The live CRM uses FastAPI 0.12x lazy _IncludedRouter nodes for the
    # original read router. app.router.routes does not contain those leaves.
    # Resolve them WITHOUT altering any original owner router or handler.
    original_routes = []
    for outer in app.router.routes:
        if (type(outer).__module__, type(outer).__name__) == (
            "fastapi.routing", "_IncludedRouter"
        ):
            nested = getattr(outer, "original_router", None)
            leaves = getattr(nested, "routes", None)
            if not isinstance(leaves, list):
                raise RuntimeError("original_lazy_crm_router_contract_changed")
            original_routes.extend(leaves)
        else:
            original_routes.append(outer)
    for path in (HTML_PATH, JS_PATH):
        routes = [route for route in original_routes
                  if getattr(route, "path", None) == path
                  and getattr(route, "methods", set()) == {"GET"}]
        if len(routes) != 1:
            raise RuntimeError("original_crm_browser_route_missing_or_ambiguous")
        original = routes[0].endpoint()
        if original.status_code != 200:
            raise RuntimeError("original_crm_browser_route_is_not_healthy")
        originals[path] = original

    html_response = originals[HTML_PATH]
    js_response = originals[JS_PATH]
    expected_html = original_html.decode("utf8").replace(
        "/v1/revenue-crm/journeys/designer.js",
        "/v1/revenue-crm/journeys/entry.js",
    )
    if html_response.body != expected_html.encode("utf8"):
        raise RuntimeError("original_crm_login_shell_content_changed")
    if js_response.body != original_js:
        raise RuntimeError("original_crm_login_browser_code_changed")
    if (html_response.headers.get("content-security-policy") is None
        or html_response.headers.get("cache-control") != "no-store"
        or js_response.headers.get("cache-control") != "no-store"):
        raise RuntimeError("original_crm_browser_security_headers_changed")

    altered_html = patch_html(expected_html)
    altered_js = patch_js(original_js.decode("utf8"))
    for path, original, body, mime in (
        (HTML_PATH, html_response, altered_html, "text/html"),
        (JS_PATH, js_response, altered_js, "text/javascript"),
    ):
        response_headers = {
            k: v for k, v in original.headers.items()
            if k.lower() not in ("content-length", "content-type")
        }

        def handler(request, *, content=body, headers=response_headers, media_type=mime):
            return Response(
                content=content, media_type=media_type, headers=headers,
            )

        app.router.routes.insert(0, Route(path, endpoint=handler, methods=["GET"]))
    # No other route is added, replaced, or shadowed. The ordinary CRM login
    # and the approved POST /v1/data/auth/exchange remain unchanged.
