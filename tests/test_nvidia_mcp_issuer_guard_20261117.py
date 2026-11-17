"""Regression gates for NVIDIA MCP /api/auth issuer compatibility.

Only synthetic mocked metadata. No authenticated agent, OAuth credentials,
production services or vendor code touched by these tests.
"""
from __future__ import annotations

import httpx
import pytest
from auto_ontology_mcp.config import ConfigError, Settings, DEFAULT_SPEC_PATH

from scripts.nvidia_mcp_verified_issuer_20261117 import verified_issuer

API = "http://localhost:33000"
ISSUER = API + "/api/auth"


def settings(api_url=API, host="127.0.0.1", port=33013, public_url=None):
    return Settings(
        api_url=api_url,
        spec_path=DEFAULT_SPEC_PATH,
        host=host,
        port=port,
        timeout_s=20,
        chat_timeout_s=180,
        public_url=public_url or f"http://127.0.0.1:{port}",
    )


def metadata(issuer=ISSUER):
    return {
        "issuer": issuer,
        "authorization_endpoint": ISSUER + "/oauth2/authorize",
        "token_endpoint": ISSUER + "/oauth2/token",
        "registration_endpoint": ISSUER + "/oauth2/register",
        "scopes_supported": ["openid", "profile"],
    }


def check(payload, instance=None):
    def handler(req: httpx.Request):
        assert str(req.url) == ISSUER + "/.well-known/oauth-authorization-server"
        return httpx.Response(200, json=payload)
    with httpx.Client(transport=httpx.MockTransport(handler), trust_env=False) as client:
        return verified_issuer(instance or settings(), client=client)


def test_exact_metadata_issuer_replaces_incorrect_root():
    assert check(metadata()) == ISSUER


@pytest.mark.parametrize("wrong", [
    API, API + "/", "http://127.0.0.1:33000/api/auth",
    "http://localhost:33000/attacker", "https://example.net",
])
def test_issuer_mismatch_is_refused(wrong):
    with pytest.raises(ConfigError):
        check(metadata(issuer=wrong))


@pytest.mark.parametrize("field", [
    "authorization_endpoint", "token_endpoint", "registration_endpoint"
])
def test_endpoint_drift_is_refused(field):
    info=metadata()
    info[field]="https://not-expected.example/oauth2"
    with pytest.raises(ConfigError):
        check(info)


def test_openid_requirement_and_localhost_scope():
    info=metadata()
    info["scopes_supported"]=["profile"]
    with pytest.raises(ConfigError):
        check(info)
    for unsafe in (
        settings(api_url="https://nvidia.example"),
        settings(host="0.0.0.0",public_url="http://127.0.0.1:33013"),
        settings(public_url="http://0.0.0.0:33013"),
    ):
        with pytest.raises(ConfigError):
            verified_issuer(unsafe)


def test_vendor_unmodified_and_auth_verifier_unmodified():
    from auto_ontology_mcp.auto_ontology_auth import (
        AutoOntologyTokenVerifier, build_auto_ontology_auth,
    )
    vendor=build_auto_ontology_auth(settings())
    assert [str(x).rstrip("/") for x in vendor.authorization_servers] == [API]
    assert isinstance(vendor.token_verifier, AutoOntologyTokenVerifier)
