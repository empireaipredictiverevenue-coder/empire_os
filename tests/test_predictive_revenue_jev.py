from datetime import datetime, timezone

from empire_os.predictive_revenue_jev import compile_predictive_revenue_jev

NOW = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)


def signal(**overrides):
    values = {
        "signal_id": "sig-1",
        "signal_type": "market_demand",
        "observed_at": "2026-10-02T08:30:00+00:00",
        "truth_class": "OBSERVED",
        "evidence_refs": ["signal:1"],
    }
    values.update(overrides)
    return values


def normalized(**quant_overrides):
    quant = {
        "probability_success": 0.6,
        "conditional_revenue_cents": 150000.0,
        "fixed_cost_cents": 30000.0,
        "success_cost_cents": 30000.0,
        "uncertainty": 0.2,
        "time_to_revenue_days": 15.0,
        "confidence": 0.7,
    }
    quant.update(quant_overrides)
    return {
        "opportunity_key": "market:roofing:denver",
        "opportunity_class": "market_research",
        "normalized_signals": {
            "demand": 0.9,
            "buyer_intent": 0.9,
            "distribution_path": "approved_buyer_network",
        },
        "score_evidence": {
            "demand": {
                "semantic_class": "observed_stage",
                "evidence_refs": ["canonical:commercial_terms"],
            }
        },
        "quant_inputs": quant,
        "quant_input_evidence": {
            "evidence_refs": ["canonical:commercial_product_catalog"],
            "predictive_intelligence": {
                "evidence_refs": ["canonical:commercial_outcomes"],
            },
        },
        "probability_modeled_from_verified_outcomes": True,
        "execution_authority": "none",
    }


def test_verified_positive_signal_routes_to_buyer_match_review():
    packet = compile_predictive_revenue_jev(
        signal=signal(),
        normalized_opportunity=normalized(),
        as_of=NOW,
    )

    assert packet.output_type == "BUYER_MATCH_REVIEW"
    assert packet.value_available is True
    assert packet.probability_success == 0.6
    assert packet.expected_revenue_cents == 90000.0
    assert packet.expected_cost_cents == 48000.0
    assert packet.expected_gross_profit_cents == 42000.0
    assert packet.risk_adjusted_score is not None
    assert packet.freshness == "FRESH"
    assert "signal:1" in packet.evidence_refs
    assert "canonical:commercial_outcomes" in packet.evidence_refs
    assert packet.execution_authority == "none"
    assert packet.actual_revenue is False
    assert packet.outbound_action is False
    assert packet.payment_action is False
    assert packet.revenue_recognition is False


def test_missing_probability_stays_unknown_and_requires_research():
    packet = compile_predictive_revenue_jev(
        signal=signal(),
        normalized_opportunity=normalized(probability_success=None),
        as_of=NOW,
    )

    assert packet.output_type == "RESEARCH_REQUIRED"
    assert packet.value_available is False
    assert packet.probability_success is None
    assert packet.expected_revenue_cents is None
    assert packet.expected_gross_profit_cents is None
    assert "quant_input_missing:probability_success" in packet.blockers


def test_unverified_probability_never_becomes_actionable():
    row = normalized()
    row["probability_modeled_from_verified_outcomes"] = False
    packet = compile_predictive_revenue_jev(
        signal=signal(), normalized_opportunity=row, as_of=NOW
    )

    assert packet.output_type == "RESEARCH_REQUIRED"
    assert "probability_not_backed_by_verified_outcomes" in packet.blockers


def test_stale_signal_forces_research_even_with_complete_quant():
    packet = compile_predictive_revenue_jev(
        signal=signal(observed_at="2026-10-01T00:00:00+00:00"),
        normalized_opportunity=normalized(),
        as_of=NOW,
        max_signal_age_seconds=3600,
    )

    assert packet.output_type == "RESEARCH_REQUIRED"
    assert packet.freshness == "STALE"
    assert "signal_stale" in packet.blockers


def test_negative_expected_gp_routes_to_hold():
    packet = compile_predictive_revenue_jev(
        signal=signal(),
        normalized_opportunity=normalized(
            probability_success=0.2,
            conditional_revenue_cents=10000,
            fixed_cost_cents=9000,
            success_cost_cents=6000,
        ),
        as_of=NOW,
    )

    assert packet.value_available is True
    assert packet.expected_gross_profit_cents < 0
    assert packet.output_type == "HOLD"


def test_explicit_nba_output_type_is_preserved_when_action_wins():
    actions = [{
        "action_key": "outreach-review",
        "probability_action_changes_outcome": 0.5,
        "incremental_revenue_if_changed_cents": 100000,
        "action_cost_cents": 5000,
        "confidence": 0.8,
        "output_type": "OUTREACH_REVIEW",
        "evidence_refs": ["action:evidence:1"],
    }]
    packet = compile_predictive_revenue_jev(
        signal=signal(),
        normalized_opportunity=normalized(),
        as_of=NOW,
        actions=actions,
    )

    assert packet.output_type == "OUTREACH_REVIEW"
    assert packet.recommended_action["action_key"] == "outreach-review"
    assert "action:evidence:1" in packet.evidence_refs
    assert packet.outbound_action is False


def test_predictive_revenue_erv_is_composed_not_reinvented():
    erv_inputs = {
        "probability_close": 0.5,
        "probability_payment_given_close": 0.8,
        "probability_fulfilment_given_payment": 0.9,
        "ltv_cents": 200000,
        "margin_factor": 0.6,
        "capacity_factor": 1.0,
        "recency_factor": 0.9,
        "confidence": 0.7,
        "time_discount_factor": 0.95,
        "acquisition_cost_cents": 10000,
        "fulfilment_cost_cents": 20000,
        "risk_cost_cents": 5000,
        "evidence_refs": ["erv:evidence:1"],
    }
    packet = compile_predictive_revenue_jev(
        signal=signal(),
        normalized_opportunity=normalized(),
        as_of=NOW,
        predictive_revenue_inputs=erv_inputs,
    )

    assert packet.predictive_revenue_erv["status"] == "AVAILABLE"
    assert "expected_revenue_value_cents" in packet.predictive_revenue_erv
    assert "erv:evidence:1" in packet.evidence_refs
    assert packet.predictive_revenue_erv["actual_revenue"] is False


def test_future_or_invalid_signal_fails_closed():
    future = compile_predictive_revenue_jev(
        signal=signal(observed_at="2026-10-03T00:00:00+00:00"),
        normalized_opportunity=normalized(),
        as_of=NOW,
    )
    invalid = compile_predictive_revenue_jev(
        signal=signal(observed_at="not-a-time"),
        normalized_opportunity=normalized(),
        as_of=NOW,
    )

    assert future.output_type == "RESEARCH_REQUIRED"
    assert "signal_from_future" in future.blockers
    assert invalid.output_type == "RESEARCH_REQUIRED"
    assert "signal_timestamp_invalid" in invalid.blockers


def test_invalid_action_output_type_fails_closed():
    packet = compile_predictive_revenue_jev(
        signal=signal(),
        normalized_opportunity=normalized(),
        as_of=NOW,
        actions=[{
            "action_key": "bad",
            "probability_action_changes_outcome": 1.0,
            "incremental_revenue_if_changed_cents": 100,
            "action_cost_cents": 0,
            "confidence": 1.0,
            "output_type": "SEND_MONEY",
            "evidence_refs": ["action:bad"],
        }],
    )
    assert packet.output_type == "RESEARCH_REQUIRED"
    assert "recommended_action_output_type_invalid" in packet.blockers
    assert packet.payment_action is False
