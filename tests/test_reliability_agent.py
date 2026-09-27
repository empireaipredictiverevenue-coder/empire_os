from datetime import datetime, timezone
import json
from pathlib import Path

import empire_os.reliability_agent as reliability


NOW = datetime(2026, 9, 27, 8, 0, tzinfo=timezone.utc)


def _contained_observation(*, seeds: int = 2, heartbeat_age=2000):
    return reliability.ReliabilityObservation(
        observed_at=NOW.isoformat(),
        supabase_egress_contained=True,
        supabase_guard_state="contained",
        recovery_snapshot_exists=seeds > 0,
        recovery_seed_count=seeds,
        recovery_snapshot_age_seconds=100.0 if seeds else None,
        recovery_heartbeat_exists=heartbeat_age is not None,
        recovery_heartbeat_age_seconds=heartbeat_age,
        recovery_heartbeat_state="LOCAL_RECOVERY_EXECUTED",
    )


def test_contained_plan_runs_local_recovery_and_bounded_self_heal():
    actions = reliability.plan_actions(
        _contained_observation(),
        recovery_interval_seconds=900,
    )
    names = [row.action for row in actions]

    assert names[0] == "RUN_LOCAL_BUYER_RECOVERY"
    assert "RUN_BOUNDED_SELF_HEAL" in names
    assert "REFRESH_RECOVERY_SNAPSHOT" not in names


def test_contained_plan_escalates_if_last_known_good_seeds_missing():
    actions = reliability.plan_actions(
        _contained_observation(seeds=0),
    )
    names = [row.action for row in actions]

    assert "ESCALATE_RECOVERY_SEEDS_MISSING" in names
    assert "REFRESH_RECOVERY_SNAPSHOT" not in names


def test_healthy_plan_refreshes_stale_recovery_snapshot():
    observation = reliability.ReliabilityObservation(
        observed_at=NOW.isoformat(),
        supabase_egress_contained=False,
        supabase_guard_state="healthy",
        recovery_snapshot_exists=True,
        recovery_seed_count=3,
        recovery_snapshot_age_seconds=5000.0,
        recovery_heartbeat_exists=True,
        recovery_heartbeat_age_seconds=10.0,
        recovery_heartbeat_state="IDLE_GUARD_HEALTHY",
    )

    names = [
        row.action
        for row in reliability.plan_actions(
            observation,
            snapshot_refresh_seconds=900,
        )
    ]

    assert "REFRESH_RECOVERY_SNAPSHOT" in names
    assert "RUN_LOCAL_BUYER_RECOVERY" not in names


def test_run_cycle_uses_containment_safe_tools_only(monkeypatch, tmp_path):
    root = Path(tmp_path)
    guard = root / "runtime/control/supabase_egress_guard.json"
    guard.parent.mkdir(parents=True)
    guard.write_text(
        '{"state":"contained","contained":true}',
        encoding="utf-8",
    )

    from empire_os.buyer_recovery import write_local_recovery_snapshot
    write_local_recovery_snapshot(
        root,
        [{
            "id": "p1",
            "business_name": "Roof Co",
            "website": "https://roof.example",
            "seed_opportunity_key": "market:roofing:denver, co",
        }],
    )

    calls = []

    def fake_self_heal(**kwargs):
        calls.append(("self_heal", kwargs))
        return {
            "status": "HEALTHY",
            "execution_authority": "bounded_internal_repair",
        }

    def fake_local_recovery(repo_root):
        calls.append(("local_recovery", Path(repo_root)))
        heartbeat = (
            Path(repo_root)
            / "runtime/buyer_acquisition/local_recovery_latest.json"
        )
        heartbeat.parent.mkdir(parents=True, exist_ok=True)
        heartbeat.write_text(
            json.dumps({
                "state": "LOCAL_RECOVERY_EXECUTED",
                "contained": True,
            }),
            encoding="utf-8",
        )
        return {
            "state": "LOCAL_RECOVERY_EXECUTED",
            "database_write_performed": False,
            "outbound_sent": False,
            "execution_authority": "none",
        }

    result = reliability.run_cycle(
        root,
        now=NOW,
        self_heal=fake_self_heal,
        refresh_snapshot=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Supabase refresh must not run under containment")
        ),
        local_recovery=fake_local_recovery,
    )

    self_heal_call = next(row for row in calls if row[0] == "self_heal")
    assert self_heal_call[1]["observe_only"] is False
    assert self_heal_call[1]["repair_unit_allowlist"] == (
        reliability.CONTAINMENT_SAFE_REPAIR_UNITS
    )
    assert result["failed_action_count"] == 0
    assert result["authority"]["live_outbound"] is False
    assert result["authority"]["database_mutation"] is False
    assert result["execution_authority"] == "bounded_internal_repair"


def test_systemd_runs_production_module_not_recovery_script():
    root = Path(__file__).resolve().parents[1]
    text = (
        root / "deploy/systemd/empire-reliability-agent.service"
    ).read_text()

    assert "-m empire_os.reliability_agent" in text
    assert "run_buyer_acquisition_local_recovery.py" not in text
    assert "Restart=always" in text



def test_failed_action_enters_bounded_backoff_and_success_clears_it():
    state = {"action_failures": {}}

    reliability._record_action_result(
        state,
        "REFRESH_RECOVERY_SNAPSHOT",
        ok=False,
        now=NOW,
    )

    row = state["action_failures"]["REFRESH_RECOVERY_SNAPSHOT"]
    assert row["count"] == 1
    assert row["backoff_seconds"] == 60
    assert reliability._action_allowed(
        state,
        "REFRESH_RECOVERY_SNAPSHOT",
        now=NOW,
    ) is False

    reliability._record_action_result(
        state,
        "REFRESH_RECOVERY_SNAPSHOT",
        ok=True,
        now=NOW,
    )

    assert "REFRESH_RECOVERY_SNAPSHOT" not in state["action_failures"]
    assert reliability._action_allowed(
        state,
        "REFRESH_RECOVERY_SNAPSHOT",
        now=NOW,
    ) is True



def test_missing_recovery_seeds_is_degraded_even_when_escalation_succeeds(
    tmp_path,
):
    root = Path(tmp_path)
    guard = root / "runtime/control/supabase_egress_guard.json"
    guard.parent.mkdir(parents=True)
    guard.write_text(
        '{"state":"contained","contained":true}',
        encoding="utf-8",
    )

    result = reliability.run_cycle(
        root,
        now=NOW,
        self_heal=lambda **_kwargs: {
            "status": "HEALTHY",
            "execution_authority": "bounded_internal_repair",
        },
        refresh_snapshot=lambda *_args, **_kwargs: {},
        local_recovery=lambda *_args, **_kwargs: {},
    )

    assert result["status"] == "DEGRADED"
    assert result["founder_attention_required"] is True


def test_backoff_keeps_cycle_degraded_until_retry_allowed(tmp_path):
    root = Path(tmp_path)
    guard = root / "runtime/control/supabase_egress_guard.json"
    guard.parent.mkdir(parents=True)
    guard.write_text(
        '{"state":"healthy","contained":false}',
        encoding="utf-8",
    )

    state_path = root / "runtime/reliability_agent/state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps({
            "action_failures": {
                "REFRESH_RECOVERY_SNAPSHOT": {
                    "count": 1,
                    "next_allowed_at": "2026-09-27T08:01:00+00:00",
                    "backoff_seconds": 60,
                },
            },
        }),
        encoding="utf-8",
    )

    result = reliability.run_cycle(
        root,
        now=NOW,
        self_heal=lambda **_kwargs: {
            "status": "HEALTHY",
            "execution_authority": "bounded_internal_repair",
        },
        refresh_snapshot=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("backoff must defer refresh")
        ),
        local_recovery=lambda *_args, **_kwargs: {},
    )

    assert result["status"] == "DEGRADED"
    assert any(
        row["action"] == "REFRESH_RECOVERY_SNAPSHOT"
        and row["decision"] == "BACKOFF"
        for row in result["deferred_actions"]
    )
