"""Founder JEV API is non-enumerable until independently authorised."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.founder_jev_api import create_founder_jev_router
from empire_os.founder_dashboard_service import build_founder_dashboard_service

ENTITY = str(UUID(int=2))
PATH = "/v1/founder-jev/research/" + ENTITY


def make_client(**options):
    app = FastAPI()
    app.include_router(create_founder_jev_router(**options))
    return TestClient(app)


def test_default_founder_service_exposes_only_truthful_jev_status():
    app = build_founder_dashboard_service()
    paths = set(app.openapi()["paths"])
    assert "/v1/founder-jev/status" in paths
    assert not any(path.startswith("/v1/founder-jev/research/") for path in paths)
    response = TestClient(app).get("/v1/founder-jev/status")
    assert response.status_code == 200
    packet = response.json()
    assert packet["economic_reader_configured"] is False
    assert packet["real_canonical_rows_verified"] is None
    assert packet["buyers_identified"] is None
    assert packet["verified_revenue"] is None
    assert packet["send_authorized"] is False
    assert packet["production_activated"] is False


def test_partial_security_configuration_cannot_mount_research_route():
    with pytest.raises(ValueError, match="must be paired"):
        create_founder_jev_router(reader=object())
    with pytest.raises(ValueError, match="must be paired"):
        create_founder_jev_router(authorizer=lambda request: True)


class MockReader:
    def __init__(self):
        self.calls = []

    def read(self, *, entity_id, as_of):
        self.calls.append((entity_id, as_of))
        return {
            "schema_version": "empire.jev.founder_economic_review.v1",
            "mode": "OBSERVE",
            "signal_count": 1,
            "signals_by_type": {
                "revenue_leak": 1, "idle_asset": 0,
                "market_gap": 0, "idle_waste": 0,
            },
            "evidence_fingerprint": "f" * 64,
            "entity_binding_from_observed_signal": True,
            "source_reader": "empire_os.economic_signal_reader",
            "status": "ECONOMIC_EVIDENCE_FOR_RESEARCH",
            "buyer_conversations_verified": False,
            "verified_revenue": None,
            "contact_clearance_available": False,
            "buying_probability_available": False,
            "next_action": "RESEARCH_REQUIRED",
            "independent_buyer_identity_verified": False,
            "source_authorised_commercial_action": False,
            "founder_review_only": True,
            "contains_contact_data": False,
            "outbound_sent": False,
            "payment_action": False,
            "execution_authority": "none",
        }


def test_unauthorized_request_cannot_read_source():
    reader = MockReader()
    response = make_client(reader=reader, authorizer=lambda req: False).get(PATH)
    assert response.status_code == 403
    assert reader.calls == []


def test_authorizer_error_is_a_denial():
    def fail(req):
        raise RuntimeError("permission unavailable")
    reader = MockReader()
    response = make_client(reader=reader, authorizer=fail).get(PATH)
    assert response.status_code == 403
    assert reader.calls == []


def test_authenticated_read_returns_only_aggregate_no_contact():
    reader = MockReader()
    response = make_client(reader=reader, authorizer=lambda req: True).get(PATH)
    assert response.status_code == 200
    body = response.json()
    assert body["signal_count"] == 1
    assert body["contains_contact_data"] is False
    assert "tenant_id" not in body
    assert "entity_id" not in body
    assert reader.calls[0][0] == ENTITY
    assert reader.calls[0][1].tzinfo is not None


def test_bad_entity_is_rejected_before_database():
    reader = MockReader()
    response = make_client(reader=reader, authorizer=lambda req: True).get(
        "/v1/founder-jev/research/invalid-id"
    )
    assert response.status_code == 400
    assert reader.calls == []


def test_response_contract_must_not_leak_pii():
    class Leaking(MockReader):
        def read(self, **kwargs):
            output = super().read(**kwargs)
            output["email"] = "example@example.invalid"
            return output

    response = make_client(reader=Leaking(), authorizer=lambda req: True).get(PATH)
    assert response.status_code == 503
    assert "example@example.invalid" not in response.text


def test_response_contract_must_not_assert_sales_or_authority():
    class Unsafe(MockReader):
        def read(self, **kwargs):
            output = super().read(**kwargs)
            output["contact_clearance_available"] = True
            return output

    response = make_client(reader=Unsafe(), authorizer=lambda req: True).get(PATH)
    assert response.status_code == 503
