from __future__ import annotations

import os
from pathlib import Path

import pytest


_TEST_ENV_PATH = Path("/tmp/empire_os_capacity_gate_test.env")
_TEST_ENV_PATH.write_text(
    "SUPABASE_URL=http://127.0.0.1:9\n"
    "SUPABASE_SERVICE_KEY=test-only-key\n",
    encoding="utf-8",
)

_previous_env_path = os.environ.get("EMPIRE_ENV_PATH")
os.environ["EMPIRE_ENV_PATH"] = str(_TEST_ENV_PATH)

from empire_os import autonomous_execution_bus as bus

if _previous_env_path is None:
    os.environ.pop("EMPIRE_ENV_PATH", None)
else:
    os.environ["EMPIRE_ENV_PATH"] = _previous_env_path


def capacity_job(
    *,
    niche_family="roofing",
    metro="austin",
    planned_capacity=999,
):
    return bus.ClaimedJob(
        id="capacity-parent",
        opportunity_id="opportunity-1",
        job_type="fulfilment_capacity_check",
        worker_adapter="fulfilment_capacity_adapter",
        priority=0.8,
        payload={
            "target": {
                "niche_family": niche_family,
                "metro": metro,
            },
            "niche_family": niche_family,
            "metro": metro,
            "buyer_capacity": planned_capacity,
            "market_balance": "balanced",
        },
        lease_token="lease",
        attempts=1,
        max_attempts=5,
    )


def activated_fields():
    return {
        "commercial_activation_state": "activated",
        "reviewed_at": "2026-09-17T10:00:00Z",
        "commercial_activated_at": "2026-09-17T10:01:00Z",
        "commercial_terms_source": "manual_contract",
        "commercial_terms_reference": "contract:capacity-test",
        "commercial_terms_verified_at": "2026-09-17T10:01:00Z",
        "capacity_verified_at": "2026-09-17T10:01:00Z",
        "delivery_verified_at": "2026-09-17T10:01:00Z",
        "destination_phone": "+15125550123",
        "webhook_url": None,
    }

def test_capacity_gate_fails_closed_without_market_identity():
    with pytest.raises(
        bus.BusError,
        match="missing niche_family or metro",
    ):
        bus.execute_capacity_check(
            capacity_job(
                niche_family="",
                metro="",
            )
        )


def test_capacity_gate_uses_live_buyer_state(
    monkeypatch,
):
    calls = []

    def fake_rest(method, path, **kwargs):
        calls.append(
            (method, path, kwargs)
        )

        assert method == "GET"
        assert path == "/rest/v1/buyers"

        return [
            {
                "id": "buyer-1",
                "buyer_name": "Buyer One",
                "niche": "roofing",
                "metro": "Austin",
                "is_active": True,
                "status": "active",
                "daily_cap": 10,
                "calls_today": 3,
                **activated_fields(),
            },
            {
                "id": "buyer-2",
                "buyer_name": "Buyer Two",
                "niche": "roofing",
                "metro": "Austin",
                "is_active": True,
                "status": "active",
                "daily_cap": 5,
                "calls_today": 5,
                **activated_fields(),
            },
            {
                "id": "buyer-3",
                "buyer_name": "Inactive",
                "niche": "roofing",
                "metro": "Austin",
                "is_active": True,
                "status": "disabled",
                "daily_cap": 100,
                "calls_today": 0,
                **activated_fields(),
            },
            {
                "id": "buyer-4",
                "buyer_name": "Wrong Market",
                "niche": "insurance",
                "metro": "Austin",
                "is_active": True,
                "status": "active",
                "daily_cap": 100,
                "calls_today": 0,
                **activated_fields(),
            },
        ]

    monkeypatch.setattr(
        bus,
        "_rest_json",
        fake_rest,
    )

    result = bus.execute_capacity_check(
        capacity_job(planned_capacity=999)
    )

    assert result["gate_open"] is True
    assert result["gate_reason"] == (
        "live_buyer_capacity_available"
    )

    assert result["matched_buyers"] == 2
    assert result["available_buyers"] == 1

    assert result["daily_cap"] == 15
    assert result["calls_today"] == 8
    assert result["remaining_capacity"] == 7

    # Legacy field now reflects canonical live capacity.
    assert result["buyer_capacity"] == 7

    # Planner value is retained only for audit.
    assert result["planned_buyer_capacity"] == 999
    assert result["capacity_changed"] is True

    assert len(calls) == 1


def test_capacity_gate_closes_when_capacity_exhausted(
    monkeypatch,
):
    def fake_rest(method, path, **kwargs):
        assert method == "GET"
        assert path == "/rest/v1/buyers"

        return [
            {
                "id": "buyer-1",
                "buyer_name": "Buyer One",
                "niche": "roofing",
                "metro": "Austin",
                "is_active": True,
                "status": "active",
                "daily_cap": 10,
                "calls_today": 10,
                **activated_fields(),
            },
        ]

    monkeypatch.setattr(
        bus,
        "_rest_json",
        fake_rest,
    )

    result = bus.execute_capacity_check(
        capacity_job(planned_capacity=50)
    )

    assert result["gate_open"] is False
    assert result["gate_reason"] == (
        "no_live_buyer_capacity"
    )
    assert result["matched_buyers"] == 1
    assert result["available_buyers"] == 0
    assert result["remaining_capacity"] == 0

    # Stale planner capacity cannot open the gate.
    assert result["planned_buyer_capacity"] == 50
    assert result["buyer_capacity"] == 0


def test_capacity_gate_rejects_unscoped_market_wide_buyer(
    monkeypatch,
):
    def fake_rest(method, path, **kwargs):
        assert method == "GET"
        assert path == "/rest/v1/buyers"

        return [
            {
                "id": "buyer-wide",
                "buyer_name": "National Buyer",
                "niche": "",
                "metro": "",
                "is_active": True,
                "status": "active",
                "daily_cap": 20,
                "calls_today": 4,
                **activated_fields(),
            },
        ]

    monkeypatch.setattr(
        bus,
        "_rest_json",
        fake_rest,
    )

    result = bus.execute_capacity_check(
        capacity_job()
    )

    assert result["gate_open"] is False
    assert result["matched_buyers"] == 0
    assert result["available_buyers"] == 0
    assert result["remaining_capacity"] == 0

def test_capacity_gate_paginates_buyer_state(
    monkeypatch,
):
    offsets = []

    monkeypatch.setattr(
        bus,
        "CAPACITY_BUYER_PAGE_SIZE",
        2,
    )

    rows = [
        {
            "id": "buyer-1",
            "buyer_name": "Buyer One",
            "niche": "roofing",
            "metro": "Austin",
            "is_active": True,
            "status": "active",
            "daily_cap": 5,
            "calls_today": 1,
            **activated_fields(),
        },
        {
            "id": "buyer-2",
            "buyer_name": "Buyer Two",
            "niche": "roofing",
            "metro": "Austin",
            "is_active": True,
            "status": "active",
            "daily_cap": 5,
            "calls_today": 2,
            **activated_fields(),
        },
        {
            "id": "buyer-3",
            "buyer_name": "Buyer Three",
            "niche": "roofing",
            "metro": "Austin",
            "is_active": True,
            "status": "active",
            "daily_cap": 5,
            "calls_today": 3,
            **activated_fields(),
        },
    ]

    def fake_rest(method, path, **kwargs):
        assert method == "GET"
        assert path == "/rest/v1/buyers"

        params = kwargs["params"]
        offset = int(params["offset"])
        limit = int(params["limit"])

        offsets.append(offset)

        return rows[offset:offset + limit]

    monkeypatch.setattr(
        bus,
        "_rest_json",
        fake_rest,
    )

    result = bus.execute_capacity_check(
        capacity_job(planned_capacity=50)
    )

    assert offsets == [0, 2]
    assert result["matched_buyers"] == 3
    assert result["available_buyers"] == 3
    assert result["daily_cap"] == 15
    assert result["calls_today"] == 6
    assert result["remaining_capacity"] == 9
    assert result["gate_open"] is True
