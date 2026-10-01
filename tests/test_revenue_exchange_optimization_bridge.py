from empire_os.revenue_exchange_optimization_bridge import (
    build_revenue_exchange_optimization_preview,
)


def _proposal(**overrides):
    row = {
        "inventory_id": "p1",
        "buyer_id": "b1",
        "ready_for_operator_match_review": True,
        "proposed_price_cents": 12000,
        "expected_value_cents": 9000,
        "buyer_capacity_remaining": 1,
        "evidence_refs": ["proposal:p1:b1"],
    }
    row.update(overrides)
    return row


def test_ready_evidenced_proposal_builds_hybrid_preview():
    preview = build_revenue_exchange_optimization_preview(
        allocation_proposals=[_proposal()]
    )
    body = preview.as_dict()
    assert body["status"] == "AVAILABLE"
    assert body["proposals_considered"] == 1
    assert body["optimization_problem"]["status"] == "AVAILABLE"
    assert body["hybrid_plan"]["status"] == "AVAILABLE"
    assert body["recommendation_only"] is True
    assert body["allocation_execution"] is False
    assert body["pricing_mutation"] is False
    assert body["payment_action"] is False
    assert body["revenue_recognition"] is False
    assert body["execution_authority"] == "none"


def test_not_ready_proposal_is_blocked():
    preview = build_revenue_exchange_optimization_preview(
        allocation_proposals=[
            _proposal(ready_for_operator_match_review=False)
        ]
    )
    body = preview.as_dict()
    assert body["status"] == "UNAVAILABLE"
    assert body["proposals_considered"] == 0
    assert body["proposals_blocked"] == 1


def test_missing_economics_preserves_unknown():
    preview = build_revenue_exchange_optimization_preview(
        allocation_proposals=[
            _proposal(
                proposed_price_cents=None,
                expected_value_cents=None,
            )
        ]
    )
    body = preview.as_dict()
    assert body["status"] == "UNAVAILABLE"
    blocked = body["optimization_problem"]["blocked_options"]
    assert blocked[0]["reason"] == "unknown_allocation_economics_preserved"
    assert body["optimization_problem"]["unknown_is_zero"] is False


def test_capacity_is_required_not_invented():
    preview = build_revenue_exchange_optimization_preview(
        allocation_proposals=[
            _proposal(buyer_capacity_remaining=None)
        ]
    )
    body = preview.as_dict()
    assert body["status"] == "UNAVAILABLE"
    assert any(
        row["reason"] == "buyer_capacity_unknown"
        for row in body["optimization_problem"]["blocked_options"]
    )


def test_multiple_buyers_respect_capacity_and_no_execution():
    preview = build_revenue_exchange_optimization_preview(
        allocation_proposals=[
            _proposal(),
            _proposal(
                inventory_id="p2",
                buyer_id="b1",
                proposed_price_cents=9000,
                evidence_refs=["proposal:p2:b1"],
            ),
            _proposal(
                inventory_id="p2",
                buyer_id="b2",
                proposed_price_cents=10000,
                buyer_capacity_remaining=1,
                evidence_refs=["proposal:p2:b2"],
            ),
        ]
    )
    body = preview.as_dict()
    assert body["status"] == "AVAILABLE"
    exact = body["hybrid_plan"]["classical_exact"]
    assert exact["status"] == "AVAILABLE"
    assert exact["allocation_execution"] is False
    assert body["execution_authority"] == "none"


def test_proposed_price_never_substitutes_for_expected_value():
    preview = build_revenue_exchange_optimization_preview(
        allocation_proposals=[_proposal(expected_value_cents=None)]
    )
    body = preview.as_dict()

    assert body["status"] == "UNAVAILABLE"
    assert body["proposals_considered"] == 0
    assert body["optimization_problem"]["blocked_options"][0]["reason"] == (
        "unknown_allocation_economics_preserved"
    )


def test_conflicting_capacity_for_same_buyer_fails_closed():
    preview = build_revenue_exchange_optimization_preview(
        allocation_proposals=[
            _proposal(
                inventory_id="p1",
                buyer_id="b1",
                buyer_capacity_remaining=1,
                expected_value_cents=9000,
            ),
            _proposal(
                inventory_id="p2",
                buyer_id="b1",
                buyer_capacity_remaining=3,
                expected_value_cents=10000,
                evidence_refs=["proposal:p2:b1"],
            ),
        ]
    )
    body = preview.as_dict()

    assert body["status"] == "UNAVAILABLE"
    assert body["proposals_considered"] == 0
    assert any(
        row["reason"] == "conflicting_buyer_capacity_evidence"
        for row in body["optimization_problem"]["blocked_options"]
    )
