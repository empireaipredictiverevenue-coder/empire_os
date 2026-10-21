"""SSH-private Research is an explicitly configured alternate human auth edge.

It is not enabled by default and is never granted by an HTTP request header.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.founder_research_products_api import create_founder_research_products_router

PATH = "/v1/founder-research-products"
SECRET = "S" * 64
KEYS = {
    "EMPIRE_FOUNDER_RESEARCH_AUTH_MODE": "ssh_loopback",
    "EMPIRE_RESEARCH_SSH_PRIVATE_ENABLED": "1",
    "EMPIRE_PRIVATE_FOUNDER_INGRESS_REVIEWED": "1",
    "EMPIRE_RESEARCH_SSH_BRIDGE_SECRET": SECRET,
}


def client(client_ip="127.0.0.1", *, runner=None):
    app = FastAPI()
    kwargs = {}
    if runner is not None:
        kwargs["product_runner"] = runner
    app.include_router(create_founder_research_products_router(**kwargs))
    return TestClient(app, client=(client_ip, 49100))


def test_ssh_mode_disabled_without_explicit_configuration(monkeypatch):
    monkeypatch.setenv("EMPIRE_FOUNDER_RESEARCH_AUTH_MODE", "ssh_loopback")
    for key in KEYS:
        if key != "EMPIRE_FOUNDER_RESEARCH_AUTH_MODE":
            monkeypatch.delenv(key, raising=False)
    with client() as api:
        assert api.get(PATH + "/catalog").status_code == 503


@pytest.mark.parametrize("absent", [
    "EMPIRE_RESEARCH_SSH_PRIVATE_ENABLED",
    "EMPIRE_PRIVATE_FOUNDER_INGRESS_REVIEWED",
    "EMPIRE_RESEARCH_SSH_BRIDGE_SECRET",
])
def test_no_unilateral_ssh_authority(monkeypatch, absent):
    for k, value in KEYS.items():
        monkeypatch.setenv(k, value)
    monkeypatch.delenv(absent, raising=False)
    with client() as api:
        assert api.get(PATH + "/catalog",
                       headers={"authorization": "Bearer " + SECRET}).status_code == 503


def test_authorised_server_bridge_requires_exact_private_secret(monkeypatch):
    for k, value in KEYS.items():
        monkeypatch.setenv(k, value)
    with client() as api:
        for h in ({}, {"authorization": "Bearer " + "X" * 64},
                  {"cf-access-authenticated-user-email": "founder@empire-ai.co.uk"},
                  {"authorization": "Bearer " + SECRET + "x"}):
            assert api.get(PATH + "/catalog", headers=h).status_code == 401
        allowed = api.get(PATH + "/catalog",
                          headers={"authorization": "Bearer " + SECRET})
        assert allowed.status_code == 200
        assert allowed.headers["cache-control"] == "no-store, private"
        assert allowed.json()["private_execution_guardrails"]["source_admission_automatic"] is False


@pytest.mark.parametrize("forwarded_header", [
    "x-forwarded-for", "x-forwarded-host", "x-real-ip",
    "forwarded", "via", "cf-ray", "cf-connecting-ip",
])
def test_untrusted_proxy_headers_forbid_direct_api_auth(monkeypatch, forwarded_header):
    for k, value in KEYS.items():
        monkeypatch.setenv(k, value)
    with client() as api:
        answer = api.get(PATH + "/catalog", headers={
            "authorization": "Bearer " + SECRET,
            forwarded_header: "attacker-controlled",
        })
        assert answer.status_code == 403


def test_remote_peer_refused_even_with_key(monkeypatch):
    for k, value in KEYS.items():
        monkeypatch.setenv(k, value)
    with client("203.0.113.1") as api:
        assert api.get(PATH + "/catalog",
                       headers={"authorization": "Bearer " + SECRET}).status_code == 403


@pytest.mark.parametrize("mode", ["", "ssh", "none", "local", "jwt", "off"])
def test_unsupported_auth_mode_fails_closed(monkeypatch, mode):
    for k, value in KEYS.items():
        monkeypatch.setenv(k, value)
    monkeypatch.setenv("EMPIRE_FOUNDER_RESEARCH_AUTH_MODE", mode)
    with client() as api:
        assert api.get(PATH + "/catalog",
                       headers={"authorization": "Bearer " + SECRET}).status_code == 503


@pytest.mark.parametrize("bad", ["short", "!" * 64, "space " * 15, "\n" * 64])
def test_weak_or_malformed_bridge_secret_never_enables_access(monkeypatch, bad):
    for k, value in KEYS.items():
        monkeypatch.setenv(k, value)
    monkeypatch.setenv("EMPIRE_RESEARCH_SSH_BRIDGE_SECRET", bad)
    with client() as api:
        assert api.get(PATH + "/catalog",
                       headers={"authorization": "Bearer " + bad}).status_code == 503
