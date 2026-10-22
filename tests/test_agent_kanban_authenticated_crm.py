"""Existing first-party CRM session is REQUIRED before showing any agent work.

Only synthetic tasks and fake DB connectors are used. No real CRM login,
session secret, database, background worker or HTTP service is touched.
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.department_work_queue import DepartmentWorkQueue
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead, create_revenue_crm_router
from tests.test_revenue_crm_authenticated_router import A, B, repo


def synthetic_task(root, name, tenant):
    queue = DepartmentWorkQueue(root)
    item, _ = queue.enqueue_step(
        plan_id="synthetic_tenant_plan",
        step={
            "step_id": name, "goal_key": "synthetic_internal_goal",
            "department_keys": ["sales_revenue"],
            "target_component": "identity_enrichment",
            "action": "synthetic_read_only", "authority": "observe",
            "intelligence_request": {"secret": "never_exposed"},
            "success_condition": "needs independent evidence",
        }, priority=60,
    )
    path = queue.ready / f"{item.id}.json"
    record = json.loads(path.read_text())
    record["tenant_id"] = tenant
    path.write_text(json.dumps(record))
    return item.id


def client(root, tenant=None, *, session_tenant=A):
    reader, cursor = repo(tenant_id=A, session_tenant=session_tenant)
    app = FastAPI()
    app.state.verified_tenant = tenant
    app.include_router(create_revenue_crm_router(
        evidence_root=root,
        resolve_authenticated_read=lambda req: (
            AuthenticatedRevenueCrmRead(
                tenant_id=req.app.state.verified_tenant, repository=reader
            ) if req.app.state.verified_tenant else None
        ),
    ))
    return TestClient(app), cursor


def test_legacy_router_cannot_serve_any_board(tmp_path):
    app = FastAPI()
    app.include_router(create_revenue_crm_router(evidence_root=tmp_path))
    response = TestClient(app).get("/v1/revenue-crm/department-kanban")
    assert response.status_code == 503
    assert response.json()["detail"] == "authenticated_crm_scope_required"


def test_unauthenticated_and_header_spoofed_requests_are_denied(tmp_path):
    synthetic_task(tmp_path, "task-a", A)
    guest, cursor = client(tmp_path)
    response = guest.get(
        f"/v1/revenue-crm/department-kanban?tenant_id={A}",
        headers={"X-Tenant-ID": A, "X-Role": "founder", "Authorization": "Bearer forged"},
    )
    assert response.status_code == 401
    assert cursor.calls == []


def test_real_auth_resolver_and_bound_db_session_scope_card_metadata(tmp_path):
    mine = synthetic_task(tmp_path, "tenant-a-work", A)
    synthetic_task(tmp_path, "tenant-b-work", B)
    synthetic_task(tmp_path, "unbound-work", None)
    signed, cursor = client(tmp_path, tenant=A)
    response = signed.get(
        f"/v1/revenue-crm/department-kanban?tenant_id={B}&max_cards_per_lane=20",
        headers={"X-Tenant-ID": B},
    )
    assert response.status_code == 200, response.text
    board = response.json()
    assert board["read_only"] is True
    assert board["execution_authority"] == "none"
    assert board["lanes"]["ready"]["total"] == 1
    cards = board["lanes"]["ready"]["cards"]
    assert cards[0]["work_id"] == mine
    assert "intelligence_request" not in cards[0]
    assert "secret" not in response.text
    assert "tenant-a-work" not in response.text
    assert any("SET LOCAL ROLE" in sql for sql, _ in cursor.calls)
    assert any("empire_current_tenant_id" in sql for sql, _ in cursor.calls)


def test_authenticated_claim_cannot_change_db_bound_tenant(tmp_path):
    synthetic_task(tmp_path, "a-only", A)
    wrong, cursor = client(tmp_path, tenant=B)
    response = wrong.get("/v1/revenue-crm/department-kanban")
    assert response.status_code == 503
    assert "authenticated_crm_read_unavailable" == response.json()["detail"]
    assert cursor.calls == []


def test_mismatched_database_session_fails_closed(tmp_path):
    synthetic_task(tmp_path, "a-only", A)
    wrong, cursor = client(tmp_path, tenant=A, session_tenant=B)
    response = wrong.get("/v1/revenue-crm/department-kanban")
    assert response.status_code == 503
    assert response.json()["detail"] == "authenticated_crm_read_unavailable"
    assert cursor.calls


@pytest.mark.parametrize("limit", ["0", "51", "wrong"])
def test_board_limit_must_be_bounded(tmp_path, limit):
    authorized, _ = client(tmp_path, tenant=A)
    response = authorized.get(f"/v1/revenue-crm/department-kanban?max_cards_per_lane={limit}")
    assert response.status_code == 422
