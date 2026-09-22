#!/usr/bin/env python3
"""Verify Phase 3F production automation without mutating system state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any


SYSTEM_UNITS = (
    "empire-department-cycle.timer",
    "empire-predictive-intelligence.timer",
)

USER_UNITS = (
    "empire-opportunity-loop.timer",
    "empire-predictive-cloud-status.timer",
    "empire-founder-dashboard-api.service",
)

REQUIRED_ARTIFACTS = (
    "runtime/account_twin/account_twin_latest.json",
    "runtime/cortex_learning/cortex_learning_latest.json",
    "runtime/predictive_intelligence/latest.json",
    "runtime/economic_memory/latest.json",
    "runtime/opportunity_factory/value_latest.json",
    "runtime/opportunity_radar/loop_latest.json",
    "runtime/phase_closeout/phase_3f_latest.json",
)


def _run(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode, (result.stdout or "").strip()


def _unit_state(unit: str, *, user: bool) -> dict[str, Any]:
    prefix = ["systemctl"]
    if user:
        prefix.append("--user")

    enabled_rc, enabled = _run(prefix + ["is-enabled", unit])
    active_rc, active = _run(prefix + ["is-active", unit])

    return {
        "unit": unit,
        "scope": "user" if user else "system",
        "enabled": enabled_rc == 0 and enabled == "enabled",
        "enabled_state": enabled or "unknown",
        "active": active_rc == 0 and active == "active",
        "active_state": active or "unknown",
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--user", default="ubuntu")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()

    units = [
        *(_unit_state(unit, user=False) for unit in SYSTEM_UNITS),
        *(_unit_state(unit, user=True) for unit in USER_UNITS),
    ]

    linger_rc, linger_value = _run([
        "loginctl",
        "show-user",
        args.user,
        "-p",
        "Linger",
        "--value",
    ])
    linger_enabled = (
        linger_rc == 0 and linger_value.strip().lower() == "yes"
    )

    artifacts = {
        relative: (root / relative).is_file()
        for relative in REQUIRED_ARTIFACTS
    }

    closeout = _load_json(
        root / "runtime/phase_closeout/phase_3f_latest.json"
    )
    engineering_ready = closeout.get("engineering_ready") is True
    phase_can_advance = closeout.get("phase_can_advance") is True
    truth_contracts_pass = closeout.get("truth_contracts_pass") is True

    system_automation_ready = all(
        row["enabled"] and row["active"]
        for row in units
    )
    artifacts_ready = all(artifacts.values())

    production_ready = all((
        system_automation_ready,
        linger_enabled,
        artifacts_ready,
        engineering_ready,
        phase_can_advance,
        truth_contracts_pass,
    ))

    payload = {
        "schema_version": "empire.phase_3f_production_verification.v1",
        "production_ready": production_ready,
        "automation_ready": system_automation_ready,
        "linger_enabled": linger_enabled,
        "required_artifacts_present": artifacts_ready,
        "engineering_ready": engineering_ready,
        "phase_can_advance": phase_can_advance,
        "truth_contracts_pass": truth_contracts_pass,
        "production_proof_complete": closeout.get(
            "production_proof_complete"
        ) is True,
        "units": units,
        "artifacts": artifacts,
        "carried_forward_dependencies": closeout.get(
            "carried_forward_dependencies"
        ) or [],
        "database_migration_applied_by_verifier": False,
        "external_execution_performed": False,
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
        "execution_authority": "none",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if production_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
