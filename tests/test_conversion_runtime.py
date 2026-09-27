from empire_os.conversion_runtime import build_live_conversion_review


class FakeRepository:
    def approved_buyer_reviews(self):
        return [
            {"id": f"review-{n}", "status": "approved"}
            for n in range(1, 5)
        ]

    def delivered_or_replied_intents(self):
        return [
            {
                "id": "intent-1",
                "status": "delivered",
                "normalized_recipient": "a@example.com",
                "metadata": {"buyer_candidate_review_id": "review-1"},
            },
            {
                "id": "intent-2",
                "status": "delivered",
                "normalized_recipient": "b@example.com",
                "metadata": {"buyer_candidate_review_id": "review-2"},
            },
            {
                "id": "intent-3",
                "status": "replied",
                "normalized_recipient": "c@example.com",
                "metadata": {"buyer_candidate_review_id": "review-3"},
            },
        ]

    def commercial_replies(self):
        return [{
            "id": "reply-1",
            "intent_id": "intent-3",
            "classification": "positive",
            "normalized_from_contact": "c@example.com",
        }]

    def closer_cases(self):
        return [{"id": "case-1", "state": "qualified"}]

    def commercial_terms_reviews(self):
        return [{
            "id": "terms-1",
            "status": "approved",
            "fulfilment_order_id": "order-1",
        }]

    def accepted_paid_fulfilled_orders(self):
        return [{"id": "order-1", "state": "fulfilled"}]

    def payment_evidence(self):
        return [{
            "id": "payment-1",
            "fulfilment_order_id": "order-1",
        }]

    def commercial_outcomes(self):
        return [{
            "id": "outcome-1",
            "fulfilment_order_id": "order-1",
            "delivery_outcome": "success",
            "conversion_outcome": "converted",
            "buyer_satisfaction": 5,
        }]

    def snapshot(self):
        return {
            "backend": "supabase_legacy",
            "configured": True,
            "repository_authority": "read_only",
        }


def test_runtime_builds_only_canonical_observed_boundaries():
    result = build_live_conversion_review(
        FakeRepository(),
        min_sample_size=1,
    )

    assert result["source"] == "canonical_data_gateway"
    assert result["data_source"]["repository_authority"] == "read_only"
    assert result["counts"]["buyer_review_to_delivered_outreach"] == {
        "entered": 4,
        "converted": 3,
    }
    assert result["counts"]["delivered_outreach_to_reply"] == {
        "entered": 3,
        "converted": 1,
    }
    assert result["primary_bottleneck"] == "delivered_outreach_to_reply"
    assert result["experiment_candidate"]["surface"] == "outbound_message"
    assert result["execution_authority"] == "none"
    assert result["actual_revenue"] is False


def test_runtime_does_not_overreact_to_small_samples():
    result = build_live_conversion_review(
        FakeRepository(),
        min_sample_size=20,
    )
    assert result["primary_bottleneck"] is None
    assert result["experiment_candidate"] is None
