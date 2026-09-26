from urllib.parse import urlparse

from empire_os.conversion_runtime import build_live_conversion_review


class FakeRequest:
    def __call__(self, method, path, payload=None, **kwargs):
        assert method == "GET"
        p = urlparse(path).path
        if p == "/rest/v1/buyer_candidate_reviews":
            return [
                {"id": f"review-{n}", "status": "approved"}
                for n in range(1, 5)
            ]
        if p == "/rest/v1/outbound_intents":
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
        if p == "/rest/v1/outbound_replies":
            return [{
                "id": "reply-1",
                "intent_id": "intent-3",
                "classification": "positive",
                "normalized_from_contact": "c@example.com",
            }]
        if p == "/rest/v1/closer_cases":
            return [{"id": "case-1", "state": "qualified"}]
        if p == "/rest/v1/commercial_terms_reviews":
            return [{
                "id": "terms-1",
                "status": "approved",
                "fulfilment_order_id": "order-1",
            }]
        if p == "/rest/v1/fulfilment_orders":
            return [{"id": "order-1", "state": "fulfilled"}]
        if p == "/rest/v1/bsc_payment_evidence":
            return [{
                "id": "payment-1",
                "fulfilment_order_id": "order-1",
            }]
        if p == "/rest/v1/commercial_outcomes":
            return [{
                "id": "outcome-1",
                "fulfilment_order_id": "order-1",
                "delivery_outcome": "success",
                "conversion_outcome": "converted",
                "buyer_satisfaction": 5,
            }]
        raise AssertionError(p)


def test_runtime_builds_only_canonical_observed_boundaries():
    result = build_live_conversion_review(
        FakeRequest(),
        min_sample_size=1,
    )

    assert result["source"] == "canonical_supabase"
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
        FakeRequest(),
        min_sample_size=20,
    )
    assert result["primary_bottleneck"] is None
    assert result["experiment_candidate"] is None
