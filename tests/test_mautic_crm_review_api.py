"""No external service: HTTP auth and input controls for existing CRM inbox."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.mautic_crm_review_api import create_mautic_crm_review_router

PATH = "/v1/revenue-crm/integrations/mautic/inbox/reviews"


def client(resolver):
    app = FastAPI()
    app.include_router(
        create_mautic_crm_review_router(resolve_authenticated_read=resolver)
    )
    return TestClient(app)


def test_missing_existing_authenticated_crm_login_is_unauthorised():
    assert client(lambda _: None).get(PATH).status_code == 401


def test_existing_crm_authentication_errors_are_fail_closed():
    def broken(_request):
        raise RuntimeError("synthetic auth outage")
    response = client(broken).get(PATH)
    assert response.status_code == 503
    assert response.json()["detail"] == "authenticated_crm_read_unavailable"


def test_wrong_resolver_type_is_not_accepted_as_tenant_authority():
    response = client(lambda _: {"tenant_id": "spoof"}).get(PATH)
    assert response.status_code == 503


def test_caller_supplied_tenant_cannot_select_data():
    response = client(lambda _: None).get(
        PATH, params={"tenant_id": "00000000-0000-0000-0000-000000000999"}
    )
    assert response.status_code == 401


def test_bounded_limit_rejects_empty_and_excessive_queries():
    c = client(lambda _: None)
    assert c.get(PATH, params={"limit": 0}).status_code == 422
    assert c.get(PATH, params={"limit": 101}).status_code == 422


def test_router_cannot_be_constructed_without_existing_authentication():
    with pytest.raises(ValueError):
        create_mautic_crm_review_router(resolve_authenticated_read=None)
