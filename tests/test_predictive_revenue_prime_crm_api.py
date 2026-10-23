"""Request-scoped PRIME CRM status route, no customer data or auth bypass."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_api import (
    AuthenticatedRevenueCrmRead, create_revenue_crm_router,
)
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository

A = "00000000-0000-0000-0000-000000000101"
B = "00000000-0000-0000-0000-000000000102"
PROSPECT = "00000000-0000-0000-0000-000000000017"


def _reader(*, tenant=A, fail=False):
    repo = PostgresRevenueCrmRepository(
        "test-only-never-used", tenant_id=tenant,
        connect_factory=lambda _: (_ for _ in ()).throw(
            AssertionError("no actual database call"),
        ),
    )
    def rows(*, limit):
        if fail:
            from empire_os.revenue_crm_transport import RevenueCrmTransportError
            raise RevenueCrmTransportError("db-secret-NEVER-EXPOSE")
        return [{
            "tenant_id": tenant,
            "prospect_id": PROSPECT,
            "business_name": "secret-brand",
            "conversation_id": "private-convo",
            "conversation_state": "engaged",
            "closer_case_id": "private-case",
            "closer_state": "proposal_ready",
            "price_cents": 10000,
            "deal_probability": 0.7,
        }]
    repo.prospects = rows
    return repo


def _client(reader=None, *, signed_tenant=None):
    service = FastAPI()
    service.state.signed_tenant = signed_tenant
    if reader is None:
        service.include_router(create_revenue_crm_router())
    else:
        service.include_router(create_revenue_crm_router(
            resolve_authenticated_read=lambda request: (
                AuthenticatedRevenueCrmRead(
                    tenant_id=request.app.state.signed_tenant,
                    repository=reader,
                ) if request.app.state.signed_tenant else None
            )
        ))
    return TestClient(service)


def test_default_unconfigured_hub_route_returns_503():
    response = _client().get("/v1/revenue-crm/predictive-prime/prospects")
    assert response.status_code == 503
    assert response.json()["detail"] == "authenticated_crm_scope_required"


def test_unverified_header_and_query_cannot_get_prime_crm():
    response = _client(_reader()).get(
        "/v1/revenue-crm/predictive-prime/prospects?tenant_id=" + A,
        headers={"X-Tenant-ID": A, "Authorization": "Bearer fake"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "authenticated_crm_scope_required"


def test_authenticated_read_has_only_bounded_aggregate_fields():
    response = _client(_reader(), signed_tenant=A).get(
        "/v1/revenue-crm/predictive-prime/prospects?limit=100",
        headers={"X-Tenant-ID": B},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_status"] == "AUTHENTICATED_TENANT_CRM_VIEW_READ"
    assert body["returned_prospect_rows"] == 1
    assert body["engaged_conversation_rows"] == 1
    assert body["proposal_ready_rows"] == 1
    assert body["modelled_pipeline_forecast_cents"] is None
    assert body["recognized_revenue_cents"] is None
    assert body["execution_authority"] == "none"
    for forbidden in (PROSPECT, "secret-brand", "private-convo", "private-case", A):
        assert forbidden not in response.text


def test_wrong_authenticated_tenant_fails_closed():
    response = _client(_reader(tenant=A), signed_tenant=B).get(
        "/v1/revenue-crm/predictive-prime/prospects"
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "authenticated_crm_read_unavailable"


def test_read_failure_sanitized_to_503():
    response = _client(_reader(fail=True), signed_tenant=A).get(
        "/v1/revenue-crm/predictive-prime/prospects"
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "authenticated_crm_read_unavailable"
    assert "NEVER-EXPOSE" not in response.text


def test_reject_unbounded_read_limit():
    response = _client(_reader(), signed_tenant=A).get(
        "/v1/revenue-crm/predictive-prime/prospects?limit=501"
    )
    assert response.status_code == 422
