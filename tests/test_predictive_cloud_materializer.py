import json
from datetime import datetime, timezone

from empire_os.predictive_cloud_materializer import (
    refresh_predictive_cloud_materializers,
)


NOW = datetime(
    2026,
    10,
    3,
    0,
    30,
    tzinfo=timezone.utc,
)


def _write(root, rel, payload):
    path = root / rel
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_materializer_keeps_missing_economics_unknown(
    tmp_path,
):
    _write(
        tmp_path,
        "runtime/opportunity_factory/value_latest.json",
        {
            "candidate_count": 1,
            "items": [
                {
                    "status": "UNAVAILABLE",
                    "expected_revenue_cents": None,
                    "expected_gross_profit_cents": None,
                    "quant_input_evidence": {},
                }
            ],
        },
    )

    _write(
        tmp_path,
        "runtime/predictive_intelligence/latest.json",
        {
            "probability_ready_product_count": 0,
            "timing_ready_product_count": 0,
            "matched_outcome_count": 0,
        },
    )

    result = refresh_predictive_cloud_materializers(
        tmp_path,
        now=NOW,
    )

    trend = result["future_trend"]
    formula = result[
        "predictive_cloud_formula"
    ]

    assert trend["available"] is True
    assert trend["algorithm_available"] is True
    assert trend["prediction_ready"] is False

    assert formula["available"] is True
    assert formula["algorithm_available"] is True
    assert formula["formula_evaluated"] is False
    assert formula["prediction_ready"] is False

    assert (
        formula[
            "portfolio_expected_revenue_cents"
        ]
        is None
    )

    assert (
        result[
            "synthetic_economics_generated"
        ]
        is False
    )

    assert result["execution_authority"] == "none"


def test_available_economics_do_not_become_actual_revenue(
    tmp_path,
):
    _write(
        tmp_path,
        "runtime/opportunity_factory/value_latest.json",
        {
            "candidate_count": 1,
            "items": [
                {
                    "status": "AVAILABLE",
                    "expected_revenue_cents": 10000,
                    "expected_gross_profit_cents": 7000,
                    "quant_input_evidence": {
                        "evidence_refs": [
                            "canonical:test"
                        ]
                    },
                }
            ],
        },
    )

    _write(
        tmp_path,
        "runtime/predictive_intelligence/latest.json",
        {
            "probability_ready_product_count": 1,
            "timing_ready_product_count": 1,
            "matched_outcome_count": 1,
        },
    )

    result = refresh_predictive_cloud_materializers(
        tmp_path,
        now=NOW,
    )

    assert result["future_trend"][
        "prediction_ready"
    ] is True

    assert result["predictive_cloud_formula"][
        "prediction_ready"
    ] is True

    assert result["future_trend"][
        "actual_revenue"
    ] is False

    assert result["predictive_cloud_formula"][
        "actual_revenue"
    ] is False
