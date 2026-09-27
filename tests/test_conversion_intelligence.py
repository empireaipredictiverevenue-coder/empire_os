from empire_os.conversion_intelligence import (
    CANONICAL_STAGES,
    ConversionStageEvidence,
    review_conversion_system,
    review_stage,
)


def stage(name, entered, converted, ref="conversion:test"):
    return ConversionStageEvidence(
        stage=name,
        entered=entered,
        converted=converted,
        evidence_ref=f"{ref}:{name}",
    )


def test_stage_preserves_unknown_instead_of_zero():
    review = review_stage(
        ConversionStageEvidence(
            stage="visitor_to_lead",
            entered=None,
            converted=None,
            evidence_ref=None,
        )
    )
    assert review.conversion_rate is None
    assert review.review_ready is False
    assert "entered_count_unknown" in review.blockers
    assert "converted_count_unknown" in review.blockers
    assert "conversion_evidence_missing" in review.blockers


def test_system_selects_lowest_evidence_backed_conversion_bottleneck():
    review = review_conversion_system(
        [
            stage("visitor_to_lead", 1000, 120),
            stage("lead_to_qualified", 120, 60),
            stage("qualified_to_buyer_review", 60, 30),
            stage("buyer_review_to_delivered_outreach", 30, 27),
            stage("delivered_outreach_to_reply", 27, 3),
        ],
        min_sample_size=20,
    )
    assert review.primary_bottleneck == "delivered_outreach_to_reply"
    assert review.primary_bottleneck_rate == 0.1111
    assert review.experiment_candidate["surface"] == "outbound_message"
    assert review.experiment_candidate["automatic_rollout"] is False
    assert review.execution_authority == "none"


def test_small_samples_do_not_create_fake_bottleneck():
    review = review_conversion_system(
        [
            stage("visitor_to_lead", 8, 1),
            stage("lead_to_qualified", 1, 1),
        ],
        min_sample_size=20,
    )
    assert review.primary_bottleneck is None
    assert review.experiment_candidate is None


def test_every_canonical_boundary_is_declared():
    assert CANONICAL_STAGES == (
        "visitor_to_lead",
        "lead_to_qualified",
        "qualified_to_buyer_review",
        "buyer_review_to_delivered_outreach",
        "delivered_outreach_to_reply",
        "reply_to_qualified_conversation",
        "conversation_to_terms",
        "terms_to_acceptance",
        "acceptance_to_payment",
        "payment_to_fulfilment",
        "fulfilment_to_positive_outcome",
        "outcome_to_repeat_purchase",
    )
