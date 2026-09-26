import asyncio

from empire_os.ops_mcp import StaticOpsTokenVerifier, _build_server


def test_static_ops_token_verifier_accepts_only_configured_secret():
    verifier = StaticOpsTokenVerifier(
        "expected-secret",
        "http://127.0.0.1:8765/mcp",
    )
    accepted = asyncio.run(verifier.verify_token("expected-secret"))
    rejected = asyncio.run(verifier.verify_token("wrong-secret"))
    assert accepted is not None
    assert accepted.client_id == "empire-ops-client"
    assert accepted.scopes == ["empire:ops"]
    assert accepted.resource == "http://127.0.0.1:8765/mcp"
    assert rejected is None


def test_server_builds_without_http_auth_when_token_missing(monkeypatch):
    monkeypatch.delenv("EMPIRE_OPS_MCP_BEARER_TOKEN", raising=False)
    server = _build_server()
    assert server is not None


def test_server_builds_with_http_auth_when_token_present(monkeypatch):
    monkeypatch.setenv("EMPIRE_OPS_MCP_BEARER_TOKEN", "test-secret")
    monkeypatch.setenv(
        "EMPIRE_OPS_MCP_RESOURCE_URL",
        "http://127.0.0.1:8765/mcp",
    )
    monkeypatch.setenv(
        "EMPIRE_OPS_MCP_ISSUER_URL",
        "https://empire-ai.co.uk",
    )
    server = _build_server()
    assert server is not None
