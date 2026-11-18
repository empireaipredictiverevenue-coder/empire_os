"""NVIDIA MCP issuer discovery compatibility for the pinned isolated evaluation.

The vendor MCP advertises its frontend root as OAuth issuer, whereas Better Auth
actually issues under /api/auth. OpenCode strictly validates RFC 8414 issuer.
Resolve issuer from the upstream authorization server's own metadata and patch
ONLY the MCP protected-resource advertisement, leaving upstream token checking
and tool authentication unchanged. Fail closed on unexpected metadata.

No vendor edits; no credentials or token exchange; no public listener.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from urllib.parse import urlparse

import httpx
from pydantic import AnyHttpUrl
from auto_ontology_mcp.config import ConfigError, Settings, load_settings
from auto_ontology_mcp.server import build_server
from auto_ontology_mcp import get_version
if __package__ == "scripts":
    from .nvidia_mcp_env_source_compat_20261118 import install as install_env_readiness
else:
    from nvidia_mcp_env_source_compat_20261118 import install as install_env_readiness

LOG = logging.getLogger(__name__)


def verified_issuer(settings: Settings, client: httpx.Client | None = None) -> str:
    api = settings.api_url.rstrip("/")
    base = urlparse(api)
    if base.scheme != "http" or base.hostname not in {"localhost", "127.0.0.1"} or base.port != 33000:
        raise ConfigError("Issuer guard restricted to the isolated localhost NVIDIA frontend")
    expected = api + "/api/auth"
    if settings.host != "127.0.0.1" or settings.public_url != f"http://127.0.0.1:{settings.port}":
        raise ConfigError("MCP guard requires a loopback-only endpoint")
    owned = client is None
    if owned:
        client = httpx.Client(timeout=8, trust_env=False, follow_redirects=False)
    assert client is not None
    try:
        reply = client.get(expected + "/.well-known/oauth-authorization-server")
        reply.raise_for_status()
        metadata = reply.json()
    finally:
        if owned:
            client.close()
    if not isinstance(metadata, dict) or metadata.get("issuer") != expected:
        raise ConfigError("NVIDIA authorization server issuer is missing or unexpected")
    for name, suffix in {
        "authorization_endpoint": "/oauth2/authorize",
        "token_endpoint": "/oauth2/token",
        "registration_endpoint": "/oauth2/register",
    }.items():
        if metadata.get(name) != expected + suffix:
            raise ConfigError(f"NVIDIA OAuth {name} changed, refusing issuer override")
    if "openid" not in (metadata.get("scopes_supported") or []):
        raise ConfigError("NVIDIA OAuth openid scope unavailable")
    return expected


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        settings = load_settings()
        issuer = verified_issuer(settings)
        mcp, _client = build_server(settings)
        auth = mcp.auth
        if auth is None or not hasattr(auth, "authorization_servers"):
            raise ConfigError("pinned MCP no longer exposes a remote authorization server list")
        if [str(x).rstrip("/") for x in auth.authorization_servers] != [settings.api_url.rstrip("/")]:
            raise ConfigError("pinned MCP authorization server list has changed unexpectedly")
        auth.authorization_servers = [AnyHttpUrl(issuer)]
        if [str(x).rstrip("/") for x in auth.authorization_servers] != [issuer]:
            raise ConfigError("corrected issuer did not read back")
        # Reconcile NVIDIA environment-managed connections in the existing
        # readiness tool, preserving all other nine vendor MCP tool names.
        asyncio.run(install_env_readiness(mcp, _client))
    except (ConfigError, httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        LOG.error("NVIDIA MCP OAuth issuer preflight failed: %s", type(exc).__name__)
        return 2
    LOG.info("NVIDIA MCP issuer verified; native tools and user-token verifier unchanged")
    mcp.run(transport="http", host=settings.host, port=settings.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
