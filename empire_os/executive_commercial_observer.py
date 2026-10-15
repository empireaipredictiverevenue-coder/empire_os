"""Evidence-driven executive management overlay for the *existing* Astra refresh.

Read-only file/systemd inspection. No new timer, role loop, email, provider
request, database access, traffic route, commercial approval or revenue claim.
Production sources may be absent/stale: always report that explicitly.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

from empire_os.executive_commercial_roles import review_executive_commercial_roles
from empire_os.executive_relationship_registry_review import summarize_relationship_registry
from empire_os.executive_buyer_capacity_review import review_buyer_capacity

SCHEMA_VERSION = "empire.executive.commercial_observer.v1"
CURRENT_PARTNERS = Path("runtime/executive/partner_review_input_latest.json")
HISTORICAL_PARTNERS = Path(
    "docs/commercial/EXECUTIVE_BD_CURRENT_DISCUSSION_REVIEW_20261015.json"
)
EARLIER_PARTNERS = Path(
    "docs/commercial/EXECUTIVE_COMMERCIAL_REVIEW_INPUT_20261015.json"
)
OPPORTUNITY_SOURCE = (
    "runtime/opportunities_control/opportunities_runtime_observer_latest.json"
)
OPPORTUNITY_FINAL = (
    "runtime/opportunities_control/opportunities_final_controls_latest.json"
)
DEPARTMENT = Path("runtime/astra/department_cycle_latest.json")
MAILBOX = Path(
    "runtime/conversations_replies_control/founder_mailbox_inprocess_observer_latest.json"
)
COMMERCIAL_REGISTRY = Path("runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json")
BUYER_CAPACITY = Path("runtime/buyer_capacity_readiness/latest.json")
OPPORTUNITY_RADAR = Path("runtime/opportunity_radar/latest.json")
RADAR_UPSTREAM_MAX_AGE = timedelta(hours=24)
MAX_COMMERCIAL_REGISTRY_BYTES = 1_500_000
MAX_FILE_BYTES = 250_000
MAX_DEPARTMENT_BYTES = 2_000_000
SOURCE_MAX_AGE = timedelta(days=7)
DEPARTMENT_MAX_AGE = timedelta(minutes=30)
PARTNER_MAX_AGE = timedelta(hours=24)


def _file(root: Path, name: str | Path, *, max_bytes: int = MAX_FILE_BYTES) -> dict[str, Any] | None:
    path = root / name
    try:
        if (path.is_symlink() or not path.is_file()
                or path.stat().st_size > max_bytes
                or not path.resolve().is_relative_to(root.resolve())):
            return None
        with path.open(encoding="utf-8") as stream:
            raw = json.load(stream)
        return raw if isinstance(raw, dict) else None
    except (OSError, UnicodeError, ValueError, TypeError):
        return None


def _age(stamp: Any, *, now: datetime, limit: timedelta) -> bool:
    if not isinstance(stamp, str):
        return False
    try:
        when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if when.tzinfo is None or when.utcoffset() is None:
            return False
        age = now - when.astimezone(timezone.utc)
        return timedelta(0) <= age <= limit
    except (ValueError, TypeError, OverflowError):
        return False


def _proof_state(root: Path, name: str, *, now: datetime) -> dict[str, Any]:
    path = root / name
    if not path.exists():
        return {"status": "MISSING", "evidence_ref": name, "observed_at": None}
    payload = _file(root, name)
    if payload is None:
        return {"status": "UNTRUSTED", "evidence_ref": name, "observed_at": None}
    expected_schema = (
        "empire-opportunities-runtime-observer-v1"
        if name == OPPORTUNITY_SOURCE
        else "empire-opportunities-final-controls-v1"
    )
    controls = payload.get("runtime_verified_controls")
    observed_controls = (
        isinstance(controls, list) and bool(controls)
        and all(isinstance(x, str) and bool(x) for x in controls)
        and len(set(controls)) == len(controls)
    )
    source_contract = (
        payload.get("status") == "VERIFIED_RUNTIME"
        if name == OPPORTUNITY_SOURCE else
        all(type(payload.get(key)) is bool for key in (
            "entity_classification_proved",
            "outcome_linkage_proved",
        ))
    )
    if (payload.get("lane") != "opportunities"
            or payload.get("mode") != "OBSERVE"
            or payload.get("schema_version") != expected_schema
            or not observed_controls
            or not source_contract
            or any(payload.get(field) is True for field in (
                "outbound", "db_write", "campaign_state_mutated",
                "action_authority_granted", "payment_execution"
            ))):
        status = "UNTRUSTED"
    elif not _age(payload.get("generated_at"), now=now, limit=SOURCE_MAX_AGE):
        # Do not mistake a future/invalid clock for fresh proof.
        stamp = payload.get("generated_at")
        try:
            dt = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            status = "STALE" if dt.tzinfo is not None and dt < now - SOURCE_MAX_AGE else "UNTRUSTED"
        except ValueError:
            status = "UNTRUSTED"
    else:
        status = "FRESH"
    return {
        "status": status,
        "evidence_ref": name,
        "observed_at": payload.get("generated_at"),
    }


def _radar_upstream(root: Path, *, now: datetime) -> dict[str, Any]:
    """Expose actual stale radar dependencies without renewing source authority."""
    radar = _file(root, OPPORTUNITY_RADAR)
    base = {
        "source": str(OPPORTUNITY_RADAR),
        "status": "MISSING" if radar is None else "UNTRUSTED",
        "generated_at": None,
        "available_source_count": 0,
        "fresh_upstream_count": 0,
        "stale_upstream_count": 0,
        "unavailable_upstream_count": 0,
        "dependencies": [],
        "new_opportunity_or_buyer_claim_authorized": False,
        "source_refresh_performed": False,
    }
    if radar is None:
        return base
    observed = radar.get("generated_at")
    parts = radar.get("source_status")
    if (radar.get("mode") != "OBSERVE"
            or any(radar.get(key) is True for key in (
                "outbound", "db_write", "automatic_external_execution_allowed",
                "payment_execution", "action_authority_granted",
            ))
            or not isinstance(parts, dict)
            or not 1 <= len(parts) <= 25
            or any(not isinstance(k, str) or not k or len(k) > 70 for k in parts)):
        return {**base, "generated_at": observed}
    rows = []
    for name, source in sorted(parts.items()):
        if not isinstance(source, dict) or type(source.get("available")) is not bool:
            return {**base, "generated_at": observed}
        available = source["available"]
        ts = source.get("generated_at")
        state = (
            "UNAVAILABLE" if not available else
            "FRESH" if _age(ts, now=now, limit=RADAR_UPSTREAM_MAX_AGE) else
            "STALE_OR_UNTRUSTED"
        )
        rows.append({
            "component": name, "available": available,
            "observed_at": ts if isinstance(ts, str) else None,
            "status": state,
        })
    available_count = sum(item["available"] for item in rows)
    fresh_count = sum(item["status"] == "FRESH" for item in rows)
    stale_count = sum(item["status"] == "STALE_OR_UNTRUSTED" for item in rows)
    if not _age(observed, now=now, limit=RADAR_UPSTREAM_MAX_AGE):
        status = "STALE_RADAR_WRAPPER"
    elif stale_count:
        status = "STALE_UPSTREAM_HELD"
    elif not available_count:
        status = "NO_AVAILABLE_UPSTREAM"
    else:
        status = "UPSTREAM_DATES_FRESH_NOT_COMMERCIAL_PROOF"
    return {
        **base, "status": status, "generated_at": observed,
        "available_source_count": available_count,
        "fresh_upstream_count": fresh_count,
        "stale_upstream_count": stale_count,
        "unavailable_upstream_count": sum(item["status"] == "UNAVAILABLE" for item in rows),
        "dependencies": rows,
    }


def _unit_status(unit: str) -> dict[str, str]:
    """Bounded, read-only systemd query; never starts or restarts a unit."""
    if unit not in ("empire-department-cycle.service", "empire-astra-dispatcher.service"):
        raise ValueError("unexpected unit")
    try:
        completed = subprocess.run(
            ["systemctl", "show", unit, "--no-pager",
             "-p", "ActiveState", "-p", "Result", "-p", "ExecMainStatus",
             "-p", "ExecMainExitTimestamp"],
            capture_output=True, text=True, timeout=2, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if completed.returncode:
        return {}
    return dict(line.split("=", 1) for line in completed.stdout.splitlines() if "=" in line)


def _status(raw: Mapping[str, str], *, now: datetime | None = None) -> str:
    """Service success requires a *recent* completed run, not a stale exit 0."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    active = raw.get("ActiveState")
    result = raw.get("Result")
    if active == "failed" or result in ("exit-code", "timeout", "signal", "core-dump"):
        return "FAILED"
    if active != "inactive" or result != "success" or raw.get("ExecMainStatus") != "0":
        return "UNKNOWN"
    stamp = str(raw.get("ExecMainExitTimestamp") or "").strip()
    # systemd: "Thu 2026-10-15 12:04:43 UTC"; test fixtures: ISO8601.
    if len(stamp.split()) == 4 and stamp.endswith(" UTC"):
        stamp = " ".join(stamp.split()[1:-1]).replace(" ", "T") + "+00:00"
    if _age(stamp, now=current, limit=timedelta(minutes=15)):
        return "SUCCEEDED"
    return "UNKNOWN"


def _partner_packet(root: Path, *, now: datetime) -> tuple[list[dict[str, Any]], str, str]:
    for rel in (CURRENT_PARTNERS, HISTORICAL_PARTNERS, EARLIER_PARTNERS):
        payload = _file(root, rel)
        if payload is None:
            continue
        stamp = payload.get("as_of")
        if not isinstance(stamp, str):
            return [], "MISSING", str(rel)
        try:
            seen = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            return [], "MISSING", str(rel)
        if seen.tzinfo is None:
            return [], "MISSING", str(rel)
        if seen.astimezone(timezone.utc) > now:
            return [], "MISSING", str(rel)
        state = ("CURRENT_REVIEW" if _age(stamp, now=now, limit=PARTNER_MAX_AGE)
                 and rel == CURRENT_PARTNERS else
                 "HISTORICAL_ONLY" if _age(stamp, now=now, limit=PARTNER_MAX_AGE)
                 else "STALE_REVIEW")
        rows = payload.get("partners")
        if not isinstance(rows, list) or len(rows) > 250:
            return [], "MISSING", str(rel)
        return rows, state, str(rel)
    return [], "MISSING", str(CURRENT_PARTNERS)


def observe_executive_commercial_roles(
    repo_root: Path,
    *,
    as_of: datetime | None = None,
    service_evidence: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Attach a safe read-only management snapshot inside Astra's normal refresh."""
    root = Path(repo_root).resolve()
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware observation required")
    now = now.astimezone(timezone.utc)
    sources = [
        _proof_state(root, OPPORTUNITY_SOURCE, now=now),
        _proof_state(root, OPPORTUNITY_FINAL, now=now),
    ]
    radar_upstream = _radar_upstream(root, now=now)
    statuses = [row["status"] for row in sources]
    proof_state = next(
        (label for label in ("UNTRUSTED", "MISSING", "STALE") if label in statuses),
        "FRESH",
    )
    department = _file(root, DEPARTMENT, max_bytes=MAX_DEPARTMENT_BYTES)
    current_department = bool(
        department
        and department.get("mode") == "OBSERVE"
        and _age(department.get("generated_at"), now=now, limit=DEPARTMENT_MAX_AGE)
    )
    monitor = (department.get("task_monitor") or {}) if current_department else {}
    attention = monitor.get("attention_count")
    attention_known = (
        isinstance(monitor, dict) and type(attention) is int and 0 <= attention <= 1_000_000
    )
    notification_known = isinstance(monitor, dict) and type(monitor.get("notifications_sent")) is bool
    if service_evidence is not None:
        service = dict(service_evidence)
    elif root == Path("/srv/empire_os"):
        service = {
            name: _unit_status(name)
            for name in ("empire-department-cycle.service", "empire-astra-dispatcher.service")
        }
    else:
        service = {}
    cycle = _status(service.get("empire-department-cycle.service", {}), now=now)
    dispatcher = _status(service.get("empire-astra-dispatcher.service", {}), now=now)
    mailbox = _file(root, MAILBOX)
    if mailbox is None:
        mailbox_state = "MISSING"
    elif (mailbox.get("schema_version") != "empire-founder-mailbox-inprocess-observer-v1"
          or mailbox.get("mode") != "OBSERVE"
          or any(mailbox.get(field) is True for field in (
              "outbound", "db_write", "mailbox_write", "action_authority_granted"
          ))):
        mailbox_state = "ERROR"
    elif not _age(mailbox.get("generated_at"), now=now, limit=DEPARTMENT_MAX_AGE):
        mailbox_state = "STALE"
    elif mailbox.get("status") == "VERIFIED_RUNTIME":
        mailbox_state = "HEALTHY"
    elif (mailbox.get("status") == "NO_COMPLETE_INBOUND_MESSAGE"
          and mailbox.get("mailbox_read_status") == "READ_SUCCESS"
          and mailbox.get("read_path") == "EXISTING_FOUNDER_API_LOOPBACK"
          and mailbox.get("provider") in (
              "empiredb_canonical_replies", "owned_imap", "google_workspace"
          )
          and mailbox.get("provider_only_evidence") is True
          and mailbox.get("canonical_reply_identity_verified") is False
          and type(mailbox.get("observed")) is int
          and mailbox["observed"] == 0
          and type(mailbox.get("complete_candidates")) is int
          and mailbox["complete_candidates"] == 0
          and type(mailbox.get("detail_reads")) is int
          and mailbox["detail_reads"] == 0
          and type(mailbox.get("thread_ids")) is int
          and 0 <= mailbox["thread_ids"] <= 50
          and all(mailbox.get(flag) is False for flag in (
              "outbound", "db_write", "mailbox_write", "action_authority_granted"
          ))):
        mailbox_state = "PROVIDER_ONLY"
    else:
        mailbox_state = "ERROR"
    partners, partner_state, partner_ref = _partner_packet(root, now=now)
    buyer_capacity = review_buyer_capacity(_file(root, BUYER_CAPACITY), as_of=now)
    registry_review = summarize_relationship_registry(
        _file(root, COMMERCIAL_REGISTRY, max_bytes=MAX_COMMERCIAL_REGISTRY_BYTES), as_of=now,
    )
    reason = (
        "department_cycle_unit_failed"
        if cycle == "FAILED" else None
    )
    operations = {
        "department_cycle_status": cycle,
        "astra_dispatcher_status": dispatcher,
        "department_cycle_failure_reason": reason,
        "founder_attention_items": attention if attention_known else 0,
        "founder_notifications_sent": (
            monitor["notifications_sent"] if notification_known else False
        ),
        "founder_notification_evidence": "VERIFIED" if notification_known else "UNKNOWN",
        "opportunities_source_proof_state": proof_state,
        "mailbox_observer_state": mailbox_state,
        "partner_snapshot_state": partner_state,
        "buyer_capacity_state": buyer_capacity["status"],
        "evidence_refs": [
            "systemd:empire-department-cycle.service:read_only_observation",
            "systemd:empire-astra-dispatcher.service:read_only_observation",
            *(row["evidence_ref"] for row in sources),
            str(DEPARTMENT),
            str(MAILBOX),
            str(COMMERCIAL_REGISTRY),
            str(BUYER_CAPACITY),
            str(OPPORTUNITY_RADAR),
            partner_ref,
        ],
    }
    try:
        review = review_executive_commercial_roles(partners, operations, as_of=now)
        state = "REVIEW_ONLY" if partner_state == "CURRENT_REVIEW" else "HISTORICAL_REVIEW_ONLY"
    except (ValueError, TypeError, KeyError, AttributeError):
        # Never stop Astra or auto-approve a prospect on bad source input.
        state = "INVALID_EVIDENCE_HELD"
        review = None
    return {
        "schema_version": SCHEMA_VERSION,
        "as_of": now.isoformat(),
        "mode": "OBSERVE",
        "review_state": state,
        "observed_systemd": {
            "department_cycle": cycle, "astra_dispatcher": dispatcher,
            "unit_status_unknown_is_not_healthy": True,
        },
        "opportunity_radar_dependencies": radar_upstream,
        "opportunity_proof": {
            "status": proof_state, "sources": sources,
            "source_files_observed_not_repaired": True,
        },
        "existing_relationship_registry": registry_review,
        "downstream_buyer_capacity": {
            **buyer_capacity,
            "evidence_ref": str(BUYER_CAPACITY),
        },
        "founder_mailbox_observer": {
            "status": mailbox_state,
            "evidence_ref": str(MAILBOX),
            "server_mailbox_provider_read_verified": mailbox_state in ("HEALTHY", "PROVIDER_ONLY"),
            "canonical_reply_identity_verified": mailbox_state == "HEALTHY",
            "cannot_infer_no_replies_from_observer_error": True,
            "credential_or_message_content_exposed": False,
        },
        "partner_evidence": {
            "source": partner_ref,
            "state": partner_state,
            "live_provider_mailbox_checked": False,
            "partner_evidence_may_have_changed_since_snapshot": True,
        },
        "founder_attention": {
            "count": attention if attention_known else None,
            "count_verified_at_snapshot": attention_known,
            "notifications_sent_in_task_monitor": (
                monitor["notifications_sent"] if notification_known else None
            ),
            "notification_scope": "completion_task_monitor_only",
        },
        "review": review,
        "execution_authority": "none",
        "outbound_enabled": False,
        "production_changes": False,
        "service_restart": False,
        "database_writes": False,
        "external_network_requests": False,
    }
