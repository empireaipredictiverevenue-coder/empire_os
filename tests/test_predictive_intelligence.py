from empire_os.predictive_intelligence import (
    build_predictive_intelligence_snapshot,
    build_product_estimate,
)


def catalog():
    return {
        "products": [{
            "product_id": "prod-1",
            "product_code": "managed_service",
            "catalog_state": "VERIFIED",
            "version_state": "VERIFIED",
        }]
    }


def outcomes(wins=0, losses=0):
    rows = []
    for i in range(wins):
        rows.append({
            "product_id": "prod-1",
            "conversion_outcome": "won",
            "actual_revenue": True,
            "fulfilment_created_at": f"2026-09-{1+i%10:02d}T00:00:00+00:00",
            "revenue_recognized_at": f"2026-09-{3+i%10:02d}T00:00:00+00:00",
        })
    for _ in range(losses):
        rows.append({
            "product_id": "prod-1",
            "conversion_outcome": "lost",
            "actual_revenue": False,
        })
    return rows


def test_small_verified_cohort_stays_unavailable():
    estimate = build_product_estimate(
        "managed_service",
        outcomes(wins=3, losses=2),
        min_terminal_samples=20,
        min_timing_samples=3,
    )
    assert estimate["probability_available"] is False
    assert estimate["probability_success"] is None
    assert "insufficient_verified_terminal_outcomes" in estimate["blockers"]
    assert estimate["candidate_specific_causal_probability_claimed"] is False


def test_verified_product_cohort_produces_bounded_probability():
    snapshot = build_predictive_intelligence_snapshot(
        outcomes(wins=12, losses=8),
        catalog(),
        min_terminal_samples=20,
        min_timing_samples=8,
    )
    estimate = snapshot["product_estimates"]["managed_service"]
    assert estimate["probability_available"] is True
    assert 0 < estimate["probability_success"] < 1
    assert 0 <= estimate["uncertainty"] <= 0.5
    assert 0 <= estimate["confidence"] <= 1
    assert estimate["time_to_revenue_available"] is True
    assert snapshot["search_scores_used"] is False
    assert snapshot["llm_probability_used"] is False
    assert snapshot["execution_authority"] == "none"


def test_nonterminal_outcomes_do_not_update_success_probability():
    rows = [
        {
            "product_id": "prod-1",
            "conversion_outcome": "qualified",
            "actual_revenue": False,
        },
        {
            "product_id": "prod-1",
            "conversion_outcome": "booked",
            "actual_revenue": False,
        },
    ]
    estimate = build_product_estimate(
        "managed_service",
        rows,
        min_terminal_samples=1,
    )
    assert estimate["terminal_outcome_count"] == 0
    assert estimate["probability_available"] is False
    assert estimate["probability_success"] is None


def test_unverified_catalog_product_does_not_match_outcomes():
    snapshot = build_predictive_intelligence_snapshot(
        outcomes(wins=20),
        {
            "products": [{
                "product_id": "prod-1",
                "product_code": "managed_service",
                "catalog_state": "UNKNOWN",
                "version_state": "UNKNOWN",
            }]
        },
        min_terminal_samples=1,
    )
    assert snapshot["matched_outcome_count"] == 0
    assert snapshot["product_estimates"] == {}
