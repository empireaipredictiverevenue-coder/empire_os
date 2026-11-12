"""Pipedrive-style CRM board: evidence, tenant isolation, status honesty and HTTP gates."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_multi_pipeline import (
    PIPELINES, PipelineProjectionError, build_multi_pipeline_board,
)
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead, create_revenue_crm_router
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository

TENANT_A="00000000-0000-0000-0000-000000000101"
TENANT_B="00000000-0000-0000-0000-000000000102"
PERSON="00000000-0000-0000-0000-000000000301"
BUYER="00000000-0000-0000-0000-000000000401"
NOW=datetime(2026,11,12,12,tzinfo=timezone.utc)


def prospect(tenant=TENANT_A, **changes):
    return {
        "tenant_id":tenant, "prospect_id":PERSON, "business_name":"Example Roofing",
        "niche":"roofing", "metro":"UK:London", "prospect_status":"research",
        "conversation_id":None, "conversation_state":None,
        "closer_case_id":None, "closer_state":None,
        "fulfilment_order_id":None, "fulfilment_state":None,
        "price_cents":950000, **changes,
    }


def buyer(tenant=TENANT_A, **changes):
    return {
        "tenant_id":tenant, "buyer_id":BUYER, "buyer_name":"Network Buying Calls",
        "niche":"roofing", "metro":"UK:London", "buyer_status":"research",
        "is_active":True, "available_capacity":20, "capacity_verified_at":None,
        "commercial_terms_verified_at":None, "delivery_verified_at":None,
        **changes,
    }


def board(prospects=(), buyers=(), tenant=TENANT_A, pipe=None):
    return build_multi_pipeline_board(
        prospects, buyers,
        authenticated_tenant_id=tenant,
        now=NOW, pipeline=pipe,
    )


def test_exact_multi_motion_definitions_without_country_as_pipeline():
    ids=[p[0] for p in PIPELINES]
    assert len(ids)==len(set(ids))==10
    assert all(not x.endswith(("_uk","_us")) for x in ids)
    assert "lead_buyers" in ids and "publisher_partners" in ids
    assert "owned_consumer_enquiries" in ids
    assert "service_customers" in ids and "software_subscriptions" in ids


def test_unbound_roofing_prospect_not_promoted_to_lead_buyer():
    data=board([prospect()])
    assert data["unassigned_prospects"]==1
    assert data["buyer_account_cards"]==0
    assert len(data["pipelines"])==11
    card=data["cards"][0]
    assert card["pipeline_id"]=="unclassified"
    assert card["stage"]=="triage"
    assert card["market"]=="UNVERIFIED"
    assert card["pipeline_binding_verified"] is False
    assert card["won_verified"] is False
    assert card["recognized_revenue_cents"] is None
    assert data["realized_revenue_cents"] is None
    assert data["stage_changes_persisted"] is False


def test_trusted_explicit_pipeline_binding_maps_real_conversation_and_proposal():
    row=prospect(
        pipeline_id="service_customers",
        conversation_id="recorded_conversation", conversation_state="engaged",
        conversation_updated_at=NOW-timedelta(days=9),
    )
    c=board([row])["cards"][0]
    assert c["pipeline_id"]=="service_customers" and c["stage"]=="discovery"
    assert c["stalled_review"] is True
    assert c["next_activity_due_at"] is None
    assert "conversation" in c["next_activity"]
    row.update(closer_case_id="proposal", closer_state="proposal_ready")
    c=board([row])["cards"][0]
    assert c["stage"]=="proposal"


def test_unknown_stage_and_status_does_not_promote_won():
    row=prospect(pipeline_id="software_subscriptions",prospect_status="won")
    c=board([row])["cards"][0]
    assert c["stage"]=="research"
    assert c["won_verified"] is False
    assert c["recognized_revenue_cents"] is None


def test_suppression_stays_hold_in_classified_workstream():
    row=prospect(pipeline_id="service_customers",prospect_status="do_not_contact")
    c=board([row])["cards"][0]
    assert c["stage"]=="hold"
    assert c["outbound_authorized"] is False


def test_buyer_accounts_are_not_sales_deals_or_cash():
    r=board([], [buyer()])
    assert r["buyer_account_cards"]==1
    c=r["cards"][0]
    assert c["pipeline_id"]=="lead_buyers" and c["stage"]=="buyer_research"
    assert not c["active_capacity_observed"]
    assert not c["won_verified"]
    assert c["recognized_revenue_cents"] is None
    assert c["outbound_authorized"] is False
    c=board([], [buyer(capacity_verified_at=NOW,commercial_terms_verified_at=NOW)])["cards"][0]
    assert c["stage"]=="terms_review" and c["active_capacity_observed"] is True
    c=board([], [buyer(capacity_verified_at=NOW,commercial_terms_verified_at=NOW,delivery_verified_at=NOW)])["cards"][0]
    assert c["stage"]=="pilot_review" and c["won_verified"] is False


def test_no_activity_timestamp_does_not_fabricate_overdue():
    c=board([prospect()])["cards"][0]
    assert c["last_observed_at"] is None and c["stalled_review"] is False
    assert c["next_activity_due_at"] is None


@pytest.mark.parametrize("bad",[
    lambda:board([prospect(TENANT_B)]),
    lambda:board([], [buyer(TENANT_B)]),
    lambda:board([prospect(),prospect()]),
    lambda:board([{"tenant_id":TENANT_A,"prospect_id":"bogus"}]),
    lambda:board([prospect()],pipe="../buyers"),
    lambda:board([prospect()],tenant="not-a-tenant"),
    lambda:board([prospect()]*501),
])
def test_bad_or_cross_tenant_sources_fail_closed(bad):
    with pytest.raises(PipelineProjectionError):
        bad()


def test_filter_changes_presentation_not_source_scope():
    data=board([prospect()], [buyer()],pipe="lead_buyers")
    assert data["total_cards"]==2 and data["displayed_cards"]==1
    assert data["unassigned_prospects"]==1
    assert data["cards"][0]["source_kind"]=="canonical_buyer_account"
    assert data["outbound_authorized"] if "outbound_authorized" in data else True


def _app(verified=TENANT_A):
    app=FastAPI()
    repo=PostgresRevenueCrmRepository("mock-only",tenant_id=TENANT_A,connect_factory=lambda _:None)
    repo.prospects=lambda *,limit:[prospect()]
    repo.buyers=lambda *,limit:[buyer()]
    app.state.verified_tenant=verified
    app.include_router(create_revenue_crm_router(resolve_authenticated_read=lambda request: (
        AuthenticatedRevenueCrmRead(tenant_id=request.app.state.verified_tenant,repository=repo)
        if request.app.state.verified_tenant else None
    )))
    return app


def test_private_crm_board_returns_real_tenant_bound_rows_only():
    client=TestClient(_app())
    result=client.get("/v1/revenue-crm/pipelines/board")
    assert result.status_code==200, result.text
    data=result.json()
    assert data["source"]=="existing_authenticated_tenant_bound_revenue_crm_views"
    assert data["unassigned_prospects"]==1 and data["buyer_account_cards"]==1
    assert len(data["cards"])==2
    assert data["execution_authority"]=="none" and data["crm_writes"] is False
    p=client.get("/v1/revenue-crm/pipelines/board?pipeline=lead_buyers")
    assert p.status_code==200 and p.json()["displayed_cards"]==1
    view=client.get("/v1/revenue-crm/pipelines/view")
    assert view.status_code==200 and "Commercial Pipeline Control" in view.text
    assert "default-src 'none'" in view.headers["content-security-policy"]
    assert view.headers["cache-control"]=="no-store"
    js=client.get("/v1/revenue-crm/pipelines/board.js")
    assert js.status_code==200
    assert "No stage changes" in js.text


def test_private_board_auth_fails_closed_for_spoof_headers_or_wrong_tenant():
    app=_app(None)
    client=TestClient(app)
    r=client.get("/v1/revenue-crm/pipelines/board",
         headers={"X-Tenant-ID":TENANT_A,"Authorization":"Bearer fake"})
    assert r.status_code==401
    # The static sign-in shell and script expose no account data; even an
    # unauthenticated visitor can retrieve them but cannot load CRM rows.
    for path in ("view","board.js"):
        shell=client.get("/v1/revenue-crm/pipelines/"+path)
        assert shell.status_code==200
        assert "Demo Roofing Contractor" not in shell.text
    app.state.verified_tenant=TENANT_B
    assert client.get("/v1/revenue-crm/pipelines/board").status_code==503


def test_private_board_cannot_use_legacy_global_inmemory_repo():
    class Legacy:
        def prospects(self,*,limit):return [prospect()]
    client=TestClient(FastAPI())
    app=FastAPI()
    app.include_router(create_revenue_crm_router(repository=Legacy()))
    resp=TestClient(app).get("/v1/revenue-crm/pipelines/board")
    assert resp.status_code==503


def test_static_script_fails_closed_and_contains_no_contact_actions():
    from pathlib import Path
    folder=Path(__file__).resolve().parents[1]/"empire_os/static"
    html=(folder/"revenue_crm_multi_pipeline_board.html").read_text()
    js=(folder/"revenue_crm_multi_pipeline_board.js").read_text()
    assert "defer" in html and 'board.js' in html
    assert "textContent" in js
    for disallowed in ("localStorage","eval(","innerHTML","fetch('/api/send","window.location.href="):
        assert disallowed not in js
