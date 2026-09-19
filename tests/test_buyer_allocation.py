from pathlib import Path

import pytest

from empire_os.buyer_allocation import (
    BuyerAllocationError,
    allocate_owned_prospect,
    buyer_activation_decision,
    allocation_key,
    fetch_buyer_rows,
    fetch_latest_qualification,
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
        "scoring_version": "v1",
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
    activation_state="activated",
    reviewed_at="2026-09-17T10:00:00Z",
    commercial_activated_at="2026-09-17T10:01:00Z",
    commercial_terms_source="manual_contract",
    commercial_terms_reference="contract:buyer-test",
    commercial_terms_verified_at="2026-09-17T10:01:00Z",
    capacity_verified_at="2026-09-17T10:01:00Z",
    delivery_verified_at="2026-09-17T10:01:00Z",
    destination_phone="+15125550123",
    webhook_url=None,
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
        "commercial_activation_state": activation_state,
        "reviewed_at": reviewed_at,
        "commercial_activated_at": commercial_activated_at,
        "commercial_terms_source": commercial_terms_source,
        "commercial_terms_reference": commercial_terms_reference,
        "commercial_terms_verified_at": commercial_terms_verified_at,
        "capacity_verified_at": capacity_verified_at,
        "delivery_verified_at": delivery_verified_at,
        "destination_phone": destination_phone,
        "webhook_url": webhook_url,
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


def test_v2_qualification_requires_evidence_confidence_floor():
    allowed, reason = qualification_decision(
        qualification(
            scoring_version="v2",
            evidence_confidence=0.49,
        )
    )
    assert allowed is False
    assert reason == "qualification_evidence_confidence_below_floor"

    allowed, reason = qualification_decision(
        qualification(
            scoring_version="v2",
            evidence_confidence=None,
        )
    )
    assert allowed is False
    assert reason == "qualification_evidence_confidence_missing"

    assert qualification_decision(
        qualification(
            scoring_version="v2",
            evidence_confidence=0.50,
        )
    ) == (True, "qualified")


def test_fetch_latest_qualification_prefers_v2_with_v1_fallback():
    calls = []

    def reader(path, params):
        assert path == "/rest/v1/prospect_qualifications"
        calls.append(dict(params))
        return [
            qualification(scoring_version="v1", score=99),
            qualification(
                scoring_version="v2",
                score=86.3,
                evidence_confidence=0.55,
            ),
        ]

    row = fetch_latest_qualification(reader, PROSPECT_ID)
    assert row["scoring_version"] == "v2"
    assert row["score"] == 86.3
    assert calls[0]["scoring_version"] == "in.(v2,v1)"
    assert calls[0]["limit"] == "2"


def test_buyer_activation_gate_rejects_auto_created_capacity():
    row = buyer(
        "auto-created",
        daily_cap=50,
        activation_state="discovered",
        reviewed_at=None,
    )
    allowed, reason = buyer_activation_decision(row)
    assert allowed is False
    assert reason == "buyer_not_commercially_activated"


def test_buyer_activation_gate_requires_verified_evidence():
    assert buyer_activation_decision(buyer("ok")) == (True, "activated")
    assert buyer_activation_decision(
        buyer("no-terms", commercial_terms_reference="")
    ) == (False, "commercial_terms_reference_missing")
    assert buyer_activation_decision(
        buyer("no-cap-proof", capacity_verified_at=None)
    ) == (False, "buyer_capacity_unverified")
    assert buyer_activation_decision(
        buyer("no-route", destination_phone="", webhook_url=None)
    ) == (False, "buyer_delivery_destination_missing")


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

    assert [item.buyer_id for item in ranked] == ["exact"]
    assert ranked[0].exact_niche is True
    assert ranked[0].exact_metro is True
    assert ranked[0].remaining_capacity == 8


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


def test_phase3d_buyer_activation_migration_is_fail_closed():
    sql = Path("migrations/005_buyer_activation_gate.sql").read_text(encoding="utf-8")
    required = (
        "commercial_activation_state TEXT NOT NULL DEFAULT 'discovered'",
        "commercial_terms_reference TEXT",
        "capacity_verified_at TIMESTAMPTZ",
        "delivery_verified_at TIMESTAMPTZ",
        "lower(trim(COALESCE(status, ''))) = 'active'",
        "lower(trim(COALESCE(commercial_activation_state, ''))) = 'activated'",
        "reviewed_at IS NOT NULL",
        "commercial_terms_verified_at IS NOT NULL",
        "capacity_verified_at IS NOT NULL",
        "delivery_verified_at IS NOT NULL",
        "lower(trim(niche)) = lower(trim(COALESCE(v_prospect.niche, '')))",
        "lower(trim(metro)) = lower(trim(COALESCE(v_prospect.metro, '')))",
        "REVOKE ALL ON FUNCTION public.allocate_prospect_atomic",
    )
    for fragment in required:
        assert fragment in sql


def test_buyer_commercial_evidence_migration_verifies_sources():
    sql = Path("migrations/006_buyer_commercial_evidence.sql").read_text(encoding="utf-8")
    required = (
        "CREATE TABLE IF NOT EXISTS public.buyer_commercial_evidence",
        "verification_state TEXT NOT NULL DEFAULT 'pending'",
        "active buyer subscription does not verify these terms",
        "agreement_sha256",
        "verified payment does not resolve to this buyer",
        "commercial_terms_sha256",
        "activate_buyer_from_evidence",
        "buyer_commercially_activated",
        "REVOKE ALL ON FUNCTION public.activate_buyer_from_evidence",
    )
    for fragment in required:
        assert fragment in sql


def test_gtm_control_rpc_migration_is_service_role_only():
    sql = Path("migrations/007_lock_gtm_control_rpcs.sql").read_text(encoding="utf-8")
    for fn in (
        "claim_next_gtm_job",
        "heartbeat_gtm_job",
        "complete_gtm_job",
        "fail_gtm_job",
    ):
        assert f"public.{fn}" in sql
    assert "FROM PUBLIC, anon, authenticated" in sql
    assert "TO service_role" in sql
