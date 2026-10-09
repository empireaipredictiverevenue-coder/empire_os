from __future__ import annotations

from datetime import datetime
from typing import Any

from empire_os.lead_smart_coverage_reader import (
    lookup_zip,
)


def predictive_revenue_signal(
    snapshot: dict[str, Any],
    zip_code: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Convert current Lead Smart coverage evidence into a
    Predictive Revenue INPUT.

    This function intentionally does NOT invent:
      - payable-call probability
      - expected revenue
      - expected margin
      - conversion probability

    Those require calibrated realised-outcome evidence.
    """

    coverage = lookup_zip(
        snapshot,
        zip_code,
        now=now,
    )

    return {
        "schema_version":
            "empire.predictive_revenue."
            "lead_smart_signal.v1",

        "buyer":
            "Lead Smart",

        "vertical":
            "Roofing",

        "zip":
            coverage["zip"],

        "evidence_class":
            coverage["evidence_class"],

        "coverage_observed":
            coverage["coverage_observed"],

        "fresh_for_targeting_analysis":
            coverage["freshness"][
                "fresh_for_targeting_analysis"
            ],

        "observed_top_payout_prior":
            coverage["observed_top_payout"],

        "observed_duration_payout_prior":
            coverage[
                "observed_duration_payout"
            ],

        "observed_cpl_payout_prior":
            coverage[
                "observed_cpl_payout"
            ],

        # No guessing.
        "predicted_payable_probability":
            None,

        "predicted_qualified_probability":
            None,

        "expected_revenue":
            None,

        "expected_margin":
            None,

        "calibration_status":
            "AWAITING_REALISED_RINGBA_OUTCOMES",

        "can_rank_by_observed_payout_prior":
            coverage["targeting_candidate"],

        "can_claim_expected_revenue":
            False,

        "live_route_eligible":
            coverage["live_route_eligible"],

        "payout_guaranteed":
            False,

        "revenue_truth_authority":
            [
                "REALISED_RINGBA_PAYOUT",
                "VERIFIED_RINGBA_CALL_EVENT",
                "OBSERVED_COVERAGE_GUIDANCE",
                "MODEL_PREDICTION",
                "HYPOTHESIS",
            ],

        "execution_authority":
            "NONE",
    }


def realised_outcome_feature_contract() -> dict[str, Any]:
    """
    Fields required before Empire may calibrate an actual
    P(payable | context) model for this buyer/vertical.
    """

    return {
        "schema_version":
            "empire.predictive_revenue."
            "lead_smart_calibration_contract.v1",

        "required_realised_features": [
            "ringba_call_id",
            "zip",
            "intent_class",
            "route_class",
            "started_at",
            "connected_seconds",
            "appointment_event",
            "duplicate_within_30d",
            "realised_payout",
            "payout_currency",
            "payout_observed_at",
        ],

        "route_classes": [
            "DURATION",
            "APPOINTMENT_CPL",
        ],

        "prediction_allowed_before_calibration":
            False,

        "execution_authority":
            "NONE",
    }
