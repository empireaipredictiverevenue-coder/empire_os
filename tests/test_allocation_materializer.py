from __future__ import annotations

import os
from pathlib import Path

import pytest


_TEST_ENV_PATH = Path("/tmp/empire_os_allocation_test.env")
_TEST_ENV_PATH.write_text(
    "SUPABASE_URL=http://127.0.0.1:9\n"
    "SUPABASE_SERVICE_KEY=test-only-key\n",
    encoding="utf-8",
)

_previous_env_path = os.environ.get("EMPIRE_ENV_PATH")
os.environ["EMPIRE_ENV_PATH"] = str(_TEST_ENV_PATH)

from empire_os import autonomous_execution_bus as bus
from empire_os import gtm_engine

if _previous_env_path is None:
    os.environ.pop("EMPIRE_ENV_PATH", None)
else:
    os.environ["EMPIRE_ENV_PATH"] = _previous_env_path


def allocation_parent(*, batch_size=5):
    return bus.ClaimedJob(
        id="allocation-parent",
        opportunity_id="22222222-2222-4222-8222-222222222222",
        job_type="buyer_allocation_materialize",
        worker_adapter="buyer_allocation_materializer_adapter",
        priority=0.9,
        payload={
            "target": {"niche_family": "roofing", "metro": "austin, tx"},
            "allocation_batch_size": batch_size,
        },
        lease_token="lease",
        attempts=1,
        max_attempts=5,
    )


def prospect(pid, score=90):
    return {
        "id": pid,
        "business_name": f"Roof Co {pid}",
        "niche": "roofing",
        "metro": "austin, tx",
        "status": "new",
        "buy_signal_score": score,
        "phone": "5125550101",
        "website": None,
        "address": None,
        "contact_source": "overpass_osm",
        "contacted_status": "not_contacted",
    }


def qualification(pid, score=80, tier="hot"):
    return {
        "prospect_id": pid,
        "score": score,
        "tier": tier,
        "status": "scored",
        "scored_at": "2026-09-17T00:00:00Z",
    }


def buyer_row():
    return {
        "id": "33333333-3333-4333-8333-333333333333",
        "buyer_name": "Austin Buyer",
        "niche": "roofing",
        "metro": "austin, tx",
        "is_active": True,
        "status": "active",
        "daily_cap": 10,
        "calls_today": 2,
        "base_payout": None,
        "per_lead_rate": 80,
        "priority": 90,
        "destination_phone": "+15125550123",
        "webhook_url": None,
        "reviewed_at": "2026-09-17T10:00:00Z",
        "commercial_activation_state": "activated",
        "commercial_activated_at": "2026-09-17T10:01:00Z",
        "commercial_terms_source": "manual_contract",
        "commercial_terms_reference": "contract:materializer-test",
        "commercial_terms_verified_at": "2026-09-17T10:01:00Z",
        "capacity_verified_at": "2026-09-17T10:01:00Z",
        "delivery_verified_at": "2026-09-17T10:01:00Z",
    }


def test_materializer_creates_only_approval_required_unallocated_job(monkeypatch):
    p1 = "44444444-4444-4444-8444-444444444444"
    p2 = "55555555-5555-4555-8555-555555555555"
    posts = []

    def fake_rest(method, path, **kwargs):
        if path == "/rest/v1/prospects":
            return [prospect(p1, 95), prospect(p2, 85)]
        if path == "/rest/v1/prospect_qualifications":
            return [qualification(p1, 90), qualification(p2, 75, "warm")]
        if path == "/rest/v1/fulfilment_orders":
            return [{"prospect_id": p2}]
        if path == "/rest/v1/gtm_jobs" and method == "GET":
            return []
        if path == "/rest/v1/gtm_jobs" and method == "POST":
            posts.append(kwargs["payload"])
            return [{"id": "job-1"}]
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr(bus, "_rest_json", fake_rest)

    result = bus._materialize_allocation_jobs(allocation_parent())

    assert result["candidates"] == 1
    assert result["jobs_created"] == 1
    assert len(posts) == 1
    child = posts[0]
    assert child["payload"]["prospect_id"] == p1
    assert child["status"] == "planned"
    assert child["requires_approval"] is True
    assert child["approved_at"] is None
    assert child["worker_adapter"] == "buyer_allocation_adapter"
    assert child["idempotency_key"] == f"allocation:{p1}:v1"


def test_materializer_existing_child_is_idempotent(monkeypatch):
    pid = "66666666-6666-4666-8666-666666666666"

    def fake_rest(method, path, **kwargs):
        if path == "/rest/v1/prospects":
            return [prospect(pid)]
        if path == "/rest/v1/prospect_qualifications":
            return [qualification(pid)]
        if path == "/rest/v1/fulfilment_orders":
            return []
        if path == "/rest/v1/gtm_jobs" and method == "GET":
            return [{"id": "existing"}]
        if path == "/rest/v1/gtm_jobs" and method == "POST":
            raise AssertionError("existing child must not be inserted")
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr(bus, "_rest_json", fake_rest)
    result = bus._materialize_allocation_jobs(allocation_parent())

    assert result["jobs_created"] == 0
    assert result["jobs_existing"] == 1


def test_materializer_batch_is_bounded():
    with pytest.raises(bus.BusError, match="must be between"):
        bus._materialize_allocation_jobs(
            allocation_parent(batch_size=99)
        )


def test_approved_child_adapter_calls_atomic_rpc(monkeypatch):
    pid = "77777777-7777-4777-8777-777777777777"
    rpc_calls = []

    def fake_rest(method, path, **kwargs):
        if path == "/rest/v1/prospects":
            return [prospect(pid)]
        if path == "/rest/v1/prospect_qualifications":
            return [qualification(pid)]
        if path == "/rest/v1/prospect_entity_links":
            return [{
                "prospect_id": pid,
                "entity_id": "99999999-9999-4999-8999-999999999999",
                "match_score": 1.0,
                "active": True,
                "created_at": "2026-09-17T00:00:00Z",
            }]
        if path == "/rest/v1/buyers":
            return [buyer_row()]
        raise AssertionError(f"unexpected request: {method} {path}")

    def fake_rpc(name, payload):
        rpc_calls.append((name, payload))
        return {
            "decision": "allocated",
            "fulfilment_order_id": "88888888-8888-4888-8888-888888888888",
            "buyer_id": buyer_row()["id"],
            "prospect_id": pid,
            "match_score": 98,
        }

    monkeypatch.setattr(bus, "_rest_json", fake_rest)
    monkeypatch.setattr(bus, "rpc", fake_rpc)

    child = bus.ClaimedJob(
        id="allocation-child",
        opportunity_id="22222222-2222-4222-8222-222222222222",
        job_type="prospect_buyer_allocation",
        worker_adapter="buyer_allocation_adapter",
        priority=0.9,
        payload={"prospect_id": pid},
        lease_token="lease",
        attempts=1,
        max_attempts=5,
    )

    result = bus.execute_buyer_allocation(child)

    assert result["decision"] == "allocated"
    assert result["executed"] is True
    assert len(rpc_calls) == 1
    name, payload = rpc_calls[0]
    assert name == "allocate_prospect_atomic"
    assert payload["p_prospect_id"] == pid
    assert payload["p_candidates"][0]["buyer_id"] == buyer_row()["id"]


def opportunity(*, buyer_capacity=10):
    return gtm_engine.Opportunity(
        niche="roofing",
        niche_family="roofing",
        metro="austin, tx",
        prospect_count=20,
        new_count=20,
        bridged_count=0,
        activated_count=0,
        buyer_count=1 if buyer_capacity else 0,
        buyer_capacity=buyer_capacity,
        high_priority_buyer_count=1 if buyer_capacity else 0,
        observed_buyer_rate=80.0 if buyer_capacity else None,
        supply_score=0.5,
        buyer_demand_score=0.5,
        economic_score=0.5,
        fulfilment_score=0.5,
        visibility_score=0.5,
        activation_gap_score=0.5,
        market_balance="balanced" if buyer_capacity else "demand-constrained",
        priority_score=0.9,
        expected_revenue_cents=0,
        expected_margin_cents=0,
        rationale=[],
    )


def test_planner_adds_allocation_materializer_only_with_capacity():
    jobs = gtm_engine.build_gtm_jobs([opportunity(buyer_capacity=10)])
    alloc = [
        job for job in jobs
        if job.worker_adapter == "buyer_allocation_materializer_adapter"
    ]
    assert len(alloc) == 1
    assert alloc[0].requires_approval is False
    assert alloc[0].payload["allocation_batch_size"] == 5

    no_capacity_jobs = gtm_engine.build_gtm_jobs([
        opportunity(buyer_capacity=0)
    ])
    assert not any(
        job.worker_adapter == "buyer_allocation_materializer_adapter"
        for job in no_capacity_jobs
    )
