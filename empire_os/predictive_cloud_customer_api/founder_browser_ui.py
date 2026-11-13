"""Guarded, additive Data Cloud search control in the ORIGINAL CRM browser.

Wraps the live existing two browser code responses; retains upstream HTML,
signed CRM token closure, CSP/cache headers and unrelated routes. No new UI app.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable

from fastapi import FastAPI
from starlette.responses import Response
from starlette.routing import Route

HTML_PATH = "/v1/revenue-crm/journeys/entry"
JS_PATH = "/v1/revenue-crm/journeys/entry.js"
# SHA256 of independently read existing protected CRM browser responses,
# 13 Nov 2026. Drift refuses activation; it does not overwrite another owner.
ORIGINAL_HTML_SHA = "17903e07c92278f00033d654b03e6afe2438d656bbd84f28da5c77d76b9a283a"
ORIGINAL_JS_SHA = "a9d62c2d03715e33e328f7fff55c1155bd3c80c895d3a2913e98c9c41bc0f42e"
BUTTON = "data-cloud-search-button"

SEARCH_HTML = """
<section id="data-cloud-founders-search" aria-labelledby="data-cloud-search-title">
  <h3 id="data-cloud-search-title">Founder Data Cloud search</h3>
  <label for="data-cloud-search-query">Search public web intelligence</label>
  <input type="search" id="data-cloud-search-query" maxlength="180" value="python programming language" autocomplete="off"/>
  <button type="button" id="data-cloud-search-button" disabled>Search Data Cloud</button>
  <p id="data-cloud-search-status" role="status" aria-live="polite">Sign in to run a metered first-party search.</p>
  <ul id="data-cloud-search-results" aria-label="Data Cloud verified search results"></ul>
</section>
"""

SEARCH_JS = r"""
  // Same tab, same existing signed CRM session. The browser NEVER sees the
  // sealed Data Cloud API key or receives a Data Cloud session token.
  async function searchOriginalDataCloud() {
    const button = byId("data-cloud-search-button");
    const status = byId("data-cloud-search-status");
    const results = byId("data-cloud-search-results");
    if (!sessionBearer || Date.now() >= sessionUntil) {
      status.textContent = "CRM session expired. Sign in again.";
      button.disabled = true;
      return;
    }
    const query = byId("data-cloud-search-query").value.trim();
    if (query.length < 3 || query.length > 180) {
      status.textContent = "Enter a query between 3 and 180 characters.";
      return;
    }
    const generation = sessionGeneration;
    button.disabled = true;
    results.replaceChildren();
    status.textContent = "Running your existing first-party Data Cloud search…";
    try {
      const response = await fetch("/v1/data/founder/search", {
        method: "POST", cache: "no-store", redirect: "error",
        credentials: "omit",
        headers: {
          "Authorization": "Bearer " + sessionBearer,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({query: query, limit: 2})
      });
      if (generation !== sessionGeneration || !sessionBearer ||
          Date.now() >= sessionUntil) return;
      if (!response.ok) throw new Error("The search was not completed (HTTP " + response.status + ").");
      const data = await response.json();
      if (!Array.isArray(data.results) ||
          !["results", "no_results"].includes(data.status)) throw new Error("Invalid search response.");
      for (const row of data.results) {
        if (typeof row.url !== "string" || !row.url.startsWith("https://") ||
            typeof row.title !== "string") continue;
        const li = document.createElement("li");
        const link = document.createElement("a");
        link.href = row.url;
        link.textContent = row.title;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        li.appendChild(link);
        if (typeof row.snippet === "string" && row.snippet) {
          const detail = document.createElement("span");
          detail.textContent = " — " + row.snippet;
          li.appendChild(detail);
        }
        results.appendChild(li);
      }
      status.textContent = "Data Cloud search completed: " + data.results.length + " result(s). Metered in the existing ledger.";
    } catch (_) {
      if (generation === sessionGeneration) status.textContent =
        "Data Cloud search unavailable or refused. No results were claimed.";
    } finally {
      if (generation === sessionGeneration && sessionBearer &&
          Date.now() < sessionUntil) button.disabled = false;
    }
  }
  byId("data-cloud-search-button").addEventListener("click", searchOriginalDataCloud);
"""


def _replace_one(source: str, before: str, after: str) -> str:
    if source.count(before) != 1:
        raise RuntimeError("original_crm_browser_patch_anchor_changed")
    return source.replace(before, after, 1)


def patch_html(source: str) -> str:
    anchor = 'id="data-cloud-verify-status"'
    if source.count(anchor) != 1:
        raise RuntimeError("existing_data_cloud_browser_augmentation_missing")
    index = source.find("</p>", source.index(anchor))
    if index < 0:
        raise RuntimeError("original_crm_browser_status_missing")
    index += 4
    return source[:index] + SEARCH_HTML + source[index:]


def patch_js(source: str) -> str:
    old_clear = '    byId("verify-data-cloud").disabled = true;'
    old_login = '      byId("verify-data-cloud").disabled = false;'
    anchor = '  byId("verify-data-cloud").addEventListener("click", verifyDataCloudExchange);'
    source = _replace_one(source, old_clear, old_clear + """
    byId("data-cloud-search-button").disabled = true;
    byId("data-cloud-search-results").replaceChildren();
    byId("data-cloud-search-status").textContent =
      "Sign in to run a metered first-party search.";""")
    source = _replace_one(source, old_login, old_login +
                          '\n      byId("data-cloud-search-button").disabled = false;')
    return _replace_one(source, anchor, anchor + "\n" + SEARCH_JS)


def _existing_response(host: FastAPI, path: str) -> Response:
    # Prior owner injected a simple static Starlette Route before the
    # original included router. Retain that EXACT response and its headers.
    for route in host.router.routes:
        if getattr(route, "path", None) == path and "GET" in getattr(route, "methods", set()):
            if not isinstance(route, Route):
                raise RuntimeError("original_crm_ui_route_contract_changed")
            response = route.endpoint(None)
            if not isinstance(response, Response):
                raise RuntimeError("original_crm_ui_response_contract_changed")
            return response
    raise RuntimeError("original_crm_ui_route_not_found")


def install_founder_search_ui(host: FastAPI) -> None:
    """Fail atomically before adding any of the two guarded browser routes."""
    original = []
    for path, digest, patch in (
        (HTML_PATH, ORIGINAL_HTML_SHA, patch_html),
        (JS_PATH, ORIGINAL_JS_SHA, patch_js),
    ):
        response = _existing_response(host, path)
        if (
            response.headers.get("cache-control") != "no-store"
            or hashlib.sha256(response.body).hexdigest() != digest
        ):
            raise RuntimeError("original_crm_ui_sha256_changed")
        if path == HTML_PATH and not response.headers.get("content-security-policy"):
            raise RuntimeError("original_crm_ui_csp_missing")
        body = patch(response.body.decode("utf8")).encode("utf8")
        headers = {k: v for k, v in response.headers.items()
                   if k.lower() not in ("content-type", "content-length")}
        media_type = "text/html" if path == HTML_PATH else "text/javascript"
        original.append((path, body, headers, media_type))

    for path, content, headers, media_type in original:
        def handler(_request, *, body=content, h=headers, mime=media_type):
            return Response(body, media_type=mime, headers=h)
        host.router.routes.insert(0, Route(path, endpoint=handler, methods=["GET"]))
