from pathlib import Path

import pytest

from empire_os.buyer_allocation import (
    BuyerAllocationError,
    allocate_owned_prospect,
    allocation_key,
    fetch_buyer_rows,
    plan_allocation,
    qualification_decision,
    rank_buyers,
)


PROSPECT_ID = "11111111-1111-4111-8111-111111111111"


def prospect(**overrides):
    row = {
        "id": PROSPECT_ID,
        "business_name": "Austin Roof Co",
        "niche": "roofing",
        "metro": "Austin, TX",
    }
    row.update(overrides)
    return row


def qualification(**overrides):
    row = {
        "prospect_id": PROSPECT_ID,
        "score": 82,
        "tier": "hot",
        "status": "scored",
    }
    row.update(overrides)
    return row


def buyer(
    buyer_id: str,
    *,
    niche="roofing",
    metro="austin, tx",
    active=True,
    status="active",
    daily_cap=10,
    calls_today=0,
    priority=50,
    rate=75,
):
    return {
        "id": buyer_id,
        "buyer_name": f"Buyer {buyer_id}",
        "niche": niche,
        "metro": metro,
        "is_active": active,
        "status": status,
        "daily_cap": daily_cap,
        "calls_today": calls_today,
        "priority": priority,
        "per_lead_rate": rate,
        "base_payout": None,
    }


def test_qualification_gate_is_fail_closed():
    assert qualification_decision(None) == (
        False,
        "missing_qualification",
    )
    assert qualification_decision(
        qualification(score=49, tier="cold")
    )[0] is False
    assert qualification_decision(qualification())[0] is True


def test_rank_buyers_prefers_exact_market_and_filters_ineligible():
    rows = [
        buyer("exact", calls_today=2, priority=50),
        buyer("wildcard", niche="", metro="", daily_cap=100, priority=100),
        buyer("inactive", active=False),
        buyer("disabled", status="disabled"),
        buyer("wrong-niche", niche="plumbing"),
        buyer("wrong-metro", metro="dallas, tx"),
        buyer("full", daily_cap=5, calls_today=5),
    ]

    ranked = rank_buyers(
        prospect(),
        qualification(),
        rows,
    )

    assert [item.buyer_id for item in ranked] == [
        "exact",
        "wildcard",
    ]
    assert ranked[0].exact_niche is True
    assert ranked[0].exact_metro is True
    assert ranked[0].remaining_capacity == 8
    assert ranked[1].exact_niche is False
    assert ranked[1].exact_metro is False


def test_rank_buyers_deduplicates_buyer_ids():
    ranked = rank_buyers(
        prospect(),
        qualification(),
        [buyer("one"), buyer("one", priority=99)],
    )
    assert len(ranked) == 1


def test_plan_allocation_keeps_unmatched_prospect_as_overflow():
    plan = plan_allocation(
        prospect(),
        qualification(),
        [buyer("full", daily_cap=1, calls_today=1)],
    )

    assert plan["decision"] == "overflow_no_capacity"
    assert plan["reason"] == "no_eligible_buyer_capacity"
    assert plan["candidates"] == []


def test_allocation_key_is_stable_and_exclusive():
    assert allocation_key(PROSPECT_ID) == (
        f"exclusive:v1:{PROSPECT_ID}"
    )


def test_fetch_buyer_rows_paginates():
    calls = []

    def reader(path, params):
        assert path == "/rest/v1/buyers"
        calls.append(dict(params))
        offset = int(params["offset"])
        if offset == 0:
            return [buyer("a"), buyer("b")]
        if offset == 2:
            return [buyer("c")]
        return []

    rows = fetch_buyer_rows(reader, page_size=2)

    assert [row["id"] for row in rows] == ["a", "b", "c"]
    assert [call["offset"] for call in calls] == ["0", "2"]


def test_allocate_owned_prospect_calls_atomic_allocator_once():
    allocator_calls = []

    def reader(path, params):
        if path == "/rest/v1/prospect_qualifications":
            return [qualification()]
        if path == "/rest/v1/buyers":
            return [buyer("buyer-1")]
        raise AssertionError(path)

    def allocator(payload):
        allocator_calls.append(payload)
        return {
            "decision": "allocated",
            "fulfilment_order_id": "order-1",
            "buyer_id": "buyer-1",
            "prospect_id": PROSPECT_ID,
            "match_score": 90,
        }

    result = allocate_owned_prospect(
        prospect(),
        reader,
        allocator,
    )

    assert result["decision"] == "allocated"
    assert result["planned_candidate_count"] == 1
    assert len(allocator_calls) == 1
    payload = allocator_calls[0]
    assert payload["p_prospect_id"] == PROSPECT_ID
    assert payload["p_allocation_key"] == f"exclusive:v1:{PROSPECT_ID}"
    assert payload["p_candidates"][0]["buyer_id"] == "buyer-1"
    assert "price_cents" not in payload["p_candidates"][0]


def test_unqualified_prospect_never_calls_allocator():
    called = False

    def reader(path, params):
        if path == "/rest/v1/prospect_qualifications":
            return [qualification(score=30, tier="cold")]
        if path == "/rest/v1/buyers":
            return [buyer("buyer-1")]
        raise AssertionError(path)

    def allocator(payload):
        nonlocal called
        called = True
        return {"decision": "allocated"}

    result = allocate_owned_prospect(prospect(), reader, allocator)

    assert result["decision"] == "not_qualified"
    assert called is False


def test_allocator_unknown_decision_fails_closed():
    def reader(path, params):
        if path == "/rest/v1/prospect_qualifications":
            return [qualification()]
        return [buyer("buyer-1")]

    with pytest.raises(
        BuyerAllocationError,
        match="invalid decision",
    ):
        allocate_owned_prospect(
            prospect(),
            reader,
            lambda payload: {"decision": "mystery"},
        )


def test_phase3d_migration_contains_atomic_guards():
    sql = Path(
        "migrations/004_atomic_buyer_allocation.sql"
    ).read_text(encoding="utf-8")

    required = (
        "uq_fulfilment_orders_allocation_key",
        "allocate_prospect_atomic",
        "WHERE id = p_prospect_id\n     FOR UPDATE;",
        "state NOT IN ('rejected', 'cancelled')",
        "FOR UPDATE",
        "calls_today = COALESCE(calls_today, 0) + 1",
        "INSERT INTO public.fulfilment_orders",
        "'matched'",
        "INSERT INTO public.commercial_events",
        "'prospect_allocated'",
        "'overflow_no_capacity'",
        "GRANT EXECUTE ON FUNCTION public.allocate_prospect_atomic",
    )

    for fragment in required:
        assert fragment in sql

    # Phase 3D must not invent commercial economics.
    assert "price_cents," in sql
    assert "expected_margin_cents," in sql
