"""Independent Omnisend-inspired Revenue CRM journey review tests.

No mail, provider, database, real tenant token or production writes are used.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_api import create_revenue_crm_router
from empire_os.revenue_crm_journeys import (
    STAGES,
    journey_blueprint,
    preview_crm_journey,
    preview_segment_distribution,
)

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def prospect(**kw):
    row = {
        "tenant_id": TENANT,
        "prospect_id": "00000000-0000-0000-0000-000000000201",
        "business_name": "A Co",
        "prospect_status": "new",
        "conversation_id": None, "conversation_state": None,
        "conversation_updated_at": None,
        "closer_case_id": None, "closer_state": None,
        "closer_updated_at": None,
        "fulfilment_order_id": None, "fulfilment_state": None,
        "fulfilment_updated_at": None,
        "price_cents": 999999, "deal_probability": 0.99,
    }
    row.update(kw)
    return row


def test_visual_graph_contract_is_bounded_no_actions():
    graph = journey_blueprint()
    assert [n["id"] for n in graph["nodes"]] == list(STAGES)
    assert len(graph["edges"]) == len(STAGES) - 1
    assert len({n["id"] for n in graph["nodes"]}) == len(STAGES)
    assert graph["visual_graph_ready"] is True
    assert graph["actual_drag_drop_editor_built"] is True
    assert graph["visual_editor_mode"] == "LOCAL_DESIGN_ONLY"
    assert graph["workflow_server_persistence"] is False
    assert {c["channel"] for c in graph["supported_channels"]} == {
        "email", "sms", "web_push"
    }
    assert all(c["send_enabled"] is False for c in graph["supported_channels"])
    assert graph["execution_authority"] == "none"
    assert not graph["recognized_revenue_enabled"]


@pytest.mark.parametrize("values,expected,ref", [
    ({"conversation_id": "conv-1", "conversation_state": "engaged"},
     "engaged_conversation_review", "conversation_id"),
    ({"closer_case_id": "case-1", "closer_state": "proposal_ready"},
     "proposal_review", "closer_case_id"),
    ({"closer_case_id": "case-1", "closer_state": "awaiting_payment"},
     "awaiting_payment_review", "closer_case_id"),
    ({"fulfilment_order_id": "order-1", "fulfilment_state": "delivered"},
     "fulfilment_review", "fulfilment_order_id"),
    ({"prospect_status": "suppressed", "conversation_id": "conv-1",
      "conversation_state": "engaged"}, "contact_hold", None),
    ({"conversation_state": "engaged"}, "unqualified_evidence_review", None),
])
def test_segment_needs_actual_canonical_object(values, expected, ref):
    result = preview_crm_journey(prospect(**values), now=NOW)
    assert result["segment"] == expected
    assert result["execution_authority"] == "none"
    assert all(x == "BLOCKED_NO_SEND" for x in result["channel_actions"].values())
    assert result["observed_attribution_revenue_cents"] is None
    assert result["forecast_revenue_cents"] is None
    assert result["potential_price_cents_is_revenue"] is False
    assert ("CANONICAL_SUPPRESSION_NOT_JOINED" in result["blockers"])
    assert (len(result["evidence_refs"]) == 1) == (ref is not None)
    if ref:
        assert result["evidence_refs"][0]["kind"] == ref


def test_timeline_recovery_proposal_never_schedules_a_send():
    stale = NOW - timedelta(days=4)
    recent = NOW - timedelta(hours=1)
    for ts, is_stale in [(stale, True), (recent, False)]:
        row = prospect(
            conversation_id="conv-1", conversation_state="engaged",
            conversation_updated_at=ts,
        )
        result = preview_crm_journey(row, now=NOW, next_action={
            "action": "review_engaged_conversation",
        })
        assert result["engaged_conversation_stale_candidate"] is is_stale
        assert result["existing_crm_next_action"] == "review_engaged_conversation"
        assert result["send_authorized"] is False
        assert result["followup_authorized"] is False


def test_unclear_timestamp_never_proves_stalled_and_naive_clock_rejected():
    row = prospect(conversation_id="conv-1", conversation_state="engaged",
                   conversation_updated_at="2026-10-01T12:00:00")
    assert preview_crm_journey(row, now=NOW)["engaged_conversation_stale_candidate"] is False
    with pytest.raises(ValueError, match="timezone"):
        preview_crm_journey(row, now=NOW.replace(tzinfo=None))


def test_unbound_identity_fails_closed():
    with pytest.raises(ValueError, match="tenant-scoped"):
        preview_crm_journey(prospect(tenant_id=None), now=NOW)
    with pytest.raises(ValueError, match="tenant-scoped"):
        preview_crm_journey(prospect(prospect_id=None), now=NOW)


def test_counts_bound_to_exact_authenticated_tenant_dedupe_and_page():
    base = prospect()
    second = prospect(
        prospect_id="00000000-0000-0000-0000-000000000202",
        conversation_id="conv-2", conversation_state="engaged",
    )
    result = preview_segment_distribution([base, second], tenant_id=TENANT, requested_limit=2)
    assert result["observed_prospect_count"] == 2
    assert {x["name"]: x["count"] for x in result["segments"]} == {
        "engaged_conversation_review": 1, "unqualified_evidence_review": 1,
    }
    assert result["page_may_be_partial"] is True
    assert result["complete_tenant_audience_verified"] is False
    assert result["subscribers_verified"] is False
    assert result["revenue_cents"] is None
    with pytest.raises(ValueError, match="cross-tenant"):
        preview_segment_distribution([base, prospect(tenant_id=OTHER, prospect_id="p3")],
                                     tenant_id=TENANT)
    with pytest.raises(ValueError, match="duplicate"):
        preview_segment_distribution([base, base], tenant_id=TENANT)
    with pytest.raises(ValueError, match="bounded"):
        preview_segment_distribution([base, second], tenant_id=TENANT, requested_limit=1)


class MemoryRepo:
    tenant_id = TENANT
    def __init__(self, rows):
        self.rows = rows
    def prospects(self, *, limit):
        return self.rows[:limit]
    def prospect(self, prospect_id):
        return next((r for r in self.rows if str(r["prospect_id"]) == str(prospect_id)), None)
    def buyers(self, *, limit):
        return []


def client(repository=None):
    app = FastAPI()
    app.include_router(create_revenue_crm_router(repository))
    return TestClient(app)


def test_crm_endpoints_are_read_only_without_live_senders_or_spoofed_approvals():
    row = prospect(
        conversation_id="conv-1", conversation_state="engaged",
        conversation_updated_at=NOW,
    )
    c = client(MemoryRepo([row]))
    for path in (
        "/v1/revenue-crm/journeys/blueprint",
        "/v1/revenue-crm/journeys/segments/preview",
        f"/v1/revenue-crm/prospects/{row['prospect_id']}/journey-preview",
    ):
        result = c.get(path, headers={"X-Tenant-ID": OTHER, "X-Consent": "true",
                                      "X-Send-Authorized": "true"})
        assert result.status_code == 200, result.text
        assert result.json()["execution_authority"] == "none"
    view = c.get(f"/v1/revenue-crm/prospects/{row['prospect_id']}/journey-preview").json()
    assert view["tenant_id"] == TENANT
    assert view["segment"] == "engaged_conversation_review"
    assert view["send_authorized"] is False
    assert c.get("/v1/revenue-crm/journeys/segments/preview?limit=501").status_code == 422
    assert c.get("/v1/revenue-crm/prospects/missing/journey-preview").status_code == 404


def test_disabled_crm_router_and_cross_tenant_rows_are_not_exposed():
    inactive = client()
    assert inactive.get("/v1/revenue-crm/journeys/blueprint").status_code == 503
    assert inactive.get("/v1/revenue-crm/journeys/segments/preview").status_code == 503
    assert inactive.get("/v1/revenue-crm/prospects/any/journey-preview").status_code == 503
    crossed = MemoryRepo([prospect(tenant_id=OTHER)])
    assert client(crossed).get("/v1/revenue-crm/journeys/segments/preview").status_code == 503
    assert client(crossed).get(
        f"/v1/revenue-crm/prospects/{crossed.rows[0]['prospect_id']}/journey-preview"
    ).status_code == 503  # cross-tenant fake rows cannot bypass the CRM guard.

def test_native_postgres_uuid_and_datetime_values_are_supported():
    from uuid import UUID
    row = prospect(
        tenant_id=UUID(TENANT),
        prospect_id=UUID("00000000-0000-0000-0000-000000000201"),
        conversation_id=UUID("00000000-0000-0000-0000-000000000301"),
        conversation_state="engaged",
        conversation_updated_at=NOW - timedelta(days=4),
    )
    preview = preview_crm_journey(row, now=NOW)
    assert preview["tenant_id"] == TENANT
    assert preview["prospect_id"] == str(row["prospect_id"])
    assert preview["engaged_conversation_stale_candidate"] is True
    assert preview["evidence_refs"][0]["record_id"] == str(row["conversation_id"])
    summary = preview_segment_distribution([row], tenant_id=TENANT)
    assert summary["segments"][0]["name"] == "engaged_conversation_review"
    c = client(MemoryRepo([row]))
    response = c.get(f"/v1/revenue-crm/prospects/{row['prospect_id']}/journey-preview")
    assert response.status_code == 200, response.text
    assert response.json()["tenant_id"] == TENANT

def test_journey_paths_require_server_authenticated_read_even_if_client_spoofs_tenant():
    app = FastAPI()
    app.include_router(create_revenue_crm_router(
        resolve_authenticated_read=lambda _request: None,
    ))
    c = TestClient(app)
    for path in (
        "/v1/revenue-crm/journeys/blueprint",
        "/v1/revenue-crm/journeys/segments/preview?limit=5",
        "/v1/revenue-crm/prospects/one/journey-preview",
    ):
        response = c.get(path, headers={
            "X-Tenant-ID": TENANT, "X-Consent": "true", "Authorization": "Bearer fake",
        })
        assert response.status_code == 401
        assert response.json()["detail"] == "authenticated_crm_scope_required"
