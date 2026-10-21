"""Fail-closed session, budget and no-GET tests for private Research product."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
import jwt
import pytest

from empire_os import founder_research_auth
from empire_os.founder_research_products_api import (
    ResearchExecutionBudget, create_founder_research_products_router,
)

PATH = "/v1/founder-research-products"


def fake_founder(request: Request):
    return "founder"


def _app(**kwargs):
    app = FastAPI()
    app.include_router(create_founder_research_products_router(**kwargs))
    return app


def test_default_missing_identity_config_denies_all_and_never_executes(monkeypatch):
    for key in ("EMPIRE_FOUNDER_CF_TEAM_DOMAIN", "EMPIRE_FOUNDER_CF_ACCESS_AUD",
                "EMPIRE_RESEARCH_ALLOWED_FOUNDER_SUB"):
        monkeypatch.delenv(key, raising=False)
    attempted = []
    with TestClient(_app(product_runner=lambda *a, **k: attempted.append(a))) as client:
        assert client.get(PATH + "/catalog").status_code == 503
        assert client.post(PATH + "/preview", json={"product": "empire_agent"}).status_code == 503
        assert client.get(PATH + "/preview").status_code == 405
    assert attempted == []


def test_founder_identity_validates_signature_audience_issuer_subject(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    team = "empire-test.cloudflareaccess.com"
    for key, value in {
        "EMPIRE_FOUNDER_CF_TEAM_DOMAIN": team,
        "EMPIRE_FOUNDER_CF_ACCESS_AUD": "audience-123",
        "EMPIRE_RESEARCH_ALLOWED_FOUNDER_SUB": "founder-sub-123",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(founder_research_auth, "_jwks_client", lambda team: SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key())
    ))
    now = datetime.now(timezone.utc)
    claims = {"sub": "founder-sub-123", "aud": "audience-123",
              "iss": "https://" + team, "iat": now, "exp": now + timedelta(minutes=5)}
    def token(**changes):
        return jwt.encode({**claims, **changes}, private, algorithm="RS256")
    with TestClient(_app()) as client:
        assert client.get(PATH + "/catalog").status_code == 401
        ok = client.get(PATH + "/catalog", headers={"Authorization": "Bearer " + token()})
        assert ok.status_code == 200
        assert ok.headers["cache-control"] == "no-store, private"
        assert ok.json()["private_execution_guardrails"]["max_original_pages_per_request"] == 6
        assert client.get(PATH + "/catalog", headers={"Authorization": "Bearer " + token(sub="other")}).status_code == 403
        assert client.get(PATH + "/catalog", headers={"Authorization": "Bearer " + token(aud="other")}).status_code == 401
        assert client.get(PATH + "/catalog", headers={"Authorization": "Bearer " + token(iss="https://wrong.cloudflareaccess.com")}).status_code == 401
        assert client.get(PATH + "/catalog", headers={"Authorization": "Bearer " + token(exp=now-timedelta(minutes=3))}).status_code == 401
        assert client.get(PATH + "/catalog", headers={"Authorization": "Bearer tampered.token.fake"}).status_code == 401


def test_execution_cooldown_exclusive_and_no_get():
    budget = ResearchExecutionBudget(min_interval_seconds=60)
    with budget.run("founder"):
        with pytest.raises(HTTPException) as busy:
            with budget.run("founder"):
                pass
    assert busy.value.status_code == 429
    with pytest.raises(HTTPException) as cooldown:
        with budget.run("founder"):
            pass
    assert cooldown.value.status_code == 429
    with budget.run("different-principal"):
        pass
    attempted = []
    with TestClient(_app(product_runner=lambda *a, **k: attempted.append(a),
                         require_founder=fake_founder,
                         execution_budget=ResearchExecutionBudget(0))) as client:
        assert client.get(PATH + "/preview?product=empire_agent").status_code == 405
        assert client.post(PATH + "/preview", json={"product": "not-allowed"}).status_code == 422
        assert client.post(PATH + "/preview", json={"product": "empire_agent", "shell": "id"}).status_code == 422
    assert attempted == []


def test_execution_cannot_invent_commercial_authority():
    def unsafe_runner(*a, **k):
        return {"outbound_authorized": True, "database_writes": False,
                "finance_authorized": False, "customer_delivery_authorized": False,
                "original_source_count": 0}
    with TestClient(_app(product_runner=unsafe_runner,
                         require_founder=fake_founder)) as client:
        assert client.post(PATH + "/preview", json={"product": "empire_agent"}).status_code == 503
