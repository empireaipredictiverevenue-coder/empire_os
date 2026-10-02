"""Empire Engineering Gauntlet.

Deterministic promotion gate used by agentic control loops. The Gauntlet never
creates authority. It evaluates whether a bounded action has enough architecture,
policy, verification and evidence to advance.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

INTERNAL_AUTHORITIES = frozenset({"observe", "internal_write"})
FOUNDER_AUTHORITY = "founder_gate"
ALLOWED_AUTHORITIES = INTERNAL_AUTHORITIES | {FOUNDER_AUTHORITY}


@dataclass(frozen=True)
class GauntletCandidate:
    action_key: str
    component: str
    authority: str
    evidence_refs: tuple[str, ...]
    architecture_contract: bool
    fresh_context_critic_passed: bool
    tests_policy_passed: bool
    independent_verify_ready: bool
    diff_clean: bool
    reversible: bool
    consequential: bool = False

    def validate(self) -> None:
        if not self.action_key.strip():
            raise ValueError("action_key required")
        if not self.component.strip():
            raise ValueError("component required")
        if self.authority not in ALLOWED_AUTHORITIES:
            raise ValueError("unsupported Gauntlet authority")
        if not self.evidence_refs:
            raise ValueError("Gauntlet evidence required")
        if self.authority in INTERNAL_AUTHORITIES and self.consequential:
            raise ValueError("consequential action cannot use internal authority")


@dataclass(frozen=True)
class GauntletDecision:
    action_key: str
    component: str
    decision: str
    stages: tuple[dict[str, Any], ...]
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    execution_authority: str
    founder_gate_required: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_gauntlet(candidate: GauntletCandidate) -> GauntletDecision:
    candidate.validate()
    checks = (
        ("architecture_contract", candidate.architecture_contract),
        ("fresh_context_critic", candidate.fresh_context_critic_passed),
        ("tests_security_policy", candidate.tests_policy_passed),
        ("independent_verifier_contract", candidate.independent_verify_ready),
        ("diff_review", candidate.diff_clean),
    )
    stages = tuple(
        {"stage": name, "passed": bool(passed)}
        for name, passed in checks
    )
    blockers = [name for name, passed in checks if not passed]

    if candidate.authority in INTERNAL_AUTHORITIES and not candidate.reversible:
        blockers.append("internal_action_not_reversible")

    if blockers:
        decision = "BLOCKED"
        execution_authority = "none"
    elif candidate.authority == FOUNDER_AUTHORITY or candidate.consequential:
        decision = "READY_FOR_APPROVAL"
        execution_authority = "none"
    else:
        decision = "READY_FOR_INTERNAL_EXECUTION"
        execution_authority = candidate.authority

    return GauntletDecision(
        action_key=candidate.action_key,
        component=candidate.component,
        decision=decision,
        stages=stages,
        blockers=tuple(blockers),
        evidence_refs=tuple(dict.fromkeys(candidate.evidence_refs)),
        execution_authority=execution_authority,
        founder_gate_required=decision == "READY_FOR_APPROVAL",
    )
