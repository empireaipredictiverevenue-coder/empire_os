"""Phase 4 Astra runtime activation preflight.

This module intentionally never emits secret values.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


POLICY_KEYS = (
    "EMPIRE_ASTRA_PREMIUM_AI_BUDGET_CENTS",
    "EMPIRE_ASTRA_OUTBOUND_DOMAIN_VERIFIED",
)


@dataclass(frozen=True)
class AstraRuntimePreflight:
    env_file_exists: bool
    env_permissions_secure: bool
    observe_mode_configured: bool
    observer_dsn_configured: bool
    observer_token_rpc_configured: bool
    observer_token_file_exists: bool
    observer_token_permissions_secure: bool
    observer_transport_configured: bool
    policy_bindings_complete: bool
    service_installed: bool
    timer_installed: bool
    timer_enabled: bool
    cron_scheduler_enabled: bool
    scheduler_ready: bool
    runtime_ready: bool
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_env_file(path: str | Path) -> dict[str, str]:
    env_path = Path(path)
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def env_permissions_secure(path: str | Path) -> bool:
    env_path = Path(path)
    if not env_path.exists():
        return False
    return (env_path.stat().st_mode & 0o077) == 0


def assess_runtime_preflight(
    *,
    env_path: str | Path,
    service_installed: bool,
    timer_installed: bool,
    timer_enabled: bool,
    cron_scheduler_enabled: bool = False,
    environ: Mapping[str, str] | None = None,
) -> AstraRuntimePreflight:
    env_file = Path(env_path)
    values = dict(environ) if environ is not None else parse_env_file(env_file)
    exists = env_file.exists()
    secure = env_permissions_secure(env_file) if exists else False
    mode_ok = str(values.get("EMPIRE_ASTRA_MODE", "")).strip().upper() == "OBSERVE"
    dsn_ok = bool(str(values.get("EMPIRE_ASTRA_OBSERVER_DSN", "")).strip())
    token_file_raw = str(values.get("EMPIRE_ASTRA_OBSERVER_TOKEN_FILE", "")).strip()
    token_file = Path(token_file_raw) if token_file_raw else None
    token_file_exists = bool(token_file and token_file.is_file())
    token_file_secure = bool(
        token_file_exists and (token_file.stat().st_mode & 0o077) == 0
    )
    token_rpc_configured = all(bool(str(values.get(key, "")).strip()) for key in (
        "EMPIRE_ASTRA_SUPABASE_URL",
        "EMPIRE_ASTRA_SUPABASE_PUBLISHABLE_KEY",
        "EMPIRE_ASTRA_OBSERVER_TOKEN_FILE",
    ))
    token_rpc_ok = token_rpc_configured and token_file_exists and token_file_secure
    transport_ok = dsn_ok or token_rpc_ok
    source_health_static = bool(
        str(values.get("EMPIRE_ASTRA_SOURCE_HEALTH_OK", "")).strip()
    )
    source_health_file_raw = str(
        values.get("EMPIRE_ASTRA_SOURCE_HEALTH_FILE", "")
    ).strip()
    source_health_file_exists = bool(
        source_health_file_raw and Path(source_health_file_raw).is_file()
    )
    source_health_binding_ok = (
        source_health_static
        or source_health_file_exists
    )
    policy_ok = (
        all(bool(str(values.get(key, "")).strip()) for key in POLICY_KEYS)
        and source_health_binding_ok
    )
    systemd_ready = service_installed and timer_installed and timer_enabled
    scheduler_ready = systemd_ready or cron_scheduler_enabled

    blockers: list[str] = []
    if not exists:
        blockers.append("observer_env_file_missing")
    elif not secure:
        blockers.append("observer_env_permissions_insecure")
    if not mode_ok:
        blockers.append("observe_mode_not_configured")
    if token_rpc_configured and not token_file_exists:
        blockers.append("observer_token_file_missing")
    elif token_rpc_configured and not token_file_secure:
        blockers.append("observer_token_permissions_insecure")
    if not transport_ok:
        blockers.append("observer_transport_not_configured")
    if source_health_file_raw and not source_health_file_exists:
        blockers.append("source_health_file_missing")
    if not policy_ok:
        blockers.append("policy_bindings_incomplete")
    if not scheduler_ready:
        if not service_installed:
            blockers.append("observer_service_not_installed")
        if not timer_installed:
            blockers.append("observer_timer_not_installed")
        if not timer_enabled:
            blockers.append("observer_timer_not_enabled")
        blockers.append("observer_scheduler_not_enabled")

    ordered = tuple(sorted(set(blockers)))
    return AstraRuntimePreflight(
        env_file_exists=exists,
        env_permissions_secure=secure,
        observe_mode_configured=mode_ok,
        observer_dsn_configured=dsn_ok,
        observer_token_rpc_configured=token_rpc_configured,
        observer_token_file_exists=token_file_exists,
        observer_token_permissions_secure=token_file_secure,
        observer_transport_configured=transport_ok,
        policy_bindings_complete=policy_ok,
        service_installed=service_installed,
        timer_installed=timer_installed,
        timer_enabled=timer_enabled,
        cron_scheduler_enabled=cron_scheduler_enabled,
        scheduler_ready=scheduler_ready,
        runtime_ready=not ordered,
        blockers=ordered,
    )
