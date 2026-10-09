"""Hybrid Factory V1 review coordinator: read-only, fail-closed.

The department queue currently lacks a public REVIEW transition. Its _finish
requires a RUNNING, leased item, so a BLOCKED item cannot be completed by simply
calling complete(). This module never mutates queue state or approves execution.

Review evidence must be loaded from trusted canonical services by a future
adapter. Merely presenting JSON to this coordinator never constitutes an
attestation or authority to close a work item.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from empire_os.factory_hybrid_quality_v1 import (
    BLOCK, ESCALATE, FOUNDER, REPAIR, VERIFIED, WAIT,
    evaluate_hybrid_quality,
)

SCHEMA = "empire.factory_hybrid_review.v1"
CANDIDATE = "AWAITING_AUTHENTICATED_REVIEW"
NOT_READY = "NOT_READY_FOR_REVIEW"
REVIEWED = "REVIEWED_PENDING_TRUSTED_FINALISATION"


@dataclass(frozen=True)
class ReviewAssessment:
    work_id: str
    status: str
    reason: str
    proposal_branch: str = ""
    quality_status: str = ""
    evidence_refs: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA,
            "work_id": self.work_id,
            "status": self.status,
            "reason": self.reason,
            "proposal_branch": self.proposal_branch,
            "quality_status": self.quality_status,
            "evidence_refs": list(self.evidence_refs),
            "queue_mutated": False,
            "department_work_done": False,
            "execution_completed": False,
            "production_merge": False,
            "production_deploy": False,
            "external_send": False,
            "payment_action": False,
            "revenue_recognition": False,
            "execution_authority": "none",
        }


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def assess_held_review(
    *,
    work_item: Mapping[str, Any],
    quality_request: Mapping[str, Any] | None = None,
    self_review: Mapping[str, Any] | None = None,
    independent_review: Mapping[str, Any] | None = None,
    promptfoo_result: Mapping[str, Any] | None = None,
    council_result: Mapping[str, Any] | None = None,
) -> ReviewAssessment:
    """Classify a held candidate, never authenticate receipts or finalize it.

    `quality_request` and reviewer inputs are *untrusted* unless separately
    fetched and attested by a system adapter. Even a completely passing review
    produces REVIEWED_PENDING_TRUSTED_FINALISATION, never DONE.
    """
    item = _map(work_item)
    work_id = _str(item.get("id"))

    def outcome(status: str, reason: str, branch: str = "", quality: str = "", refs: tuple[str, ...] = ()) -> ReviewAssessment:
        return ReviewAssessment(work_id, status, reason, branch, quality, refs)

    if not work_id or "/" in work_id or "\\" in work_id or work_id in {".", ".."}:
        return outcome(BLOCK, "invalid_work_identity")
    if _str(item.get("target_component")) not in {"agent_tool_execution_plane", "empire_coder"}:
        return outcome(NOT_READY, "not_an_engineering_bridge")
    status = _str(item.get("status"))
    if status not in {"BLOCKED", "REVIEW"}:
        return outcome(NOT_READY, "item_is_not_held_for_review")
    if item.get("lease_id") is not None or item.get("worker_id") is not None:
        return outcome(BLOCK, "held_item_retains_execution_lease")

    result = _map(item.get("result"))
    hold = _map(result.get("hybrid_factory"))
    if hold.get("schema_version") != "empire.hybrid_factory_worker_guard.v1":
        return outcome(BLOCK, "hybrid_hold_schema_mismatch")
    if hold.get("enforced") is not True or hold.get("department_work_done") is not False:
        return outcome(BLOCK, "hybrid_hold_not_enforced")
    if _str(hold.get("request_id")) != work_id:
        return outcome(BLOCK, "hybrid_hold_wrong_work_identity")
    if _str(hold.get("disposition")) != "READY_FOR_INDEPENDENT_REVIEW":
        return outcome(NOT_READY, "candidate_not_ready_for_independent_review")
    if status == "BLOCKED" and _str(item.get("error")) != "hybrid_factory_ready_for_independent_review":
        return outcome(BLOCK, "unexpected_blocked_reason")
    if status == "REVIEW" and item.get("error") is not None:
        return outcome(BLOCK, "review_state_has_error")

    if _str(result.get("adapter")) != "agent_tool_execution_plane":
        return outcome(BLOCK, "candidate_missing_execution_plane_bridge")
    dispatch = _map(result.get("dispatch"))
    if _str(dispatch.get("request_id")) != work_id:
        return outcome(BLOCK, "dispatch_identity_mismatch")
    if _str(dispatch.get("status")) != "CANDIDATE_GATE_PASSED":
        return outcome(NOT_READY, "candidate_not_verified_by_execution_plane")
    if (_str(result.get("execution_authority")) != "none"
            or result.get("implementation_performed") is not False
            or result.get("external_execution_performed") is not False):
        return outcome(BLOCK, "bridge_claims_execution_authority")
    if dispatch.get("execution_authority") != "none":
        return outcome(BLOCK, "dispatch_claims_execution_authority")
    if any(dispatch.get(key) is not False for key in ("production_deploy", "external_send", "payment_action", "revenue_recognition")):
        return outcome(BLOCK, "dispatch_claims_consequential_action")
    proposal_gate = _map(dispatch.get("proposal_gate"))
    branch = _str(proposal_gate.get("proposal_branch"))
    if not branch or proposal_gate.get("candidate_gate_passed") is not True:
        return outcome(BLOCK, "candidate_gate_missing_or_unpassed")
    if proposal_gate.get("promptfoo_required") is not False:
        return outcome(NOT_READY, "promptfoo_requires_separate_completed_gate")
    if proposal_gate.get("production_promotion_allowed") is not False:
        return outcome(BLOCK, "candidate_claims_promotion_authority")
    if proposal_gate.get("execution_authority") != "none":
        return outcome(BLOCK, "candidate_claims_execution_authority")

    req = _map(quality_request)
    if not req:
        return outcome(CANDIDATE, "independent_review_evidence_not_supplied", branch)
    if _str(req.get("request_id")) != work_id or _str(req.get("proposal_branch")) != branch:
        return outcome(BLOCK, "quality_request_identity_mismatch", branch)
    if _str(req.get("authority")) != _str(item.get("authority")):
        return outcome(BLOCK, "quality_request_authority_mismatch", branch)
    quality = evaluate_hybrid_quality(
        request=req, proposal_gate=proposal_gate, self_review=self_review,
        independent_review=independent_review, promptfoo_result=promptfoo_result,
        council_result=council_result,
    )
    if quality.status == VERIFIED:
        return outcome(REVIEWED, "separate_trusted_finalization_required", branch, quality.status, quality.evidence_refs)
    if quality.status == WAIT:
        return outcome(CANDIDATE, "missing_review_evidence", branch, quality.status, quality.evidence_refs)
    if quality.status in {BLOCK, REPAIR, ESCALATE, FOUNDER}:
        return outcome(quality.status, quality.reasons[0] if quality.reasons else "quality_gate_not_passed", branch, quality.status, quality.evidence_refs)
    return outcome(BLOCK, "unrecognized_quality_verdict", branch)
