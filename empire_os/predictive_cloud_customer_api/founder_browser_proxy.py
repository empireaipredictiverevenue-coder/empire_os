"""Additive private-CRM founder search proxy for the ORIGINAL Empire Data Cloud.

The browser sends its in-memory CRM bearer to the existing private issuer.
The issuer exchanges it for a Data Cloud session and uses a systemd-sealed API
key server-side. No API key, Data Cloud JWT, or CRM token enters the response.
No new collector, tenant, billing logic, key file or gateway.
"""
from __future__ import annotations

import ipaddress
import os
import re
import secrets
import stat
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from empire_os.predictive_cloud_founder_session import DataCloudFounderAuthority

ROUTE = "/v1/data/founder/search"
UPSTREAM = "http://127.0.0.1:80/v1/data/search"
SOURCE = "empire_search_fabric_public"
CREDENTIAL_NAME = "empire-data-cloud-founder-api-key"
ENGINE_IDS = frozenset({"bing_html", "duckduckgo_html", "google_html", "brave_web"})
PRIVATE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


class FounderSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: StrictStr = Field(min_length=3, max_length=180)
    limit: StrictInt = Field(default=2, ge=1, le=3)


def _answer(code: int, data: dict) -> JSONResponse:
    return JSONResponse(data, status_code=code, headers=PRIVATE_HEADERS)


def _read_systemd_key() -> str:
    """Read only the credential explicitly delivered to this private service."""
    directory = os.environ.get("CREDENTIALS_DIRECTORY")
    if not directory or not Path(directory).is_absolute():
        raise ValueError("systemd_credential_directory_missing")
    root = Path(directory)
    path = root / CREDENTIAL_NAME
    if (
        root.is_symlink() or path.is_symlink() or not path.is_file()
        or not stat.S_ISREG(path.stat().st_mode)
        or stat.S_IMODE(path.stat().st_mode) & 0o022
    ):
        raise ValueError("data_cloud_api_credential_not_sealed")
    value = path.read_text(encoding="utf8").strip()
    if not 32 <= len(value) <= 256 or any(c.isspace() for c in value):
        raise ValueError("data_cloud_api_credential_invalid")
    return value


def _public_https_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 2048:
        return None
    if any(ord(c) < 32 or c in "\\\x7f" for c in value):
        return None
    try:
        p = urlsplit(value)
        host = (p.hostname or "").lower().rstrip(".")
        if p.scheme != "https" or not host or p.username or p.password or p.port not in (None, 443):
            return None
        if host in ("localhost", "local") or host.endswith((".local", ".internal", ".localhost")):
            return None
        if (
            "." not in host
            or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in host.split(".")
            )
        ):
            return None
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            return None
        return value
    except ValueError:
        return None


def _safe_results(data: object, *, limit: int) -> dict:
    if not isinstance(data, dict) or data.get("status") not in ("results", "no_results"):
        raise ValueError("unrecognized_metered_response")
    if data.get("buyer_intent_verified") is not False:
        raise ValueError("unexpected_buyer_intent_claim")
    raw = data.get("results")
    if not isinstance(raw, list) or len(raw) > limit:
        raise ValueError("unbounded_metered_response")
    safe = []
    for row in raw:
        if not isinstance(row, dict) or not isinstance(row.get("source"), dict):
            raise ValueError("invalid_search_lineage")
        src = row["source"]
        url = _public_https_url(row.get("url"))
        if (
            not url or src.get("url") != url
            or src.get("source_id") != SOURCE
            or src.get("upstream_engine") not in ENGINE_IDS
            or not isinstance(src.get("observed_at"), str)
            or not src["observed_at"]
        ):
            raise ValueError("invalid_search_provenance")
        safe.append({
            "title": str(row.get("title", ""))[:180],
            "url": url,
            "snippet": str(row.get("snippet", ""))[:500],
            "engine": src["upstream_engine"],
            "observed_at": src["observed_at"],
            "source_id": SOURCE,
        })
    if (data["status"] == "results") != bool(safe):
        raise ValueError("inconsistent_search_results")
    return {
        "status": data["status"],
        "results": safe,
        "buyer_intent_verified": False,
    }


def install_founder_crm_search(
    host: FastAPI,
    authority: DataCloudFounderAuthority,
    *,
    credential_reader: Callable[[], str] = _read_systemd_key,
    client_factory: Callable[[], httpx.Client] | None = None,
) -> None:
    """One original-private-host addition; nothing is mounted by default."""
    if not isinstance(host, FastAPI) or not isinstance(authority, DataCloudFounderAuthority):
        raise ValueError("existing_private_data_cloud_authority_required")
    if any(getattr(route, "path", None) == ROUTE for route in host.router.routes):
        raise ValueError("existing_founder_search_route_collision")
    if not callable(credential_reader):
        raise ValueError("trusted_credential_reader_required")
    factory = client_factory or (lambda: httpx.Client(
        timeout=httpx.Timeout(9.0), trust_env=False, follow_redirects=False,
    ))

    @host.post(ROUTE)
    def search(req: FounderSearchRequest, request: Request,
               authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith("Bearer "):
            return _answer(401, {"detail": "crm_session_required"})
        # Browser access is same-origin; forbid a cross-origin POST even with
        # an accidentally leaked bearer. No cookies or Origin-based trust.
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return _answer(403, {"detail": "cross_origin_search_denied"})
        query = req.query.strip()
        if len(query) < 3 or any(ord(c) < 32 or ord(c) == 127 for c in query):
            return _answer(422, {"detail": "invalid_search_query"})
        try:
            exchanged = authority.exchange(authorization[7:])
            data_token = exchanged["access_token"]
        except PermissionError:
            return _answer(403, {"detail": "founder_membership_not_entitled"})
        except (ValueError, KeyError, TypeError):
            return _answer(401, {"detail": "invalid_crm_session"})

        try:
            api_key = credential_reader()
            if not isinstance(api_key, str) or not 32 <= len(api_key) <= 256:
                raise ValueError("invalid_sealed_key")
        except (OSError, ValueError, UnicodeError):
            return _answer(503, {"detail": "protected_data_cloud_access_unavailable"})
        headers = {
            "X-Empire-Data-Session": data_token,
            "Authorization": "Bearer " + api_key,
            "Idempotency-Key": "crm-founder-search-" + secrets.token_hex(12),
        }
        try:
            with factory() as client:
                response = client.post(
                    UPSTREAM, headers=headers,
                    json={"query": query, "limit": req.limit},
                )
                if response.status_code != 200:
                    code = 429 if response.status_code == 429 else (
                        403 if response.status_code == 403 else 503)
                    return _answer(code, {"detail": "data_cloud_search_not_completed"})
                output = _safe_results(response.json(), limit=req.limit)
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            return _answer(503, {"detail": "data_cloud_response_unavailable"})
        return _answer(200, output)
