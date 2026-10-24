"""PRIME prediction precision, accuracy and reliability SHADOW metrics.

This receives paired, ORIGINAL verified-learning reviews from the established
owner-only calibration gate, never observations scraped from external sources.
It is a deterministic diagnostic, NOT an authenticated feedback reader, live
financial record, trading signal, classification policy or model promotion.

Classification threshold 0.50 is purely a declared RESEARCH convention,
not the original prediction's business action threshold. When a denominator
is empty the metric is UNKNOWN (None), never 0 or 100 percent.
"""
from __future__ import annotations

from collections.abc import Sequence
from math import isfinite, sqrt
from typing import Any

from empire_os.quant_brain import brier_score, log_loss, calibration_bins

SCHEMA = "empire.prime.shadow_prediction_quality.v1"
RESEARCH_CLASSIFICATION_THRESHOLD = 0.5
MIN_SHADOW_SCREENING_PAIRS = 30
RELIABILITY_BINS = 5


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _wilson95(successes: int, total: int) -> list[float] | None:
    """Approximate Wilson 95% CI for sample fraction, not model validity."""
    if not total:
        return None
    z = 1.959963984540054
    p = successes / total
    denom = 1 + z*z / total
    centre = (p + z*z/(2*total)) / denom
    margin = z * sqrt((p * (1-p) + z*z/(4*total)) / total) / denom
    return [round(max(0., centre-margin), 6), round(min(1., centre+margin), 6)]


def evaluate_prime_prediction_quality(
    probabilities: Sequence[float], outcomes: Sequence[int],
) -> dict[str, Any]:
    """Pure score for existing *paired owner-review inputs* only.

    No successful score implies that the inputs were independently read,
    representative, prospective, holdout, licensed or financially verified.
    """
    if type(probabilities) not in (list, tuple) or type(outcomes) not in (list, tuple):
        raise ValueError("exact ordered paired probability/outcome sequences required")
    if len(probabilities) != len(outcomes) or len(probabilities) > 50:
        raise ValueError("bounded and matched original outcome pairs required")
    ps: list[float] = []
    ys: list[int] = []
    for p, y in zip(probabilities, outcomes):
        if type(p) not in (float, int) or not isfinite(p) or not 0 <= p <= 1:
            raise ValueError("finite bounded original probability required")
        if type(y) is not int or y not in (0, 1):
            raise ValueError("exact binary terminal outcome required")
        ps.append(float(p))
        ys.append(y)
    n = len(ps)
    if not n:
        return {
            "schema_version": SCHEMA,
            "mode": "OBSERVE",
            "status": "NO_PAIRED_OUTCOMES",
            "sample_count": 0,
            "positive_outcome_count": 0,
            "predicted_positive_count": 0,
            "research_threshold": RESEARCH_CLASSIFICATION_THRESHOLD,
            "true_positive": 0, "true_negative": 0,
            "false_positive": 0, "false_negative": 0,
            "precision": None, "accuracy": None, "recall": None,
            "specificity": None, "f1_score": None,
            "balanced_accuracy": None,
            "positive_outcome_base_rate": None,
            "majority_class_accuracy_baseline": None,
            "accuracy_beats_majority_baseline": None,
            "precision_wilson95_interval": None,
            "accuracy_wilson95_interval": None,
            "brier_score": None, "log_loss": None,
            "expected_calibration_error": None,
            "calibration_bins_used": None,
            "shadow_minimum_screening_threshold_met": False,
            "both_outcome_classes_observed": False,
            "prospective_holdout_independently_verified": False,
            "source_provenance_authenticated_by_metric": False,
            "production_accuracy_verified": False,
            "production_precision_verified": False,
            "model_promotion_authorized": False,
            "execution_authority": "none",
            "blockers": ["NO_PAIRED_TERMINAL_OUTCOMES"],
        }
    tp = tn = fp = fn = 0
    for p, y in zip(ps, ys):
        positive = p >= RESEARCH_CLASSIFICATION_THRESHOLD
        if positive and y == 1:
            tp += 1
        elif positive and y == 0:
            fp += 1
        elif not positive and y == 1:
            fn += 1
        else:
            tn += 1
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    specificity = _ratio(tn, tn + fp)
    accuracy = _ratio(tp + tn, n)
    balanced = (
        round((recall + specificity) / 2, 6)
        if recall is not None and specificity is not None else None
    )
    f1 = _ratio(2*tp, 2*tp + fp + fn)
    wins = tp + fn
    support_met = n >= MIN_SHADOW_SCREENING_PAIRS
    both = 0 < wins < n
    quantified = brier_score(ps, ys)
    loss = log_loss(ps, ys)
    reliability = calibration_bins(ps, ys, bins=RELIABILITY_BINS)
    if not all(q.get("available") is True and q.get("sample_count") == n
               for q in (quantified, loss, reliability)):
        raise ValueError("original Quant scoring contract mismatch")
    baseline = _ratio(max(wins, n-wins), n)
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "SHADOW_DIAGNOSTICS_UNPROMOTED",
        "sample_count": n,
        "positive_outcome_count": wins,
        "predicted_positive_count": tp + fp,
        "research_threshold": RESEARCH_CLASSIFICATION_THRESHOLD,
        "true_positive": tp, "true_negative": tn,
        "false_positive": fp, "false_negative": fn,
        "precision": precision, "accuracy": accuracy,
        "recall": recall, "specificity": specificity,
        "f1_score": f1, "balanced_accuracy": balanced,
        "positive_outcome_base_rate": _ratio(wins, n),
        "majority_class_accuracy_baseline": baseline,
        "accuracy_beats_majority_baseline": (
            accuracy > baseline if support_met and both else None
        ),
        "precision_wilson95_interval": _wilson95(tp, tp+fp),
        "accuracy_wilson95_interval": _wilson95(tp+tn, n),
        "brier_score": quantified["brier_score"],
        "log_loss": loss["log_loss"],
        "expected_calibration_error": reliability["expected_calibration_error"],
        "calibration_bins_used": RELIABILITY_BINS,
        "shadow_minimum_screening_threshold_met": support_met,
        "both_outcome_classes_observed": both,
        "prospective_holdout_independently_verified": False,
        "source_provenance_authenticated_by_metric": False,
        "production_accuracy_verified": False,
        "production_precision_verified": False,
        "model_promotion_authorized": False,
        "execution_authority": "none",
        "blockers": [
            "ORIGINAL_PREDICTION_AND_OUTCOME_AUTHENTICATION_REQUIRED",
            "OUT_OF_TIME_HOLDOUT_VALIDATION_REQUIRED",
            "SELECTION_BIAS_AND_COHORT_REPRESENTATIVENESS_UNVERIFIED",
            "CLASSIFICATION_THRESHOLD_NOT_BUSINESS_APPROVED",
        ] + ([] if support_met else ["SHADOW_SAMPLE_COUNT_TOO_SMALL"])
            + ([] if both else ["SINGLE_OUTCOME_CLASS_CANNOT_ASSESS_DISCRIMINATION"]),
    }
