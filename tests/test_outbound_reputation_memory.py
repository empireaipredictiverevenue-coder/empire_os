from datetime import date

from empire_os.outbound_reputation_economic_memory import score_cohort
from empire_os.outbound_root_cause import detect_metric_shift, rank_candidate_causes


def test_reputation_economic_memory_penalises_complaints_heavily():
    result = score_cohort({
        "sent": 20,
        "positive_replies": 1,
        "complaints": 1,
        "actual_revenue": 0,
    })
    assert result["reputation_cost"] >= 25
    assert result["uses_opens_as_success_signal"] is False


def test_reputation_economic_memory_rewards_real_revenue():
    result = score_cohort({
        "sent": 10,
        "positive_replies": 2,
        "meetings": 1,
        "hard_bounces": 0,
        "complaints": 0,
        "actual_revenue": 5000,
    })
    assert result["band"] == "EXCELLENT"


def test_change_point_and_candidate_cause_ranking():
    shift = detect_metric_shift(
        {"bounce_rate": 0.01, "delivery_rate": 0.99},
        {"bounce_rate": 0.04, "delivery_rate": 0.95},
    )
    assert shift["shift_detected"] is True
    ranked = rank_candidate_causes(
        [{
            "kind": "recipient_source_changed",
            "change_id": "c1",
            "evidence_strength": 0.9,
            "temporal_proximity": 1.0,
            "affected_metrics": ["bounce_rate"],
        }],
        shift,
    )
    assert ranked["candidates"][0]["change_id"] == "c1"
    assert ranked["candidates"][0]["claim"] == "candidate_cause_not_proven_causation"
