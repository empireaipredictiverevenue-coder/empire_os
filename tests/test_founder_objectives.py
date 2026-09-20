from empire_os.founder_objectives import (
    CURRENT_FOUNDER_OBJECTIVES,
    LEGACY_RECOVERED_OBJECTIVES,
    MetricEvidence,
    evaluate_objectives,
)


def observed(metric, value):
    return MetricEvidence(
        metric=metric,
        value=value,
        observed_at="2026-09-20T23:40:00Z",
        evidence_refs=(f"canonical:{metric}",),
        source="canonical_test",
    )


def test_current_objectives_score_only_observed_evidence():
    result = evaluate_objectives(
        CURRENT_FOUNDER_OBJECTIVES,
        {
            "commercial_buyer_conversations": observed(
                "commercial_buyer_conversations", 0
            ),
            "commercial_terms": observed("commercial_terms", 0),
            "verified_payments": observed("verified_payments", 0),
            "recognized_revenue_cents": observed(
                "recognized_revenue_cents", 0
            ),
        },
        cycle="2026-Q3",
    )

    first = result["objectives"][0]
    assert first["key"] == "F1"
    assert first["evidence_coverage"] == 1.0
    assert first["evidence_weighted_progress"] == 0.0
    assert result["unknown_metrics_are_not_zero"] is True


def test_unknown_metrics_do_not_get_converted_to_zero_progress():
    result = evaluate_objectives(
        CURRENT_FOUNDER_OBJECTIVES,
        {},
        cycle="2026-Q3",
    )

    first = result["objectives"][0]
    assert first["evidence_coverage"] == 0.0
    assert all(
        row["progress"] is None
        for row in first["key_results"]
    )


def test_confirmed_current_targets_are_distinct_from_legacy_targets():
    current = evaluate_objectives(
        CURRENT_FOUNDER_OBJECTIVES,
        {},
        cycle="2026-Q3",
    )
    legacy = evaluate_objectives(
        LEGACY_RECOVERED_OBJECTIVES,
        {},
        cycle="2026-Q3",
    )

    assert current["overall_target_confirmation_coverage"] == 1.0
    assert legacy["overall_target_confirmation_coverage"] == 0.0


def test_metric_evidence_requires_refs_when_observed():
    bad = MetricEvidence(
        metric="commercial_terms",
        value=1,
        observed_at="2026-09-20T23:40:00Z",
        evidence_refs=(),
        source="canonical_test",
    )

    try:
        evaluate_objectives(
            CURRENT_FOUNDER_OBJECTIVES,
            {"commercial_terms": bad},
            cycle="2026-Q3",
        )
    except ValueError as exc:
        assert "evidence refs" in str(exc)
    else:
        raise AssertionError("observed evidence must require refs")


def test_partial_progress_reports_coverage_separately():
    result = evaluate_objectives(
        CURRENT_FOUNDER_OBJECTIVES,
        {
            "commercial_buyer_conversations": observed(
                "commercial_buyer_conversations", 1
            ),
        },
        cycle="2026-Q3",
    )

    first = result["objectives"][0]
    assert first["evidence_weighted_progress"] == 0.25
    assert first["evidence_coverage"] == 0.25
