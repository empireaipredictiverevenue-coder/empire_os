"""EmpireOS Hybrid Factory V1: pure, fail-closed pre-promotion quality decision.

A decision here never grants operational authority, promotes code, changes a
checklist item, or represents production proof. Caller must obtain results from
trusted services; user/agent-submitted JSON is not a verifiable attestation.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

SCHEMA = "empire.factory_hybrid_quality.v1"
VERIFIED = "VERIFIED_FOR_REVIEW"
WAIT = "WAITING_FOR_EVIDENCE"
REPAIR = "REPAIR_REQUIRED"
BLOCK = "BLOCKED"
ESCALATE = "ESCALATE_TO_COUNCIL"
FOUNDER = "AWAITING_FOUNDER_GATE"
VALID_RISK = frozenset({"low", "medium", "high", "critical"})
VALID_AUTHORITY = frozenset({"observe", "internal_write"})
HIGH_RISK_ACTIONS = frozenset({
    "external_send", "payment_action", "revenue_recognition",
    "production_deploy", "production_merge", "database_migration",
    "commercial_terms_acceptance", "tenant_authority_change",
})


@dataclass(frozen=True)
class GateDecision:
    status: str
    reasons: tuple[str, ...]
    request_id: str
    proposal_branch: str
    evidence_refs: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA,
            "status": self.status,
            "reasons": list(self.reasons),
            "request_id": self.request_id,
            "proposal_branch": self.proposal_branch,
            "evidence_refs": list(self.evidence_refs),
            # Deliberately invariant; do not infer authority from any verdict.
            "production_promotion_allowed": False,
            "production_merge": False,
            "production_deploy": False,
            "external_send": False,
            "payment_action": False,
            "revenue_recognition": False,
            "execution_authority": "none",
            "task_done": False,
        }


def _object(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _nonempty(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def evaluate_hybrid_quality(
    *,
    request: Mapping[str, Any],
    proposal_gate: Mapping[str, Any],
    self_review: Mapping[str, Any] | None = None,
    independent_review: Mapping[str, Any] | None = None,
    promptfoo_result: Mapping[str, Any] | None = None,
    council_result: Mapping[str, Any] | None = None,
) -> GateDecision:
    """Assess candidate evidence without ever granting merge/deploy authority.

    Expected `proposal_gate` comes from verify_proposal_candidate(). Extra
    evidence must come from trusted, separately authenticated implementations;
    this function does NOT authenticate a supplied claim or JSON document.
    """
    req = _object(request)
    gate = _object(proposal_gate)
    local = _object(self_review)
    independent = _object(independent_review)
    promptfoo = _object(promptfoo_result)
    council = _object(council_result)
    rid = _nonempty(req.get("request_id"))
    branch = _nonempty(gate.get("proposal_branch"))
    refs: list[str] = []

    def decide(status: str, *reasons: str) -> GateDecision:
        return GateDecision(status, tuple(reasons), rid, branch, tuple(refs))

    if not rid or not branch:
        return decide(BLOCK, "request_identity_or_proposal_branch_missing")
    if _nonempty(req.get("authority")) not in VALID_AUTHORITY:
        return decide(BLOCK, "unsupported_authority")
    risk = _nonempty(req.get("risk_class"))
    if risk not in VALID_RISK:
        return decide(BLOCK, "invalid_risk_class")
    builder = _nonempty(req.get("builder_id"))
    persona = _nonempty(req.get("persona_id"))
    soul = _nonempty(req.get("soul_id"))
    if not (builder and persona and soul):
        return decide(BLOCK, "builder_persona_or_soul_identity_missing")
    if _nonempty(req.get("proposal_branch")) != branch:
        return decide(BLOCK, "request_proposal_branch_mismatch")
    if type(req.get("founder_gate_required")) is not bool:
        return decide(BLOCK, "founder_gate_policy_missing")
    if any(req.get(name) is True for name in HIGH_RISK_ACTIONS):
        return decide(BLOCK, "consequential_action_not_authorised_by_quality_gate")
    if gate.get("schema_version") != "empire.execution-plane-candidate-gate.v1":
        return decide(BLOCK, "candidate_gate_schema_mismatch")
    if gate.get("production_promotion_allowed") is not False:
        return decide(BLOCK, "candidate_gate_claims_promotion_authority")
    if gate.get("execution_authority") != "none":
        return decide(BLOCK, "candidate_gate_claims_execution_authority")

    candidate = _object(gate.get("candidate_verification"))
    if candidate.get("passed") is False:
        return decide(REPAIR, "deterministic_candidate_verification_failed")
    if candidate.get("passed") is not True:
        return decide(WAIT, "deterministic_candidate_verification_missing")
    if gate.get("candidate_gate_passed") not in (True, False) or gate.get("awaiting_promptfoo") not in (True, False):
        return decide(BLOCK, "candidate_gate_state_missing")
    if gate.get("promptfoo_required") not in (True, False):
        return decide(BLOCK, "promptfoo_requirement_unspecified")
    proof_ref = _nonempty(candidate.get("candidate_patch_path"))
    if proof_ref:
        refs.append(proof_ref)

    if _nonempty(local.get("builder_id")) != builder:
        return decide(WAIT, "builder_self_review_missing_or_unbound")
    if _nonempty(local.get("proposal_branch")) != branch:
        return decide(BLOCK, "self_review_wrong_proposal")
    if local.get("passed") is False:
        return decide(REPAIR, "builder_self_review_failed")
    if local.get("passed") is not True:
        return decide(WAIT, "builder_self_review_not_passed")
    self_ref = _nonempty(local.get("evidence_ref"))
    if not self_ref:
        return decide(WAIT, "builder_self_review_evidence_missing")
    refs.append(self_ref)

    reviewer = _nonempty(independent.get("reviewer_id"))
    if not reviewer:
        return decide(WAIT, "independent_review_missing")
    if reviewer == builder:
        return decide(BLOCK, "builder_cannot_review_own_work")
    if _nonempty(independent.get("proposal_branch")) != branch:
        return decide(BLOCK, "independent_review_wrong_proposal")
    if independent.get("advisory_only") is not True:
        # DistinctModelReviewer is advisory and must not impersonate a gate.
        return decide(BLOCK, "independent_model_review_misrepresented_as_authoritative")
    verdict = independent.get("verdict")
    if verdict == "FAIL":
        return decide(ESCALATE, "independent_model_review_rejected_candidate")
    if verdict not in ("PASS", "PASS_WITH_WARNINGS"):
        return decide(WAIT, "independent_model_review_unresolved")
    review_ref = _nonempty(independent.get("evidence_ref"))
    if not review_ref:
        return decide(WAIT, "independent_model_review_evidence_missing")
    refs.append(review_ref)

    if gate.get("promptfoo_required") is True:
        if gate.get("awaiting_promptfoo") is not True or gate.get("candidate_gate_passed") is not False:
            return decide(BLOCK, "inconsistent_promptfoo_candidate_gate")
        if _nonempty(promptfoo.get("proposal_branch")) not in ("", branch):
            return decide(BLOCK, "promptfoo_wrong_proposal")
        if promptfoo.get("status") in ("FAIL", "FAILED"):
            return decide(REPAIR, "promptfoo_failed")
        if promptfoo.get("status") != "PASS":
            return decide(WAIT, "promptfoo_not_finished")
        if _nonempty(promptfoo.get("proposal_branch")) != branch or not _nonempty(promptfoo.get("evidence_ref")):
            return decide(WAIT, "promptfoo_attestation_not_bound")
        if _nonempty(promptfoo.get("verifier_id")) in ("", builder):
            return decide(BLOCK, "promptfoo_verifier_not_independent")
        refs.append(_nonempty(promptfoo.get("evidence_ref")))
    else:
        if gate.get("awaiting_promptfoo") is not False or gate.get("candidate_gate_passed") is not True:
            return decide(BLOCK, "inconsistent_candidate_gate_status")

    if risk in ("high", "critical") or verdict == "PASS_WITH_WARNINGS":
        if council.get("status") == "REJECT":
            return decide(BLOCK, "council_rejected")
        if council.get("status") != "RECOMMEND_APPROVE":
            return decide(ESCALATE, "risk_or_review_warnings_require_council")
        if _nonempty(council.get("proposal_branch")) != branch:
            return decide(BLOCK, "council_result_wrong_proposal")
        voters = council.get("voter_ids")
        if (not isinstance(voters, (tuple, list)) or len(voters) < 2
                or any(not isinstance(v, str) or not _nonempty(v) or v == builder
                       for v in voters)
                or len(set(voters)) != len(voters)):
            return decide(BLOCK, "council_not_independent")
        if not _nonempty(council.get("evidence_ref")):
            return decide(WAIT, "council_evidence_missing")
        refs.append(_nonempty(council.get("evidence_ref")))

    if req["founder_gate_required"] is True:
        return decide(FOUNDER, "external_founder_approval_required")
    return decide(VERIFIED, "candidate_quality_verified_for_separate_promotion_review")
