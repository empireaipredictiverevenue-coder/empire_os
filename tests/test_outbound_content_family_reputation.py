from empire_os.outbound_content_family_reputation import (
    evaluate_content_family_reputation,
)


def test_content_family_with_complaint_is_quarantined():
    result = evaluate_content_family_reputation(
        "template:roofing:v1",
        [
            {"family_key": "template:roofing:v1", "kind": "sent", "count": 25},
            {"family_key": "template:roofing:v1", "kind": "complaint"},
        ],
    )
    assert result["posture"] == "QUARANTINE"
    assert "content_family_complaint_present" in result["blockers"]


def test_content_family_with_bad_seed_placement_is_quarantined():
    result = evaluate_content_family_reputation(
        "template:a",
        [
            {"family_key": "template:a", "kind": "seed_test", "count": 10},
            {"family_key": "template:a", "kind": "spam_placement", "count": 3},
        ],
    )
    assert result["posture"] == "QUARANTINE"
    assert result["spam_placement_rate"] == 0.3


def test_content_family_with_elevated_seed_spam_is_degraded():
    result = evaluate_content_family_reputation(
        "template:a",
        [
            {"family_key": "template:a", "kind": "seed_test", "count": 10},
            {"family_key": "template:a", "kind": "spam_placement", "count": 1},
        ],
    )
    assert result["posture"] == "DEGRADED"


def test_new_content_family_remains_learning():
    result = evaluate_content_family_reputation(
        "template:new",
        [{"family_key": "template:new", "kind": "sent", "count": 3}],
    )
    assert result["posture"] == "LEARNING"


def test_clean_family_with_commercial_outcomes_is_healthy():
    result = evaluate_content_family_reputation(
        "template:good",
        [
            {"family_key": "template:good", "kind": "sent", "count": 30},
            {"family_key": "template:good", "kind": "seed_test", "count": 10},
            {"family_key": "template:good", "kind": "positive_reply", "count": 3},
            {"family_key": "template:good", "kind": "meeting_booked"},
            {"family_key": "template:good", "kind": "revenue", "amount": 5000},
        ],
    )
    assert result["posture"] == "HEALTHY"
    assert result["commercial_score"] > 0
    assert result["revenue"] == 5000
