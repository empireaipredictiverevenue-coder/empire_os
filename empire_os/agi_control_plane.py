"""Empire agentic-intelligence control plane.

This module provides typed, evidence-grounded cognitive packets and readiness
analysis. It does not execute tools, widen authority, persist private
chain-of-thought, or mutate production state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


LAYERS = (
    "grounding",
    "perception",
    "world_model",
    "memory",
    "goals",
    "planning",
    "model_routing",
    "specialists",
    "deliberation",
    "verification",
    "simulation",
    "policy",
    "execution_bus",
    "runtime_safety",
    "learning",
    "self_improvement",
    "evaluation",
    "agent_identity",
    "audit",
)

MEMORY_TYPES = {
    "working",
    "episodic",
    "semantic",
    "procedural",
    "outcome_conditioned",
}

AUTHORITY_MODES = {
    "OBSERVE",
    "ASSIST",
    "GUARDED_EXECUTE",
}

SIDE_EFFECT_CLASSES = {
    "none",
    "reversible_internal",
    "external_communication",
    "commercial_mutation",
    "financial",
    "infrastructure",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class MemoryRef:
    memory_type: str
    ref: str
    observed_at: str | None = None
    verified_outcome: bool | None = None

    def validate(self) -> None:
        if self.memory_type not in MEMORY_TYPES:
            raise ValueError("unsupported memory_type")
        if not _text(self.ref):
            raise ValueError("memory ref required")
        if self.memory_type == "outcome_conditioned" and self.verified_outcome is not True:
            raise ValueError("outcome_conditioned memory requires verified_outcome=true")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class CandidateOption:
    option_id: str
    summary: str
    expected_value_cents: float | None
    expected_cost_cents: float | None
    risk_score: float | None
    reversible: bool
    required_authority: str
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not _text(self.option_id) or not _text(self.summary):
            raise ValueError("option_id and summary required")
        if self.risk_score is not None and not 0 <= self.risk_score <= 1:
            raise ValueError("risk_score must be between 0 and 1")
        if not _text(self.required_authority):
            raise ValueError("required_authority required")
        if not self.evidence_refs:
            raise ValueError("candidate option requires evidence_refs")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        result = asdict(self)
        result["evidence_refs"] = list(self.evidence_refs)
        if self.expected_value_cents is not None and self.expected_cost_cents is not None:
            result["expected_gross_value_cents"] = (
                self.expected_value_cents - self.expected_cost_cents
            )
        else:
            result["expected_gross_value_cents"] = None
        return result


def build_cognitive_packet(
    *,
    task_id: str,
    goal: str,
    evidence_refs: Sequence[str],
    world_state_ref: str,
    memory_refs: Sequence[Mapping[str, Any]] = (),
    options: Sequence[Mapping[str, Any]] = (),
    selected_option_id: str | None = None,
    constraints: Sequence[str] = (),
    verifier: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
    authority_mode: str = "OBSERVE",
    side_effect_class: str = "none",
) -> dict[str, Any]:
    """Create an auditable cognitive packet without exposing chain-of-thought."""
    task_id = _text(task_id)
    goal = _text(goal)
    world_state_ref = _text(world_state_ref)
    evidence = tuple(dict.fromkeys(_text(ref) for ref in evidence_refs if _text(ref)))
    if not task_id:
        raise ValueError("task_id required")
    if not goal:
        raise ValueError("goal required")
    if not world_state_ref:
        raise ValueError("world_state_ref required")
    if not evidence:
        raise ValueError("evidence_refs required")
    if authority_mode not in AUTHORITY_MODES:
        raise ValueError("unsupported authority_mode")
    if side_effect_class not in SIDE_EFFECT_CLASSES:
        raise ValueError("unsupported side_effect_class")
    if authority_mode == "OBSERVE" and side_effect_class != "none":
        raise ValueError("OBSERVE cognitive packets cannot request side effects")

    memories = []
    for raw in memory_refs:
        ref = MemoryRef(
            memory_type=_text(raw.get("memory_type")),
            ref=_text(raw.get("ref")),
            observed_at=_text(raw.get("observed_at")) or None,
            verified_outcome=raw.get("verified_outcome"),
        )
        memories.append(ref.as_dict())

    candidate_options = []
    option_ids: set[str] = set()
    for raw in options:
        option = CandidateOption(
            option_id=_text(raw.get("option_id")),
            summary=_text(raw.get("summary")),
            expected_value_cents=_number(raw.get("expected_value_cents")),
            expected_cost_cents=_number(raw.get("expected_cost_cents")),
            risk_score=_number(raw.get("risk_score")),
            reversible=raw.get("reversible") is True,
            required_authority=_text(raw.get("required_authority")) or "none",
            evidence_refs=tuple(
                _text(ref) for ref in raw.get("evidence_refs", ()) if _text(ref)
            ),
        )
        if option.option_id in option_ids:
            raise ValueError("duplicate option_id")
        option_ids.add(option.option_id)
        candidate_options.append(option.as_dict())

    selected = _text(selected_option_id) or None
    if selected is not None and selected not in option_ids:
        raise ValueError("selected_option_id must reference a candidate option")

    verifier_data = dict(verifier or {})
    verifier_state = {
        "status": _text(verifier_data.get("status")) or "not_run",
        "evidence_supported": verifier_data.get("evidence_supported"),
        "policy_consistent": verifier_data.get("policy_consistent"),
        "freshness_verified": verifier_data.get("freshness_verified"),
        "independent": verifier_data.get("independent"),
        "issues": list(verifier_data.get("issues") or []),
    }
    policy_data = dict(policy or {})
    policy_state = {
        "status": _text(policy_data.get("status")) or "not_checked",
        "capability": _text(policy_data.get("capability")) or None,
        "approval_required": policy_data.get("approval_required"),
        "approval_present": policy_data.get("approval_present"),
        "allowed": policy_data.get("allowed"),
        "blockers": list(policy_data.get("blockers") or []),
    }

    execution_ready = (
        selected is not None
        and verifier_state["status"] == "passed"
        and verifier_state["evidence_supported"] is True
        and verifier_state["policy_consistent"] is True
        and verifier_state["freshness_verified"] is True
        and policy_state["status"] == "passed"
        and policy_state["allowed"] is True
        and (
            policy_state["approval_required"] is not True
            or policy_state["approval_present"] is True
        )
        and authority_mode == "GUARDED_EXECUTE"
        and side_effect_class != "none"
    )

    return {
        "schema_version": "empire_cognitive_packet.v1",
        "task_id": task_id,
        "goal": goal,
        "world_state_ref": world_state_ref,
        "evidence_refs": list(evidence),
        "memory_refs": memories,
        "constraints": list(dict.fromkeys(_text(c) for c in constraints if _text(c))),
        "candidate_options": candidate_options,
        "selected_option_id": selected,
        "verifier": verifier_state,
        "policy": policy_state,
        "authority_mode": authority_mode,
        "side_effect_class": side_effect_class,
        "execution_ready": execution_ready,
        "execution_performed": False,
        "private_chain_of_thought_persisted": False,
        "audit_summary_only": True,
    }


def assess_agi_layer_readiness(
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Assess whether each cognitive layer has explicit evidence-backed support."""
    evidence = dict(evidence or {})

    requirements = {
        "grounding": ("canonical_evidence", "source_provenance", "freshness"),
        "perception": ("bounded_context", "missing_evidence_detection"),
        "world_model": ("temporal_entities", "relationship_graph", "uncertainty"),
        "memory": ("working_memory", "episodic_memory", "semantic_memory", "procedural_memory"),
        "goals": ("explicit_goal", "hard_constraints", "utility_function"),
        "planning": ("multi_option_plan", "dependencies", "economics", "reversibility"),
        "model_routing": ("task_classification", "cost_awareness", "privacy_awareness"),
        "specialists": ("scoped_capabilities", "structured_outputs"),
        "deliberation": ("independent_proposals", "disagreement_capture"),
        "verification": ("independent_verifier", "evidence_check", "policy_check"),
        "simulation": ("simulation_label", "counterfactuals"),
        "policy": ("external_policy_engine", "capability_grants", "approval_checks"),
        "execution_bus": ("typed_tools", "idempotency", "audit_log"),
        "runtime_safety": ("health_observer", "pause_or_quarantine"),
        "learning": ("verified_outcomes", "calibration", "promotion_gate"),
        "self_improvement": ("proposal_only_improvement", "evaluation_before_promotion"),
        "evaluation": ("regression_eval", "shadow_eval", "adversarial_eval"),
        "agent_identity": ("agent_identities", "capability_scope", "versioning"),
        "audit": ("decision_ledger", "evidence_lineage", "outcome_links"),
    }

    layers = []
    for layer in LAYERS:
        required = requirements[layer]
        missing = [key for key in required if evidence.get(key) is not True]
        layers.append({
            "layer": layer,
            "status": "READY" if not missing else "INCOMPLETE",
            "missing": missing,
        })

    ready_count = sum(1 for layer in layers if layer["status"] == "READY")
    blockers = [layer["layer"] for layer in layers if layer["status"] != "READY"]

    return {
        "schema_version": "agi_layer_readiness.v1",
        "claim": "agentic_intelligence_architecture_not_proven_human_level_agi",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "layers": layers,
        "ready_layer_count": ready_count,
        "total_layer_count": len(layers),
        "incomplete_layers": blockers,
        "consequential_autonomy_ready": False,
        "authority_expansion_requires_verified_revenue_loop": True,
    }


def review_learning_candidate(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Gate self-improvement on verified outcome evidence and evaluation."""
    blockers: list[str] = []

    if candidate.get("verified_outcome") is not True:
        blockers.append("verified_outcome_required")
    if not _text(candidate.get("outcome_ref")):
        blockers.append("outcome_ref_required")
    if not _text(candidate.get("baseline_ref")):
        blockers.append("baseline_ref_required")
    if not _text(candidate.get("candidate_ref")):
        blockers.append("candidate_ref_required")
    if candidate.get("evaluation_passed") is not True:
        blockers.append("evaluation_not_passed")
    if candidate.get("shadow_passed") is not True:
        blockers.append("shadow_not_passed")
    if candidate.get("policy_review_passed") is not True:
        blockers.append("policy_review_not_passed")
    if candidate.get("synthetic_only") is True:
        blockers.append("synthetic_only_cannot_promote")

    return {
        "schema_version": "agi_learning_candidate.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "model_weight_mutation": False,
        "policy_mutation": False,
        "permission_expansion": False,
        "promotion_ready_for_human_review": not blockers,
        "blockers": blockers,
        "promotion_state": "PROPOSED" if blockers else "EVALUATED",
    }
