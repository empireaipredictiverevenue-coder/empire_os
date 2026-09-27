"""Phase 4 Astra activation readiness gates."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AstraActivationEvidence:
    canonical_migrations_applied: bool
    observer_login_provisioned: bool
    observer_dsn_configured: bool
    policy_bindings_complete: bool
    observer_service_installed: bool
    observer_timer_enabled: bool
    feedback_rpc_verified: bool
    operational_evidence_rpc_verified: bool
    first_revenue_loop_verified: bool
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not self.evidence_refs:
            raise ValueError("Astra activation readiness requires evidence")


@dataclass(frozen=True)
class AstraActivationReadiness:
    observe_activation_ready: bool
    consequential_authority_ready: bool
    observe_blockers: tuple[str, ...]
    consequential_blockers: tuple[str, ...]
    execution_authority: str = "none"
    side_effects: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_astra_activation_readiness(
    evidence: AstraActivationEvidence,
) -> AstraActivationReadiness:
    evidence.validate()

    checks = (
        ("canonical_migrations_not_applied", evidence.canonical_migrations_applied),
        ("observer_login_not_provisioned", evidence.observer_login_provisioned),
        ("observer_dsn_not_configured", evidence.observer_dsn_configured),
        ("policy_bindings_incomplete", evidence.policy_bindings_complete),
        ("observer_service_not_installed", evidence.observer_service_installed),
        ("observer_timer_not_enabled", evidence.observer_timer_enabled),
        ("feedback_rpc_not_verified", evidence.feedback_rpc_verified),
        (
            "operational_evidence_rpc_not_verified",
            evidence.operational_evidence_rpc_verified,
        ),
    )
    observe_blockers = tuple(name for name, ok in checks if not ok)
    observe_ready = not observe_blockers

    consequential = list(observe_blockers)
    if not evidence.first_revenue_loop_verified:
        consequential.append("first_revenue_loop_not_verified")

    return AstraActivationReadiness(
        observe_activation_ready=observe_ready,
        consequential_authority_ready=not consequential,
        observe_blockers=observe_blockers,
        consequential_blockers=tuple(consequential),
    )
