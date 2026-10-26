"""One EmpireOS Prospect Recovery Agent, supervising existing commercial workers.

A deterministic controller, not a second qualification/buyer/AI/DB engine.
Only owner-installed root systemd oneshot may request restarts of allowlisted
EXISTING services after stale-source checks and durable cooldown. It never
handles contact records, grants buyer authority or creates revenue truth.
"""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Callable, Mapping


WORKSPACE = Path("/var/lib/empire-prospect-recovery-agent")
SNAPSHOT = WORKSPACE / "latest.json"
STATE = WORKSPACE / "state.json"
LOCK = WORKSPACE / ".lock"
SOURCES = {
    "exchange": Path("runtime/commercial_exchange/latest.json"),
    "buyer_plan": Path("runtime/buyer_acquisition/latest.json"),
    "buyer_scout": Path("runtime/buyer_acquisition/scout_latest.json"),
    "qualification": Path("runtime/qualification/historical_backfill_cursor.json"),
    "linked_qualification": Path("runtime/qualification/historical_identity_linked_cursor.json"),
}
# Only these pre-existing, evidence-gated owner services can be requested.
UNIT_POLICY = (
    ("qualification", "empire-qualification.service", 50, 45),
    ("exchange", "empire-commercial-exchange.service", 25, 30),
    ("buyer_plan", "empire-buyer-acquisition-team.service", 35, 45),
    ("buyer_scout", "empire-buyer-acquisition-scout.service", 100, 100),
)
MAX_REPAIR_REQUESTS = 2
MAX_JSON_BYTES = 12_000_000


def _when(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:
        return None


def _read_json(path: Path, *, optional: bool = False) -> dict[str, Any] | None:
    if not path.exists():
        if path.is_symlink():
            raise ValueError("symlink source disallowed")
        return None if optional else {}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("unsafe source path")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON snapshot must be object")
    return data


def _int(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _source_state(
    snapshot: Mapping[str, Any] | None,
    kind: str,
    now: datetime,
) -> dict[str, Any]:
    if snapshot is None:
        return {"state": "MISSING", "age_minutes": None}
    key = "observed_at" if kind == "exchange" else (
        "updated_at" if kind.endswith("qualification") else "generated_at"
    )
    observed = _when(snapshot.get(key))
    if observed is None:
        return {"state": "INVALID_TIMESTAMP", "age_minutes": None}
    age = round((now - observed).total_seconds() / 60, 2)
    if age < -5:
        return {"state": "FUTURE_TIMESTAMP_HOLD", "age_minutes": None}
    return {"state": "VALID", "age_minutes": max(0.0, age)}


def _buyer_briefs(buyer_plan: Mapping[str, Any] | None, limit: int = 12) -> list[dict]:
    rows = (buyer_plan or {}).get("demand_gap_queue")
    if not isinstance(rows, list):
        return []
    sorted_rows = sorted(
        (row for row in rows if isinstance(row, Mapping)),
        key=lambda row: (
            -min(100_000, _int(row.get("overflow_count")) or 0),
            -min(100_000, _int(row.get("priority_score")) or 0),
            str(row.get("corridor_key") or ""),
        ),
    )
    briefs = []
    seen = set()
    for row in sorted_rows:
        if row.get("buyer_hunt_required") is not True:
            continue
        overflow = _int(row.get("overflow_count"))
        lane = str(row.get("niche_family") or "").strip()
        territory = str(row.get("territory") or "").strip()
        corridor = str(row.get("corridor_key") or "").strip()
        if not overflow or not lane or not territory or not corridor or corridor in seen:
            continue
        if len(corridor) > 240 or len(lane) > 90 or len(territory) > 100:
            continue
        seen.add(corridor)
        briefs.append({
            "corridor_key": corridor,
            "sector": lane,
            "market": territory,
            "overflow_prospects": overflow,
            "active_capacity": _int(row.get("active_remaining_capacity")),
            "owner": "existing_buyer_acquisition_scout",
            "required_evidence": [
                "first_party_buyer_demand",
                "current_capacity_and_accepted_terms",
                "named_decision_maker_and_verified_contact_path",
            ],
            "next_action": "prioritise_existing_scout_research_and_buyer_review",
            "automatic_outbound": False,
        })
        if len(briefs) == limit:
            break
    return briefs


def build_recovery_plan(
    sources: Mapping[str, Mapping[str, Any] | None],
    prior: Mapping[str, Any] | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    now = now.astimezone(timezone.utc)
    exchange = sources.get("exchange") or {}
    buyer_plan = sources.get("buyer_plan") or {}
    scout = sources.get("buyer_scout") or {}
    cursor = sources.get("qualification") or {}
    linked = sources.get("linked_qualification") or {}
    census = exchange.get("qualification_population_census") or {}
    if not isinstance(census, Mapping):
        census = {}
    diag = exchange.get("supply_gate_diagnostics") or {}
    if not isinstance(diag, Mapping):
        diag = {}
    blockers = diag.get("identity_blocker_counts") or {}
    if not isinstance(blockers, Mapping):
        blockers = {}
    states = {
        key: _source_state(sources.get(key), key, now)
        for key in SOURCES
    }
    active = census.get("state") == "CANONICAL_COUNT_AVAILABLE"
    total = _int(census.get("canonical_prospect_total")) if active else None
    have_record = _int(census.get("v2_qualification_record_total")) if active else None
    without = _int(census.get("prospects_without_v2_record")) if active else None
    if active and (
        total is None or have_record is None or without is None
        or have_record + without != total
    ):
        active = False
        total = have_record = without = None
    overflow = _int(exchange.get("overflow_count"))
    priorities = _buyer_briefs(buyer_plan)
    prior_metrics = (prior or {}).get("metrics") or {}
    prior_total = _int(prior_metrics.get("v2_records"))
    delta = have_record - prior_total if have_record is not None and prior_total is not None else None
    requests = []
    for source_key, unit, stale_minutes, cooldown_minutes in UNIT_POLICY:
        fresh = states[source_key]
        if source_key == "qualification" and (without is None or without == 0):
            continue
        if source_key == "buyer_scout" and (overflow is None or overflow == 0):
            continue
        if fresh["state"] not in {"MISSING", "VALID"}:
            continue  # Never repair from corrupt/future-dated data.
        age = fresh["age_minutes"]
        if fresh["state"] == "VALID" and age is not None and age < stale_minutes:
            continue
        prior_req = _when(((prior or {}).get("restart_requests") or {}).get(unit))
        if prior_req is not None and (now - prior_req).total_seconds() < cooldown_minutes * 60:
            continue
        requests.append({
            "service": unit,
            "reason": f"{source_key}_stale_or_missing",
            "source_state": fresh["state"],
            "age_minutes": age,
            "authorization": "existing_owner_service_only",
        })
    # Only the first two repairs per run; stale source priority is explicit.
    return {
        "schema_version": "empire.prospect_recovery_agent.v1",
        "generated_at": now.isoformat(),
        "mode": "OBSERVE",
        "agent_id": "empire_prospect_recovery",
        "existing_service_supervisor": True,
        "inputs": states,
        "metrics": {
            "canonical_prospects": total,
            "v2_records": have_record,
            "without_v2_record": without,
            "v2_scored": _int(census.get("v2_scored_prospect_total")) if active else None,
            "v2_hot": _int(census.get("v2_hot_tier_total")) if active else None,
            "v2_warm": _int(census.get("v2_warm_tier_total")) if active else None,
            "v2_records_delta_since_prior_agent_cycle": delta,
            "chronological_cursor": _int(cursor.get("next_offset")),
            "identity_linked_cursor": _int(linked.get("next_offset")),
            "exchange_selection_count": _int(exchange.get("inventory_count")),
            "exchange_selection_limited": ((exchange.get("selection_window") or {}).get("limit_reached") is True),
            "exchange_identity_ready_in_selection": _int(diag.get("identity_ready_count")),
            "exchange_missing_active_identity_in_selection": _int(blockers.get("missing_active_identity_link")),
            "exchange_overflow": overflow,
            "omega_scores_in_selection": _int((exchange.get("omega_scoring") or {}).get("scores_with_exact_qualification_and_identity")),
            "buyer_scout_researched": _int(scout.get("candidate_count")),
            "buyer_scout_budget_verified": _int(scout.get("verified_budget_candidate_count")),
            "buyer_scout_direct_payer_candidates": _int(scout.get("explicit_direct_buyer_candidate_count")),
            "verified_saleable_total": None,
            "realised_revenue_claimed": False,
        },
        "buyer_recruitment_worklist": priorities,
        "worklist_count": len(priorities),
        "source_recovery_priority": {
            "existing_owner": "empire_qualification_and_existing_enrichment_workers",
            "action": "recover_authoritative_source_lineage_and_site_evidence",
            "missing_v2_backlog": without,
            "identity_gap_in_selection": _int(blockers.get("missing_active_identity_link")),
            "new_identity_or_contact_claim_without_evidence": False,
        },
        "next_actions": requests[:MAX_REPAIR_REQUESTS],
        "repair_requests_held_for_next_cycle": max(0, len(requests) - MAX_REPAIR_REQUESTS),
        "execution_authority": "existing_unit_restart_only",
        "new_scoring_model": False,
        "new_database": False,
        "outbound_sent": False,
        "payments_changed": False,
        "buyer_seats_activated": False,
    }


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("unsafe recovery workspace")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False,
            prefix=".agent-", suffix=".json",
        ) as handle:
            temp = Path(handle.name)
            os.fchmod(handle.fileno(), 0o644 if path.name == "latest.json" else 0o600)
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def run_agent(
    repo_root: Path,
    *,
    execute: bool = False,
    now: datetime | None = None,
    start_unit: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    if execute and root != Path("/srv/empire_os"):
        raise ValueError("live actions require canonical EmpireOS root")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    ws = root / WORKSPACE
    if execute:
        ws.mkdir(parents=True, exist_ok=True, mode=0o755)
        if ws.is_symlink():
            raise ValueError("unsafe agent workspace")
        lock = ws / LOCK
        if lock.is_symlink():
            raise ValueError("unsafe agent lock")
        lock.touch(exist_ok=True)
        os.chmod(lock, 0o600)
    else:
        lock = None
    def inner() -> dict[str, Any]:
        prior = _read_json(root / STATE, optional=True) if execute else None
        sources = {key: _read_json(root / path, optional=True) for key, path in SOURCES.items()}
        plan = build_recovery_plan(sources, prior, now=now)
        if not execute:
            return {**plan, "execution_mode": "DRY_RUN", "unit_requests": []}
        request_log = dict((prior or {}).get("restart_requests") or {})
        receipts: list[dict[str, Any]] = []
        for row in plan["next_actions"]:
            unit = row["service"]
            if unit not in {policy[1] for policy in UNIT_POLICY}:
                raise ValueError("unit not on recovery allowlist")
            if start_unit is None:
                completed = subprocess.run(
                    ("/usr/bin/systemctl", "start", "--no-block", unit),
                    capture_output=True, text=True, timeout=10, check=False,
                )
                accepted = completed.returncode == 0
            else:
                accepted = bool(start_unit(unit))
            receipts.append({
                "service": unit,
                "status": "START_REQUEST_ACCEPTED_NOT_COMPLETION" if accepted else "REQUEST_FAILED",
            })
            # Persist a conservative cooldown even on request failure.
            request_log[unit] = now.isoformat()
        plan["execution_mode"] = "OWNER_INSTALLED_SUPERVISOR"
        plan["unit_requests"] = receipts
        plan["next_actions"] = []  # processed requests are in receipts.
        plan["mode"] = "SUPERVISING_EXISTING_WORKERS"
        plan["automatic_external_action"] = False
        _atomic_write(root / SNAPSHOT, plan)
        _atomic_write(root / STATE, {
            "schema_version": "empire.prospect_recovery_agent_state.v1",
            "generated_at": now.isoformat(),
            "metrics": plan["metrics"],
            "restart_requests": request_log,
        })
        return plan
    if lock is None:
        return inner()
    with lock.open("r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            return inner()
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def main() -> int:
    """Standalone stdlib-only root-owned service entrypoint."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.execute and os.geteuid() != 0:
        parser.error("systemd owner authority required")
    result = run_agent(Path(args.repo_root), execute=args.execute)
    print(json.dumps({
        "agent_id": result["agent_id"],
        "mode": result["mode"],
        "metrics": result["metrics"],
        "buyer_worklist_count": result["worklist_count"],
        "unit_requests": result["unit_requests"],
        "execution_mode": result["execution_mode"],
        "outbound_sent": False,
        "payments_changed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
