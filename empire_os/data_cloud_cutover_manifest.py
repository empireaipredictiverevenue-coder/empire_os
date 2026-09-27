"""Fail-closed EmpireDB cutover manifest.

Aggregates already-produced evidence only. It never mutates infrastructure,
changes EMPIRE_DATA_BACKEND, infers founder approval, or grants cutover
authority.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path("/srv/empire_os")
HEALTH = ROOT / "runtime/data_cloud/health_latest.json"
ROLLBACK = ROOT / "runtime/data_cloud/rollback_readiness_latest.json"
RUNTIME_CANARY = ROOT / "runtime/data_cloud/runtime_canary_latest.json"
TENANT = ROOT / "runtime/data_cloud/tenant_isolation_latest.json"
RECOVERY = ROOT / "runtime/data_cloud/recovery_proof_latest.json"


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _gate(
    name: str,
    value: bool | None,
    evidence: str,
) -> dict[str, Any]:
    status = "GREEN" if value is True else "OPEN" if value is False else "UNKNOWN"
    return {
        "name": name,
        "status": status,
        "verified": value is True,
        "evidence": evidence,
    }


def build_cutover_manifest(
    *,
    health: Mapping[str, Any],
    rollback: Mapping[str, Any],
    runtime_canary: Mapping[str, Any],
    tenant: Mapping[str, Any],
    recovery: Mapping[str, Any],
    founder_approved: bool = False,
) -> dict[str, Any]:
    backup = health.get("backup")
    backup = backup if isinstance(backup, Mapping) else {}

    gates = [
        _gate(
            "candidate_runtime",
            health.get("candidate_runtime_healthy") is True
            if health else None,
            "runtime/data_cloud/health_latest.json",
        ),
        _gate(
            "local_encrypted_backup",
            (
                backup.get("healthy") is True
                and backup.get("encrypted") is True
            ) if backup else None,
            "runtime/data_cloud/health_latest.json",
        ),
        _gate(
            "off_node_backup",
            backup.get("off_node_repository_verified") is True
            if backup else None,
            "runtime/data_cloud/health_latest.json",
        ),
        _gate(
            "wal_pitr",
            health.get("pitr_verified") is True
            if health else None,
            "runtime/data_cloud/health_latest.json",
        ),
        _gate(
            "rollback",
            rollback.get("rollback_ready") is True
            if rollback else None,
            "runtime/data_cloud/rollback_readiness_latest.json",
        ),
        _gate(
            "runtime_canary",
            runtime_canary.get("verified") is True
            if runtime_canary else None,
            "runtime/data_cloud/runtime_canary_latest.json",
        ),
        _gate(
            "tenant_isolation",
            tenant.get("verified") is True
            if tenant else None,
            "runtime/data_cloud/tenant_isolation_latest.json",
        ),
        _gate(
            "recovery_restore",
            recovery.get("verified") is True
            if recovery else None,
            "runtime/data_cloud/recovery_proof_latest.json",
        ),
    ]

    technical_ready = all(gate["verified"] for gate in gates)
    founder_gate = _gate(
        "founder_cutover_approval",
        True if founder_approved else False,
        "external_explicit_founder_approval",
    )

    return {
        "schema_version": "empire.data-cloud-cutover-manifest.v1",
        "canonical_backend": health.get("canonical_backend") if health else None,
        "technical_gates": gates,
        "technical_ready_for_founder_approval": technical_ready,
        "founder_gate": founder_gate,
        "canonical_cutover_approved": bool(founder_approved),
        "production_cutover_ready": bool(technical_ready and founder_approved),
        "production_cutover_authority": False,
        "authority": {
            "backend_change": False,
            "database_mutation": False,
            "service_restart": False,
            "fund_movement": False,
            "founder_approval_inferred": False,
        },
    }


def main() -> int:
    manifest = build_cutover_manifest(
        health=_read(HEALTH),
        rollback=_read(ROLLBACK),
        runtime_canary=_read(RUNTIME_CANARY),
        tenant=_read(TENANT),
        recovery=_read(RECOVERY),
        founder_approved=False,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["technical_ready_for_founder_approval"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
