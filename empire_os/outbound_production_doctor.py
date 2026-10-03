"""Single read-only production doctor for the Empire outbound control plane.

Aggregates exact-SHA CI attestation, OBSERVE preflight, local provider-event ingest health,
observer heartbeat, systemd unit health, EmpireDB activation state, and the formal
activation-readiness model. It never applies migrations, changes roles, starts services,
changes DNS, provisions senders, or authorizes outbound.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping

from empire_os.outbound_activation_readiness import evaluate_activation_readiness
from empire_os.outbound_domain_sovereignty import evaluate_domain_sovereignty
from empire_os.outbound_empiredb_activation_probe import (
    EmpireDBActivationProbeError,
    probe_empiredb_deliverability,
)
from empire_os.outbound_observer_heartbeat import (
    DEFAULT_OBSERVER_HEARTBEAT_PATH,
    evaluate_observer_heartbeat,
)
from empire_os.outbound_release_attestation import (
    DEFAULT_RELEASE_ATTESTATION_PATH,
    load_release_attestation,
)
from empire_os.outbound_ringleader_preflight import (
    DEFAULT_CONTEXT_PATH,
    evaluate_preflight,
)
from empire_os.outbound_telemetry_probe import probe_loopback_health


_OBSERVER_SERVICE = "empire-outbound-ringleader-observer.service"
_OBSERVER_TIMER = "empire-outbound-ringleader-observer.timer"
_WATCHDOG_SERVICE = "empire-outbound-ringleader-watchdog.service"
_WATCHDOG_TIMER = "empire-outbound-ringleader-watchdog.timer"
_RESEND_SERVICE = "empire-resend-inbound.service"


def _run(args: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.returncode, completed.stdout.strip()


def _command_value(
    args: list[str],
    *,
    command_runner: Callable[[list[str]], tuple[int, str]],
) -> str:
    rc, output = command_runner(args)
    return output.strip() if rc == 0 else ""


def _systemd_unit(
    unit: str,
    *,
    command_runner: Callable[[list[str]], tuple[int, str]],
) -> dict[str, Any]:
    active = _command_value(
        ["systemctl", "is-active", unit],
        command_runner=command_runner,
    ) or "unknown"
    enabled = _command_value(
        ["systemctl", "is-enabled", unit],
        command_runner=command_runner,
    ) or "unknown"
    result = _command_value(
        ["systemctl", "show", unit, "--property=Result", "--value"],
        command_runner=command_runner,
    ) or "unknown"
    exec_status_raw = _command_value(
        ["systemctl", "show", unit, "--property=ExecMainStatus", "--value"],
        command_runner=command_runner,
    )
    try:
        exec_status = int(exec_status_raw)
    except (TypeError, ValueError):
        exec_status = None

    failed = (
        active == "failed"
        or result == "failed"
        or (exec_status is not None and exec_status != 0)
    )
    # Timer-driven Type=oneshot services are normally inactive after a
    # successful run. Healthy therefore means not failed and either a
    # successful recorded result or a currently active unit.
    healthy = (
        not failed
        and (
            active == "active"
            or result == "success"
        )
    )
    return {
        "unit": unit,
        "active_state": active,
        "enabled_state": enabled,
        "result": result,
        "exec_main_status": exec_status,
        "active": active == "active",
        "enabled": enabled in {"enabled", "static"},
        "healthy": healthy,
    }


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, PermissionError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def collect_production_readiness(
    env: Mapping[str, str] | None = None,
    *,
    now: datetime | None = None,
    expected_sha: str | None = None,
    command_runner: Callable[[list[str]], tuple[int, str]] | None = None,
    provider_probe: Callable[..., Mapping[str, Any]] | None = None,
    empiredb_probe: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    environment = dict(os.environ if env is None else env)
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    runner = command_runner or _run
    probe_provider = provider_probe or probe_loopback_health
    probe_db = empiredb_probe or probe_empiredb_deliverability

    deployed_sha = str(expected_sha or "").strip()
    if not deployed_sha:
        deployed_sha = _command_value(
            ["git", "rev-parse", "HEAD"],
            command_runner=runner,
        )

    release_path = Path(
        environment.get(
            "EMPIRE_OUTBOUND_RELEASE_ATTESTATION_PATH",
            str(DEFAULT_RELEASE_ATTESTATION_PATH),
        )
    )
    release = load_release_attestation(
        path=release_path,
        expected_sha=deployed_sha,
        now=timestamp,
        max_age_hours=int(
            environment.get(
                "EMPIRE_OUTBOUND_RELEASE_ATTESTATION_MAX_AGE_HOURS",
                "168",
            )
        ),
    )

    context_path = Path(
        environment.get(
            "EMPIRE_OUTBOUND_RINGLEADER_CONTEXT_PATH",
            str(DEFAULT_CONTEXT_PATH),
        )
    )
    context = _load_json_object(context_path)

    try:
        preflight = evaluate_preflight(
            environment,
            context_path=context_path,
        )
    except Exception as exc:
        preflight = {
            "status": "BLOCKED",
            "mode": str(
                environment.get(
                    "EMPIRE_OUTBOUND_RINGLEADER_MODE",
                    "OBSERVE",
                )
            ).upper(),
            "persistence_required": (
                str(
                    environment.get(
                        "EMPIRE_OUTBOUND_REQUIRE_PERSISTENCE",
                        "",
                    )
                ).lower()
                in {"1", "true", "yes", "on"}
            ),
            "signed_evidence_required": False,
            "evidence_signature_status": None,
            "blockers": [
                "preflight_exception:" + type(exc).__name__
            ],
            "warnings": [],
            "activation_authorized": False,
        }

    provider_ingest = dict(
        probe_provider(
            "provider_event_ingest",
            "http://127.0.0.1:8097/health",
            now=timestamp,
        )
    )

    heartbeat_path = Path(
        environment.get(
            "EMPIRE_OUTBOUND_OBSERVER_HEARTBEAT_PATH",
            str(DEFAULT_OBSERVER_HEARTBEAT_PATH),
        )
    )
    heartbeat = evaluate_observer_heartbeat(
        path=heartbeat_path,
        now=timestamp,
        max_age_minutes=int(
            environment.get(
                "EMPIRE_OUTBOUND_OBSERVER_MAX_AGE_MINUTES",
                "15",
            )
        ),
    )

    units = {
        unit: _systemd_unit(unit, command_runner=runner)
        for unit in (
            _RESEND_SERVICE,
            _OBSERVER_SERVICE,
            _OBSERVER_TIMER,
            _WATCHDOG_SERVICE,
            _WATCHDOG_TIMER,
        )
    }

    probe_dsn = (
        str(
            environment.get(
                "EMPIRE_OUTBOUND_ACTIVATION_PROBE_DSN",
                "",
            )
        ).strip()
        or str(environment.get("EMPIREDB_MIGRATOR_DSN", "")).strip()
    )
    if probe_dsn:
        try:
            empiredb = dict(probe_db(probe_dsn))
        except EmpireDBActivationProbeError as exc:
            empiredb = {
                "status": "BLOCKED",
                "schema_ready": False,
                "roles_ready": False,
                "privileges_ready": False,
                "error": str(exc),
                "mutation_authorized": False,
            }
        except Exception as exc:
            empiredb = {
                "status": "BLOCKED",
                "schema_ready": False,
                "roles_ready": False,
                "privileges_ready": False,
                "error": type(exc).__name__,
                "mutation_authorized": False,
            }
    else:
        empiredb = {
            "status": "UNCONFIGURED",
            "schema_ready": False,
            "roles_ready": False,
            "privileges_ready": False,
            "mutation_authorized": False,
        }

    auth = dict(context.get("authentication") or {})
    auth_ready = all(
        auth.get(key) is True
        for key in (
            "spf_aligned",
            "dkim_aligned",
            "dmarc_valid",
            "tls_ready",
        )
    )
    sovereignty = evaluate_domain_sovereignty(
        context.get("domain_sovereignty")
    )
    provider_policy_verified = (
        context.get("provider_policy_permits_use_case") is True
    )

    signed_required = (
        preflight.get("signed_evidence_required") is True
    )
    signature_status = str(
        preflight.get("evidence_signature_status") or ""
    ).upper()
    signed_verified = signature_status == "VERIFIED"

    readiness_evidence = {
        "targeted_ci_green": release.get("status") == "CURRENT",
        "observer_preflight_ready": preflight.get("status") == "READY",
        "observer_mode": preflight.get("mode"),
        "telemetry_available": bool(
            environment.get("RESEND_API_KEY")
            and provider_ingest.get("success") is True
        ),
        "provider_policy_verified": provider_policy_verified,
        "domain_sovereignty_ready": sovereignty.get("status") == "READY",
        "authentication_ready": auth_ready,
        "persistence_required": (
            preflight.get("persistence_required") is True
        ),
        "empiredb_migrations_applied": empiredb.get("schema_ready") is True,
        "empiredb_roles_bound": bool(
            empiredb.get("roles_ready") is True
            and empiredb.get("privileges_ready") is True
        ),
        "signed_evidence_required": signed_required,
        "signed_evidence_verified": signed_verified,
        "observer_service_healthy": units[_OBSERVER_SERVICE]["healthy"],
        "observer_timer_active": units[_OBSERVER_TIMER]["active"],
        "observer_watchdog_healthy": units[_WATCHDOG_SERVICE]["healthy"],
        "observer_watchdog_timer_active": units[_WATCHDOG_TIMER]["active"],
        "observer_heartbeat_status": heartbeat.get("status"),
        "telemetry_sla_posture": heartbeat.get("telemetry_posture"),
        "provider_event_ingest_ready": (
            provider_ingest.get("success") is True
            and provider_ingest.get("coverage") is True
            and units[_RESEND_SERVICE]["active"]
        ),
        # Live-send evidence is deliberately not inferred by this production
        # doctor. Those gates remain false unless a later exact-batch gate
        # supplies canonical evidence explicitly.
        "outbound_governor_live_ready": False,
        "recipient_verification_ready": False,
        "suppression_ready": False,
        "seed_placement_measured": False,
        "sender_pool_ready": False,
        "transport_policy_compatible": False,
        "capacity_reservation_ready": False,
        "claim_evidence_ready": False,
        "account_saturation_ready": False,
        "source_reputation_ready": False,
        "content_family_reputation_ready": False,
        "fleet_readiness_status": "UNKNOWN",
        "founder_live_send_approved": False,
        "exact_batch_approval_bound": False,
    }
    activation = evaluate_activation_readiness(readiness_evidence)

    return {
        "status": (
            "READY"
            if activation["operational_observe"]["status"] == "READY"
            else "BLOCKED"
        ),
        "observed_at": timestamp.isoformat(),
        "deployed_sha": deployed_sha or None,
        "release_attestation": release,
        "preflight": preflight,
        "provider_event_ingest": provider_ingest,
        "observer_heartbeat": heartbeat,
        "systemd": units,
        "empiredb": empiredb,
        "domain_sovereignty": sovereignty,
        "authentication_ready": auth_ready,
        "provider_policy_verified": provider_policy_verified,
        "activation_readiness": activation,
        "database_activation_authorized": False,
        "service_activation_authorized": False,
        "dns_mutation_authorized": False,
        "provisioning_authorized": False,
        "send_authorized": False,
    }


def main() -> int:
    result = collect_production_readiness()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
