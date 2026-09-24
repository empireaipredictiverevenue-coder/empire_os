"""EmpireOS deterministic runtime self-healing controller.

This controller repairs only bounded, reversible operational faults. It never
sends outbound, changes commercial truth, moves funds, applies database schema
changes, recognizes revenue, or expands its own authority.

The controller is intentionally boring: observe -> classify -> bounded repair ->
verify -> persist evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable, Mapping
import urllib.error
import urllib.request

from empire_os.ops_privileged_client import (
    PrivilegedHelperUnavailable,
    privileged_request,
)


ROOT = Path("/srv/empire_os")
LATEST_PATH = ROOT / "runtime" / "self_heal" / "latest.json"
STATE_PATH = ROOT / "runtime" / "self_heal" / "state.json"
DEFAULT_REPAIR_COOLDOWN_SECONDS = 300
DEFAULT_MAX_REPAIRS_PER_RUN = 5


@dataclass(frozen=True)
class ServiceSpec:
    key: str
    unit: str
    repair_action: str = "service_restart"
    auto_repair: bool = True


@dataclass(frozen=True)
class SnapshotSpec:
    key: str
    path: str
    max_age_seconds: int
    repair_unit: str
    repair_action: str = "service_start"


@dataclass(frozen=True)
class HttpSpec:
    key: str
    url: str
    repair_unit: str
    expected_status: int = 200


AUTO_REPAIR_SERVICES: tuple[ServiceSpec, ...] = (
    ServiceSpec("public_gateway", "empire-public-gateway.service"),
    ServiceSpec("self_serve_checkout", "empire-self-serve-checkout.service"),
    ServiceSpec("ops_mcp", "empire-ops-mcp.service"),
)

AUTO_REPAIR_TIMERS: tuple[ServiceSpec, ...] = (
    ServiceSpec("commercial_catalog_timer", "empire-commercial-product-catalog.timer"),
    ServiceSpec("commercial_exchange_timer", "empire-commercial-exchange.timer"),
    ServiceSpec("buyer_acquisition_timer", "empire-buyer-acquisition-team.timer"),
    ServiceSpec("source_health_timer", "empire-source-health.timer"),
    ServiceSpec("revenue_pulse_timer", "empire-revenue-pulse.timer"),
    ServiceSpec("acquisition_timer", "empire-acquisition.timer"),
    ServiceSpec("qualification_timer", "empire-qualification.timer"),
    ServiceSpec("hermes_control_timer", "empire-hermes-control.timer"),
    ServiceSpec(
        "buyer_deferred_enrichment_timer",
        "empire-buyer-deferred-enrichment.timer",
    ),
    ServiceSpec(
        "enterprise_contact_intelligence_timer",
        "empire-predictive-revenue-enterprise-activation.timer",
    ),
    ServiceSpec(
        "enterprise_contact_repair_timer",
        "empire-enterprise-contact-repair.timer",
    ),
)

SNAPSHOTS: tuple[SnapshotSpec, ...] = (
    SnapshotSpec(
        "commercial_catalog",
        "/srv/empire_os/runtime/commercial_catalog/latest.json",
        900,
        "empire-commercial-product-catalog.service",
    ),
    SnapshotSpec(
        "commercial_exchange",
        "/srv/empire_os/runtime/commercial_exchange/latest.json",
        900,
        "empire-commercial-exchange.service",
    ),
    SnapshotSpec(
        "buyer_acquisition",
        "/srv/empire_os/runtime/buyer_acquisition/latest.json",
        900,
        "empire-buyer-acquisition-team.service",
    ),
    SnapshotSpec(
        "revenue_pulse",
        "/srv/empire_os/runtime/revenue_pulse/latest.json",
        900,
        "empire-revenue-pulse.service",
    ),
    SnapshotSpec(
        "source_health",
        "/srv/empire_os/runtime/source_health/latest.json",
        1800,
        "empire-source-health.service",
    ),
    SnapshotSpec(
        "enterprise_contact_intelligence",
        "/srv/empire_os/runtime/predictive_revenue/"
        "enterprise_contact_intelligence_latest.json",
        108000,
        "empire-enterprise-contact-sync.service",
    ),
    SnapshotSpec(
        "enterprise_contact_repair",
        "/srv/empire_os/runtime/predictive_revenue/"
        "enterprise_contact_repair_latest.json",
        1800,
        "empire-enterprise-contact-repair.service",
    ),
)

HTTP_CHECKS: tuple[HttpSpec, ...] = (
    HttpSpec(
        "public_gateway_http",
        "http://127.0.0.1/health",
        "empire-public-gateway.service",
    ),
    HttpSpec(
        "self_serve_checkout_http",
        "http://127.0.0.1:8098/health",
        "empire-self-serve-checkout.service",
    ),
)

# These may be observed elsewhere, but this controller will never repair or
# start them because doing so could cause an external or commercial action.
FOUNDER_GATE_UNIT_PREFIXES: tuple[str, ...] = (
    "empire-outbound-",
    "empire-outreach-",
    "empire-voice-outbound",
    "empire-closer-reply",
    "empire-call-manager",
    "empire-payment",
    "empire-settlement",
    "empire-settle-",
    "empire-revenue-recognition",
    "empire-ppc-billing",
    "empire-marketing-deploy",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def classify_unit_policy(unit: str) -> str:
    text = str(unit or "").strip()
    if any(text.startswith(prefix) for prefix in FOUNDER_GATE_UNIT_PREFIXES):
        return "FOUNDER_GATE"
    if unit_is_auto_repairable(text):
        return "AUTO_REPAIR"
    return "OBSERVE_ONLY"


def _discover_empire_units() -> list[dict[str, Any]]:
    """Inventory installed Empire system units with one bounded systemd scan."""
    files = subprocess.run(
        [
            "systemctl",
            "list-unit-files",
            "empire-*",
            "--no-legend",
            "--no-pager",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    active = subprocess.run(
        [
            "systemctl",
            "list-units",
            "--all",
            "empire-*",
            "--no-legend",
            "--no-pager",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    active_map: dict[str, dict[str, str]] = {}
    for raw in (active.stdout or "").splitlines():
        parts = raw.split(None, 4)
        if len(parts) < 4:
            continue
        unit, load_state, active_state, sub_state = parts[:4]
        active_map[unit] = {
            "load_state": load_state,
            "active_state": active_state,
            "sub_state": sub_state,
        }

    rows: list[dict[str, Any]] = []
    for raw in (files.stdout or "").splitlines():
        parts = raw.split()
        if len(parts) < 2:
            continue
        unit, unit_file_state = parts[:2]
        runtime = active_map.get(unit, {})
        rows.append({
            "unit": unit,
            "unit_file_state": unit_file_state,
            "load_state": runtime.get("load_state", "unknown"),
            "active_state": runtime.get("active_state", "inactive"),
            "sub_state": runtime.get("sub_state", "unknown"),
            "policy": classify_unit_policy(unit),
        })
    rows.sort(key=lambda row: str(row["unit"]))
    return rows


def unit_is_auto_repairable(unit: str) -> bool:
    text = str(unit or "").strip()
    if any(text.startswith(prefix) for prefix in FOUNDER_GATE_UNIT_PREFIXES):
        return False
    allowed = {
        spec.unit for spec in AUTO_REPAIR_SERVICES + AUTO_REPAIR_TIMERS
    } | {spec.repair_unit for spec in SNAPSHOTS}
    return text in allowed


def _systemctl_active(unit: str) -> tuple[bool, str]:
    completed = subprocess.run(
        ["systemctl", "is-active", unit],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    state = (completed.stdout or completed.stderr or "").strip() or "unknown"
    return completed.returncode == 0 and state == "active", state


def _http_ok(url: str, expected_status: int = 200) -> tuple[bool, str]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status == expected_status, f"http_{response.status}"
    except urllib.error.HTTPError as exc:
        return False, f"http_{exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"{type(exc).__name__}"


def _snapshot_health(
    spec: SnapshotSpec,
    *,
    now: datetime,
) -> dict[str, Any]:
    path = Path(spec.path)
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {
            "key": spec.key,
            "path": spec.path,
            "healthy": False,
            "reason": "missing",
            "age_seconds": None,
            "readable": False,
            "json_valid": False,
        }
    except PermissionError:
        return {
            "key": spec.key,
            "path": spec.path,
            "healthy": False,
            "reason": "permission_denied",
            "age_seconds": None,
            "readable": False,
            "json_valid": False,
        }

    age = max(0.0, now.timestamp() - stat.st_mtime)
    try:
        raw = path.read_text(encoding="utf-8")
    except PermissionError:
        return {
            "key": spec.key,
            "path": spec.path,
            "healthy": False,
            "reason": "permission_denied",
            "age_seconds": round(age, 1),
            "readable": False,
            "json_valid": False,
        }
    except OSError as exc:
        return {
            "key": spec.key,
            "path": spec.path,
            "healthy": False,
            "reason": f"read_error:{type(exc).__name__}",
            "age_seconds": round(age, 1),
            "readable": False,
            "json_valid": False,
        }

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "key": spec.key,
            "path": spec.path,
            "healthy": False,
            "reason": "invalid_json",
            "age_seconds": round(age, 1),
            "readable": True,
            "json_valid": False,
        }

    if not isinstance(payload, Mapping):
        return {
            "key": spec.key,
            "path": spec.path,
            "healthy": False,
            "reason": "invalid_root_type",
            "age_seconds": round(age, 1),
            "readable": True,
            "json_valid": True,
        }

    stale = age > spec.max_age_seconds
    return {
        "key": spec.key,
        "path": spec.path,
        "healthy": not stale,
        "reason": "stale" if stale else "ok",
        "age_seconds": round(age, 1),
        "max_age_seconds": spec.max_age_seconds,
        "readable": True,
        "json_valid": True,
    }


def _load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"last_repairs": {}}
    if not isinstance(value, dict):
        return {"last_repairs": {}}
    repairs = value.get("last_repairs")
    if not isinstance(repairs, dict):
        value["last_repairs"] = {}
    return value


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o640)
    tmp.replace(path)
    os.chmod(path, 0o640)


def _repair_on_cooldown(
    key: str,
    state: Mapping[str, Any],
    *,
    now: datetime,
    cooldown_seconds: int,
) -> bool:
    last_repairs = state.get("last_repairs")
    if not isinstance(last_repairs, Mapping):
        return False
    raw = last_repairs.get(key)
    if not raw:
        return False
    try:
        when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (now - when.astimezone(timezone.utc)).total_seconds() < cooldown_seconds


def _record_repair(state: dict[str, Any], key: str, now: datetime) -> None:
    repairs = state.setdefault("last_repairs", {})
    repairs[key] = _iso(now)


def _attempt_repair(
    *,
    key: str,
    unit: str,
    action: str,
    state: dict[str, Any],
    now: datetime,
    repair: Callable[[str, str], Mapping[str, Any]],
    cooldown_seconds: int,
    observe_only: bool,
) -> dict[str, Any]:
    if not unit_is_auto_repairable(unit):
        return {
            "key": key,
            "unit": unit,
            "decision": "FOUNDER_GATE",
            "executed": False,
            "ok": False,
            "reason": "unit_not_auto_repairable",
        }
    if observe_only:
        return {
            "key": key,
            "unit": unit,
            "decision": "WOULD_AUTO_REPAIR",
            "executed": False,
            "ok": True,
        }
    if _repair_on_cooldown(
        key,
        state,
        now=now,
        cooldown_seconds=cooldown_seconds,
    ):
        return {
            "key": key,
            "unit": unit,
            "decision": "COOLDOWN",
            "executed": False,
            "ok": False,
        }

    try:
        result = dict(repair(action, unit))
    except (PrivilegedHelperUnavailable, ValueError, OSError) as exc:
        return {
            "key": key,
            "unit": unit,
            "decision": "REPAIR_FAILED",
            "executed": False,
            "ok": False,
            "reason": f"{type(exc).__name__}:{str(exc)[:240]}",
        }
    _record_repair(state, key, now)
    return {
        "key": key,
        "unit": unit,
        "decision": "AUTO_REPAIR",
        "executed": True,
        "ok": result.get("ok") is True,
        "helper_result": result,
    }


def run_runtime_self_heal(
    *,
    now: datetime | None = None,
    observe_only: bool = True,
    cooldown_seconds: int = DEFAULT_REPAIR_COOLDOWN_SECONDS,
    max_repairs_per_run: int = DEFAULT_MAX_REPAIRS_PER_RUN,
    service_status: Callable[[str], tuple[bool, str]] = _systemctl_active,
    http_check: Callable[[str, int], tuple[bool, str]] = _http_ok,
    repair: Callable[[str, str], Mapping[str, Any]] = privileged_request,
    unit_inventory: Callable[[], list[dict[str, Any]]] = _discover_empire_units,
    latest_path: Path = LATEST_PATH,
    state_path: Path = STATE_PATH,
) -> dict[str, Any]:
    current = (now or _utc_now()).astimezone(timezone.utc)
    mode = str(os.getenv("EMPIRE_AUTONOMOUS_MODE", "OBSERVE")).strip().upper()
    if mode != "OBSERVE":
        observe_only = True

    state = _load_state(state_path)
    try:
        inventory = unit_inventory()
    except (OSError, subprocess.SubprocessError) as exc:
        inventory = [{
            "unit": "systemd_inventory",
            "unit_file_state": "unknown",
            "load_state": "unknown",
            "active_state": "unknown",
            "sub_state": type(exc).__name__,
            "policy": "OBSERVE_ONLY",
        }]
    installed_units = {
        str(row.get("unit") or "")
        for row in inventory
        if str(row.get("unit") or "")
    }
    policy_counts: dict[str, int] = {}
    for row in inventory:
        policy = str(row.get("policy") or "OBSERVE_ONLY")
        policy_counts[policy] = policy_counts.get(policy, 0) + 1

    explicitly_checked_units = {
        spec.unit for spec in AUTO_REPAIR_SERVICES + AUTO_REPAIR_TIMERS
    }
    inventory_findings: list[dict[str, Any]] = []
    for row in inventory:
        unit = str(row.get("unit") or "")
        if not unit.endswith(".timer") or unit in explicitly_checked_units:
            continue
        file_state = str(row.get("unit_file_state") or "")
        active_state = str(row.get("active_state") or "")
        if file_state.startswith("enabled") and active_state != "active":
            inventory_findings.append({
                "code": "enabled_timer_inactive",
                "unit": unit,
                "policy": row.get("policy") or "OBSERVE_ONLY",
                "unit_file_state": file_state,
                "active_state": active_state,
                "repair_executed": False,
            })

    checks: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    repair_count = 0

    def maybe_repair(key: str, unit: str, action: str) -> dict[str, Any]:
        nonlocal repair_count
        if repair_count >= max_repairs_per_run:
            result = {
                "key": key,
                "unit": unit,
                "decision": "REPAIR_BUDGET_EXHAUSTED",
                "executed": False,
                "ok": False,
            }
            repairs.append(result)
            return result
        result = _attempt_repair(
            key=key,
            unit=unit,
            action=action,
            state=state,
            now=current,
            repair=repair,
            cooldown_seconds=cooldown_seconds,
            observe_only=observe_only,
        )
        if result.get("executed") is True:
            repair_count += 1
        repairs.append(result)
        return result

    for spec in AUTO_REPAIR_SERVICES:
        if installed_units and spec.unit not in installed_units:
            continue
        healthy, detail = service_status(spec.unit)
        row = {
            "kind": "service",
            "key": spec.key,
            "unit": spec.unit,
            "healthy": healthy,
            "detail": detail,
        }
        if not healthy:
            row["repair"] = maybe_repair(
                f"service:{spec.unit}",
                spec.unit,
                spec.repair_action,
            )
            if row["repair"].get("executed") is True and row["repair"].get("ok") is True:
                after_ok, after_detail = service_status(spec.unit)
                row["after_repair"] = {
                    "healthy": after_ok,
                    "detail": after_detail,
                }
        checks.append(row)

    for spec in AUTO_REPAIR_TIMERS:
        if installed_units and spec.unit not in installed_units:
            continue
        healthy, detail = service_status(spec.unit)
        row = {
            "kind": "timer",
            "key": spec.key,
            "unit": spec.unit,
            "healthy": healthy,
            "detail": detail,
        }
        if not healthy:
            row["repair"] = maybe_repair(
                f"timer:{spec.unit}",
                spec.unit,
                spec.repair_action,
            )
            if row["repair"].get("executed") is True and row["repair"].get("ok") is True:
                after_ok, after_detail = service_status(spec.unit)
                row["after_repair"] = {
                    "healthy": after_ok,
                    "detail": after_detail,
                }
        checks.append(row)

    for spec in SNAPSHOTS:
        before = _snapshot_health(spec, now=current)
        row = {"kind": "snapshot", **before}
        if not before["healthy"]:
            repair_result = maybe_repair(
                f"snapshot:{spec.key}",
                spec.repair_unit,
                spec.repair_action,
            )
            row["repair"] = repair_result
            if repair_result.get("executed") is True and repair_result.get("ok") is True:
                # Bounded settle time for oneshot writer completion.
                time.sleep(1.0)
                row["after_repair"] = _snapshot_health(spec, now=current)
        checks.append(row)

    for spec in HTTP_CHECKS:
        healthy, detail = http_check(spec.url, spec.expected_status)
        row = {
            "kind": "http",
            "key": spec.key,
            "url": spec.url,
            "healthy": healthy,
            "detail": detail,
        }
        if not healthy:
            repair_result = maybe_repair(
                f"http:{spec.key}",
                spec.repair_unit,
                "service_restart",
            )
            row["repair"] = repair_result
            if repair_result.get("executed") is True and repair_result.get("ok") is True:
                time.sleep(1.0)
                after_ok, after_detail = http_check(spec.url, spec.expected_status)
                row["after_repair"] = {
                    "healthy": after_ok,
                    "detail": after_detail,
                }
        checks.append(row)

    unresolved = 0
    for row in checks:
        after = row.get("after_repair")
        if isinstance(after, Mapping):
            if after.get("healthy") is not True:
                unresolved += 1
        elif row.get("healthy") is not True:
            unresolved += 1

    unresolved += len(inventory_findings)

    payload = {
        "schema_version": "empire.runtime-self-heal.v1",
        "observed_at": _iso(current),
        "mode": "OBSERVE",
        "observe_only": observe_only,
        "status": "HEALTHY" if unresolved == 0 else "DEGRADED",
        "check_count": len(checks),
        "unresolved_count": unresolved,
        "repair_count": repair_count,
        "repair_budget": max_repairs_per_run,
        "system_unit_count": len(inventory),
        "system_unit_policy_counts": dict(sorted(policy_counts.items())),
        "system_units": inventory,
        "inventory_finding_count": len(inventory_findings),
        "founder_gate_required_count": sum(
            row.get("policy") == "FOUNDER_GATE"
            for row in inventory_findings
        ),
        "inventory_findings": inventory_findings,
        "checks": checks,
        "repairs": repairs,
        "founder_gate_policy": {
            "unit_prefixes": list(FOUNDER_GATE_UNIT_PREFIXES),
            "live_outbound": False,
            "payment_or_settlement": False,
            "binding_terms": False,
            "revenue_recognition": False,
            "destructive_database_or_infra": False,
            "authority_expansion": False,
        },
        "execution_authority": "bounded_internal_repair",
        "actual_revenue": False,
    }
    _atomic_json(latest_path, payload)
    _atomic_json(state_path, state)
    return payload
