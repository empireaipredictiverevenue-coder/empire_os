from empire_os.outbound_policy_promotion import (
    PolicyPromotionCriteria,
    build_policy_manifest,
    evaluate_candidate_promotion,
    policy_fingerprint,
)


def test_policy_manifest_is_stable_and_never_activates():
    payload = {"max_bounce_rate": 0.02, "max_daily_cap": 40}
    one = build_policy_manifest(
        name="ringleader",
        version="v2",
        policy_payload=payload,
        source_commit="abc123",
    )
    two = build_policy_manifest(
        name="ringleader",
        version="v2",
        policy_payload=dict(reversed(list(payload.items()))),
        source_commit="abc123",
    )
    assert one["fingerprint"] == two["fingerprint"]
    assert one["fingerprint"] == policy_fingerprint(payload)
    assert one["activation_authorized"] is False


def test_safe_shadow_candidate_becomes_ready_for_review_only():
    result = evaluate_candidate_promotion(
        {
            "samples": 100,
            "disagreement_rate": 0.03,
            "candidate_looser": 0,
            "promotion_authorized": False,
        },
        {
            "production_mutation_authorized": False,
        },
    )
    assert result["status"] == "READY_FOR_REVIEW"
    assert result["activation_authorized"] is False
    assert result["requires_explicit_release_approval"] is True


def test_looser_candidate_requires_review_even_when_shadow_is_stable():
    result = evaluate_candidate_promotion(
        {
            "samples": 100,
            "disagreement_rate": 0.02,
            "candidate_looser": 1,
            "promotion_authorized": False,
        },
        {
            "production_mutation_authorized": False,
        },
    )
    assert result["status"] == "REVIEW_REQUIRED"
    assert "candidate_is_looser_than_current_policy" in result["review_flags"]


def test_insufficient_shadow_evidence_blocks_promotion():
    result = evaluate_candidate_promotion(
        {
            "samples": 3,
            "disagreement_rate": 0.0,
            "candidate_looser": 0,
            "promotion_authorized": False,
        },
        {
            "production_mutation_authorized": False,
        },
        criteria=PolicyPromotionCriteria(min_shadow_samples=20),
    )
    assert result["status"] == "NOT_READY"
    assert "insufficient_shadow_samples" in result["blockers"]
