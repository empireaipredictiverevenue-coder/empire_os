"""Governed promotion checks for Ringleader policy candidates.

Candidate policies may be evaluated in shadow and counterfactual mode, but this module
can only mark a candidate as ready for human/release review. It never activates policy.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PolicyPromotionCriteria:
    min_shadow_samples: int = 20
    max_disagreement_rate: float = 0.10
    max_looser_cases: int = 0


def policy_fingerprint(policy_payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        dict(policy_payload),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_policy_manifest(
    *,
    name: str,
    version: str,
    policy_payload: Mapping[str, Any],
    source_commit: str,
) -> dict[str, Any]:
    payload = dict(policy_payload)
    return {
        "name": str(name),
        "version": str(version),
        "source_commit": str(source_commit),
        "fingerprint": policy_fingerprint(payload),
        "policy": payload,
        "activation_authorized": False,
    }


def evaluate_candidate_promotion(
    shadow_result: Mapping[str, Any],
    counterfactual_result: Mapping[str, Any],
    *,
    criteria: PolicyPromotionCriteria | None = None,
) -> dict[str, Any]:
    criteria = criteria or PolicyPromotionCriteria()

    samples = int(shadow_result.get("samples") or 0)
    disagreement_rate = float(shadow_result.get("disagreement_rate") or 0.0)
    candidate_looser = int(shadow_result.get("candidate_looser") or 0)
    promotion_authorized = shadow_result.get("promotion_authorized")
    replay_mutation = counterfactual_result.get("production_mutation_authorized")

    blockers: list[str] = []
    review_flags: list[str] = []

    if samples < criteria.min_shadow_samples:
        blockers.append("insufficient_shadow_samples")
    if disagreement_rate > criteria.max_disagreement_rate:
        blockers.append("shadow_disagreement_rate_too_high")
    if candidate_looser > criteria.max_looser_cases:
        review_flags.append("candidate_is_looser_than_current_policy")
    if promotion_authorized is not False:
        blockers.append("shadow_mode_authority_violation")
    if replay_mutation is not False:
        blockers.append("counterfactual_authority_violation")

    if blockers:
        status = "NOT_READY"
    elif review_flags:
        status = "REVIEW_REQUIRED"
    else:
        status = "READY_FOR_REVIEW"

    return {
        "status": status,
        "blockers": blockers,
        "review_flags": review_flags,
        "samples": samples,
        "disagreement_rate": disagreement_rate,
        "candidate_looser": candidate_looser,
        "activation_authorized": False,
        "requires_explicit_release_approval": True,
    }
