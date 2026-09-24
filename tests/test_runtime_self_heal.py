from datetime import datetime, timezone
from pathlib import Path

import empire_os.runtime_self_heal as runtime_self_heal


NOW = datetime(2026, 9, 24, 10, 30, tzinfo=timezone.utc)


def _clear_runtime(monkeypatch):
    monkeypatch.setattr(runtime_self_heal, "AUTO_REPAIR_SERVICES", ())
    monkeypatch.setattr(runtime_self_heal, "AUTO_REPAIR_TIMERS", ())
    monkeypatch.setattr(runtime_self_heal, "SNAPSHOTS", ())
    monkeypatch.setattr(runtime_self_heal, "HTTP_CHECKS", ())


def test_consequential_units_are_never_auto_repairable():
    for unit in (
        "empire-outbound-governor.service",
        "empire-outbound-followup.service",
        "empire-voice-outbound.service",
        "empire-closer-reply-worker.service",
        "empire-payment-verifier.service",
        "empire-settlement.service",
    ):
        assert runtime_self_heal.unit_is_auto_repairable(unit) is False


def test_inactive_safe_service_is_repaired_and_verified(monkeypatch, tmp_path):
    _clear_runtime(monkeypatch)
    spec = runtime_self_heal.ServiceSpec(
        "gateway",
        "empire-public-gateway.service",
    )
    monkeypatch.setattr(runtime_self_heal, "AUTO_REPAIR_SERVICES", (spec,))

    calls = []
    states = iter(((False, "inactive"), (True, "active")))

    def status(_unit):
        return next(states)

    def repair(action, unit):
        calls.append((action, unit))
        return {"ok": True, "returncode": 0}

    payload = runtime_self_heal.run_runtime_self_heal(
        now=NOW,
        service_status=status,
        repair=repair,
        latest_path=tmp_path / "latest.json",
        state_path=tmp_path / "state.json",
    )

    assert payload["status"] == "HEALTHY"
    assert payload["repair_count"] == 1
    assert payload["unresolved_count"] == 0
    assert calls == [
        ("service_restart", "empire-public-gateway.service")
    ]
    row = payload["checks"][0]
    assert row["healthy"] is False
    assert row["after_repair"]["healthy"] is True


def test_missing_snapshot_runs_bounded_writer_repair(monkeypatch, tmp_path):
    _clear_runtime(monkeypatch)
    snapshot = tmp_path / "catalog.json"
    spec = runtime_self_heal.SnapshotSpec(
        "catalog",
        str(snapshot),
        900,
        "empire-commercial-product-catalog.service",
    )
    monkeypatch.setattr(runtime_self_heal, "SNAPSHOTS", (spec,))
    monkeypatch.setattr(runtime_self_heal.time, "sleep", lambda _seconds: None)

    def repair(action, unit):
        assert action == "service_start"
        assert unit == "empire-commercial-product-catalog.service"
        snapshot.write_text('{"ok": true}\n', encoding="utf-8")
        return {"ok": True, "returncode": 0}

    payload = runtime_self_heal.run_runtime_self_heal(
        now=NOW,
        repair=repair,
        latest_path=tmp_path / "latest.json",
        state_path=tmp_path / "state.json",
    )

    assert payload["status"] == "HEALTHY"
    assert payload["repair_count"] == 1
    row = payload["checks"][0]
    assert row["reason"] == "missing"
    assert row["after_repair"]["healthy"] is True


def test_repair_cooldown_prevents_restart_loop(monkeypatch, tmp_path):
    _clear_runtime(monkeypatch)
    spec = runtime_self_heal.ServiceSpec(
        "gateway",
        "empire-public-gateway.service",
    )
    monkeypatch.setattr(runtime_self_heal, "AUTO_REPAIR_SERVICES", (spec,))

    state = tmp_path / "state.json"
    state.write_text(
        '{"last_repairs":{"service:empire-public-gateway.service":"2026-09-24T10:29:00+00:00"}}',
        encoding="utf-8",
    )

    payload = runtime_self_heal.run_runtime_self_heal(
        now=NOW,
        service_status=lambda _unit: (False, "inactive"),
        repair=lambda _action, _unit: (_ for _ in ()).throw(
            AssertionError("repair must not run during cooldown")
        ),
        latest_path=tmp_path / "latest.json",
        state_path=state,
    )

    assert payload["status"] == "DEGRADED"
    assert payload["repair_count"] == 0
    assert payload["repairs"][0]["decision"] == "COOLDOWN"


def test_non_observe_mode_forces_observe_only(monkeypatch, tmp_path):
    _clear_runtime(monkeypatch)
    spec = runtime_self_heal.ServiceSpec(
        "gateway",
        "empire-public-gateway.service",
    )
    monkeypatch.setattr(runtime_self_heal, "AUTO_REPAIR_SERVICES", (spec,))
    monkeypatch.setenv("EMPIRE_AUTONOMOUS_MODE", "EXECUTE")

    payload = runtime_self_heal.run_runtime_self_heal(
        now=NOW,
        service_status=lambda _unit: (False, "inactive"),
        repair=lambda _action, _unit: (_ for _ in ()).throw(
            AssertionError("repair must not execute")
        ),
        latest_path=tmp_path / "latest.json",
        state_path=tmp_path / "state.json",
    )

    assert payload["observe_only"] is True
    assert payload["repairs"][0]["decision"] == "WOULD_AUTO_REPAIR"
    assert payload["repairs"][0]["executed"] is False
