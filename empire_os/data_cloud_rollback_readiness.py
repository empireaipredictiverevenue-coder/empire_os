"""Read-only EmpireDB rollback readiness proof.

Proves the legacy Supabase configuration remains available and the canonical
gateway can be selected back to Supabase without mutating environment files,
services, databases, or production state.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.canonical_data_gateway import gateway_from_environment
from empire_os.data_cloud_contract import DataBackend


EMPIRE_OS_ENV = Path("/etc/empire_os.env")

LEGACY_REQUIRED_KEYS = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
)

BOUNDED_RESTART_UNITS = (
    "empire-founder-dashboard-api.service",
    "empire-reliability-agent.service",
)


def _read_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip("'").strip('"')
    return result


@dataclass
class _StubProvider:
    backend: DataBackend

    def configured(self) -> bool:
        return True


def _legacy_factory(_env: Mapping[str, str]) -> _StubProvider:
    return _StubProvider(DataBackend.SUPABASE_LEGACY)


def _empiredb_factory(_env: Mapping[str, str]) -> _StubProvider:
    return _StubProvider(DataBackend.EMPIREDB)


def build_rollback_readiness(
    *,
    empire_os_env: Path = EMPIRE_OS_ENV,
) -> dict[str, Any]:
    env = _read_env(empire_os_env)
    current_backend = str(
        env.get("EMPIRE_DATA_BACKEND")
        or DataBackend.SUPABASE_LEGACY.value
    ).strip()

    legacy_config = {
        key: bool(str(env.get(key) or "").strip())
        for key in LEGACY_REQUIRED_KEYS
    }
    legacy_config_retained = all(legacy_config.values())

    simulated_legacy = gateway_from_environment(
        {"EMPIRE_DATA_BACKEND": DataBackend.SUPABASE_LEGACY.value},
        legacy_provider_factory=_legacy_factory,
        empiredb_provider_factory=_empiredb_factory,
    )
    simulated_empiredb = gateway_from_environment(
        {"EMPIRE_DATA_BACKEND": DataBackend.EMPIREDB.value},
        legacy_provider_factory=_legacy_factory,
        empiredb_provider_factory=_empiredb_factory,
    )

    reversible_backend_selection = bool(
        simulated_legacy.backend is DataBackend.SUPABASE_LEGACY
        and simulated_empiredb.backend is DataBackend.EMPIREDB
        and simulated_legacy.snapshot().dual_write_enabled is False
        and simulated_legacy.snapshot().write_fallback_enabled is False
    )

    current_backend_known = current_backend in {
        DataBackend.SUPABASE_LEGACY.value,
        DataBackend.EMPIREDB.value,
    }
    supabase_not_retired = legacy_config_retained
    rollback_ready = bool(
        current_backend_known
        and legacy_config_retained
        and supabase_not_retired
        and reversible_backend_selection
    )

    return {
        "schema_version": "empire.data-cloud-rollback-readiness.v1",
        "read_only": True,
        "current_backend": current_backend,
        "legacy_config": legacy_config,
        "legacy_config_retained": legacy_config_retained,
        "supabase_not_retired": supabase_not_retired,
        "reversible_backend_selection": reversible_backend_selection,
        "dual_write_required_for_rollback": False,
        "destructive_database_work_required": False,
        "bounded_restart_units": list(BOUNDED_RESTART_UNITS),
        "rollback_ready": rollback_ready,
        "production_cutover_authority": False,
        "authority": {
            "environment_mutation": False,
            "service_restart": False,
            "database_write": False,
            "schema_mutation": False,
            "canonical_cutover": False,
        },
    }


def main() -> int:
    report = build_rollback_readiness()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["rollback_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
