"""Read-only Stage 1 closure gate for original commercial evidence plumbing.

No deployment, DB reads, credentials, agent dispatch, outbound, or score writes.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import subprocess

from empire_os.reply_lineage_health import assess_reply_lineage


ROOT = Path("/srv/empire_os")


def _read(root: Path, relative: str) -> dict:
    try:
        data = json.loads((root / relative).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _date(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:
        return None


def assess(
    root: Path, *,
    now: datetime,
    market_service_healthy: bool,
    root_timer_active: bool,
    masked_collector_post: bool,
    independent_health_monitor_ready: bool = False,
) -> dict:
    if now.tzinfo is None:
        raise ValueError("timezone aware time required")
    now = now.astimezone(timezone.utc)
    collector = _read(root, "runtime/conversations_replies_control/collector_health_latest.json")
    canonical = _read(root, "runtime/conversations_replies_control/latest.json")
    gps = _read(root, "runtime/market_sweeps/revenue_gps_latest.json")
    resolver = _read(root, "runtime/opportunity_factory/evidence_resolution_latest.json")
    intake = _read(root, "runtime/opportunity_factory/intake_latest.json")

    issues = []
    def gate(ok: bool, reason: str):
        if not ok:
            issues.append(reason)

    health_time = _date(collector.get("observed_at"))
    source_time = _date(canonical.get("generated_at"))
    gate(health_time is not None and timedelta(minutes=-5) <=
         now - health_time <= timedelta(minutes=15), "COLLECTOR_HEALTH_NOT_CURRENT")
    gate(
        collector.get("status") == "READ_SUCCESS"
        and collector.get("source_query_completed") is True
        and type(collector.get("database_table_count")) is int
        and collector["database_table_count"] >= 1,
        "COLLECTOR_READ_NOT_VERIFIED",
    )
    gate(
        source_time is not None and health_time is not None
        and abs((health_time - source_time).total_seconds()) <= 120,
        "COLLECTOR_SNAPSHOT_HEALTH_NOT_CORRELATED",
    )
    gate(market_service_healthy and root_timer_active, "MARKET_GPS_SERVICE_OR_TIMER_NOT_READY")
    lineage = assess_reply_lineage(gps, now)
    gate(
        lineage["status"] == "CURRENT_STRUCTURAL_COUNTS_ONLY",
        "LIVE_MARKET_REPLY_LINEAGE_NOT_VERIFIED",
    )
    gate(
        resolver.get("execution_authority") == "none"
        and resolver.get("normalized_scores_written") == 0
        and resolver.get("factory_promotion_authorized") is False
        and intake.get("factory_ready_count") == 0
        and intake.get("execution_authority") == "none",
        "FACTORY_EXECUTION_GATES_UNVERIFIED",
    )
    gate(
        not masked_collector_post or independent_health_monitor_ready,
        "COLLECTOR_SYSTEMD_FAILURE_STILL_MASKED",
    )
    return {
        "schema": "empire.buyer_evidence_stage1_acceptance.v1",
        "checked_at": now.isoformat(),
        "status": "PASS" if not issues else "BLOCKED",
        "blockers": issues,
        "collector_health_status": str(collector.get("status") or "UNKNOWN")[:64],
        "independent_health_monitor_ready": independent_health_monitor_ready,
        "collector_source_tables": collector.get("database_table_count"),
        "quarantined_message_count": (canonical.get("quarantine") or {}).get("quarantine_count"),
        "live_lineage_status": lineage["status"],
        "live_lineage_counts": lineage.get("counts"),
        "market_count": gps.get("market_count"),
        "authenticated_buyer_messages_proven": False,
        "factory_approval_authorized": False,
        "execution_authority": "none",
        "changes_applied": False,
    }


def _show(unit: str, key: str) -> str:
    result = subprocess.run(
        ["systemctl", "show", unit, "-p", key, "--value"],
        capture_output=True, text=True, timeout=5,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def recent_monitor_pass(journal: str, now: datetime) -> bool:
    """Check the latest structured oneshot result, not volatile systemd timestamps."""
    if now.tzinfo is None:
        raise ValueError("timezone-aware time required")
    observations = []
    for line in journal.splitlines():
        try:
            entry = json.loads(line)
            msg = json.loads(entry.get("MESSAGE", ""))
            stamp = datetime.fromtimestamp(
                int(entry["__REALTIME_TIMESTAMP"]) / 1000000, timezone.utc
            )
        except (ValueError, TypeError, KeyError, OverflowError, json.JSONDecodeError):
            continue
        if (
            isinstance(msg, dict)
            and msg.get("schema") == "empire.conversation_collector_systemd_health.v1"
        ):
            observations.append((stamp, msg))
    if not observations:
        return False
    stamp, msg = max(observations, key=lambda pair: pair[0])
    elapsed = now.astimezone(timezone.utc) - stamp
    return (
        timedelta(minutes=-2) <= elapsed <= timedelta(minutes=15)
        and msg.get("status") == "PASS"
        and msg.get("execution_authority") == "none"
        and msg.get("authenticated_buyer_intent") is False
    )


def _recent_monitor_verified() -> bool:
    try:
        completed = subprocess.run(
            [
                "journalctl", "-u", "empire-conversation-collector-health.service",
                "--no-pager", "-o", "json", "-n", "80",
            ],
            capture_output=True, text=True, timeout=8,
        )
        return (
            completed.returncode == 0
            and recent_monitor_pass(completed.stdout, datetime.now(timezone.utc))
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


def main() -> int:
    try:
        cat = subprocess.run(
            ["systemctl", "cat", "empire-department-cycle.service"],
            capture_output=True, text=True, timeout=8,
        )
        masked = (
            cat.returncode != 0
            or any(
                line.strip().startswith("ExecStartPost=-")
                and "run_conversations_replies_control.py" in line
                for line in cat.stdout.splitlines()
            )
        )
        report = assess(
            ROOT, now=datetime.now(timezone.utc),
            market_service_healthy=_show("empire-market-gps.service", "Result") == "success",
            root_timer_active=(
                _show("empire-market-gps.timer", "ActiveState") == "active"
                and _show("empire-market-gps.timer", "UnitFileState") == "enabled"
            ),
            masked_collector_post=masked,
            independent_health_monitor_ready=(
                _show("empire-conversation-collector-health.service", "LoadState") == "loaded"
                and _show("empire-conversation-collector-health.service", "Result") == "success"
                and "empire-conversation-collector-health.service" in cat.stdout
                and _recent_monitor_verified()
            ),
        )
    except (OSError, subprocess.TimeoutExpired):
        report = {"status": "BLOCKED", "blockers": ["SYSTEMD_INSPECTION_UNAVAILABLE"],
                  "execution_authority": "none", "changes_applied": False}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
