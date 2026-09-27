"""EmpireOS production reliability agent.

Long-running agentic control loop:

OBSERVE -> DIAGNOSE -> PLAN -> ACT -> VERIFY -> RECORD -> REPEAT

The agent coordinates deterministic, allowlisted tools. It does not use an LLM
to improvise production mutations. It never sends outbound, changes commercial
truth, accepts terms, moves funds, recognizes revenue, changes schema, or
expands its own authority.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import time
from typing import Any, Callable, Mapping

from empire_os.buyer_recovery import (
    RECOVERY_HEARTBEAT,
    RECOVERY_SEED_SNAPSHOT,
    load_local_recovery_seeds,
    refresh_last_known_good_snapshot,
    run_local_buyer_recovery,
)
from empire_os.runtime_self_heal import run_runtime_self_heal
from empire_os.supabase_egress_guard import (
    STATUS_PATH as EGRESS_STATUS_PATH,
    supabase_egress_contained,
)


ROOT = Path("/srv/empire_os")
LATEST_PATH = ROOT / "runtime/reliability_agent/latest.json"
STATE_PATH = ROOT / "runtime/reliability_agent/state.json"

DEFAULT_INTERVAL_SECONDS = 120
DEFAULT_RECOVERY_INTERVAL_SECONDS = 900
DEFAULT_SNAPSHOT_REFRESH_SECONDS = 900
MAX_ACTIONS_PER_CYCLE = 3

CONTAINMENT_SAFE_REPAIR_UNITS = frozenset({
    "empire-public-gateway.service",
    "empire-self-serve-checkout.service",
    "empire-ops-mcp.service",
})


@dataclass(frozen=True)
class ReliabilityObservation:
    observed_at: str
    supabase_egress_contained: bool
    supabase_guard_state: str
    recovery_snapshot_exists: bool
    recovery_seed_count: int
    recovery_snapshot_age_seconds: float | None
    recovery_heartbeat_exists: bool
    recovery_heartbeat_age_seconds: float | None
    recovery_heartbeat_state: str | None


@dataclass(frozen=True)
class ReliabilityAction:
    action: str
    reason: str
    priority: int


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _load_state(path: Path) -> dict[str, Any]:
    value = _load_json(path)
    failures = value.get("action_failures")
    if not isinstance(failures, dict):
        value["action_failures"] = {}
    return value


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _action_allowed(
    state: Mapping[str, Any],
    action: str,
    *,
    now: datetime,
) -> bool:
    failures = state.get("action_failures")
    failures = failures if isinstance(failures, Mapping) else {}
    row = failures.get(action)
    row = row if isinstance(row, Mapping) else {}
    next_at = _parse_time(row.get("next_allowed_at"))
    return next_at is None or now >= next_at


def _record_action_result(
    state: dict[str, Any],
    action: str,
    *,
    ok: bool,
    now: datetime,
) -> None:
    failures = state.setdefault("action_failures", {})
    if ok:
        failures.pop(action, None)
        return

    previous = failures.get(action)
    previous = previous if isinstance(previous, Mapping) else {}
    count = int(previous.get("count") or 0) + 1
    delay = min(1800, 60 * (2 ** min(count - 1, 5)))
    failures[action] = {
        "count": count,
        "last_failed_at": _iso(now),
        "next_allowed_at": _iso(
            datetime.fromtimestamp(
                now.timestamp() + delay,
                tz=timezone.utc,
            )
        ),
        "backoff_seconds": delay,
    }


def _age_seconds(path: Path, *, now: datetime) -> float | None:
    try:
        return max(0.0, now.timestamp() - path.stat().st_mtime)
    except OSError:
        return None


def observe(
    repo_root: str | Path = ROOT,
    *,
    now: datetime | None = None,
) -> ReliabilityObservation:
    root = Path(repo_root).resolve()
    current = (now or _now()).astimezone(timezone.utc)
    guard_path = root / EGRESS_STATUS_PATH.relative_to(ROOT)
    contained = supabase_egress_contained(guard_path)
    guard = _load_json(guard_path)

    snapshot_path = root / RECOVERY_SEED_SNAPSHOT
    heartbeat_path = root / RECOVERY_HEARTBEAT
    heartbeat = _load_json(heartbeat_path)

    return ReliabilityObservation(
        observed_at=_iso(current),
        supabase_egress_contained=contained,
        supabase_guard_state=str(
            guard.get("state") or "unknown"
        ),
        recovery_snapshot_exists=snapshot_path.exists(),
        recovery_seed_count=len(load_local_recovery_seeds(root)),
        recovery_snapshot_age_seconds=_age_seconds(
            snapshot_path,
            now=current,
        ),
        recovery_heartbeat_exists=heartbeat_path.exists(),
        recovery_heartbeat_age_seconds=_age_seconds(
            heartbeat_path,
            now=current,
        ),
        recovery_heartbeat_state=(
            str(heartbeat.get("state"))
            if heartbeat.get("state") is not None
            else None
        ),
    )


def plan_actions(
    observation: ReliabilityObservation,
    *,
    recovery_interval_seconds: int = DEFAULT_RECOVERY_INTERVAL_SECONDS,
    snapshot_refresh_seconds: int = DEFAULT_SNAPSHOT_REFRESH_SECONDS,
) -> list[ReliabilityAction]:
    """Pure decision policy for one reliability cycle."""
    actions: list[ReliabilityAction] = [
        ReliabilityAction(
            "RUN_BOUNDED_SELF_HEAL",
            "continuous runtime health verification",
            90,
        )
    ]

    if observation.supabase_egress_contained:
        due = (
            not observation.recovery_heartbeat_exists
            or observation.recovery_heartbeat_state
            != "LOCAL_RECOVERY_EXECUTED"
            or observation.recovery_heartbeat_age_seconds is None
            or observation.recovery_heartbeat_age_seconds
            >= max(60, int(recovery_interval_seconds))
        )
        if observation.recovery_seed_count > 0 and due:
            actions.append(ReliabilityAction(
                "RUN_LOCAL_BUYER_RECOVERY",
                "Supabase contained; continue first-party buyer validation "
                "from last-known-good local seeds",
                100,
            ))
        elif observation.recovery_seed_count == 0:
            actions.append(ReliabilityAction(
                "ESCALATE_RECOVERY_SEEDS_MISSING",
                "Supabase contained and no last-known-good buyer recovery "
                "snapshot exists",
                100,
            ))
    else:
        refresh_due = (
            not observation.recovery_snapshot_exists
            or observation.recovery_snapshot_age_seconds is None
            or observation.recovery_snapshot_age_seconds
            >= max(60, int(snapshot_refresh_seconds))
        )
        if refresh_due:
            actions.append(ReliabilityAction(
                "REFRESH_RECOVERY_SNAPSHOT",
                "Supabase healthy; refresh last-known-good opportunity seeds",
                80,
            ))

    actions.sort(key=lambda row: (-row.priority, row.action))
    return actions[:MAX_ACTIONS_PER_CYCLE]


def _execute_action(
    action: ReliabilityAction,
    *,
    root: Path,
    self_heal: Callable[..., Mapping[str, Any]],
    refresh_snapshot: Callable[..., Mapping[str, Any]],
    local_recovery: Callable[..., Mapping[str, Any]],
    contained: bool,
) -> dict[str, Any]:
    try:
        if action.action == "RUN_BOUNDED_SELF_HEAL":
            result = dict(self_heal(
                observe_only=False,
                repair_unit_allowlist=(
                    CONTAINMENT_SAFE_REPAIR_UNITS
                    if contained
                    else None
                ),
            ))
        elif action.action == "RUN_LOCAL_BUYER_RECOVERY":
            result = dict(local_recovery(root))
        elif action.action == "REFRESH_RECOVERY_SNAPSHOT":
            result = dict(refresh_snapshot(root))
        elif action.action == "ESCALATE_RECOVERY_SEEDS_MISSING":
            result = {
                "ok": False,
                "state": "FOUNDER_ATTENTION_REQUIRED",
                "reason": action.reason,
                "execution_authority": "none",
            }
        else:
            result = {
                "ok": False,
                "state": "UNKNOWN_ACTION",
                "execution_authority": "none",
            }
    except Exception as exc:
        result = {
            "ok": False,
            "state": "ACTION_EXCEPTION",
            "error": f"{type(exc).__name__}:{str(exc)[:500]}",
            "execution_authority": "none",
        }

    return {
        "action": action.action,
        "reason": action.reason,
        "priority": action.priority,
        "result": result,
    }


def _action_verified(row: Mapping[str, Any]) -> bool:
    action = str(row.get("action") or "")
    result = row.get("result")
    result = result if isinstance(result, Mapping) else {}

    if action == "RUN_BOUNDED_SELF_HEAL":
        return result.get("execution_authority") == "bounded_internal_repair"

    if action == "RUN_LOCAL_BUYER_RECOVERY":
        return (
            result.get("state") == "LOCAL_RECOVERY_EXECUTED"
            and result.get("database_write_performed") is False
            and result.get("outbound_sent") is False
            and result.get("execution_authority") == "none"
        )

    if action == "REFRESH_RECOVERY_SNAPSHOT":
        return (
            result.get("ok") is True
            and result.get("database_write_performed") is False
            and result.get("outbound_sent") is False
            and result.get("execution_authority") == "none"
            and result.get("state")
            in {"REFRESHED", "PRESERVED_LAST_KNOWN_GOOD"}
        )

    if action == "ESCALATE_RECOVERY_SEEDS_MISSING":
        return result.get("state") == "FOUNDER_ATTENTION_REQUIRED"

    return False


def run_cycle(
    repo_root: str | Path = ROOT,
    *,
    now: datetime | None = None,
    self_heal: Callable[..., Mapping[str, Any]] = run_runtime_self_heal,
    refresh_snapshot: Callable[..., Mapping[str, Any]] = (
        refresh_last_known_good_snapshot
    ),
    local_recovery: Callable[..., Mapping[str, Any]] = (
        run_local_buyer_recovery
    ),
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    current = (now or _now()).astimezone(timezone.utc)
    before = observe(root, now=current)
    actions = plan_actions(before)

    state_path = root / STATE_PATH.relative_to(ROOT)
    state = _load_state(state_path)
    executed: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []

    for action in actions:
        if not _action_allowed(
            state,
            action.action,
            now=current,
        ):
            deferred.append({
                **asdict(action),
                "decision": "BACKOFF",
                "failure_state": (
                    state.get("action_failures", {})
                    .get(action.action)
                ),
            })
            continue

        row = _execute_action(
            action,
            root=root,
            self_heal=self_heal,
            refresh_snapshot=refresh_snapshot,
            local_recovery=local_recovery,
            contained=before.supabase_egress_contained,
        )
        verified = _action_verified(row)
        row["verified"] = verified
        executed.append(row)
        _record_action_result(
            state,
            action.action,
            ok=verified,
            now=current,
        )

    _atomic_json(state_path, state)

    after = observe(root)
    verified_count = sum(
        row.get("verified") is True
        for row in executed
    )
    failures = [
        row for row in executed
        if row.get("verified") is not True
    ]
    founder_attention_required = any(
        row.get("action") == "ESCALATE_RECOVERY_SEEDS_MISSING"
        for row in executed
    )
    runtime_degraded = any(
        row.get("action") == "RUN_BOUNDED_SELF_HEAL"
        and isinstance(row.get("result"), Mapping)
        and row["result"].get("status") not in {None, "HEALTHY"}
        for row in executed
    )
    degraded = bool(
        failures
        or deferred
        or founder_attention_required
        or runtime_degraded
    )

    payload = {
        "schema_version": "empire.reliability-agent.v1",
        "observed_at": before.observed_at,
        "mode": "OBSERVE",
        "loop": "OBSERVE_DIAGNOSE_PLAN_ACT_VERIFY_RECORD",
        "before": asdict(before),
        "planned_actions": [asdict(row) for row in actions],
        "executed_actions": executed,
        "deferred_actions": deferred,
        "verified_action_count": verified_count,
        "failed_action_count": len(failures),
        "after": asdict(after),
        "status": "DEGRADED" if degraded else "HEALTHY",
        "operating_state": (
            "SUPABASE_CONTAINED_LOCAL_RECOVERY"
            if before.supabase_egress_contained
            else "NORMAL"
        ),
        "founder_attention_required": founder_attention_required,
        "authority": {
            "internal_repair": "allowlisted_reversible_only",
            "live_outbound": False,
            "database_mutation": False,
            "binding_terms": False,
            "fund_movement": False,
            "revenue_recognition": False,
            "authority_expansion": False,
        },
        "execution_authority": "bounded_internal_repair",
        "actual_revenue": False,
    }
    _atomic_json(root / LATEST_PATH.relative_to(ROOT), payload)
    return payload


class EmpireReliabilityAgent:
    def __init__(
        self,
        repo_root: str | Path = ROOT,
        *,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        self.root = Path(repo_root).resolve()
        self.interval_seconds = max(30, int(interval_seconds))
        self._stop = False

    def stop(self, *_args: Any) -> None:
        self._stop = True

    def run_forever(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

        while not self._stop:
            started = time.monotonic()
            run_cycle(self.root)
            elapsed = time.monotonic() - started
            sleep_for = max(1.0, self.interval_seconds - elapsed)
            deadline = time.monotonic() + sleep_for
            while not self._stop and time.monotonic() < deadline:
                time.sleep(min(1.0, deadline - time.monotonic()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.once:
        payload = run_cycle(args.repo_root)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["status"] == "HEALTHY" else 2

    agent = EmpireReliabilityAgent(
        args.repo_root,
        interval_seconds=args.interval_seconds,
    )
    agent.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
