"""Existing Data Cloud gateway -> original first-party Search Fabric public fetch.

Synthetic fetch + meter, no production DB, network, paid provider or secrets.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from empire_os.predictive_cloud_customer_api import gateway_candidate_entrypoint as owner
from empire_os.predictive_cloud_customer_api import durable_api
from empire_os.predictive_cloud_customer_api.durable_store import ActiveTenant
from tests.test_predictive_cloud_route_assembly_20261107 import components

TOKEN = "synthetic-first-party-search-client-token"
QUERY = "roofing suppliers chicago"
SOURCE = owner.FIRST_PARTY_SEARCH_SOURCE


class ObservedRows(list):
    def __init__(self, rows=(), *, available=True):
        super().__init__(rows)
        self.provider_available = available


class LocalMeter:
    def __init__(self):
        self.tenant = ActiveTenant(
            "synthetic-tenant-one", 20, 10000, 500, 500,
            frozenset({"search"}), frozenset(),
        )
        self.reserves = []
        self.settlements = []

    def authenticate(self, token):
        assert token == TOKEN
        return self.tenant

    def reserve(self, policy, operation, key, fingerprint, token_hash, target_host=None):
        assert policy is self.tenant
        assert operation == "search"
        self.reserves.append((key, fingerprint))
        return 123

    def settle(self, policy, reservation_id, state, **kwargs):
        assert policy is self.tenant
        assert reservation_id == 123
        self.settlements.append((state, kwargs))


def build(monkeypatch, *, enable=True, available=True, rows=None,
          source_allowed=True, output_allowed=True, callbacks=True,
          quality_filter=None):
    meter = LocalMeter()
    calls = {"fetch": 0, "preflight": [], "output": [], "attestation": []}
    if rows is None:
        rows = [{
            "title": "Real first-party parser fixture",
            "link": "https://supplier.example.org/catalog",
            "snippet": "Public data search result",
            "engine": "bing_html",
        }]

    def fetch(query, *, num):
        calls["fetch"] += 1
        assert query == QUERY
        assert num == 2
        return ObservedRows(rows, available=available)

    def preflight(tenant, source, query, limit):
        calls["preflight"].append((tenant, source, query, limit))
        return source_allowed

    def output_check(tenant, source, payload):
        calls["output"].append((tenant, source, payload["source_id"]))
        return output_allowed

    monkeypatch.setattr(owner, "EmpireDbMeteringStore", lambda factory: meter)
    monkeypatch.setattr(
        durable_api, "verify_gateway_attestation",
        lambda request, *, tenant_id: calls["attestation"].append(tenant_id),
    )
    app = owner.create_gateway_candidate_app(
        connect_factory=lambda: None,
        enable_first_party_search=enable,
        first_party_public_fetch=fetch,
        first_party_quality_filter=quality_filter or (
            lambda rows, query, limit: rows[:limit]
        ),
        source_request_preflight=preflight if callbacks else None,
        source_output_check=output_check if callbacks else None,
    )
    return app, meter, calls


def search(app):
    with TestClient(app) as client:
        return client.post(
            "/v1/data/search",
            headers={
                "Authorization": "Bearer " + TOKEN,
                "Idempotency-Key": "original-fabric-test-001",
            },
            json={"query": QUERY, "limit": 2},
        )


def test_existing_gateway_first_party_fetch_full_customer_response(monkeypatch):
    app, meter, calls = build(monkeypatch)
    response = search(app)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "results"
    assert body["buyer_intent_verified"] is False
    assert len(body["results"]) == 1
    provenance = body["results"][0]["source"]
    assert provenance["source_id"] == SOURCE
    assert provenance["upstream_engine"] == "bing_html"
    assert provenance["url"] == "https://supplier.example.org/catalog"
    assert datetime.fromisoformat(provenance["observed_at"]).tzinfo is not None
    assert datetime.fromisoformat(provenance["retrieved_at"]).tzinfo is not None
    assert calls["attestation"] == ["synthetic-tenant-one"]
    assert calls["preflight"] == [("synthetic-tenant-one", SOURCE, QUERY, 2)]
    assert calls["output"] == [("synthetic-tenant-one", SOURCE, SOURCE)]
    assert calls["fetch"] == len(meter.reserves) == len(meter.settlements) == 1
    assert meter.settlements[0][0] == "completed"
    # The original PG18 SQL holds the whole tenant on NULL cost. A directly
    # observed public fetch is verified free of *paid search API* charges.
    assert meter.settlements[0][1]["actual_usd_micros"] == 0
    assert meter.settlements[0][1]["cost_source_ref"] == (
        "empire_fabric_direct_public_no_paid_api_v1"
    )
    assert response.headers["cache-control"] == "no-store"


def test_first_party_collector_not_on_by_default(monkeypatch):
    app, meter, calls = build(monkeypatch, enable=False)
    response = search(app)
    assert response.status_code == 403
    assert "customer_source_use_not_approved" in response.text
    assert calls["fetch"] == 0
    assert meter.reserves == meter.settlements == []


def test_source_use_rejection_precedes_fetch_and_meter(monkeypatch):
    app, meter, calls = build(monkeypatch, source_allowed=False)
    response = search(app)
    assert response.status_code == 403
    assert calls["fetch"] == 0
    assert meter.reserves == meter.settlements == []
    assert calls["output"] == []


def test_result_rights_failure_never_returns_customer_data(monkeypatch):
    app, meter, calls = build(monkeypatch, output_allowed=False)
    response = search(app)
    assert response.status_code == 503
    assert "Real first-party parser fixture" not in response.text
    assert calls["fetch"] == 1
    assert meter.settlements[0][0] == "provider_error"
    assert meter.settlements[0][1]["actual_usd_micros"] == 0


def test_healthy_zero_result_is_not_an_outage(monkeypatch):
    app, meter, calls = build(monkeypatch, rows=[])
    response = search(app)
    assert response.status_code == 200
    assert response.json() == {
        "status": "no_results", "results": [],
        "buyer_intent_verified": False,
    }
    assert calls["fetch"] == 1
    assert meter.settlements[0][0] == "completed"
    assert meter.settlements[0][1]["actual_usd_micros"] == 0


def test_failed_source_retrieval_is_not_a_genuine_zero_result(monkeypatch):
    app, meter, calls = build(monkeypatch, rows=[], available=False)
    response = search(app)
    assert response.status_code == 503
    assert calls["fetch"] == 1
    assert meter.settlements[0][0] == "provider_error"
    assert meter.settlements[0][1]["actual_usd_micros"] == 0


@pytest.mark.parametrize("rows", [
    [{"title": "not verified", "link": "https://example.org"}],
    [{"title": "wrong source", "link": "https://example.org", "engine": "unknown"}],
    [{"title": "unsafe", "link": "http://127.0.0.1/", "engine": "bing_html"}],
])
def test_source_identity_and_safe_result_errors_fail_closed(monkeypatch, rows):
    app, meter, calls = build(monkeypatch, rows=rows)
    response = search(app)
    assert response.status_code == 503
    assert meter.settlements[0][0] == "provider_error"


def test_gateway_configuration_cannot_skip_source_use_callbacks(monkeypatch):
    with pytest.raises(ValueError, match="first_party_source_use_policy_callbacks_required"):
        build(monkeypatch, callbacks=False)


def test_existing_relevance_filter_excludes_unrelated_observed_results(monkeypatch):
    app, meter, calls = build(
        monkeypatch,
        quality_filter=lambda rows, query, limit: [],
    )
    response = search(app)
    assert response.status_code == 200
    assert response.json()["status"] == "no_results"
    assert response.json()["results"] == []
    assert calls["fetch"] == 1
    assert meter.settlements[0][0] == "completed"


def test_existing_relevance_filter_failure_never_leaks_raw_results(monkeypatch):
    def fail(*_):
        raise ValueError("quality pipeline offline")
    app, meter, calls = build(monkeypatch, quality_filter=fail)
    response = search(app)
    assert response.status_code == 503
    assert "Real first-party parser fixture" not in response.text
    assert meter.settlements[0][0] == "provider_error"


def test_existing_signed_gateway_full_customer_search_chain(monkeypatch, components):
    """Real signed Data Cloud session + original mount + owned collector contract.

    Synthetic first-party rows/meter and explicit TEST-ONLY release evidence.
    Does not assert any production permission, identity, or deployment.
    """
    from fastapi import FastAPI
    from empire_os.predictive_cloud_route_assembly import (
        SEARCH_PILOT_REQUIREMENTS, attach_existing_customer_routes,
    )
    verifier, state, candidate, evidence, signed_session = components
    meter = LocalMeter()
    # The existing CRM founder test verifier validates the same synthetic
    # tenant as the synthetic canonical Data Cloud meter.
    meter.tenant = ActiveTenant(
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", 20, 10000, 500, 500,
        frozenset({"search"}), frozenset(),
    )
    observed = []

    def original_collector(query, *, num):
        observed.append(("fetch", query, num))
        return ObservedRows([{
            "title": "Python official documentation",
            "link": "https://docs.python.org/3/",
            "snippet": "Programming language reference",
            "engine": "bing_html",
        }])

    def source_preflight(tenant_id, source_id, query, limit):
        observed.append(("preflight", tenant_id, source_id))
        return tenant_id == meter.tenant.tenant_id and source_id == SOURCE

    def output_check(tenant_id, source_id, payload):
        observed.append(("output", tenant_id, source_id))
        return tenant_id == meter.tenant.tenant_id and payload["source_id"] == SOURCE

    monkeypatch.setattr(owner, "EmpireDbMeteringStore", lambda factory: meter)
    customer = owner.create_gateway_candidate_app(
        connect_factory=lambda: None,
        enable_first_party_search=True,
        first_party_public_fetch=original_collector,
        first_party_quality_filter=lambda rows, query, limit: rows[:limit],
        source_request_preflight=source_preflight,
        source_output_check=output_check,
    )
    host = FastAPI()

    @host.get("/existing")
    def original_route():
        return {"untouched": True}

    selected = attach_existing_customer_routes(
        host, customer, verifier,
        release_evidence=lambda: {k: True for k in SEARCH_PILOT_REQUIREMENTS},
        search_pilot=True,
    )
    assert selected == ("/v1/data/search", "/v1/data/usage")
    request = {
        "Authorization": "Bearer " + TOKEN,
        "X-Empire-Data-Session": signed_session(),
        "Idempotency-Key": "original-first-party-test-0001",
    }
    with TestClient(host) as client:
        assert client.get("/existing").json() == {"untouched": True}
        assert client.post("/v1/data/site-audits").status_code == 404
        assert client.post(
            "/v1/data/search",
            headers={"Authorization": "Bearer " + TOKEN},
            json={"query": QUERY, "limit": 2},
        ).status_code == 401
        response = client.post(
            "/v1/data/search", headers=request,
            json={"query": QUERY, "limit": 2},
        )
        assert response.status_code == 200, response.text
        assert response.json()["results"][0]["source"]["source_id"] == SOURCE
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert observed == [
            ("preflight", meter.tenant.tenant_id, SOURCE),
            ("fetch", QUERY, 2),
            ("output", meter.tenant.tenant_id, SOURCE),
        ]
        assert len(meter.reserves) == 1
        assert meter.settlements[0][0] == "completed"
        state["entitled"] = False
        blocked = client.post(
            "/v1/data/search", headers=request,
            json={"query": QUERY, "limit": 2},
        )
        assert blocked.status_code == 403
        assert len(meter.reserves) == 1
