import json
import subprocess

import empire_os.supabase_egress_guard as guard


def _result(args, code=0, stdout=""):
    return subprocess.CompletedProcess(args, code, stdout=stdout, stderr="")



def _test_governor(tmp_path):
    from empire_os.legacy_data_egress import (
        LegacyDataEgressGovernor,
        LegacyEgressConfig,
    )

    return LegacyDataEgressGovernor(
        LegacyEgressConfig(
            state_path=tmp_path / "state.json",
            lock_path=tmp_path / "legacy_egress.lock",
            hourly_budget=100,
            component_hourly_budget=100,
            daily_budget=1000,
            probe_seconds=60,
        ),
        environ={"EMPIRE_COMPONENT": "test"},
        now=lambda: 1000.0,
    )


def test_shared_egress_lock_does_not_chmod_existing_lock(
    monkeypatch,
    tmp_path,
):
    """Regression: existing shared lock must not require owner chmod."""
    from empire_os import legacy_data_egress as egress

    governor = _test_governor(tmp_path)
    governor.lock_path.touch(mode=0o666)

    chmod_calls = []

    def forbidden_chmod(*args, **kwargs):
        chmod_calls.append((args, kwargs))
        raise PermissionError("simulated non-owner chmod")

    monkeypatch.setattr(egress.os, "chmod", forbidden_chmod)

    result = governor._with_lock(lambda: "LOCK_OK")

    assert result == "LOCK_OK"
    assert chmod_calls == []


def test_shared_egress_lock_new_file_is_world_writable(tmp_path):
    governor = _test_governor(tmp_path)

    assert governor._with_lock(lambda: "LOCK_OK") == "LOCK_OK"
    assert governor.lock_path.exists()
    assert (governor.lock_path.stat().st_mode & 0o777) == 0o666


def test_guard_contains_only_allowlisted_timers_on_egress_block(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        guard,
        "STATUS_PATH",
        tmp_path / "supabase_egress_guard.json",
    )
    calls = []

    def fake_run(args, **_kwargs):
        calls.append(tuple(args))
        if args[1] == "is-enabled":
            return _result(args, 0, "enabled\n")
        return _result(args)

    def blocked(*_args, **_kwargs):
        raise RuntimeError(
            "GET /rest/v1/prospects -> HTTP 402: exceed_egress_quota"
        )

    result = guard.run_guard(
        request=blocked,
        run=fake_run,
        stagger_seconds=0,
        sleep=lambda _value: None,
    )

    assert result["state"] == "contained"
    assert result["contained"] is True
    assert set(result["managed_timers"]) == set(guard.MANAGED_TIMERS)
    stopped = {
        call[2]
        for call in calls
        if len(call) >= 3 and call[1] == "stop"
    }
    assert set(guard.MANAGED_TIMERS).issubset(stopped)
    assert "empire-buyer-acquisition-team.timer" in stopped
    assert "empire-revenue-runtime-supervisor.timer" not in stopped
    assert "empire-revenue-pulse.timer" in stopped
    assert "empire-ops-control.timer" in stopped
    assert "empire-legacy-permit-recovery.timer" in stopped
    assert "empire-enterprise-contact-repair.timer" in stopped
    assert "empire-resend-inbound.service" not in stopped
    assert result["inbound_mail_touched"] is False
    assert result["revenue_mutation"] is False


def test_guard_restores_only_recorded_still_enabled_timers(
    monkeypatch,
    tmp_path,
):
    status = tmp_path / "supabase_egress_guard.json"
    monkeypatch.setattr(guard, "STATUS_PATH", status)
    status.write_text(
        json.dumps({
            "managed_timers": [
                "empire-gtm-pipeline.timer",
                "empire-outbound-governor.timer",
            ],
        }),
        encoding="utf-8",
    )
    calls = []

    def fake_run(args, **_kwargs):
        calls.append(tuple(args))
        if args[1] == "is-enabled":
            if args[2] == "empire-outbound-governor.timer":
                return _result(args, 1, "disabled\n")
            return _result(args, 0, "enabled\n")
        return _result(args)

    result = guard.run_guard(
        request=lambda *_args, **_kwargs: [],
        run=fake_run,
        stagger_seconds=0,
        sleep=lambda _value: None,
    )

    assert result["state"] == "healthy"
    assert result["restored_timers"] == ["empire-gtm-pipeline.timer"]
    starts = [
        call[2]
        for call in calls
        if len(call) >= 3 and call[1] == "start"
    ]
    assert starts == ["empire-gtm-pipeline.timer"]


def test_guard_does_not_contain_on_unrelated_probe_error(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        guard,
        "STATUS_PATH",
        tmp_path / "supabase_egress_guard.json",
    )
    calls = []

    def fake_run(args, **_kwargs):
        calls.append(tuple(args))
        return _result(args)

    def failed(*_args, **_kwargs):
        raise RuntimeError("temporary DNS failure")

    result = guard.run_guard(
        request=failed,
        run=fake_run,
        stagger_seconds=0,
        sleep=lambda _value: None,
    )

    assert result["state"] == "probe_error"
    assert result["contained"] is False
    assert calls == []



def test_guard_requests_the_explicit_recovery_probe_slot(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        guard,
        "STATUS_PATH",
        tmp_path / "supabase_egress_guard.json",
    )
    seen = {}

    def healthy(method, path, **kwargs):
        seen["method"] = method
        seen["path"] = path
        seen.update(kwargs)
        return []

    result = guard.run_guard(
        request=healthy,
        run=lambda args, **_kwargs: _result(args, 1, "disabled\n"),
        stagger_seconds=0,
        sleep=lambda _value: None,
    )

    assert result["state"] == "healthy"
    assert seen["method"] == "GET"
    assert seen["path"] == "/rest/v1/prospects?select=id&limit=1"
    assert seen["allow_egress_probe"] is True

def test_recovery_supervisor_is_never_egress_contained():
    """Recovery control plane must survive a Supabase data-plane outage."""
    from empire_os.supabase_egress_guard import MANAGED_TIMERS

    assert (
        "empire-revenue-runtime-supervisor.timer"
        not in MANAGED_TIMERS
    )
