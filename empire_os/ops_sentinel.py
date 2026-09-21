"""Canonical EmpireOS operations sentinel and bounded healing planner.

Reads current service/runtime evidence, diagnoses failures and emits only
allowlisted reversible repair actions. It does not move funds, accept terms,
recognize revenue, alter schemas, delete data or widen authority.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


ROOT = Path("/srv/empire_os")
RUNTIME = ROOT / "runtime"

CRITICAL_SERVICES = (
    "empire-autonomous-execution.service",
    "empire-public-gateway.service",
    "empire-ops-mcp.service",
    "empire-cloudflared.service",
)
CRITICAL_TIMERS = (
    "empire-acquisition.timer",
    "empire-qualification.timer",
)
REPAIRABLE_UNITS = frozenset((*CRITICAL_SERVICES, *CRITICAL_TIMERS))

RUNTIME_INPUTS = {
    "source_health": RUNTIME / "source_health/latest.json",
    "commercial_loop": RUNTIME / "commercial_loop/latest.json",
    "model_health": RUNTIME / "llm/model_health.json",
    "acquisition": RUNTIME / "acquisition/latest.json",
    "buyer_review": RUNTIME / "buyer_review_materializer/latest.json",
    "coder_model_health": RUNTIME / "coder/model_health.json",
}


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    component: str
    summary: str
    repairable: bool
    commercial_priority: int
    evidence: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _commercial_blocker(loop: Mapping[str, Any]) -> str:
    direct = str(
        loop.get("highest_priority_blocker")
        or loop.get("highest_blocker")
        or loop.get("blocker")
        or ""
    ).strip()
    if direct:
        return direct
    for row in loop.get("stages") or []:
        if isinstance(row, Mapping) and row.get("observed") is False:
            stage = str(row.get("stage") or "").strip()
            if stage:
                return stage
    return "unknown"


def analyze(
    *,
    unit_states: Mapping[str, str],
    runtime: Mapping[str, Mapping[str, Any]],
) -> list[Finding]:
    findings: list[Finding] = []

    for unit in CRITICAL_SERVICES:
        state = str(unit_states.get(unit) or "unknown")
        if state != "active":
            findings.append(Finding(
                "critical_service_down", "critical", unit,
                f"{unit} is {state}, expected active",
                unit in REPAIRABLE_UNITS, 100, {"state": state},
            ))

    for unit in CRITICAL_TIMERS:
        state = str(unit_states.get(unit) or "unknown")
        if state != "active":
            findings.append(Finding(
                "critical_timer_down", "warning", unit,
                f"{unit} is {state}, expected active",
                unit in REPAIRABLE_UNITS, 85, {"state": state},
            ))

    source = runtime.get("source_health") or {}
    if source and source.get("end_to_end_healthy") is not True:
        findings.append(Finding(
            "source_pipeline_degraded", "warning", "source_health",
            "Acquisition source pipeline is not end-to-end healthy",
            True, 90, {"end_to_end_healthy": source.get("end_to_end_healthy")},
        ))

    loop = runtime.get("commercial_loop") or {}
    if loop and loop.get("loop_complete") is not True:
        blocker = _commercial_blocker(loop)
        findings.append(Finding(
            "commercial_loop_blocked", "info", "commercial_loop",
            f"Commercial loop remains incomplete; blocker={blocker}",
            False, 95, {
                "highest_blocker": blocker,
                "execution_authority": loop.get("execution_authority"),
            },
        ))

    model = runtime.get("model_health") or {}
    if model:
        degraded = bool(model.get("degraded")) or str(model.get("status") or "").lower() in {
            "degraded", "error", "failed"
        }
        if degraded:
            findings.append(Finding(
                "model_provider_degraded", "warning", "model_health",
                "Model/provider health is degraded",
                False, 70, {"status": model.get("status")},
            ))

    buyer = runtime.get("buyer_review") or {}
    if buyer and buyer.get("ok") is False:
        findings.append(Finding(
            "buyer_review_worker_failed", "warning", "buyer_review",
            "Latest buyer-review materializer cycle reported failure",
            True, 92, {"errors": buyer.get("errors") or []},
        ))

    coder_health = runtime.get("coder_model_health") or {}
    routes = coder_health.get("routes") if isinstance(coder_health, Mapping) else {}
    degraded_routes = [
        key for key, row in (routes or {}).items()
        if isinstance(row, Mapping) and row.get("status") == "cooldown"
    ]
    if degraded_routes:
        findings.append(Finding(
            "coder_model_route_degraded", "warning", "empire_coder",
            f"{len(degraded_routes)} Coder model route(s) are cooling down; failover is active",
            False, 75, {"routes": degraded_routes},
        ))

    return sorted(
        findings,
        key=lambda item: (
            -item.commercial_priority,
            {"critical": 0, "warning": 1, "info": 2}.get(item.severity, 3),
        ),
    )


def build_repair_plan(findings: list[Finding]) -> list[dict[str, Any]]:
    """Safe repair proposals only; executor remains separately governed."""
    actions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for finding in findings:
        if not finding.repairable:
            continue
        if finding.code in {"critical_service_down", "critical_timer_down"}:
            unit = finding.component
            key = f"restart:{unit}"
            if unit in REPAIRABLE_UNITS and key not in seen:
                actions.append({
                    "action": "restart_unit",
                    "target": unit,
                    "authority": "internal_write",
                    "reason": finding.code,
                    "commercial_priority": finding.commercial_priority,
                })
                seen.add(key)
        elif finding.code == "source_pipeline_degraded":
            key = "run:source_health_refresh"
            if key not in seen:
                actions.append({
                    "action": "run_safe_job",
                    "target": "source_health_refresh",
                    "authority": "internal_write",
                    "reason": finding.code,
                    "commercial_priority": finding.commercial_priority,
                })
                seen.add(key)
        elif finding.code == "buyer_review_worker_failed":
            key = "run:buyer_review_materializer"
            if key not in seen:
                actions.append({
                    "action": "run_safe_job",
                    "target": "buyer_review_materializer",
                    "authority": "internal_write",
                    "reason": finding.code,
                    "commercial_priority": finding.commercial_priority,
                })
                seen.add(key)
    return actions


def observe(unit_reader: Callable[[str], str]) -> dict[str, Any]:
    units = {unit: unit_reader(unit) for unit in (*CRITICAL_SERVICES, *CRITICAL_TIMERS)}
    runtime = {name: _read_json(path) for name, path in RUNTIME_INPUTS.items()}
    findings = analyze(unit_states=units, runtime=runtime)
    repairs = build_repair_plan(findings)
    return {
        "schema_version": "empire.ops_sentinel.v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "units": units,
        "findings": [item.as_dict() for item in findings],
        "repair_plan": repairs,
        "safe_auto_repair_count": len(repairs),
        "prohibited": [
            "fund_movement",
            "payment_confirmation",
            "revenue_recognition",
            "commercial_terms_acceptance",
            "schema_or_data_destruction",
            "authority_expansion",
        ],
    }
