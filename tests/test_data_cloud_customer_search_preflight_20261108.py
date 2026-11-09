"""Data Cloud only: no unlicensed or chargeable search before request-rights proof.

Synthetic local store and provider; no production DB or external network.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from empire_os.predictive_cloud_customer_api.durable_api import create_metered_private_app
from empire_os.predictive_cloud_customer_api.durable_store import ActiveTenant


TOKEN = "synthetic-local-test-token-no-real-credential-0001"
SOURCE_ID = "approved_provider_fixture"
HEADERS = {
    "Authorization": "Bearer " + TOKEN,
    "Idempotency-Key": "synthetic-search-001",
}


def build(preflight=None, *, output_rights=True, licensed=True,
          authenticated_tenant="synthetic-local-tenant",
          preflight_source_tenant=None, output_source_tenant=None,
          configured_source=SOURCE_ID, observed_source=None,
          observed_hours_ago=0, source_state="RESULTS",
          operational_status="HEALTHY", result_link="https://example.org",
          provider_cost_receipt=None, cost_receipt_verifier=None):
    calls = {"adapter": 0, "reserve": 0, "settle": 0, "preflight": 0, "output_check": 0}
    tenant = ActiveTenant(
        authenticated_tenant, 5, 10000, 500, 500,
        frozenset({"search"}), frozenset()
    )

    class OfflineMeter:
        def authenticate(self, token):
            assert token == TOKEN
            return tenant

        def reserve(self, policy, operation, key, request_hash, token_hash, target_host=None):
            assert policy is tenant and operation == "search"
            calls["reserve"] += 1
            return 17

        def settle(self, policy, reservation_id, state, **kwargs):
            assert policy is tenant and reservation_id == 17
            calls["settle"] += 1
            calls["settlement_state"] = state
            calls["settlement_kwargs"] = kwargs

    def adapter(query, limit):
        calls["adapter"] += 1
        response = {
            "source_id": observed_source if observed_source is not None else configured_source,
            "source_observed_at": (
                datetime.now(timezone.utc) - timedelta(hours=observed_hours_ago)
            ).isoformat(),
            "search_operational_status": operational_status,
            "searchParameters": {"search_state": source_state},
            "organic": [{"title": "Example Service", "link": result_link}]
                if source_state == "RESULTS" else [],
        }
        if provider_cost_receipt is not None:
            response["provider_cost_receipt"] = provider_cost_receipt
        return response

    def preflight_wrapper(tenant_id, source_id, query, limit):
        calls["preflight"] += 1
        calls["preflight_tenant"] = tenant_id
        calls["preflight_source"] = source_id
        assert source_id == configured_source
        assert tenant_id == tenant.tenant_id
        assert query == "HVAC contractor"
        assert limit == 2
        if preflight is None:
            raise AssertionError("not used")
        if preflight_source_tenant is not None and tenant_id != preflight_source_tenant:
            return False
        return preflight(query, limit)

    def output_check(tenant_id, source_id, payload):
        calls["output_check"] += 1
        calls["output_tenant"] = tenant_id
        calls["output_source"] = source_id
        assert source_id == configured_source
        assert tenant_id == tenant.tenant_id
        if output_source_tenant is not None and tenant_id != output_source_tenant:
            return False
        return output_rights

    api = create_metered_private_app(
        store=OfflineMeter(), search_adapter=adapter,
        search_source_id=configured_source,
        licensed_search_output=licensed, source_rights_check=output_check,
        cost_receipt_verifier=cost_receipt_verifier,
        source_request_preflight=preflight_wrapper if preflight is not None else None,
    )
    return api, calls


def _search(api):
    with TestClient(api) as client:
        return client.post(
            "/v1/data/search", headers=HEADERS,
            json={"query": "HVAC contractor", "limit": 2},
        )


@pytest.mark.parametrize("preflight,expected_status,detail", [
    (None, 503, "source_request_rights_preflight_unconfigured"),
    (lambda _q, _n: False, 403, "source_request_rights_not_authorized"),
    (lambda _q, _n: None, 403, "source_request_rights_not_authorized"),
    (lambda _q, _n: 1, 403, "source_request_rights_not_authorized"),
])
def test_never_reserve_or_call_provider_without_exact_true_preflight(preflight, expected_status, detail):
    api, calls = build(preflight)
    response = _search(api)
    assert response.status_code == expected_status
    assert detail in response.text
    assert calls["adapter"] == calls["reserve"] == calls["settle"] == 0
    assert calls["output_check"] == 0
    assert response.headers["cache-control"] == "no-store"


def test_unavailable_rights_owner_fails_closed_before_billable_attempt():
    def unavailable(_q, _n):
        raise RuntimeError("synthetic rights owner unavailable")
    api, calls = build(unavailable)
    response = _search(api)
    assert response.status_code == 503
    assert "source_request_rights_preflight_unavailable" in response.text
    assert calls["adapter"] == calls["reserve"] == calls["settle"] == 0


def test_explicit_customer_rights_flag_false_prevents_preflight_and_provider():
    api, calls = build(lambda _q, _n: True, licensed=False)
    response = _search(api)
    assert response.status_code == 403
    assert "customer_source_use_not_approved" in response.text
    assert calls["preflight"] == calls["adapter"] == calls["reserve"] == 0


def test_source_output_rights_rechecked_after_preflight():
    api, calls = build(lambda _q, _n: True, output_rights=False)
    response = _search(api)
    assert response.status_code == 503
    assert calls["preflight"] == calls["adapter"] == calls["reserve"] == 1
    assert calls["output_check"] == 1
    assert calls["settlement_state"] == "provider_error"
    assert "upstream_or_cost_evidence_unavailable" in response.text


def test_only_verified_two_stage_rights_allows_synthetic_output():
    api, calls = build(lambda _q, _n: True)
    response = _search(api)
    assert response.status_code == 200, response.text
    assert response.json()["buyer_intent_verified"] is False
    assert response.json()["results"][0]["url"] == "https://example.org/"
    assert calls["preflight"] == calls["adapter"] == calls["reserve"] == 1
    assert calls["output_check"] == calls["settle"] == 1
    assert calls["settlement_state"] == "completed"
    assert calls["preflight_source"] == calls["output_source"] == SOURCE_ID
    result_source = response.json()["results"][0]["source"]
    assert result_source["source_id"] == SOURCE_ID
    assert result_source["observed_at"].endswith("+00:00")


def test_source_entitlement_is_bound_to_authenticated_tenant_before_provider_call():
    # One authorised tenant cannot donate its supplier grant to another.
    api, calls = build(
        lambda _q, _n: True,
        authenticated_tenant="tenant-not-approved",
        preflight_source_tenant="tenant-with-source-grant",
    )
    response = _search(api)
    assert response.status_code == 403
    assert calls["preflight_tenant"] == "tenant-not-approved"
    assert calls["preflight"] == 1
    assert calls["reserve"] == calls["adapter"] == calls["settle"] == 0


def test_source_output_entitlement_rechecks_same_authenticated_tenant():
    # Even a permissive query gate must not bypass result-level tenant rights.
    api, calls = build(
        lambda _q, _n: True,
        authenticated_tenant="tenant-not-approved",
        output_source_tenant="tenant-with-source-grant",
    )
    response = _search(api)
    assert response.status_code == 503
    assert calls["preflight_tenant"] == "tenant-not-approved"
    assert calls["output_tenant"] == "tenant-not-approved"
    assert calls["adapter"] == calls["reserve"] == 1
    assert calls["settlement_state"] == "provider_error"
    assert "Example Service" not in response.text


def test_original_verified_tenant_receives_exact_identity_at_both_rights_gates():
    api, calls = build(
        lambda _q, _n: True,
        authenticated_tenant="tenant-with-source-grant",
        preflight_source_tenant="tenant-with-source-grant",
        output_source_tenant="tenant-with-source-grant",
    )
    response = _search(api)
    assert response.status_code == 200
    assert calls["preflight_tenant"] == "tenant-with-source-grant"
    assert calls["output_tenant"] == "tenant-with-source-grant"
    assert calls["settlement_state"] == "completed"


@pytest.mark.parametrize("source_id", [None, "", " ", "UNAPPROVED", "invalid source", "x" * 80])
def test_missing_or_invalid_trusted_supplier_blocks_before_provider(source_id):
    api, calls = build(lambda _q, _n: True, configured_source=source_id)
    response = _search(api)
    assert response.status_code == 503
    assert "trusted_search_source_id_unconfigured" in response.text
    assert calls["preflight"] == calls["reserve"] == calls["adapter"] == 0


def test_source_identity_cannot_switch_after_licensed_preflight():
    api, calls = build(
        lambda _q, _n: True,
        configured_source="supplier_a",
        observed_source="supplier_b",
    )
    response = _search(api)
    assert response.status_code == 503
    assert calls["preflight_source"] == "supplier_a"
    assert calls["adapter"] == calls["reserve"] == 1
    assert calls["settlement_state"] == "provider_error"
    assert calls["output_check"] == 0
    assert "supplier_b" not in response.text


def test_stale_cache_cannot_be_relabelled_as_fresh_customer_data():
    api, calls = build(lambda _q, _n: True, observed_hours_ago=48)
    response = _search(api)
    assert response.status_code == 503
    assert calls["preflight_source"] == calls["output_source"] == SOURCE_ID
    assert calls["settlement_state"] == "provider_error"
    assert "Example Service" not in response.text


@pytest.mark.parametrize("status,state", [
    ("DEGRADED", "NO_RELEVANT_RESULTS"),
    ("UNKNOWN", "NO_RELEVANT_RESULTS"),
    ("HEALTHY", "ERROR"),
    ("RECOVERED", "STALE"),
])
def test_provider_failure_is_never_reported_as_zero_customer_results(status, state):
    api, calls = build(
        lambda _q, _n: True,
        operational_status=status, source_state=state,
    )
    response = _search(api)
    assert response.status_code == 503
    assert calls["settlement_state"] == "provider_error"
    assert calls["reserve"] == calls["adapter"] == 1


@pytest.mark.parametrize("link", [
    "http://127.0.0.1/private",
    "https://127.0.0.1/",
    "https://user:password@valid.org/",
    "https://host.localhost/",
    "https://valid.org:8443/",
    "javascript:alert(1)",
])
def test_bad_search_result_urls_never_leak_to_customer(link):
    api, calls = build(lambda _q, _n: True, result_link=link)
    response = _search(api)
    assert response.status_code == 503
    assert calls["settlement_state"] == "provider_error"
    assert link not in response.text


def test_healthy_source_can_report_genuine_zero_hits_not_provider_outage():
    api, calls = build(
        lambda _q, _n: True, source_state="NO_RELEVANT_RESULTS",
        operational_status="HEALTHY",
    )
    response = _search(api)
    assert response.status_code == 200
    assert response.json() == {
        "status": "no_results", "results": [], "buyer_intent_verified": False,
    }
    assert calls["settlement_state"] == "completed"


# A provider can claim cost receipt "verified": true; that is not independent
# evidence of actual spend. The gateway must supply an outside reconciler.
COST_CLAIM = {
    "verified": True, "actual_usd_micros": 1534,
    "source_ref": "provider-claimed-receipt-001",
}


def test_unverified_provider_cost_claim_cannot_be_booked_as_actual_spend():
    api, calls = build(
        lambda _q, _n: True,
        provider_cost_receipt=COST_CLAIM,
    )
    response = _search(api)
    assert response.status_code == 503
    assert calls["adapter"] == calls["reserve"] == 1
    assert calls["settlement_state"] == "provider_error"
    assert calls["settlement_kwargs"].get("actual_usd_micros") is None
    assert "provider-claimed-receipt" not in response.text


def test_no_provider_cost_receipt_means_unknown_actual_not_zero():
    api, calls = build(lambda _q, _n: True)
    response = _search(api)
    assert response.status_code == 200
    assert calls["settlement_state"] == "completed"
    assert calls["settlement_kwargs"]["actual_usd_micros"] is None
    assert calls["settlement_kwargs"]["cost_source_ref"] is None


def test_only_independent_cost_verifier_outputs_reach_meter():
    verified_calls = []
    def verify(tenant, operation, source, receipt):
        verified_calls.append((tenant, operation, source, receipt))
        return 1500, "independently-reconciled-ledger-0001"
    api, calls = build(
        lambda _q, _n: True,
        provider_cost_receipt=COST_CLAIM,
        cost_receipt_verifier=verify,
    )
    response = _search(api)
    assert response.status_code == 200
    assert len(verified_calls) == 1
    assert verified_calls[0][:3] == (
        "synthetic-local-tenant", "search", SOURCE_ID,
    )
    assert verified_calls[0][3] == COST_CLAIM
    assert calls["settlement_state"] == "completed"
    assert calls["settlement_kwargs"]["actual_usd_micros"] == 1500
    assert calls["settlement_kwargs"]["cost_source_ref"] == (
        "independently-reconciled-ledger-0001"
    )
    assert "provider-claimed-receipt" not in response.text


@pytest.mark.parametrize("result", [
    None,
    False,
    True,
    (True, "fake"),
    ("1534", "ref"),
    (-1, "ref"),
    (10**13, "ref"),
    (1534, ""),
    (1534, "line\nbreak"),
    [1534, "ref"],
])
def test_untrusted_or_invalid_cost_reconciler_result_blocks_actual_claim(result):
    api, calls = build(
        lambda _q, _n: True,
        provider_cost_receipt=COST_CLAIM,
        cost_receipt_verifier=lambda *_: result,
    )
    response = _search(api)
    assert response.status_code == 503
    assert calls["settlement_state"] == "provider_error"


@pytest.mark.parametrize("receipt", [
    {"verified": True, "actual_usd_micros": True, "source_ref": "ref"},
    {"verified": True, "actual_usd_micros": -1, "source_ref": "ref"},
    {"verified": False, "actual_usd_micros": 1, "source_ref": "ref"},
    {"verified": True, "actual_usd_micros": 2, "source_ref": " "},
])
def test_malformed_provider_cost_claim_rejected_before_external_reconciler(receipt):
    verifier_calls = []
    def verify(*arguments):
        verifier_calls.append(arguments)
        return 50, "reviewed"
    api, calls = build(
        lambda _q, _n: True,
        provider_cost_receipt=receipt,
        cost_receipt_verifier=verify,
    )
    response = _search(api)
    assert response.status_code == 503
    assert calls["settlement_state"] == "provider_error"
    assert verifier_calls == []


def test_independent_cost_verification_outage_remains_held():
    def unavailable(*_):
        raise RuntimeError("invoice reader unavailable")
    api, calls = build(
        lambda _q, _n: True,
        provider_cost_receipt=COST_CLAIM,
        cost_receipt_verifier=unavailable,
    )
    response = _search(api)
    assert response.status_code == 503
    assert calls["settlement_state"] == "provider_error"
