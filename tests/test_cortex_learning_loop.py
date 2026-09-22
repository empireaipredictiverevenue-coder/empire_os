from empire_os.cortex_learning_loop import (
    build_cortex_learning_packet,
    build_cortex_learning_snapshot,
)


def _twin():
    return {
        "entity_id": "entity-golden",
        "identity": {
            "company_name": "Golden Spike Roofing Inc",
        },
        "buyer_state": {
            "current_factual_state": "RESEARCHED",
        },
        "qualification": {
            "history": [{
                "score": 86.2,
                "status": "insufficient_evidence",
            }],
        },
        "public_evidence": {
            "supported_claim_count": 3,
        },
        "competitor_relationships": {
            "evidence_count": 3,
        },
        "research": {
            "observation_count": 4,
        },
        "conversation": {
            "history_available": True,
            "replies": [],
        },
        "commercial": {
            "payment_evidence": [],
            "fulfilment_orders": [],
        },
        "outcomes": {
            "available": True,
            "history": [],
        },
        "revenue_truth": {
            "available": True,
            "recognized_revenue_cents": 0,
            "realized_gp_cents": 0,
            "actual_revenue": False,
        },
        # Must never become outcome truth.
        "forecast": {
            "expected_revenue_cents": 500000,
            "conversion_probability": 0.99,
        },
    }


def _verified_outcome(conversion="won"):
    return {
        "conversion_outcome": conversion,
        "delivery_outcome": "delivered",
        "buyer_satisfaction": 9.0,
        "evidence_kind": "buyer_confirmation",
        "evidence_reference": "evidence://outcome/1",
        "recorded_at": "2026-09-22T12:00:00+00:00",
    }


def test_research_evidence_is_features_only_not_label():
    result = build_cortex_learning_packet(_twin())

    assert result["research_features"]["supported_claim_count"] == 3
    assert result["research_features"]["competitor_evidence_count"] == 3
    assert result["research_features"]["features_only"] is True
    assert result["research_features"]["commercial_label"] is False
    assert result["label"]["available"] is False
    assert result["synthetic_commercial_label"] is False


def test_replies_are_observed_outcomes_not_commercial_labels():
    twin = _twin()
    twin["conversation"]["replies"] = [{
        "classification": "question",
        "confidence": 0.91,
        "received_at": "2026-09-22T12:00:00+00:00",
    }]

    result = build_cortex_learning_packet(twin)

    assert result["reply_outcome"]["observed"] is True
    assert result["reply_outcome"]["reply_count"] == 1
    assert result["reply_outcome"]["classifications"] == ["question"]
    assert result["reply_outcome"]["commercial_label"] is False
    assert result["label"]["available"] is False


def test_won_outcome_without_full_verified_chain_is_blocked():
    twin = _twin()
    twin["outcomes"]["history"] = [_verified_outcome("won")]

    result = build_cortex_learning_packet(twin)

    assert result["label"]["available"] is False
    assert "verified_payment_missing" in result["label"]["blockers"]
    assert "verified_fulfilment_missing" in result["label"]["blockers"]
    assert "recognized_revenue_missing" in result["label"]["blockers"]
    assert result["verified_customer_learning"] is False


def test_verified_customer_label_requires_payment_fulfilment_and_revenue():
    twin = _twin()
    twin["commercial"]["payment_evidence"] = [{
        "transaction_hash": "0xabc",
        "verified_at": "2026-09-22T11:45:00+00:00",
    }]
    twin["commercial"]["fulfilment_orders"] = [{
        "state": "outcome_captured",
        "delivered_at": "2026-09-22T11:50:00+00:00",
    }]
    twin["outcomes"]["history"] = [_verified_outcome("won")]
    twin["revenue_truth"].update({
        "recognized_revenue_cents": 150000,
        "realized_gp_cents": 90000,
        "actual_revenue": True,
    })

    result = build_cortex_learning_packet(twin)

    assert result["label"]["available"] is True
    assert result["label"]["kind"] == "verified_customer_conversion"
    assert result["label"]["value"] == 1
    assert result["label"]["synthetic"] is False
    assert result["label"]["forecast_derived"] is False
    assert result["verified_customer_learning"] is True
    assert result["calibration_feedback"]["available"] is True
    assert result["calibration_feedback"]["qualification_score"] == 86.2
    assert result["calibration_feedback"]["verified_label"] == 1
    assert (
        result["calibration_feedback"]["model_weight_mutation_authorized"]
        is False
    )


def test_verified_lost_outcome_can_supply_negative_label():
    twin = _twin()
    twin["outcomes"]["history"] = [_verified_outcome("lost")]

    result = build_cortex_learning_packet(twin)

    assert result["label"]["available"] is True
    assert result["label"]["kind"] == "verified_non_conversion"
    assert result["label"]["value"] == 0
    assert result["verified_customer_learning"] is False
    assert result["calibration_feedback"]["available"] is True


def test_forecast_is_never_used_as_outcome_or_label():
    result = build_cortex_learning_packet(_twin())

    assert result["forecast_used_as_outcome"] is False
    assert result["label"]["forecast_derived"] is False
    assert result["label"]["available"] is False


def test_snapshot_exposes_learning_readiness_without_execution():
    twin = _twin()
    result = build_cortex_learning_snapshot({"twins": [twin]})

    assert result["packet_count"] == 1
    assert result["learning_ready_count"] == 0
    assert result["verified_customer_learning_count"] == 0
    assert result["forecast_used_as_outcome"] is False
    assert result["synthetic_commercial_label_count"] == 0
    assert result["model_weight_mutation_authorized"] is False
    assert result["execution_authority"] == "none"
