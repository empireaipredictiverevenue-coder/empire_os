from empire_os.buyer_capacity_learning import (
    BuyerCapacityOutcomeWindow,
    assess_buyer_capacity_learning,
)


def window(
    key,
    *,
    offered=10,
    accepted=8,
    capacity_rejected=0,
    quality_rejected=2,
    unresolved=0,
):
    return BuyerCapacityOutcomeWindow(
        observation_key=key,
        buyer_id="buyer-1",
        product_key="permit_intelligence",
        market_key="roofing:austin",
        offered_units=offered,
        accepted_units=accepted,
        capacity_rejected_units=capacity_rejected,
        quality_rejected_units=quality_rejected,
        unresolved_units=unresolved,
        observed_at="2026-10-01T10:00:00+00:00",
        evidence_refs=(f"outcome:{key}",),
    )


def test_sparse_windows_fail_closed():
    result = assess_buyer_capacity_learning(
        [window("w1"), window("w2")],
        verified_capacity_limit=10,
        capacity_evidence_ref="capacity:buyer-1",
    )

    assert result.recommendation == "INSUFFICIENT_EVIDENCE"
    assert result.recommended_capacity_ceiling is None
    assert "insufficient_unique_outcome_windows" in result.blockers


def test_duplicate_window_does_not_inflate_sample():
    result = assess_buyer_capacity_learning(
        [window("w1"), window("w1"), window("w2"), window("w3")],
        verified_capacity_limit=10,
        capacity_evidence_ref="capacity:buyer-1",
    )

    assert result.unique_window_count == 3
    assert result.resolved_unit_count == 30


def test_quality_rejection_is_not_capacity_exhaustion():
    result = assess_buyer_capacity_learning(
        [window("w1"), window("w2"), window("w3")],
        verified_capacity_limit=10,
        capacity_evidence_ref="capacity:buyer-1",
    )

    assert result.capacity_rejected_unit_count == 0
    assert result.quality_rejected_unit_count == 6
    assert result.recommendation == "MAINTAIN_VERIFIED_LIMIT"
    assert result.recommended_capacity_ceiling == 10


def test_capacity_rejection_can_only_recommend_downward_review():
    result = assess_buyer_capacity_learning(
        [
            window("w1", accepted=7, capacity_rejected=3, quality_rejected=0),
            window("w2", accepted=8, capacity_rejected=2, quality_rejected=0),
            window("w3", accepted=7, capacity_rejected=3, quality_rejected=0),
            window("w4", accepted=8, capacity_rejected=2, quality_rejected=0),
        ],
        verified_capacity_limit=10,
        capacity_evidence_ref="capacity:buyer-1",
    )

    assert result.recommendation == "REVIEW_DOWNWARD"
    assert result.recommended_capacity_ceiling == 8
    assert result.recommended_capacity_ceiling <= 10
    assert result.buyer_capacity_mutation is False
    assert result.allocation_execution is False
    assert result.execution_authority == "none"


def test_acceptance_never_recommends_above_verified_limit():
    result = assess_buyer_capacity_learning(
        [
            window("w1", offered=15, accepted=12, quality_rejected=3),
            window("w2", offered=15, accepted=13, quality_rejected=2),
            window("w3", offered=15, accepted=14, quality_rejected=1),
        ],
        verified_capacity_limit=10,
        capacity_evidence_ref="capacity:buyer-1",
    )

    assert result.recommendation == "MAINTAIN_VERIFIED_LIMIT"
    assert result.recommended_capacity_ceiling == 10


def test_missing_verified_capacity_evidence_blocks_recommendation():
    result = assess_buyer_capacity_learning(
        [window("w1"), window("w2"), window("w3")],
        verified_capacity_limit=10,
        capacity_evidence_ref=None,
    )

    assert result.recommendation == "INSUFFICIENT_EVIDENCE"
    assert "capacity_evidence_ref_missing" in result.blockers


def test_unresolved_units_do_not_count_as_resolved():
    result = assess_buyer_capacity_learning(
        [
            window("w1", offered=10, accepted=2, quality_rejected=0, unresolved=8),
            window("w2", offered=10, accepted=2, quality_rejected=0, unresolved=8),
            window("w3", offered=10, accepted=2, quality_rejected=0, unresolved=8),
        ],
        verified_capacity_limit=10,
        capacity_evidence_ref="capacity:buyer-1",
    )

    assert result.resolved_unit_count == 6
    assert result.recommendation == "INSUFFICIENT_EVIDENCE"
    assert "insufficient_resolved_units" in result.blockers
