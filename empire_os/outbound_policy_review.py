"""Compose shadow, counterfactual, and promotion evidence into one review packet."""
from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

from empire_os.outbound_counterfactual_replay import replay_threshold_policy
from empire_os.outbound_deliverability_snapshot import DeliverabilityThresholds
from empire_os.outbound_policy_promotion import evaluate_candidate_promotion
from empire_os.outbound_policy_shadow import compare_policies


Evaluator = Callable[[Mapping[str, Any]], Mapping[str, Any]]


def build_policy_review_packet(
    *,
    current_manifest: Mapping[str, Any],
    candidate_manifest: Mapping[str, Any],
    contexts: Iterable[Mapping[str, Any]],
    historical_windows: Iterable[Mapping[str, Any]],
    current_evaluator: Evaluator,
    candidate_evaluator: Evaluator,
    proposed_thresholds: DeliverabilityThresholds,
) -> dict[str, Any]:
    current_fingerprint = str(current_manifest.get("fingerprint") or "")
    candidate_fingerprint = str(candidate_manifest.get("fingerprint") or "")

    if not current_fingerprint or not candidate_fingerprint:
        raise ValueError("policy_manifest_fingerprint_required")

    if current_fingerprint == candidate_fingerprint:
        return {
            "status": "NO_CHANGE",
            "current_fingerprint": current_fingerprint,
            "candidate_fingerprint": candidate_fingerprint,
            "activation_authorized": False,
        }

    shadow = compare_policies(
        contexts,
        current=current_evaluator,
        candidate=candidate_evaluator,
    )
    replay = replay_threshold_policy(
        historical_windows,
        proposed=proposed_thresholds,
    )
    promotion = evaluate_candidate_promotion(shadow, replay)

    return {
        "status": promotion["status"],
        "current_fingerprint": current_fingerprint,
        "candidate_fingerprint": candidate_fingerprint,
        "shadow": shadow,
        "counterfactual": replay,
        "promotion": promotion,
        "activation_authorized": False,
        "review_packet_only": True,
    }
