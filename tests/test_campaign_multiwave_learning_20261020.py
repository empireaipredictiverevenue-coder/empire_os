"""Cross-wave learning fixtures are synthetic and never reach production."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import pytest

from empire_os.campaign_intelligence import (
    TrustedCampaignLearningWave, TrustedArmOutcome,
    CampaignIntelligenceHeld, review_multiwave_commercial_learning,
)

NOW = datetime(2026, 10, 20, 11, tzinfo=timezone.utc)
CLOSE1 = NOW - timedelta(days=35)
START1 = CLOSE1 - timedelta(days=21)
CLOSE2 = NOW - timedelta(days=1)
START2 = CLOSE2 - timedelta(days=21)


def outcomes(*, customers=(2, 70, 30, 15),
             gp=(100, 6000, 3000, 1500), verified_finance=False,
             unsub=(0, 2, 3, 4), complaints=(0, 0, 0, 0)):
    arms = (
        "no_marketing_holdout",
        "buyer_inventory_fit_offer",
        "revenue_leak_signal_offer",
        "verified_market_opportunity_brief",
    )
    return tuple(TrustedArmOutcome(
        arm=arm,
        assigned_accounts=150 if i == 0 else 450,
        delivered_accounts=0 if i == 0 else 440,
        paying_customers=customers[i],
        unsubscribe_accounts=unsub[i],
        complaint_accounts=complaints[i],
        realized_gp_cents=gp[i] if verified_finance else None,
        recognized_revenue_cents=max(0, gp[i] * 4) if verified_finance else None,
        canonical_receipts_verified=True,
        assignment_integrity_verified=True,
        outcome_window_closed=True,
        financial_receipts_verified=verified_finance,
    ) for i, arm in enumerate(arms))


def wave(i=1, *, arms=None, **changes):
    return replace(TrustedCampaignLearningWave(
        wave_key="a"*32 if i == 1 else "b"*32,
        tenant_ref="tenant_empireai",
        market_scope="GB:solar:buyers",
        experiment_id="tam-full-funnel-offer-angle-20261020",
        started_at=START1 if i == 1 else START2,
        outcome_window_closed_at=CLOSE1 if i == 1 else CLOSE2,
        evidence_issued_at=NOW - timedelta(hours=1),
        arm_outcomes=outcomes() if arms is None else arms,
        source_receipts_verified=True,
        assignment_replay_verified=True,
        cross_wave_identity_dedup_verified=True,
        comparable_cohort_verified=True,
    ), **changes)


def run(*rows, **kw):
    return review_multiwave_commercial_learning(rows, now=NOW, **kw)


def test_no_authenticated_evidence_cannot_train_or_claim_a_winner():
    out = run()
    assert out["status"] == "NO_AUTHENTICATED_LEARNING_WAVES"
    assert out["proposed_offer"] is None
    assert out["next_learning_action"] == "AWAIT_VERIFIED_CAMPAIGN_OUTCOMES"
    assert out["auto_reallocation"] is False


def test_one_wave_preserves_holdout_and_asks_for_replication():
    out = run(wave())
    assert out["waves_reviewed"] == 1
    assert out["comparable_pool_ready"] is True
    assert out["proposed_offer"] is None
    assert out["next_learning_action"] == "COLLECT_SECOND_COMPARABLE_MARKET_WAVE"
    assert out["arm_statistics"][0]["assigned_accounts"] == 150
    assert out["arm_statistics"][0]["observed_customer_rate"] == 0.013333
    assert out["arm_statistics"][1]["customer_rate_bounds_above_holdout"] is True
    assert out["cohort_trend"]["marketing_outcome_receipts_all_financially_verified"] is False
    assert "tenant_empireai" not in json.dumps(out)
    assert "a"*32 not in json.dumps(out)


def test_two_replicated_cohorts_make_conservative_human_review_candidate():
    out = run(wave(1), wave(2))
    assert out["status"] == "REPLICATED_CANDIDATE_FOR_HUMAN_CAUSAL_REVIEW"
    assert out["proposed_offer"] == "buyer_inventory_fit_offer"
    assert out["next_learning_action"] == "HUMAN_REVIEW_REPLICATED_OFFER_RESULT_WITH_EXISTING_CAUSAL_SPECIALIST"
    assert out["causal_lift_or_significance_claimed"] is False
    assert out["auto_reallocation"] is False and out["budget_mutation"] is False
    assert out["arm_statistics"][1]["assigned_accounts"] == 900


def test_financially_verified_realized_margin_outweighs_customer_count():
    a = outcomes(verified_finance=True, gp=(100, 1000, 50000, 3000))
    out = run(wave(1, arms=a), wave(2, arms=a))
    assert out["proposed_offer"] == "revenue_leak_signal_offer"
    assert out["arm_statistics"][2]["observed_gp_per_account_cents"] == 111.11


def test_all_loss_making_offers_do_not_prompt_more_outreach():
    a = outcomes(verified_finance=True, gp=(-20000, -100, -200, -300))
    out = run(wave(1, arms=a), wave(2, arms=a))
    assert out["proposed_offer"] is None
    assert out["next_learning_action"] == "REVIEW_REALIZED_MARGIN_BEFORE_ANY_CAMPAIGN_EXPANSION"


def test_stale_or_immature_source_fails_closed():
    for change in (
        {"started_at": CLOSE2 - timedelta(days=2),
         "outcome_window_closed_at": CLOSE2},
        {"source_receipts_verified": False},
        {"comparable_cohort_verified": False},
        {"assignment_replay_verified": False},
        {"cross_wave_identity_dedup_verified": False},
    ):
        out = run(wave(2, **change))
        assert out["status"] == "HOLD_MISSING_OR_INCOMPARABLE_CAMPAIGN_EVIDENCE"
        assert out["comparable_pool_ready"] is False
        assert out["proposed_offer"] is None
        assert out["arm_statistics"] is None
    stale = run(wave(1, evidence_issued_at=NOW-timedelta(days=20)))
    assert "OUTCOME_SOURCE_SNAPSHOT_STALE" in stale["source_holds"]


def test_overlapping_wave_windows_are_not_pooled():
    another = wave(2, started_at=CLOSE1-timedelta(days=1),
                   outcome_window_closed_at=CLOSE1+timedelta(days=20))
    out = run(wave(1), another)
    assert out["status"] == "HOLD_MISSING_OR_INCOMPARABLE_CAMPAIGN_EVIDENCE"
    assert "OVERLAPPING_OR_CONTAMINATED_WAVE_WINDOWS" in out["source_holds"]


def test_duplicate_wave_id_and_wrong_market_experiment_tenant_rejected():
    with pytest.raises(CampaignIntelligenceHeld, match="DUPLICATE"):
        run(wave(1), wave(1))
    for change in (
        {"tenant_ref": "tenant_otherabc"},
        {"market_scope": "US:roofing:buyers"},
        {"experiment_id": "other_experiment"},
    ):
        with pytest.raises(CampaignIntelligenceHeld, match="INCOMPARABLE"):
            run(wave(1), wave(2, **change))


def test_future_or_causally_impossible_clocks_rejected():
    for change in (
        {"started_at": NOW+timedelta(hours=2)},
        {"outcome_window_closed_at": NOW+timedelta(days=1)},
        {"evidence_issued_at": NOW+timedelta(days=1)},
    ):
        with pytest.raises(CampaignIntelligenceHeld, match="CLOCK"):
            run(wave(1, **change))


def test_missing_canonical_arm_receipt_prevents_learning():
    a = outcomes()
    a = a[:1] + (replace(a[1], canonical_receipts_verified=False),) + a[2:]
    report = run(wave(1, arms=a))
    assert report["proposed_offer"] is None
    assert "ARM_RECEIPT_OR_SAFETY_HOLD" in report["source_holds"]


def test_bad_optouts_or_complaints_block_pooled_promotion():
    a = outcomes(unsub=(0, 30, 3, 4))
    result = run(wave(1, arms=a), wave(2, arms=a))
    assert result["proposed_offer"] is None
    assert "ARM_RECEIPT_OR_SAFETY_HOLD" in result["source_holds"]


def test_nonrepeating_win_does_not_become_winner_from_one_good_wave():
    a = outcomes()
    b = outcomes(customers=(5, 3, 30, 15))
    result = run(wave(1, arms=a), wave(2, arms=b))
    assert result["proposed_offer"] != "buyer_inventory_fit_offer"


def test_invalid_wave_count_and_policy_parameters_rejected():
    with pytest.raises(CampaignIntelligenceHeld, match="TOO_MANY"):
        run(*[wave(1 if i == 0 else 2) for i in range(13)])
    with pytest.raises(CampaignIntelligenceHeld, match="SAMPLE"):
        run(wave(), minimum_assigned_per_arm=True)
    with pytest.raises(CampaignIntelligenceHeld, match="FRESHNESS"):
        run(wave(), max_evidence_age_days=0)


def test_deviation_from_existing_10_percent_holdout_design_is_held():
    arm_rows = list(outcomes())
    arm_rows[0] = replace(arm_rows[0], assigned_accounts=350)
    report = run(wave(1, arms=tuple(arm_rows)))
    assert "HOLDOUT_RANDOMIZATION_SHARE_MISMATCH" in report["source_holds"]
    assert report["proposed_offer"] is None


def test_imbalanced_treatment_allocation_is_held_even_with_valid_control():
    arm_rows = list(outcomes())
    arm_rows[1] = replace(arm_rows[1], assigned_accounts=650)
    # Increase other treatment counts so the 10% holdout remains valid,
    # but the chosen offer arm is much larger than the other two.
    arm_rows[2] = replace(arm_rows[2], assigned_accounts=450)
    arm_rows[3] = replace(arm_rows[3], assigned_accounts=450)
    # Control share is 150/1700=8.8% (still within 7%-13%).
    report = run(wave(1, arms=tuple(arm_rows)))
    assert "TREATMENT_ARM_ALLOCATION_IMBALANCE" in report["source_holds"]


def test_control_baseline_drift_prevents_misleading_wave_pool():
    first = wave(1)
    shifted_control = outcomes(customers=(70, 70, 30, 15))
    second = wave(2, arms=shifted_control)
    report = run(first, second)
    assert "CONTROL_BASELINE_SHIFT_REQUIRES_SOURCE_REVIEW" in report["source_holds"]
    assert report["proposed_offer"] is None
    assert report["arm_statistics"] is None


def test_wave_order_does_not_affect_strategy_result():
    earlier = wave(1)
    later = wave(2)
    expected = run(earlier, later)
    reverse = run(later, earlier)
    assert expected == reverse
    assert expected["cohort_trend"]["observed_holdout_customer_rates_by_wave"] == [
        0.013333, 0.013333,
    ]


def test_bool_gate_is_not_treated_as_authenticated_receipt():
    candidate = wave(1, assignment_replay_verified=1)
    with pytest.raises(CampaignIntelligenceHeld, match="UNKNOWN_LEARNING_TRUST_GATE"):
        run(candidate)


def test_multiwave_learning_reuses_existing_full_funnel_entrypoint():
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        review_authenticated_campaign_intelligence,
    )
    out = review_authenticated_campaign_intelligence(
        now=NOW, learning_waves=(wave(1), wave(2)),
    )
    assert out["source_status"] == "EXISTING_OWNERS_MUST_SUPPLY_AUTHENTICATED_RECEIPT_ADAPTERS"
    assert out["multiwave_campaign_learning"]["proposed_offer"] == "buyer_inventory_fit_offer"
    assert out["account_intelligence"] is None
    assert out["verified_customer_experiment"] is None
    assert out["live_recipient_contact_or_messages"] is False
    assert out["production_training_or_model_mutation"] is False


def test_no_connected_learning_waves_is_unknown_not_zero_performance():
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        review_authenticated_campaign_intelligence,
    )
    out = review_authenticated_campaign_intelligence(now=NOW)
    assert out["multiwave_campaign_learning"] is None
    assert out["database_writes"] is False
