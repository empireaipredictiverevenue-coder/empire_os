"""Typed incident correlation for EmpireOS Control Fabric.

Known repairable failures remain owned by ops_sentinel/ops_healer. This layer
correlates unresolved findings, assigns commercial impact, and selects only a
named playbook or escalation. It never emits executable shell.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

ALLOWED_LABELS = (
    "provider_degradation",
    "capacity_contention",
    "workflow_stall",
    "data_freshness",
    "business_blocker",
    "dependency_failure",
    "unknown",
)

ALLOWED_PLAYBOOKS = (
    "provider_failover",
    "queue_recovery",
    "data_refresh",
    "observe_business_blocker",
    "escalate",
)

_CODE_MAP = {
    "model_provider_degraded": ("provider_degradation", "provider_failover"),
    "coder_model_route_degraded": ("capacity_contention", "provider_failover"),
    "commercial_loop_blocked": ("business_blocker", "observe_business_blocker"),
    "source_pipeline_degraded": ("data_freshness", "data_refresh"),
    "buyer_review_worker_failed": ("workflow_stall", "queue_recovery"),
    "critical_service_down": ("dependency_failure", "escalate"),
    "critical_timer_down": ("workflow_stall", "escalate"),
}


@dataclass(frozen=True)
class IncidentDiagnosis:
    incident_key: str
    label: str
    playbook: str
    severity: str
    commercial_priority: int
    affected_components: tuple[str, ...]
    evidence_codes: tuple[str, ...]
    escalation_required: bool
    execution_authority: str = "none"

    def __post_init__(self) -> None:
        if self.label not in ALLOWED_LABELS:
            raise ValueError("incident label not allowlisted")
        if self.playbook not in ALLOWED_PLAYBOOKS:
            raise ValueError("incident playbook not allowlisted")
        if self.execution_authority != "none":
            raise ValueError("incident diagnosis cannot grant execution authority")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def correlate_findings(findings: list[Mapping[str, Any]]) -> list[IncidentDiagnosis]:
    unresolved = [
        row for row in findings
        if isinstance(row, Mapping)
        and not bool(row.get("repairable"))
    ]
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in unresolved:
        code = str(row.get("code") or "unknown")
        label, playbook = _CODE_MAP.get(code, ("unknown", "escalate"))
        grouped.setdefault((label, playbook), []).append(row)

    diagnoses: list[IncidentDiagnosis] = []
    for (label, playbook), rows in grouped.items():
        components = tuple(sorted({
            str(row.get("component") or "unknown")
            for row in rows
        }))
        codes = tuple(sorted({
            str(row.get("code") or "unknown")
            for row in rows
        }))
        priority = max(
            max(0, min(100, int(row.get("commercial_priority") or 50)))
            for row in rows
        )
        severities = {str(row.get("severity") or "info") for row in rows}
        severity = (
            "critical" if "critical" in severities
            else "warning" if "warning" in severities
            else "info"
        )
        escalation_required = (
            playbook == "escalate"
            or label == "unknown"
            or severity == "critical"
        )
        key = f"{label}:{'+'.join(components)}"
        diagnoses.append(IncidentDiagnosis(
            incident_key=key,
            label=label,
            playbook=playbook,
            severity=severity,
            commercial_priority=priority,
            affected_components=components,
            evidence_codes=codes,
            escalation_required=escalation_required,
        ))
    return sorted(
        diagnoses,
        key=lambda item: (-item.commercial_priority, item.incident_key),
    )


def build_incident_report(sentinel: Mapping[str, Any]) -> dict[str, Any]:
    findings = sentinel.get("findings") if isinstance(sentinel, Mapping) else []
    findings = findings if isinstance(findings, list) else []
    diagnoses = correlate_findings(findings)
    return {
        "schema_version": "empire.incident_manager.v1",
        "incident_count": len(diagnoses),
        "highest_priority": (
            diagnoses[0].commercial_priority if diagnoses else None
        ),
        "requires_escalation": any(
            item.escalation_required for item in diagnoses
        ),
        "diagnoses": [item.as_dict() for item in diagnoses],
        "controls_execution": False,
        "execution_authority": "none",
        "raw_command_generation": False,
    }
