"""Pure hypothetical EmpireDB timer ledger recovery, cancellation and replay."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest

from empire_os.prime_flagship_timer_recovery_shadow import (
    TimerRecoveryHold, replay_original_timer_shadow,
    planned_next_original_timer_action, founder_timer_recovery_status,
)

TENANT = "123e4567-e89b-42d3-a456-426614174000"
OTHER_TENANT = "123e4567-e89b-42d3-a456-426614174001"
TIMER = sha256(b"fixture-purpose-keyed-synthetic-timer").hexdigest()
START = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)


def row(i, kind="TIMER_CREATED", *, at=None, timer=TIMER, tenant=TENANT,
        duration=None, due=None, receipt=None):
    when = at if at is not None else START
    return {
        "tenant_id": tenant,
        "timer_digest": timer,
        "event_digest": sha256(f"fake-owner-opaque-row-{i}".encode()).hexdigest(),
        "seq": i,
        "kind": kind,
        "occurred_at": when.isoformat(),
        "due_at": due.isoformat() if due is not None else None,
        "duration_seconds": duration,
        "provider_receipt_digest": receipt,
        "synthetic_fixture_only": True,
    }


def created(duration=2):
    return row(1, duration=duration, due=START+timedelta(seconds=duration))


def r(rows, *, now=None):
    return replay_original_timer_shadow(
        tenant_id=TENANT, timer_digest=TIMER,
        original_empiredb_event_rows=rows,
        as_of=now or START+timedelta(seconds=4),
    )


def receipt(i):
    return sha256(f"synthetic-unverified-provider-{i}".encode()).hexdigest()


def test_future_scheduled_before_due_is_not_delivered():
    out = r([created()],now=START+timedelta(seconds=1))
    assert out["status"] == "SCHEDULED_WAITING"
    assert out["actual_provider_notification_sent"] is False
    assert out["actual_provider_delivery_verified"] is False
    assert out["durable_original_empiredb_rows_independently_verified"] is False
    assert planned_next_original_timer_action(out)["recommended_nonexecuting_step"] == "WAIT_FOR_ORIGINAL_DUE_TIMESTAMP"


def test_unclaimed_due_timer_requires_real_atomic_empiredb_claim_not_delivery():
    out = r([created()])
    assert out["status"] == "DUE_UNCLAIMED_REQUIRES_ATOMIC_DB_CLAIM"
    plan = planned_next_original_timer_action(out)
    assert plan["recommended_nonexecuting_step"] == "HOLD_FOR_OWNER_APPROVED_ATOMIC_DB_CLAIM"
    assert plan["notification_sent"] is False
    assert plan["automated_retry_allowed"] is False


def test_cancel_before_due_survives_synthetic_restart_without_dispatch():
    events = [
        created(),
        row(2,"TIMER_CANCELLED",at=START+timedelta(seconds=1)),
    ]
    raw = json.dumps(events,sort_keys=True)  # fixture export; not a DB or persisted system
    loaded = json.loads(raw)
    replayed = r(loaded,now=START+timedelta(seconds=300))
    assert replayed["status"] == "CANCELLED_BEFORE_DISPATCH"
    assert planned_next_original_timer_action(replayed)["recommended_nonexecuting_step"] == "STOP_NO_NOTIFICATION"
    assert replayed["actual_provider_notification_sent"] is False


def test_claimed_without_provider_ack_after_restart_never_double_fires():
    events = [created(), row(2,"DISPATCH_CLAIMED",at=START+timedelta(seconds=2))]
    recovered = r(json.loads(json.dumps(events)),now=START+timedelta(hours=1))
    assert recovered["status"] == "CLAIMED_RECONCILIATION_REQUIRED"
    assert recovered["claim_seq"] == 2
    assert planned_next_original_timer_action(recovered)["recommended_nonexecuting_step"] == "STOP_AND_RECONCILE_PROVIDER_BEFORE_RETRY"
    assert recovered["actual_provider_notification_sent"] is False


def test_provider_accepted_is_not_delivered():
    events = [created(),row(2,"DISPATCH_CLAIMED",at=START+timedelta(seconds=2)),
              row(3,"PROVIDER_ACCEPTED_REPORTED",at=START+timedelta(seconds=3),
                  receipt=receipt(3))]
    out = r(events)
    assert out["status"] == "PROVIDER_ACCEPTED_NOT_DELIVERED"
    assert planned_next_original_timer_action(out)["recommended_nonexecuting_step"] == "STOP_PENDING_INDEPENDENT_DELIVERY_RECEIPT"
    assert out["actual_provider_delivery_verified"] is False


def test_delivery_report_still_not_cryptographic_or_user_proof():
    events = [
        created(),
        row(2,"DISPATCH_CLAIMED",at=START+timedelta(seconds=2)),
        row(3,"PROVIDER_ACCEPTED_REPORTED",at=START+timedelta(seconds=3),receipt=receipt(3)),
        row(4,"PROVIDER_DELIVERED_REPORTED",at=START+timedelta(seconds=4),receipt=receipt(4)),
    ]
    out = r(events)
    assert out["status"] == "DELIVERY_REPORTED_NOT_INDEPENDENTLY_VERIFIED"
    assert out["provider_receipt_reported_not_verified"] is True
    assert out["actual_provider_delivery_verified"] is False
    founder = founder_timer_recovery_status(out)
    assert founder["status"] == out["status"]
    assert founder["real_notification_delivery_verified"] is False
    assert TENANT not in str(founder)
    assert TIMER not in str(founder)
    assert receipt(4) not in str(founder)


def test_failed_provider_receipt_stops_auto_retry():
    events = [
        created(),
        row(2,"DISPATCH_CLAIMED",at=START+timedelta(seconds=2)),
        row(3,"PROVIDER_FAILED_REPORTED",at=START+timedelta(seconds=3),receipt=receipt(3)),
    ]
    out = r(events)
    assert out["status"] == "DELIVERY_FAILED_REPORTED_NO_AUTO_RETRY"
    assert planned_next_original_timer_action(out)["recommended_nonexecuting_step"] == "STOP_MANUAL_DELIVERY_REVIEW"


@pytest.mark.parametrize("bad_events,match",[
    ([row(1,"DISPATCH_CLAIMED")], "first_event_must_create"),
    ([created(),created()], "atomic_ordered_event_replay_required"),
    ([created(),row(2,"TIMER_CREATED")],"duplicate_timer_creation"),
    ([created(),row(2,"DISPATCH_CLAIMED",at=START+timedelta(seconds=1))],"dispatch_requires_due"),
    ([created(),row(2,"TIMER_CANCELLED",at=START+timedelta(seconds=2))],"cancellation_after_due"),
    ([created(),row(2,"TIMER_CANCELLED",at=START+timedelta(seconds=1)),
      row(3,"DISPATCH_CLAIMED",at=START+timedelta(seconds=2))], "dispatch_requires_due"),
    ([created(),row(2,"DISPATCH_CLAIMED",at=START+timedelta(seconds=2)),
      row(3,"TIMER_CANCELLED",at=START+timedelta(seconds=3))], "cancellation_after_due"),
    ([created(),row(2,"PROVIDER_DELIVERED_REPORTED",at=START+timedelta(seconds=3),receipt=receipt(2))],"original_provider_report_after_claim"),
    ([created(),row(2,"DISPATCH_CLAIMED",at=START+timedelta(seconds=2)),
      row(3,"PROVIDER_DELIVERED_REPORTED",at=START+timedelta(seconds=3),receipt=receipt(3))], "delivery_requires_prior_provider_acceptance"),
])
def test_illegal_transition_refuses_to_launder_commercial_proof(bad_events,match):
    with pytest.raises(TimerRecoveryHold,match=match):
        r(bad_events)


def test_cross_tenant_or_timer_binding_refused():
    for bad in [row(1,duration=2,due=START+timedelta(seconds=2),tenant=OTHER_TENANT),
                row(1,duration=2,due=START+timedelta(seconds=2),timer=receipt(11))]:
        with pytest.raises(TimerRecoveryHold,match="cross_tenant"):
            r([bad])


@pytest.mark.parametrize("tamper,match",[
    ({"synthetic_fixture_only": False},"real_owner_event_not_authorized"),
    ({"event_digest":"not_a_digest"},"bounded_event_nonce"),
    ({"seq":True},"bounded_event_nonce"),
    ({"seq":0},"bounded_event_nonce"),
    ({"extra_contact":"private@example.test"},"exact_original_minimal"),
    ({"duration_seconds":3601},"bounded_original_timer_duration"),
    ({"duration_seconds":-1},"bounded_original_timer_duration"),
    ({"due_at":None},"created_event_due"),
])
def test_event_schema_is_strict_and_privacy_minimal(tamper,match):
    event=created()
    event.update(tamper)
    with pytest.raises(TimerRecoveryHold,match=match):
        r([event])


def test_due_timestamp_mismatch_refused():
    with pytest.raises(TimerRecoveryHold,match="due_time_must_match"):
        r([row(1,duration=2,due=START+timedelta(seconds=300))])


def test_clock_reordered_event_refused():
    with pytest.raises(TimerRecoveryHold,match="out_of_order_event"):
        r([created(),row(2,"TIMER_CANCELLED",at=START-timedelta(seconds=1))])


def test_replay_at_future_time_refused_without_now_authority():
    with pytest.raises(TimerRecoveryHold,match="future_evidence"):
        r([created()],now=START-timedelta(hours=1))


def test_unbounded_stream_refused():
    with pytest.raises(TimerRecoveryHold,match="bounded_nonempty"):
        r([])
    with pytest.raises(TimerRecoveryHold,match="bounded_nonempty"):
        r([created()]*33)


@pytest.mark.parametrize("tamper",[
    {"actual_provider_notification_sent": True},
    {"actual_provider_delivery_verified": True},
    {"execution_authority": "live"},
    {"durable_original_empiredb_rows_independently_verified": True},
    {"claim_atomicity_proven_by_a_real_database": True},
    {"source_owner_consent_verified": True},
    {"original_empiredb_writes": True},
])
def test_founder_rejects_fabricated_delivery_or_execution_authority(tamper):
    value=r([created()])
    value.update(tamper)
    with pytest.raises(TimerRecoveryHold,match="untrusted_original_timer_replay_projection"):
        founder_timer_recovery_status(value)


def test_founder_unknown_is_not_proven_durable_storage():
    packet=founder_timer_recovery_status(None)
    assert packet["status"]=="NOT_CONNECTED"
    assert packet["real_notification_delivery_verified"] is False
    assert packet["execution_authority"]=="none"


def test_held_original_empiredb_migration_is_not_a_live_notification_system():
    from pathlib import Path
    sql = Path("migrations/empiredb/057_flagship_voice_timer_ledger_held.sql").read_text()
    executable_lines = [
        line.strip().lower() for line in sql.splitlines()
        if line.strip() and not line.lstrip().startswith("--")
    ]
    executable = "\n".join(executable_lines)
    assert "set local role empiredb_migrator" in executable
    assert "timer057_wrong_database" in executable
    assert "empire_timer_fixture" in executable
    assert "force row level security" in executable
    assert executable.count("force row level security") == 2
    assert "revoke all on table public.empire_prime_voice_timer_requests from public" in executable
    assert "revoke all on table public.empire_prime_voice_timer_events from public" in executable
    assert "before update or delete" in executable
    assert "on delete restrict" in executable
    assert "unique (tenant_id,event_digest)" in executable
    assert "on conflict" not in executable
    assert not any(line.startswith("grant ") for line in executable_lines)
    assert not any(line.startswith("create role") for line in executable_lines)
    assert not any(line.startswith("create policy") for line in executable_lines)
    assert not any(line.startswith("create extension") for line in executable_lines)
    assert not any(line.startswith("create login") for line in executable_lines)
    assert not any(line.startswith("insert into ") for line in executable_lines)
    assert not any(line.startswith("update ") for line in executable_lines)
    assert not any(line.startswith("delete from") for line in executable_lines)
    assert "no runtime" in sql.lower()
    assert "supabase" not in executable
    assert "empire_prime_voice_timer_requests" in executable
    assert "empire_prime_voice_timer_events" in executable


def test_original_founder_cockpit_reports_timer_recovery_unconnected_not_live():
    from empire_os.prime_digital_twin_cockpit import build_prime_digital_twin_cockpit
    from fastapi.testclient import TestClient
    from empire_os.founder_dashboard_service import build_founder_dashboard_service
    packet = build_prime_digital_twin_cockpit()
    assert packet["original_timer_recovery"]["status"] == "NOT_CONNECTED"
    assert packet["original_timer_recovery"]["real_notification_delivery_verified"] is False
    assert packet["original_empiredb_writes"] is False
    with TestClient(build_founder_dashboard_service()) as api:
        response=api.get("/v1/founder-dashboard/prime-digital-twin")
        assert response.status_code==200
        assert response.json()["original_timer_recovery"]["status"]=="NOT_CONNECTED"
        assert api.post("/v1/founder-dashboard/prime-digital-twin").status_code==405


def test_actual_separate_process_synthetic_restart_replay_has_four_consistent_holds():
    import subprocess
    import sys
    fixture_run = subprocess.run(
        [sys.executable, "-B", "-m",
         "scripts.rehearse_prime_original_timer_recovery_20261024"],
        capture_output=True, text=True, timeout=15,
    )
    assert fixture_run.returncode == 0, fixture_run.stderr
    report=json.loads(fixture_run.stdout)
    assert report["status"]=="FOUR_FICTIONAL_RESTART_CONTRACTS_PASS"
    assert report["fresh_processes_launched"]==4
    assert all(case["new_process_replay_passed"] is True for case in report["cases"])
    assert report["database_snapshot_restored"] is False
    assert report["persistent_empiredb_ledger_live"] is False
    assert report["original_empiredb_writes"] is False
    assert report["external_notification_delivered"] is False
    assert report["execution_authority"] == "none"
